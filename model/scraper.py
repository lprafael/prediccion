"""
Extractor de datos en vivo de partidos para aposta.la (Kambi Sportsbook API + Fallback Playwright).
Extrae equipos, marcadores por cuarto, tiempo restante y cuotas Over/Under en tiempo real.
"""

import re
import json
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import requests

_kambi_session = requests.Session()
_kambi_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://aposta.la/"
})


@dataclass
class LiveMatchData:
    """Datos del partido extraídos de la página live."""
    team_home: str = ""
    team_away: str = ""
    score_home: int = 0
    score_away: int = 0
    quarter: int = 1
    clock_min: int = 0
    clock_sec: int = 0
    quarter_scores: List[Tuple[int, int]] = field(default_factory=lambda: [(0, 0), (0, 0), (0, 0), (0, 0)])
    odds_over: Optional[float] = None
    odds_under: Optional[float] = None
    odds_line: Optional[float] = None
    status: str = "unknown"   # "live", "finished", "not_started", "error"
    error_msg: str = ""
    raw_url: str = ""
    plays: List[dict] = field(default_factory=list)
    current_run_team: str = ""
    current_run_pts: int = 0
    league_name: str = ""
    quarter_duration: int = 10   # 10 min (FIBA/Euroliga/NBL/Local) o 12 min (NBA)
    tournament_key: str = "FIBA" # "NBA", "NBL", "FIBA", "NCAA_FEMENIL"


def extract_event_id(url: str) -> Optional[str]:
    """Extrae el ID numérico del evento de una URL de aposta.la o similar."""
    url = url.strip()
    if url.isdigit():
        return url
    m = re.search(r"event/(?:live/)?(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"(\d{8,12})", url)
    return m.group(1) if m else None


def fetch_kambi_direct(event_id: str) -> Optional[LiveMatchData]:
    """
    Consulta directamente las APIs REST de Kambi CDN utilizadas por aposta.la.
    Es ultra rápido (~200ms) y no consume recursos de navegador.
    """
    result = LiveMatchData()

    status_bo = 0
    status_ld = 0

    # 1. Obtener nombres de equipos y ofertas de apuestas (BetOffers)
    url_bo = f"https://us.offering-api.kambicdn.com/offering/v2018/betplayintpy/betoffer/event/{event_id}.json?lang=es_PY&market=PY&client_id=200"
    try:
        resp_bo = _kambi_session.get(url_bo, timeout=8)
        status_bo = resp_bo.status_code
        if resp_bo.status_code == 200:
            data_bo = resp_bo.json()
        else:
            data_bo = {}

        events = data_bo.get("events", [])
        ev_obj = events[0] if events else data_bo.get("event", {})
        if ev_obj:
            result.team_home = ev_obj.get("homeName", "").strip()
            result.team_away = ev_obj.get("awayName", "").strip()
            group_val = ev_obj.get("group", "")
            path_val = [p.get("name", "") for p in ev_obj.get("path", []) if isinstance(p, dict)]
            league_tokens = [group_val] + path_val
            result.league_name = " / ".join(filter(None, league_tokens))
            # Detección precisa de torneos y duración de cuartos:
            # - NBA (12 min/cuarto): NBA y NBA G-League.
            # - NBL (10 min/cuarto): NBL de Australia & Nueva Zelanda (alta velocidad, ~84 poss).
            # - FIBA (10 min/cuarto): Euroliga, ligas locales, torneos de selecciones, WNBA.
            is_nba = False
            is_nbl = False
            for t in league_tokens:
                t_str = str(t).strip().lower()
                if "nbl" in t_str or "australia" in t_str:
                    is_nbl = True
                elif "wnba" in t_str:
                    pass
                elif re.search(r"\b(nba|g-league|g league)\b", t_str):
                    is_nba = True

            if is_nba and not is_nbl:
                result.quarter_duration = 12
                result.tournament_key = "NBA"
            elif is_nbl:
                result.quarter_duration = 10
                result.tournament_key = "NBL"
            else:
                result.quarter_duration = 10
                result.tournament_key = "FIBA"

        # Buscar la línea principal (MAIN_LINE) de Total de Puntos del partido completo
        candidates = []
        for bo in data_bo.get("betOffers", []):
            crit_label = bo.get("criterion", {}).get("label", "").strip()
            crit_lower = crit_label.lower()
            tags = bo.get("tags", [])
            bo_type = bo.get("betOfferType", {}).get("name", "")

            # Excluir apuestas de periodos parciales, hándicaps, par/impar, o props individuales
            excluded_keywords = [
                "cuarto", "quarter", "1.ª parte", "1ª parte", "1ra parte", 
                "2.ª parte", "2ª parte", "2da parte", "mitad", "half", 
                "tiempo", "periodo", "period",
                "1er", "2do", "3er", "4to", "1st", "2nd", "3rd", "4th", 
                "1º", "2º", "3º", "4º", "1.º", "2.º", "1.er", "2.o", "1.o",
                "par/impar", "impar", "par ", "local", "visitante", "equipo", "team", "home", "away",
                "jugador", "player", "hándicap", "handicap", "apuesta sin empate",
                "carrera", "race", "margen", "triples", "asistencias", "rebotes", "robos", "tapones",
                "primero en", "primera mitad", "segunda mitad"
            ]
            if any(kw in crit_lower for kw in excluded_keywords):
                continue

            # Verificar que sea mercado de total de puntos
            is_total_market = (
                ("total" in crit_lower and ("punto" in crit_lower or "point" in crit_lower)) or
                ("total" in crit_lower and bo_type in ["Más/Menos de", "Over/Under", "Total"]) or
                (bo_type in ["Más/Menos de", "Over/Under"] and "puntos" in crit_lower)
            )
            if not is_total_market:
                continue

            bo_over = None
            bo_under = None
            bo_line = None
            for oc in bo.get("outcomes", []):
                lbl = oc.get("label", "").lower()
                line = oc.get("line", 0) / 1000.0 if "line" in oc else None
                dec_odds = oc.get("odds", 0) / 1000.0
                if "más" in lbl or "mas" in lbl or "over" in lbl:
                    bo_over = dec_odds
                    if line is not None:
                        bo_line = line
                elif "menos" in lbl or "under" in lbl:
                    bo_under = dec_odds
                    if line is not None:
                        bo_line = line

            if bo_line is not None and (bo_over is not None or bo_under is not None):
                # Un total de partido completo en baloncesto profesional nunca es menor a 105 puntos.
                # Líneas menores a 105 puntos corresponden a mitades (ej. 71.5) o cuartos (ej. 35.5).
                if bo_line < 105.0:
                    continue

                is_main = "MAIN_LINE" in tags or "MAIN" in tags
                candidates.append({
                    "line": bo_line,
                    "over": bo_over,
                    "under": bo_under,
                    "is_main": is_main,
                    "label": crit_label
                })

        if candidates:
            # Prioridad 1: Candidatos con MAIN_LINE del partido completo
            main_candidates = [c for c in candidates if c["is_main"]]
            pool = main_candidates if main_candidates else candidates
            # Prioridad 2: Línea con cuotas más equilibradas (~1.85 / ~1.85)
            main_c = min(pool, key=lambda c: abs((c["over"] or 2.0) - (c["under"] or 2.0)))

            result.odds_line = main_c["line"]
            result.odds_over = main_c["over"]
            result.odds_under = main_c["under"]

    except Exception as e:
        # Podría fallar si el evento ya cerró mercados o endpoint temporal
        pass

    # 2. Obtener marcador en vivo y reloj (LiveData)
    url_ld = f"https://us.offering-api.kambicdn.com/offering/v2018/betplayintpy/event/{event_id}/livedata.json?lang=es_PY&market=PY&client_id=200"
    try:
        resp_ld = _kambi_session.get(url_ld, timeout=8)
        status_ld = resp_ld.status_code
        if status_ld == 200:
            data_ld = resp_ld.json()
        else:
            data_ld = {}

        # Si ambos endpoints de Kambi retornan 404, el evento ya no está en la oferta en vivo (finalizó)
        if status_bo == 404 and status_ld == 404:
            result.status = "finished"
            result.error_msg = f"El evento (ID: {event_id}) no está disponible en vivo en Aposta.la (posiblemente ha finalizado)."
            return result

        ld = data_ld.get("liveData", {})
        score = ld.get("score", {})
        result.score_home = int(score.get("home", 0))
        result.score_away = int(score.get("away", 0))
        score_info = score.get("info", "")

        # Reloj
        clock = ld.get("matchClock", {})
        result.clock_min = int(clock.get("minutesLeftInPeriod", 0))
        result.clock_sec = int(clock.get("secondsLeftInMinute", 0))
        # Si el reloj del periodo marca físicamente más de 10 minutos restantes (ej. 11:30 o 12:00),
        # es evidencia física concluyente de que el cuarto dura 12 minutos (ej. NBA).
        if result.clock_min > 10:
            result.quarter_duration = 12
        period_id = str(clock.get("periodId", "")).upper()
        period_name = str(clock.get("period", "")).lower()

        # Cuarto actual
        if "1" in period_id or "1" in period_name:
            result.quarter = 1
        elif "2" in period_id or "2" in period_name:
            result.quarter = 2
        elif "3" in period_id or "3" in period_name:
            result.quarter = 3
        elif "4" in period_id or "4" in period_name:
            result.quarter = 4
        elif "OT" in period_id or "pr" in period_name:
            result.quarter = 5

        # Puntos por cuarto desglosados (ej: 'Q1: 8-18 | Q2: 8-17 | Q3: 9-21 | Q4: 12-3')
        q_scores = [(0, 0), (0, 0), (0, 0), (0, 0)]
        parts = re.findall(r"Q(\d):\s*(\d+)-(\d+)", score_info)
        for q_idx_str, pts_h, pts_a in parts:
            qi = int(q_idx_str) - 1
            if 0 <= qi < 4:
                q_scores[qi] = (int(pts_h), int(pts_a))

        # Reconciliación: Kambi a menudo demora en actualizar `score.info` del cuarto en juego,
        # mientras que `score.home` y `score.away` se actualizan al instante.
        # Ajustamos el cuarto en juego para que la suma siempre coincida con el total real.
        if 1 <= result.quarter <= 4:
            curr_q_idx = result.quarter - 1
            pts_prev_h = sum(q_scores[i][0] for i in range(curr_q_idx))
            pts_prev_a = sum(q_scores[i][1] for i in range(curr_q_idx))
            reconciled_h = max(0, result.score_home - pts_prev_h)
            reconciled_a = max(0, result.score_away - pts_prev_a)
            q_scores[curr_q_idx] = (reconciled_h, reconciled_a)

        result.quarter_scores = q_scores

        # 3. Historial de jugadas (Play-by-Play) y rachas anotadoras
        feed_updates = ld.get("liveFeedUpdates", [])
        parsed_plays = []
        prev_h = 0
        prev_a = 0
        for f in feed_updates:
            f_score = f.get("score", {})
            h = int(f_score.get("home", 0))
            a = int(f_score.get("away", 0))
            who = f_score.get("who", "")
            info = f_score.get("info", "")

            diff_h = h - prev_h
            diff_a = a - prev_a

            pts = 0
            team_scored = ""
            if who == "HOME" or diff_h > 0:
                pts = diff_h if diff_h > 0 else 2
                team_scored = result.team_home or "Local"
            elif who == "AWAY" or diff_a > 0:
                pts = diff_a if diff_a > 0 else 2
                team_scored = result.team_away or "Visitante"

            if pts > 0 or h != prev_h or a != prev_a:
                parsed_plays.append({
                    "score_home": h,
                    "score_away": a,
                    "team": team_scored,
                    "who": who,
                    "pts": pts,
                    "info": info
                })
                prev_h = h
                prev_a = a

        # Calcular racha anotadora activa sin respuesta
        run_team = ""
        run_pts = 0
        for p in reversed(parsed_plays):
            if not run_team:
                run_team = p["team"]
                run_pts = p["pts"]
            elif p["team"] == run_team:
                run_pts += p["pts"]
            else:
                break

        result.plays = parsed_plays
        result.current_run_team = run_team
        result.current_run_pts = run_pts

        result.status = "live"
        return result
    except Exception as e:
        return None


def scrape_aposta_la(url: str, timeout_ms: int = 15000) -> LiveMatchData:
    """
    Punto de entrada principal para extraer información del partido.
    Intenta primero la API directa Kambi. Si no está disponible, recurre a Playwright.
    """
    result = LiveMatchData(raw_url=url)
    event_id = extract_event_id(url)

    if not event_id:
        result.status = "error"
        result.error_msg = "No se pudo identificar el ID del evento en el link. Formato esperado: https://aposta.la/bets#event/live/XXXXXXXXXX"
        return result

    # 1. Intentar API directa Kambi (Rápido y liviano)
    direct_data = fetch_kambi_direct(event_id)
    if direct_data:
        if direct_data.status == "finished":
            direct_data.raw_url = url
            return direct_data
        if direct_data.team_home or direct_data.score_home > 0 or direct_data.score_away > 0:
            direct_data.raw_url = url
            return direct_data

    # 2. Fallback con Playwright si la API directa no respondió
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()

        # Intentar rescatar datos básicos del HTML
        m = re.search(r"(\d{1,3})\s*[-–:]\s*(\d{1,3})", html)
        if m:
            result.score_home = int(m.group(1))
            result.score_away = int(m.group(2))
            result.status = "live"
    except Exception:
        result.status = "error"
        result.error_msg = f"No se encontraron datos en vivo para el evento (ID: {event_id}). Asegurate de que el partido este actualmente en juego en Aposta.la."

    return result
