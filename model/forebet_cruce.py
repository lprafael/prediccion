"""
Motor de Cruce y Detección de Apuestas con Valor (+EV):
Forebet (Predicciones Matemáticas y Probabilidades) vs Aposta.la (Cuotas Kambi Sportsbook).
"""

import time
import os
import re
import difflib
import unicodedata
from typing import List, Dict, Any, Optional
import requests

# Cache en memoria para evitar saturar Forebet en cada petición web
_CACHE: Dict[str, Any] = {
    "timestamp": 0.0,
    "forebet_matches": [],
    "aposta_matches": [],
    "recommendations": [],
    "summary": {}
}
CACHE_TTL_SECONDS = 900  # 15 minutos de validez


def normalize_team_name(text: str) -> str:
    """Normaliza nombres de equipos removiendo tildes, signos y palabras comunes de club."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    # Quitar palabras genéricas que causan discordancia
    text = re.sub(r'\b(fc|cf|sc|ac|cd|fk|sk|ca|csd|de|la|el|club|balompie|sporting|united|city|real|atletico|deportivo)\b', '', text)
    text = re.sub(r'[^a-z0-9]', '', text)
    return text.strip()


import difflib

TEAM_ALIASES = {
    "napoles": "napoli", "bayern munich": "bayern munchen", "bayern múnich": "bayern munchen",
    "marsella": "marseille", "olympique marsella": "marseille", "niza": "nice",
    "estrasburgo": "strasbourg", "monaco": "monaco", "as monaco": "monaco", "as mónaco": "monaco",
    "paris fc": "paris fc", "psg": "paris saint germain", "paris saint-germain": "paris saint germain",
    "hamburgo": "hamburger sv", "colonia": "koln", "1. fc koln": "koln", "1. fc köln": "koln",
    "bolonia": "bologna", "genova": "genoa", "génova": "genoa", "turin": "torino",
    "ac milan": "milan", "ac milán": "milan", "inter": "inter milan", "brujas": "club brugge",
    "sporting lisboa": "sporting cp", "sporting lisbon": "sporting cp", "oporto": "porto",
    "fc porto": "porto", "atletico madrid": "atletico madrid", "atlético madrid": "atletico madrid",
    "real madrid": "real madrid", "real sociedad": "real sociedad", "real betis": "betis",
    "athletic bilbao": "athletic club", "tottenham": "tottenham hotspur",
    "brighton": "brighton and hove albion", "wolves": "wolverhampton wanderers",
    "afc bournemouth": "bournemouth", "estrella roja": "crvena zvezda",
}


def _alias(name: str) -> str:
    key = (name or "").strip().lower()
    plain = unicodedata.normalize("NFKD", key).encode("ASCII", "ignore").decode("utf-8")
    return TEAM_ALIASES.get(key) or TEAM_ALIASES.get(plain) or (name or "")


def _same_day(t1: Optional[str], t2: Optional[str], max_hours: float = 30.0) -> bool:
    """True si ambas fechas estan a menos de max_hours (o si falta alguna)."""
    from datetime import datetime
    if not t1 or not t2:
        return True
    try:
        d1 = datetime.fromisoformat(str(t1).replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(str(t2).replace("Z", "+00:00"))
        if (d1.tzinfo is None) != (d2.tzinfo is None):
            return True
        return abs((d1 - d2).total_seconds()) <= max_hours * 3600
    except (ValueError, TypeError):
        return True


def _diff_horas(t1: Optional[str], t2: Optional[str]) -> float:
    from datetime import datetime
    try:
        d1 = datetime.fromisoformat(str(t1).replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(str(t2).replace("Z", "+00:00"))
        return abs((d1 - d2).total_seconds()) / 3600
    except (ValueError, TypeError):
        return 999.0


def _es_femenino(name: str) -> bool:
    return bool(re.search(r"\((f|w)\)|\bwomen\b|\bfemenin|\bfem\b|\bladies\b", (name or "").lower()))


def teams_match(h1: str, a1: str, h2: str, a2: str) -> bool:
    """Compara si dos pares de nombres de equipos corresponden al mismo partido."""
    if _es_femenino(h1) != _es_femenino(h2) or _es_femenino(a1) != _es_femenino(a2):
        return False
    h1, a1, h2, a2 = _alias(h1), _alias(a1), _alias(h2), _alias(a2)
    # Evita confundir Real Madrid / Atletico Madrid, Real Sociedad / Sociedad, etc.
    for x, y in ((h1, h2), (a1, a2)):
        lx, ly = x.lower(), y.lower()
        if ("real madrid" in lx) != ("real madrid" in ly) or ("atletico madrid" in lx) != ("atletico madrid" in ly):
            return False
    nh1 = normalize_team_name(h1)
    na1 = normalize_team_name(a1)
    nh2 = normalize_team_name(h2)
    na2 = normalize_team_name(a2)

    if not nh1 or not na1 or not nh2 or not na2:
        return False

    home_match = (nh1 == nh2) or (nh1 in nh2) or (nh2 in nh1) or (difflib.SequenceMatcher(None, nh1, nh2).ratio() >= 0.78)
    away_match = (na1 == na2) or (na1 in na2) or (na2 in na1) or (difflib.SequenceMatcher(None, na1, na2).ratio() >= 0.78)

    return home_match and away_match


def fetch_aposta_matches() -> List[Dict[str, Any]]:
    """Consulta los partidos y cuotas activas de fútbol desde la API de Kambi utilizada por Aposta.la."""
    url = "https://us.offering-api.kambicdn.com/offering/v2018/betplayintpy/listView/football.json?lang=es_PY&market=PY&client_id=200"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://aposta.la/"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            print(f"[Aposta.la API] Error HTTP {resp.status_code}")
            return []
        data = resp.json()
    except Exception as e:
        print(f"[Aposta.la API] Error al conectar: {e}")
        return []

    events = data.get("events", [])
    aposta_matches = []

    for e in events:
        ev = e.get("event", {})
        event_id = ev.get("id")
        home = ev.get("homeName", "").strip()
        away = ev.get("awayName", "").strip()
        group = ev.get("group", "")
        start_time = ev.get("start", "")
        state = ev.get("state", "")

        odds_1x2 = {}
        for bo in e.get("betOffers", []):
            crit = bo.get("criterion", {})
            bo_type = bo.get("betOfferType", {})
            if bo_type.get("name") in ["Partido", "Match"] or crit.get("englishLabel") == "Full Time":
                for oc in bo.get("outcomes", []):
                    label = oc.get("label")
                    raw_odds = oc.get("odds")
                    status = oc.get("status")
                    if raw_odds and status != "SUSPENDED":
                        odds_1x2[label] = round(raw_odds / 1000.0, 2)

        texto = f"{group} {home} {away}".lower()
        es_virtual = bool(re.search(r"cyber|e-?sports?|esoccer|virtual|simulad|\d+x\d+ ?min", texto)) \
            or bool(re.search(r"\([a-z0-9_]*[a-z][a-z0-9_]*[0-9_][a-z0-9_]*\)|\((?=[a-z0-9_]*[a-z])[a-z0-9_]{4,}\)", f"{home} {away}"))
        if es_virtual or state not in ("", "NOT_STARTED"):
            continue

        if home and away and odds_1x2:
            aposta_matches.append({
                "id": event_id,
                "home": home,
                "away": away,
                "league": group,
                "start": start_time,
                "state": state,
                "odds": odds_1x2
            })

    return aposta_matches


def execute_forebet_aposta_cross(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Ejecuta el cruce completo entre Forebet y Aposta.la, calculando Value Bets (+EV)
    y métricas del Criterio de Kelly.
    """
    global _CACHE
    now = time.time()

    if not force_refresh and _CACHE["recommendations"] and (now - _CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return {
            "cached": True,
            "last_updated": _CACHE["timestamp"],
            "summary": _CACHE["summary"],
            "items": _CACHE["recommendations"]
        }

    # 1. Obtener probabilidades de fuentes oficiales (The Odds API / API-Football)
    from model.fuentes_oficiales import obtener_probabilidades_oficiales, fuentes_configuradas
    fb_list = obtener_probabilidades_oficiales() if any(fuentes_configuradas().values()) else []
    data_source = "fuentes_oficiales"
    if fb_list:
        try:
            from model.database import guardar_forebet_matches
            guardar_forebet_matches(fb_list)
        except Exception as e:
            print(f"[Forebet Cache] Error al persistir en DB: {e}")
    else:
        # Sin claves configuradas o sin datos: usar las ultimas predicciones guardadas/importadas
        try:
            from model.database import obtener_forebet_matches
            fb_list = obtener_forebet_matches()
            if fb_list:
                data_source = "base_de_datos"
                print(f"[Forebet Cache] Usando {len(fb_list)} predicciones respaldadas en base de datos")
        except Exception as e:
            print(f"[Forebet Cache] Error al leer DB: {e}")

    ap_list = fetch_aposta_matches()

    recommendations = []
    total_val_bets = 0


    for fb in fb_list:
        h1, a1 = fb["home"], fb["away"]
        match_found = None
        candidatos = [ap for ap in ap_list
                      if teams_match(h1, a1, ap["home"], ap["away"])
                      and _same_day(fb.get("dateTime"), ap.get("start"), max_hours=6.0)]
        if candidatos:
            match_found = min(candidatos, key=lambda ap: _diff_horas(fb.get("dateTime"), ap.get("start")))

        if not match_found:
            continue

        odds = match_found["odds"]
        probs = {
            "1": (fb["p1"] / 100.0) if fb["p1"] else None,
            "X": (fb["px"] / 100.0) if fb["px"] else None,
            "2": (fb["p2"] / 100.0) if fb["p2"] else None,
        }

        evaluations = []
        for pick in ["1", "X", "2"]:
            p = probs.get(pick)
            cuota = odds.get(pick)
            if p and cuota and cuota > 1.0:
                ev = (p * cuota) - 1.0
                implied_p = 1.0 / cuota
                edge = p - implied_p

                # Criterio de Kelly (fraccionario 1/4)
                b = cuota - 1.0
                kelly = (p * b - (1.0 - p)) / b if b > 0 else 0.0
                quarter_kelly = max(0.0, kelly * 0.25)

                sospechoso = ev > 0.25 or abs(edge) > 0.15
                is_value = ev > 0.0 and not sospechoso
                is_high_value = is_value and ev >= 0.08 and p >= 0.30

                evaluations.append({
                    "pick": pick,
                    "prob_fb_pct": round(p * 100.0, 1),
                    "cuota_aposta": cuota,
                    "prob_implied_pct": round(implied_p * 100.0, 1),
                    "ev_pct": round(ev * 100.0, 1),
                    "edge_pct": round(edge * 100.0, 1),
                    "kelly_pct": round(quarter_kelly * 100.0, 1),
                    "is_value": is_value,
                    "is_high_value": is_high_value,
                    "revisar_cruce": sospechoso
                })

        # Identificar la mejor selección por EV
        best_pick = None
        if evaluations:
            # Filtrar picks con EV positivo y probabilidad razonable, o el de mayor EV
            positive_evals = [e for e in evaluations if e["is_value"]]
            if positive_evals:
                best_pick = max(positive_evals, key=lambda x: x["ev_pct"])
                total_val_bets += 1
            else:
                best_pick = max(evaluations, key=lambda x: x["ev_pct"])

        # Detectar si el favorito señalado por Forebet es una "Cuota Trampa" (EV negativo)
        trap_favorite = False
        fb_pred = fb.get("pred")
        if fb_pred:
            matching_eval = next((e for e in evaluations if e["pick"] == fb_pred), None)
            if matching_eval and matching_eval["ev_pct"] < -5.0:
                trap_favorite = True

        recommendations.append({
            "forebet": fb,
            "aposta": match_found,
            "evaluations": evaluations,
            "best_pick": best_pick,
            "has_value": bool(best_pick and best_pick["is_value"]),
            "is_high_value": bool(best_pick and best_pick["is_high_value"]),
            "trap_favorite": trap_favorite
        })

    # Ordenar: primero los de alto valor, luego por EV descendente
    recommendations.sort(
        key=lambda x: (
            1 if x["is_high_value"] else (0 if x["has_value"] else -1),
            x["best_pick"]["ev_pct"] if x["best_pick"] else -999.0
        ),
        reverse=True
    )

    summary = {
        "forebet_matches_found": len(fb_list),
        "partidos_con_probabilidad": len(fb_list),
        "aposta_events_available": len(ap_list),
        "total_matched": len(recommendations),
        "total_value_bets": total_val_bets,
        "high_value_bets": sum(1 for r in recommendations if r["is_high_value"]),
        "best_opportunity": recommendations[0]["forebet"]["home"] + " vs " + recommendations[0]["forebet"]["away"] if recommendations else None,
        "best_ev": recommendations[0]["best_pick"]["ev_pct"] if recommendations and recommendations[0]["best_pick"] else None,
        "data_source": data_source,
        "fuentes": sorted({m.get("fuente", "Forebet (importado)") for m in fb_list}),
    }

    _CACHE = {
        "timestamp": now,
        "forebet_matches": fb_list,
        "aposta_matches": ap_list,
        "recommendations": recommendations,
        "summary": summary
    }

    return {
        "cached": False,
        "last_updated": now,
        "summary": summary,
        "items": recommendations
    }


def importar_forebet_matches_manual(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Importa predicciones de Forebet externamente y recalcula el cruce contra cuotas en vivo de Aposta.la."""
    from model.database import guardar_forebet_matches
    guardar_forebet_matches(matches)

    global _CACHE
    _CACHE["timestamp"] = 0.0
    _CACHE["recommendations"] = []

    return execute_forebet_aposta_cross(force_refresh=True)

