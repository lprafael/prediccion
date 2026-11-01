"""
Fuentes de datos oficiales (con API y licencia) para estimar probabilidades reales
de cada partido y cruzarlas con las cuotas de Aposta.la.

1. The Odds API (https://the-odds-api.com)  -> fuente principal
   Cuotas de casas europeas; se usa Pinnacle (la casa mas "afilada") o, si no esta,
   el consenso de todas. Se les quita el margen y queda una probabilidad justa.
   Variable: ODDS_API_KEY

2. API-Football (https://www.api-football.com)  -> complemento
   Predicciones (% local/empate/visitante) para ligas que The Odds API no cubre,
   p. ej. Primera Division de Paraguay.
   Variable: API_FOOTBALL_KEY

Devuelve partidos con el mismo formato que usaba Forebet (home, away, p1, px, p2, ...)
para reutilizar el motor de cruce existente.
"""

import os
import time
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

ODDS_API_URL = "https://api.the-odds-api.com/v4"
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

# Ligas consultadas en The Odds API (1 credito por liga por consulta).
DEFAULT_ODDS_SPORTS = ",".join([
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_portugal_primeira_liga",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_brazil_campeonato",
    "soccer_argentina_primera_division",
    "soccer_conmebol_copa_libertadores",
])

SHARP_BOOKS = ("pinnacle", "betfair_ex_eu", "matchbook")

_last_run: Dict[str, Any] = {"odds_api": {}, "api_football": {}}


def _env_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name) or default
    return [x.strip() for x in raw.split(",") if x.strip()]


def _devig(prices: List[float]) -> Optional[List[float]]:
    """Convierte cuotas decimales en probabilidades sin margen.

    Metodo por defecto: "power" (p_i = (1/cuota_i)^k, con k tal que la suma da 1).
    A diferencia del metodo proporcional, no infla la probabilidad de los equipos
    muy poco favoritos (sesgo favorito-longshot). DEVIG_METODO=proporcional
    vuelve al metodo anterior.
    """
    if not prices or any((p is None or p <= 1.0) for p in prices):
        return None
    inv = [1.0 / p for p in prices]
    total = sum(inv)
    if os.getenv("DEVIG_METODO", "power").lower().startswith("prop") or total <= 1.0:
        return [x / total for x in inv]
    lo, hi = 1.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if sum(x ** k for x in inv) > 1.0:
            lo = k
        else:
            hi = k
    probs = [x ** ((lo + hi) / 2) for x in inv]
    s = sum(probs)
    return [x / s for x in probs]


# ─── 1. The Odds API ──────────────────────────────────────────────────────────

def _probs_from_event(ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    home, away = ev.get("home_team"), ev.get("away_team")
    sharp: Optional[List[float]] = None
    sharp_name = None
    consensus: List[List[float]] = []

    for bk in ev.get("bookmakers", []):
        for mk in bk.get("markets", []):
            if mk.get("key") != "h2h":
                continue
            price = {o.get("name"): o.get("price") for o in mk.get("outcomes", [])}
            trio = [price.get(home), price.get("Draw"), price.get(away)]
            probs = _devig(trio)
            if not probs:
                continue
            consensus.append(probs)
            if sharp is None and bk.get("key") in SHARP_BOOKS:
                sharp, sharp_name = probs, bk.get("title") or bk.get("key")

    if sharp:
        probs, metodo, n = sharp, f"Sin margen: {sharp_name}", 1
    elif len(consensus) >= 3:
        probs = [statistics.median(c[i] for c in consensus) for i in range(3)]
        s = sum(probs)
        probs = [p / s for p in probs]
        metodo, n = "Sin margen: consenso de casas", len(consensus)
    else:
        return None

    p1, px, p2 = (round(p * 100.0, 1) for p in probs)
    pred = max((("1", p1), ("X", px), ("2", p2)), key=lambda t: t[1])[0]
    return {"p1": p1, "px": px, "p2": p2, "pred": pred, "metodo": metodo, "n_casas": n}


def fetch_odds_api_probabilities() -> List[Dict[str, Any]]:
    key = os.getenv("ODDS_API_KEY")
    if not key:
        return []
    sports = _env_list("ODDS_API_SPORTS", DEFAULT_ODDS_SPORTS)
    regions = os.getenv("ODDS_API_REGIONS", "eu")
    out: List[Dict[str, Any]] = []
    info: Dict[str, Any] = {"ligas": {}, "creditos_restantes": None, "errores": []}

    for sport in sports:
        try:
            r = requests.get(
                f"{ODDS_API_URL}/sports/{sport}/odds",
                params={"apiKey": key, "regions": regions, "markets": "h2h",
                        "oddsFormat": "decimal", "dateFormat": "iso"},
                timeout=20,
            )
            info["creditos_restantes"] = r.headers.get("x-requests-remaining", info["creditos_restantes"])
            if r.status_code != 200:
                info["errores"].append(f"{sport}: HTTP {r.status_code} {r.text[:120]}")
                continue
            events = r.json()
        except Exception as e:  # red, JSON, etc.
            info["errores"].append(f"{sport}: {e}")
            continue

        n = 0
        for ev in events:
            probs = _probs_from_event(ev)
            if not probs:
                continue
            out.append({
                "tournament": ev.get("sport_title", sport),
                "home": ev.get("home_team"),
                "away": ev.get("away_team"),
                "dateTime": ev.get("commence_time"),
                "exactScore": None, "avgGoals": None,
                "fbOdd1": None, "fbOddX": None, "fbOdd2": None,
                "fuente": "The Odds API",
                **probs,
            })
            n += 1
        info["ligas"][sport] = n

    info["timestamp"] = time.time()
    _last_run["odds_api"] = info
    return out


# ─── 2. API-Football ──────────────────────────────────────────────────────────

def _af_get(path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        return None
    r = requests.get(f"{API_FOOTBALL_URL}{path}", params=params,
                     headers={"x-apisports-key": key}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"])[:200])
    return data


def _pct(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_api_football_predictions() -> List[Dict[str, Any]]:
    """Predicciones para las ligas en API_FOOTBALL_LEAGUES (ids) o de los paises en
    API_FOOTBALL_COUNTRIES (por defecto Paraguay). 1 consulta por partido: se limita
    con API_FOOTBALL_MAX_PRED para cuidar la cuota diaria."""
    if not os.getenv("API_FOOTBALL_KEY"):
        return []
    # Cuota gratuita: 100 consultas/dia. Se reutiliza el resultado durante
    # API_FOOTBALL_REFRESH_MIN minutos (por defecto 6 horas).
    refresh_s = float(os.getenv("API_FOOTBALL_REFRESH_MIN", "360")) * 60
    prev = _last_run.get("api_football", {})
    if prev.get("datos") and time.time() - prev.get("timestamp", 0) < refresh_s:
        return prev["datos"]
    info: Dict[str, Any] = {"ligas": [], "partidos": 0, "errores": []}
    out: List[Dict[str, Any]] = []
    days = int(os.getenv("API_FOOTBALL_DAYS", "3"))
    max_pred = int(os.getenv("API_FOOTBALL_MAX_PRED", "15"))

    try:
        leagues: List[Dict[str, Any]] = []
        ids = _env_list("API_FOOTBALL_LEAGUES", "")
        if ids:
            for lid in ids:
                d = _af_get("/leagues", {"id": lid, "current": "true"})
                leagues += (d or {}).get("response", [])
        else:
            for country in _env_list("API_FOOTBALL_COUNTRIES", "Paraguay"):
                d = _af_get("/leagues", {"country": country, "current": "true", "type": "league"})
                leagues += (d or {}).get("response", [])

        today = datetime.now(timezone.utc).date()
        fixtures: List[Dict[str, Any]] = []
        for lg in leagues:
            league, seasons = lg.get("league", {}), lg.get("seasons", [])
            season = next((s.get("year") for s in seasons if s.get("current")), None)
            if not season:
                continue
            info["ligas"].append(f"{league.get('name')} ({league.get('id')})")
            d = _af_get("/fixtures", {
                "league": league.get("id"), "season": season, "status": "NS",
                "from": today.isoformat(), "to": (today + timedelta(days=days)).isoformat(),
            })
            fixtures += (d or {}).get("response", [])

        fixtures.sort(key=lambda f: f.get("fixture", {}).get("date", ""))
        for fx in fixtures[:max_pred]:
            fid = fx.get("fixture", {}).get("id")
            try:
                d = _af_get("/predictions", {"fixture": fid})
            except Exception as e:
                info["errores"].append(f"prediccion {fid}: {e}")
                continue
            resp = (d or {}).get("response", [])
            if not resp:
                continue
            pr = resp[0].get("predictions", {})
            pc = pr.get("percent", {})
            p1, px, p2 = _pct(pc.get("home")), _pct(pc.get("draw")), _pct(pc.get("away"))
            if p1 is None or px is None or p2 is None:
                continue
            pred = max((("1", p1), ("X", px), ("2", p2)), key=lambda t: t[1])[0]
            teams = fx.get("teams", {})
            out.append({
                "tournament": fx.get("league", {}).get("name"),
                "home": teams.get("home", {}).get("name"),
                "away": teams.get("away", {}).get("name"),
                "dateTime": fx.get("fixture", {}).get("date"),
                "p1": p1, "px": px, "p2": p2, "pred": pred,
                "exactScore": None, "avgGoals": None,
                "fbOdd1": None, "fbOddX": None, "fbOdd2": None,
                "consejo": pr.get("advice"),
                "metodo": "Prediccion API-Football",
                "fuente": "API-Football",
            })
    except Exception as e:
        info["errores"].append(str(e))

    info["partidos"] = len(out)
    info["timestamp"] = time.time()
    info["datos"] = out
    _last_run["api_football"] = info
    return out


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def fuentes_configuradas() -> Dict[str, bool]:
    return {"odds_api": bool(os.getenv("ODDS_API_KEY")),
            "api_football": bool(os.getenv("API_FOOTBALL_KEY"))}


def obtener_probabilidades_oficiales() -> List[Dict[str, Any]]:
    """Une ambas fuentes. Si un partido aparece en las dos, se queda el de The Odds API."""
    principal = fetch_odds_api_probabilities()
    complemento = fetch_api_football_predictions()
    vistos = {(m["home"], m["away"]) for m in principal}
    return principal + [m for m in complemento if (m["home"], m["away"]) not in vistos]


def estado_fuentes() -> Dict[str, Any]:
    resumen = {k: {kk: vv for kk, vv in v.items() if kk != "datos"} for k, v in _last_run.items()}
    return {"configuradas": fuentes_configuradas(), "ultima_ejecucion": resumen}
