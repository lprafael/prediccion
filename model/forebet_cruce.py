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


def _ascii(text: str) -> str:
    return unicodedata.normalize('NFKD', (text or "").lower()).encode('ASCII', 'ignore').decode('utf-8')


# Palabras que no identifican al equipo (siglas societarias, articulos).
# OJO: NO incluir "united", "city", "real", "atletico", "inter"... porque
# distinguen equipos (Manchester United vs Manchester City).
_STOPWORDS = {"fc", "cf", "sc", "ac", "cd", "fk", "sk", "csd", "afc", "ssc", "sv", "bk",
              "if", "club", "de", "del", "la", "el", "the", "and", "y", "1", "rj", "sp",
              "mg", "rs", "pr", "go", "ba", "ce", "pe", "sa", "s"}
# Marcas de equipos juveniles / reservas / filiales: deben coincidir en ambos lados.
_MARCAS_FILIAL = {"u17", "u18", "u19", "u20", "u21", "u23", "sub", "ii", "b", "reserves",
                  "reserva", "reservas", "castilla", "atletic", "youth", "f", "w", "women"}
_TOKEN_ALIAS = {"utd": "united", "man": "manchester", "munchen": "munich", "muenchen": "munich",
                "koeln": "koln", "cologne": "koln", "lisboa": "lisbon", "milano": "milan",
                "athletico": "athletico", "saint": "st", "sankt": "st", "wanderers": "wanderers"}


def _tokens(name: str) -> List[str]:
    t = re.sub(r"[^a-z0-9]+", " ", _ascii(_alias(name)))
    return [_TOKEN_ALIAS.get(w, w) for w in t.split()]


def normalize_team_name(text: str) -> str:
    """Nombre normalizado (sin tildes, signos ni siglas de club), conservando las
    palabras que distinguen equipos (united, city, real, atletico...)."""
    if not text:
        return ""
    return "".join(w for w in _tokens(text) if w not in _STOPWORDS)


def _token_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
        return True  # erratas / transliteraciones (koln-koeln, ...)
    return False


def same_team(n1: str, n2: str) -> bool:
    """True si dos nombres corresponden al mismo equipo.

    Regla: las marcas de filial/juvenil/femenino deben coincidir, y todas las
    palabras significativas del nombre mas corto deben estar en el mas largo
    ("Atletico Mineiro" ~ "Atletico Mineiro-MG", pero "Inter" != "Internacional"
    y "Manchester United" != "Manchester City").
    """
    t1, t2 = _tokens(n1), _tokens(n2)
    m1 = {w for w in t1 if w in _MARCAS_FILIAL} | ({"f"} if _es_femenino(n1) else set())
    m2 = {w for w in t2 if w in _MARCAS_FILIAL} | ({"f"} if _es_femenino(n2) else set())
    m1 = {"f" if w in ("w", "women") else w for w in m1}
    m2 = {"f" if w in ("w", "women") else w for w in m2}
    if m1 != m2:
        return False
    s1 = [w for w in t1 if w not in _STOPWORDS and w not in _MARCAS_FILIAL]
    s2 = [w for w in t2 if w not in _STOPWORDS and w not in _MARCAS_FILIAL]
    if not s1 or not s2:
        return False
    if "".join(s1) == "".join(s2):
        return True
    corto, largo = (s1, s2) if len(s1) <= len(s2) else (s2, s1)
    if not all(any(_token_eq(w, x) for x in largo) for w in corto):
        return False
    # Si el nombre corto es una sola palabra generica (ej. "Real", "Atletico") no alcanza
    return len("".join(corto)) >= 4 and not (len(corto) == 1 and corto[0] in
                                              {"real", "atletico", "united", "city", "sporting",
                                               "deportivo", "nacional", "inter", "racing"} and len(largo) > 1)

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
    return same_team(h1, h2) and same_team(a1, a2)


def fetch_aposta_matches() -> List[Dict[str, Any]]:
    """Partidos pre-partido de Aposta.la (Kambi) con su 1X2: ligas configuradas
    (APOSTA_LIGAS) + listado general de proximos partidos."""
    from model.aposta_feed import fetch_eventos_cache, _get, _evento_basico
    eventos = list(fetch_eventos_cache())
    vistos = {e["id"] for e in eventos}
    general = _get("/listView/football.json") or {}
    for e in general.get("events", []):
        ev = _evento_basico(e, "general")
        if ev and ev["id"] not in vistos:
            vistos.add(ev["id"])
            eventos.append(ev)
    return [e for e in eventos if e["odds"]]


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

