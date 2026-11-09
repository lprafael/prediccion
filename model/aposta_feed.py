"""
Lectura de partidos y cuotas de Aposta.la (plataforma Kambi).

- Los partidos se leen liga por liga (el listado general de Kambi solo trae las
  proximas ~24 h y casi nunca incluye las ligas grandes).
- Para los partidos que interesan se descargan todos los mercados en lote
  (betoffer/event/{id1,id2,...}) y se extraen los de alta probabilidad:
  1X2, Doble oportunidad, Empate no apuesta, Total de goles y Ambos marcan.

Variables de entorno:
  APOSTA_LIGAS   Rutas Kambi separadas por coma (ej. "england/premier_league,champions_league").
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional

import requests

KAMBI_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplayintpy"
KAMBI_PARAMS = {"lang": "es_PY", "market": "PY", "client_id": "200", "useCombined": "true"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://aposta.la/",
}

# Ligas de Aposta.la que tienen probabilidades de referencia en The Odds API.
DEFAULT_LIGAS = ",".join([
    "england/premier_league", "england/the_championship", "spain/la_liga", "spain/la_liga_2",
    "italy/serie_a", "germany/bundesliga", "france/ligue_1", "portugal/primeira_liga",
    "netherlands/eredivisie", "scotland/scottish_premiership", "champions_league",
    "europa_league", "conference_league", "copa_libertadores", "copa_sudamericana",
    "brazil/brasileirao_serie_a", "argentina/liga_profesional", "usa/mls", "mexico/liga_mx",
    "paraguay/primera_paraguay", "uefa_nations_league",
])

# englishLabel del criterio Kambi -> codigo interno
_MERCADOS = {
    "Full Time": "1X2",
    "Double Chance": "DC",
    "Draw No Bet": "DNB",
    "Total Goals": "OU",
    "Both Teams To Score": "BTTS",
}
_OUTCOME = {
    "OT_ONE": "1", "OT_CROSS": "X", "OT_TWO": "2",
    "OT_ONE_OR_CROSS": "1X", "OT_ONE_OR_TWO": "12", "OT_CROSS_OR_TWO": "X2",
    "OT_OVER": "over", "OT_UNDER": "under", "OT_YES": "si", "OT_NO": "no",
}


def _get(path: str, timeout: float = 15.0) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(f"{KAMBI_BASE}{path}", params=KAMBI_PARAMS, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def _es_virtual(group: str, home: str, away: str) -> bool:
    texto = f"{group} {home} {away}".lower()
    return bool(re.search(r"cyber|e-?sports?|esoccer|virtual|simulad|\d+x\d+ ?min", texto))


def _evento_basico(e: Dict[str, Any], ruta: str) -> Optional[Dict[str, Any]]:
    ev = e.get("event", {})
    home, away = (ev.get("homeName") or "").strip(), (ev.get("awayName") or "").strip()
    if not home or not away or ev.get("state") not in (None, "", "NOT_STARTED"):
        return None
    if _es_virtual(ev.get("group", ""), home, away):
        return None
    odds = {}
    for bo in e.get("betOffers", []):
        if bo.get("criterion", {}).get("englishLabel") != "Full Time":
            continue
        for oc in bo.get("outcomes", []):
            k = _OUTCOME.get(oc.get("type"))
            if k and oc.get("odds") and oc.get("status", "OPEN") == "OPEN":
                odds[k] = round(oc["odds"] / 1000.0, 2)
    return {"id": ev.get("id"), "home": home, "away": away, "league": ev.get("group", ""),
            "ruta": ruta, "start": ev.get("start", ""), "state": ev.get("state", ""), "odds": odds}


def fetch_eventos(ligas: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Partidos pre-partido de las ligas indicadas (con su 1X2)."""
    rutas = list(ligas) if ligas else [x.strip() for x in (os.getenv("APOSTA_LIGAS") or DEFAULT_LIGAS).split(",") if x.strip()]

    def _liga(ruta: str) -> List[Dict[str, Any]]:
        d = _get(f"/listView/football/{ruta}.json")
        return [x for x in (_evento_basico(e, ruta) for e in (d or {}).get("events", [])) if x]

    vistos, out = set(), []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for lista in ex.map(_liga, rutas):
            for ev in lista:
                if ev["id"] not in vistos:
                    vistos.add(ev["id"])
                    out.append(ev)
    return out


def _parse_mercados(bet_offers: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    res: Dict[int, Dict[str, Any]] = {}
    for bo in bet_offers:
        cod = _MERCADOS.get(bo.get("criterion", {}).get("englishLabel"))
        if not cod:
            continue
        mk = res.setdefault(bo.get("eventId"), {})
        for oc in bo.get("outcomes", []):
            sel = _OUTCOME.get(oc.get("type"))
            if not sel or not oc.get("odds") or oc.get("status", "OPEN") != "OPEN":
                continue
            cuota = round(oc["odds"] / 1000.0, 3)
            if cod == "OU":
                if oc.get("line") is None:
                    continue
                linea = oc["line"] / 1000.0
                mk.setdefault("OU", {}).setdefault(linea, {})[sel] = cuota
            else:
                mk.setdefault(cod, {})[sel] = cuota
    return res


def fetch_mercados(event_ids: List[int], lote: int = 8) -> Dict[int, Dict[str, Any]]:
    """Todos los mercados de interes para cada evento: {id: {"1X2": {...}, "DC": {...},
    "DNB": {...}, "OU": {1.5: {"over": c, "under": c}, ...}, "BTTS": {...}}}."""
    grupos = [event_ids[i:i + lote] for i in range(0, len(event_ids), lote)]

    def _lote(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        d = _get(f"/betoffer/event/{','.join(str(i) for i in ids)}.json", timeout=20)
        return _parse_mercados((d or {}).get("betOffers", []))

    out: Dict[int, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(_lote, grupos):
            out.update(r)
    return out


_CACHE_EVENTOS: Dict[str, Any] = {"ts": 0.0, "data": []}


def fetch_eventos_cache(ttl_s: float = 300.0) -> List[Dict[str, Any]]:
    if _CACHE_EVENTOS["data"] and time.time() - _CACHE_EVENTOS["ts"] < ttl_s:
        return _CACHE_EVENTOS["data"]
    data = fetch_eventos()
    if data:
        _CACHE_EVENTOS.update(ts=time.time(), data=data)
    return data
