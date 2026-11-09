"""
Generador de selecciones y combinadas de alta probabilidad con valor (+EV) en Aposta.la.

Idea central
------------
Una combinada solo es rentable a largo plazo si CADA selección lo es: la casa cobra
un margen en cada pata y en una combinada esos margenes se multiplican. Por eso:

1. La probabilidad "real" de cada resultado sale del mercado afilado (Pinnacle /
   consenso de casas europeas, sin margen) via The Odds API.
2. De ese 1X2 se derivan, sin coste extra:
   - Doble oportunidad (1X, X2, 12) y Empate no apuesta (con devolucion si empatan),
   - Total de goles y Ambos marcan con un modelo de Poisson ajustado al 1X2
     (y a la linea de goles del mercado, si ODDS_API_MARKETS incluye "totals").
3. Se comparan con las cuotas de Aposta.la. Solo pasan las selecciones con
   probabilidad alta (por defecto >= 70 %) y EV >= 0.
4. Se combinan solo partidos distintos (independientes) y se ordenan por
   crecimiento esperado del bankroll (criterio de Kelly), con el monto sugerido.
"""

import itertools
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from model.forebet_cruce import teams_match, _same_day, _diff_horas
from model.aposta_feed import fetch_eventos_cache, fetch_mercados

MAX_GOLES = 11
_LAMBDAS = np.arange(0.10, 4.51, 0.05)
_K = np.arange(MAX_GOLES)
_FACT = np.array([math.factorial(int(k)) for k in _K], dtype=float)
# pmf[i, k] = P(Poisson(lambda_i) = k)
_PMF = np.exp(-_LAMBDAS[:, None]) * _LAMBDAS[:, None] ** _K[None, :] / _FACT[None, :]
_CDF_TOTAL_CACHE: Dict[str, np.ndarray] = {}


def _rejilla() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """P(1), P(X), P(2) para cada par (lambda_local, lambda_visita) de la rejilla."""
    if "res" not in _CDF_TOTAL_CACHE:
        mat = _PMF[:, None, :, None] * _PMF[None, :, None, :]  # [lh, la, gh, ga]
        tri_inf = np.tril(np.ones((MAX_GOLES, MAX_GOLES)), -1)  # gh > ga
        p1 = (mat * tri_inf).sum(axis=(2, 3))
        px = np.einsum("abii->ab", mat)
        p2 = (mat * tri_inf.T).sum(axis=(2, 3))
        _CDF_TOTAL_CACHE["res"] = np.stack([p1, px, p2])
    r = _CDF_TOTAL_CACHE["res"]
    return r[0], r[1], r[2]


def _p_over_total(lam_total: np.ndarray, linea: float) -> np.ndarray:
    k = np.arange(int(math.floor(linea)) + 1)
    fact = np.array([math.factorial(int(x)) for x in k], dtype=float)
    cdf = (np.exp(-lam_total)[..., None] * lam_total[..., None] ** k / fact).sum(-1)
    return 1.0 - cdf


def ajustar_poisson(p1: float, px: float, p2: float,
                    p_over: Optional[Dict[float, float]] = None) -> Tuple[float, float]:
    """Goles esperados (local, visita) que mejor reproducen el 1X2 sin margen
    (y la probabilidad de 'mas de X goles' del mercado, si existe)."""
    g1, gx, g2 = _rejilla()
    err = (g1 - p1) ** 2 + (gx - px) ** 2 + (g2 - p2) ** 2
    if p_over:
        tot = _LAMBDAS[:, None] + _LAMBDAS[None, :]
        for linea, po in p_over.items():
            err = err + 2.0 * (_p_over_total(tot, float(linea)) - po) ** 2
    i, j = np.unravel_index(np.argmin(err), err.shape)
    return float(_LAMBDAS[i]), float(_LAMBDAS[j])


def probabilidades_mercados(p1: float, px: float, p2: float,
                            p_over: Optional[Dict[float, float]] = None) -> Dict[str, Any]:
    """Probabilidades justas de todos los mercados soportados.
    Cada valor es (p_gana, p_devolucion, fuente)."""
    s = p1 + px + p2
    p1, px, p2 = p1 / s, px / s, p2 / s
    lh, la = ajustar_poisson(p1, px, p2, p_over)
    fuente_goles = "modelo+mercado" if p_over else "modelo"
    out: Dict[str, Any] = {
        ("1X2", "1"): (p1, 0.0, "mercado"), ("1X2", "X"): (px, 0.0, "mercado"),
        ("1X2", "2"): (p2, 0.0, "mercado"),
        ("DC", "1X"): (p1 + px, 0.0, "mercado"), ("DC", "X2"): (px + p2, 0.0, "mercado"),
        ("DC", "12"): (p1 + p2, 0.0, "mercado"),
        ("DNB", "1"): (p1, px, "mercado"), ("DNB", "2"): (p2, px, "mercado"),
    }
    for linea in (0.5, 1.5, 2.5, 3.5, 4.5):
        if p_over and linea in p_over:
            po = p_over[linea]
            fuente = "mercado"
        else:
            po = float(_p_over_total(np.array(lh + la), linea))
            fuente = fuente_goles
        out[(f"OU {linea}", "over")] = (po, 0.0, fuente)
        out[(f"OU {linea}", "under")] = (1.0 - po, 0.0, fuente)
    btts = (1 - math.exp(-lh)) * (1 - math.exp(-la))
    out[("BTTS", "si")] = (btts, 0.0, "modelo")
    out[("BTTS", "no")] = (1 - btts, 0.0, "modelo")
    out["_lambdas"] = (round(lh, 2), round(la, 2))
    return out


_NOMBRE_MERCADO = {"1X2": "Resultado final", "DC": "Doble oportunidad", "DNB": "Empate no apuesta",
                   "BTTS": "Ambos marcan"}


def _etiqueta(mercado: str, sel: str, home: str, away: str) -> str:
    if mercado == "1X2":
        return {"1": home, "X": "Empate", "2": away}[sel]
    if mercado == "DC":
        return {"1X": f"{home} o empate", "X2": f"{away} o empate", "12": f"{home} o {away}"}[sel]
    if mercado == "DNB":
        return f"{home if sel == '1' else away} (empate devuelve)"
    if mercado.startswith("OU"):
        return f"{'Más' if sel == 'over' else 'Menos'} de {mercado.split()[1]} goles"
    if mercado == "BTTS":
        return f"Ambos marcan: {'Sí' if sel == 'si' else 'No'}"
    return sel


def construir_selecciones(fair: List[Dict[str, Any]], eventos: Optional[List[Dict[str, Any]]] = None,
                          horas_max: float = 72.0) -> List[Dict[str, Any]]:
    """Todas las selecciones (partido x mercado) con cuota de Aposta.la y probabilidad justa."""
    eventos = eventos if eventos is not None else fetch_eventos_cache()
    ahora = time.time()
    cruces = []
    for fb in fair:
        if fb.get("fuente") != "The Odds API" or not (fb.get("p1") and fb.get("px") and fb.get("p2")):
            continue  # solo probabilidades de mercado afilado
        cand = [ap for ap in eventos if teams_match(fb["home"], fb["away"], ap["home"], ap["away"])
                and _same_day(fb.get("dateTime"), ap.get("start"), max_hours=6.0)]
        if not cand:
            continue
        ap = min(cand, key=lambda a: _diff_horas(fb.get("dateTime"), a.get("start")))
        try:
            from datetime import datetime
            t = datetime.fromisoformat(ap["start"].replace("Z", "+00:00")).timestamp()
            if t < ahora or t - ahora > horas_max * 3600:
                continue
        except (ValueError, AttributeError):
            pass
        cruces.append((fb, ap))

    mercados = fetch_mercados([ap["id"] for _, ap in cruces]) if cruces else {}
    selecciones = []
    for fb, ap in cruces:
        mk = mercados.get(ap["id"]) or {}
        if "1X2" not in mk and ap.get("odds"):
            mk["1X2"] = ap["odds"]
        p_over = {float(k): float(v) for k, v in (fb.get("p_over") or {}).items()} or None
        probs = probabilidades_mercados(fb["p1"] / 100.0, fb["px"] / 100.0, fb["p2"] / 100.0, p_over)
        for mercado, sels in mk.items():
            if mercado == "OU":
                items = [(f"OU {l}", s, c) for l, d in sels.items() for s, c in d.items()]
            else:
                items = [(mercado, s, c) for s, c in sels.items()]
            for merc, sel, cuota in items:
                pr = probs.get((merc, sel))
                if not pr or not cuota or cuota <= 1.0:
                    continue
                p, push, fuente = pr
                ev = p * cuota + push - 1.0
                selecciones.append({
                    "evento_id": ap["id"], "partido": f"{ap['home']} vs {ap['away']}",
                    "liga": ap.get("league"), "inicio": ap.get("start"),
                    "mercado": _NOMBRE_MERCADO.get(merc, "Total de goles" if merc.startswith("OU") else merc),
                    "codigo": f"{merc}:{sel}", "seleccion": _etiqueta(merc, sel, ap["home"], ap["away"]),
                    "cuota": round(cuota, 2), "prob": round(p, 4), "prob_devolucion": round(push, 4),
                    "prob_no_perder": round(p + push, 4),
                    "cuota_justa": round((1.0 - push) / p, 3) if p > 0 else None,
                    "ev_pct": round(ev * 100, 2), "fuente_prob": fuente,
                    "referencia": fb.get("metodo"), "goles_esperados": probs["_lambdas"],
                    "ref_home": fb.get("home"), "ref_away": fb.get("away"),
                })
    return selecciones


def _kelly(p_gana: float, p_push: float, cuota: float) -> float:
    """Fraccion de Kelly para una apuesta con devolucion posible."""
    b = cuota - 1.0
    p_pierde = 1.0 - p_gana - p_push
    if b <= 0 or p_gana <= 0:
        return 0.0
    return max(0.0, (p_gana * b - p_pierde) / b)


def _resumen_combinada(patas: List[Dict[str, Any]]) -> Dict[str, Any]:
    cuota = math.prod(p["cuota"] for p in patas)
    # EV exacto con devoluciones (cada pata: gana -> cuota, devuelve -> 1, pierde -> 0)
    retorno_esp = math.prod(p["prob"] * p["cuota"] + p["prob_devolucion"] for p in patas)
    p_todas = math.prod(p["prob"] for p in patas)
    p_no_perder = math.prod(p["prob_no_perder"] for p in patas)
    # Aproximacion para Kelly: devoluciones repartidas como "gana con cuota menor"
    cuota_media = (retorno_esp / p_no_perder) if p_no_perder > 0 else cuota
    kelly = _kelly(p_no_perder, 0.0, cuota_media)
    return {
        "cuota_total": round(cuota, 2), "prob_ganar": round(p_no_perder, 4),
        "prob_todas_ganan": round(p_todas, 4), "ev_pct": round((retorno_esp - 1.0) * 100, 2),
        "kelly_completo_pct": round(kelly * 100, 2),
        # crecimiento log esperado con 1/4 de Kelly (para ordenar)
        "_score": (p_no_perder * math.log1p(0.25 * kelly * (cuota_media - 1))
                   + (1 - p_no_perder) * math.log1p(-0.25 * kelly)) if kelly > 0 else -1.0,
    }


def generar_combinadas(selecciones: List[Dict[str, Any]], *, prob_min_pata: float = 0.70,
                       ev_min_pata: float = 0.0, ev_min_modelo: float = 3.0,
                       max_patas: int = 4, cuota_min: float = 1.50, cuota_max: float = 4.0,
                       prob_min_combinada: float = 0.40, bankroll: float = 0.0,
                       fraccion_kelly: float = 0.25, tope_pct: float = 3.0,
                       max_resultados: int = 10) -> Dict[str, Any]:
    """Elige las selecciones seguras con valor y arma las mejores combinadas.

    - prob_min_pata: probabilidad minima de no perder cada pata.
    - ev_min_pata / ev_min_modelo: EV minimo (%) si la probabilidad viene del
      mercado / del modelo de goles (mas exigente porque el modelo tiene error).
    - cuota_min / cuota_max: rango de cuota total de la combinada.
    - bankroll: si se indica, se calcula el monto (fraccion_kelly x Kelly, con tope_pct %).
    """
    candidatas = []
    for s in selecciones:
        ev_min = ev_min_pata if s["fuente_prob"] == "mercado" else ev_min_modelo
        if (s["prob_no_perder"] >= prob_min_pata and s["ev_pct"] >= ev_min
                and s["ev_pct"] <= 15.0 and s["cuota"] >= 1.05):  # EV >15% = probable error de cruce
            candidatas.append(s)
    # Mejor pata por partido (no se pueden combinar dos del mismo partido)
    mejor: Dict[Any, Dict[str, Any]] = {}
    for s in sorted(candidatas, key=lambda x: (x["ev_pct"], x["prob_no_perder"]), reverse=True):
        mejor.setdefault(s["evento_id"], s)
    patas = sorted(mejor.values(), key=lambda x: x["ev_pct"] * x["prob_no_perder"], reverse=True)[:22]

    combinadas = []
    for n in range(2, max_patas + 1):
        for combo in itertools.combinations(patas, n):
            r = _resumen_combinada(list(combo))
            if not (cuota_min <= r["cuota_total"] <= cuota_max) or r["prob_ganar"] < prob_min_combinada:
                continue
            if r["ev_pct"] <= 0:
                continue
            combinadas.append((r, combo))
    combinadas.sort(key=lambda x: x[0]["_score"], reverse=True)

    # Diversificar: una misma pata en como maximo 2 combinadas sugeridas
    usos: Dict[Any, int] = {}
    elegidas = []
    for r, combo in combinadas:
        if any(usos.get(p["evento_id"], 0) >= 2 for p in combo):
            continue
        for p in combo:
            usos[p["evento_id"]] = usos.get(p["evento_id"], 0) + 1
        r = dict(r)
        r.pop("_score")
        if bankroll > 0:
            pct = min(tope_pct, r["kelly_completo_pct"] * fraccion_kelly)
            r["monto_sugerido"] = round(bankroll * pct / 100.0, -3)
            r["monto_pct_bankroll"] = round(pct, 2)
        r["patas"] = list(combo)
        elegidas.append(r)
        if len(elegidas) >= max_resultados:
            break

    sencillas = []
    for s in sorted(patas, key=lambda x: x["ev_pct"], reverse=True)[:max_resultados]:
        s = dict(s)
        k = _kelly(s["prob"], s["prob_devolucion"], s["cuota"])
        s["kelly_completo_pct"] = round(k * 100, 2)
        if bankroll > 0:
            pct = min(tope_pct, k * 100 * fraccion_kelly)
            s["monto_sugerido"] = round(bankroll * pct / 100.0, -3)
        sencillas.append(s)

    return {
        "resumen": {
            "selecciones_analizadas": len(selecciones),
            "selecciones_seguras_con_valor": len(patas),
            "combinadas_validas": len(combinadas),
        },
        "combinadas": elegidas,
        "sencillas": sencillas,
    }


def recomendar(bankroll: float = 0.0, refrescar: bool = False, **kw) -> Dict[str, Any]:
    """Punto de entrada: obtiene probabilidades justas + cuotas de Aposta.la y genera la propuesta."""
    from model.forebet_cruce import execute_forebet_aposta_cross, _CACHE
    if refrescar or not _CACHE.get("forebet_matches"):
        execute_forebet_aposta_cross(force_refresh=refrescar)
    from model import forebet_cruce
    fair = forebet_cruce._CACHE.get("forebet_matches") or []
    horas = float(kw.pop("horas_max", 72.0))
    sels = construir_selecciones(fair, horas_max=horas)
    res = generar_combinadas(sels, bankroll=bankroll, **kw)
    res["resumen"]["partidos_con_probabilidad"] = len(fair)
    res["resumen"]["generado"] = time.time()
    res["reglas"] = [
        "Solo selecciones con cuota de Aposta.la >= cuota justa (EV >= 0).",
        "Nunca dos selecciones del mismo partido.",
        "Monto = 1/4 de Kelly con tope del 3 % del bankroll por apuesta.",
        "No hacer cobro anticipado: la casa lo paga por debajo de su valor.",
    ]
    return res
