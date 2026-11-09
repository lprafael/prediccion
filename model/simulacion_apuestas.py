"""
Modo simulacion ("paper trading") del motor de combinadas.

Cada dia el motor registra las apuestas que recomendaria (sencillas y combinadas)
con el monto que corresponde al saldo simulado; cuando los partidos terminan se
liquidan con el resultado real (ESPN, gratis y sin clave) y se actualiza el saldo.
Asi se mide si el motor gana de verdad antes de arriesgar dinero.

Variables de entorno:
  SIM_BANKROLL          Saldo inicial simulado (por defecto 500000).
  SIM_HORAS             Ventana de partidos a registrar (por defecto 30 h).
  SIM_MAX_COMBINADAS    Combinadas a registrar por dia (por defecto 3).
  SIM_MAX_SENCILLAS     Sencillas a registrar por dia (por defecto 3).
"""

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from model.database import get_connection
from model.forebet_cruce import same_team

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
_FINAL = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN", "STATUS_FINAL_AGT"}
_ANULADO = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_ABANDONED", "STATUS_SUSPENDED", "STATUS_FORFEIT"}

_DDL = """
CREATE TABLE IF NOT EXISTS simulacion_apuestas (
    id          SERIAL PRIMARY KEY,
    clave       TEXT UNIQUE,              -- evita registrar dos veces la misma apuesta
    creado      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tipo        TEXT,                     -- sencilla | combinada
    patas       JSONB,
    cuota       FLOAT,
    prob        FLOAT,
    ev_pct      FLOAT,
    monto       FLOAT,
    estado      TEXT DEFAULT 'pendiente', -- pendiente | ganada | perdida | devuelta
    pago        FLOAT DEFAULT 0,
    primer_inicio TIMESTAMP,
    ultimo_inicio TIMESTAMP,
    resuelto    TIMESTAMP
);
"""


def _bankroll_inicial() -> float:
    return float(os.getenv("SIM_BANKROLL", "500000"))


def _q(sql: str, params: Tuple = (), fetch: bool = True) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()] if fetch else []
    finally:
        conn.close()


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ─── Saldo ────────────────────────────────────────────────────────────────────

def estado_saldo() -> Dict[str, Any]:
    filas = _q("SELECT estado, monto, pago FROM simulacion_apuestas")
    inicial = _bankroll_inicial()
    resueltas = [f for f in filas if f["estado"] != "pendiente"]
    pendientes = [f for f in filas if f["estado"] == "pendiente"]
    beneficio = sum((f["pago"] or 0) - (f["monto"] or 0) for f in resueltas)
    en_juego = sum(f["monto"] or 0 for f in pendientes)
    apostado = sum(f["monto"] or 0 for f in resueltas)
    return {
        "saldo_inicial": inicial,
        "saldo_actual": round(inicial + beneficio),
        "disponible": round(inicial + beneficio - en_juego),
        "en_juego": round(en_juego),
        "beneficio": round(beneficio),
        "roi_pct": round(100 * beneficio / apostado, 2) if apostado else None,
        "apuestas_resueltas": len(resueltas),
        "ganadas": sum(f["estado"] == "ganada" for f in resueltas),
        "perdidas": sum(f["estado"] == "perdida" for f in resueltas),
        "devueltas": sum(f["estado"] == "devuelta" for f in resueltas),
        "pendientes": len(pendientes),
    }


# ─── Registro diario ──────────────────────────────────────────────────────────

def _pata_min(p: Dict[str, Any]) -> Dict[str, Any]:
    return {k: p.get(k) for k in ("evento_id", "partido", "liga", "inicio", "mercado", "codigo",
                                  "seleccion", "cuota", "prob", "prob_devolucion", "cuota_justa",
                                  "ev_pct", "fuente_prob", "ref_home", "ref_away")}


def registrar_recomendaciones(propuesta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Registra las mejores sencillas y combinadas del motor con montos segun el saldo simulado."""
    from model.combinadas import recomendar
    saldo = estado_saldo()
    bank = max(0.0, float(saldo["saldo_actual"]))
    if propuesta is None:
        propuesta = recomendar(bankroll=bank, horas_max=float(os.getenv("SIM_HORAS", "30")))
    max_c = int(os.getenv("SIM_MAX_COMBINADAS", "3"))
    max_s = int(os.getenv("SIM_MAX_SENCILLAS", "3"))
    disponible = float(saldo["disponible"])
    tope_dia = 0.15 * bank  # nunca mas del 15 % del saldo en juego por dia
    usado = 0.0
    registradas = []

    candidatos = [("combinada", c["patas"], c) for c in propuesta.get("combinadas", [])[:max_c]]
    candidatos += [("sencilla", [s], s) for s in propuesta.get("sencillas", [])[:max_s]]
    for tipo, patas, info in candidatos:
        monto = float(info.get("monto_sugerido") or 0)
        monto = math.floor(monto / 1000.0) * 1000.0  # Aposta.la: montos redondos
        if monto < 1000 or monto > disponible - usado or usado + monto > tope_dia:
            continue
        clave = "|".join(sorted(f"{p['evento_id']}:{p['codigo']}" for p in patas))
        inicios = [d for d in (_parse_dt(p.get("inicio")) for p in patas) if d]
        cuota = math.prod(p["cuota"] for p in patas)
        prob = info.get("prob_ganar") or info.get("prob_no_perder")
        filas = _q("""
            INSERT INTO simulacion_apuestas (clave, tipo, patas, cuota, prob, ev_pct, monto, primer_inicio, ultimo_inicio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (clave) DO NOTHING RETURNING id
        """, (clave, tipo, json.dumps([_pata_min(p) for p in patas], ensure_ascii=False), round(cuota, 3),
              prob, info.get("ev_pct"), monto, min(inicios) if inicios else None,
              max(inicios) if inicios else None))
        if filas:
            usado += monto
            registradas.append({"id": filas[0]["id"], "tipo": tipo, "cuota": round(cuota, 2), "monto": monto,
                                "prob": prob, "ev_pct": info.get("ev_pct"),
                                "patas": [f"{p['partido']}: {p['seleccion']} @{p['cuota']}" for p in patas]})
    return {"registradas": registradas, "saldo": estado_saldo()}


# ─── Liquidacion con resultados reales ────────────────────────────────────────

_CACHE_ESPN: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def _resultados_espn(fecha: datetime) -> List[Dict[str, Any]]:
    clave = fecha.strftime("%Y%m%d")
    hit = _CACHE_ESPN.get(clave)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    try:
        r = requests.get(ESPN_URL, params={"dates": clave, "limit": 1000}, timeout=20)
        eventos = r.json().get("events", []) if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        eventos = []
    out = []
    for e in eventos:
        comp = (e.get("competitions") or [{}])[0]
        estado = comp.get("status", {}).get("type", {}).get("name")
        eq = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in eq or "away" not in eq:
            continue

        def goles90(c: Dict[str, Any]) -> Optional[int]:
            # En prorroga/penales las apuestas se liquidan a los 90 minutos
            if estado in ("STATUS_FINAL_AET", "STATUS_FINAL_PEN"):
                ls = c.get("linescores") or []
                if len(ls) >= 2:
                    return int(float(ls[0].get("value", 0)) + float(ls[1].get("value", 0)))
                return None
            try:
                return int(c.get("score"))
            except (TypeError, ValueError):
                return None

        out.append({"home": eq["home"]["team"].get("displayName", ""), "away": eq["away"]["team"].get("displayName", ""),
                    "inicio": e.get("date"), "estado": estado,
                    "gh": goles90(eq["home"]), "ga": goles90(eq["away"])})
    _CACHE_ESPN[clave] = (time.time(), out)
    return out


def buscar_resultado(partido: str, inicio: Optional[str], ref: Optional[Tuple[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Resultado ESPN del partido. Prueba primero con los nombres de referencia
    (ingles, The Odds API) y luego con los de Aposta.la."""
    nombres = []
    if ref and ref[0] and ref[1]:
        nombres.append(ref)
    if " vs " in partido:
        nombres.append(tuple(partido.split(" vs ", 1)))
    dt = _parse_dt(inicio)
    if not dt or not nombres:
        return None
    dias = {dt.date(), (dt + timedelta(hours=6)).date(), (dt - timedelta(hours=6)).date()}
    candidatos = []
    for dia in dias:
        for r in _resultados_espn(datetime(dia.year, dia.month, dia.day)):
            rdt = _parse_dt(r["inicio"])
            if rdt and abs((rdt - dt).total_seconds()) <= 6 * 3600:
                candidatos.append(r)
    for home, away in nombres:
        for r in candidatos:
            if same_team(home, r["home"]) and same_team(away, r["away"]):
                return r
    return None


def resultado_pata(codigo: str, gh: int, ga: int) -> str:
    """'gana' | 'pierde' | 'devuelve' para una seleccion dada el marcador a 90'."""
    mercado, sel = codigo.split(":")
    res = "1" if gh > ga else "2" if ga > gh else "X"
    if mercado == "1X2":
        return "gana" if sel == res else "pierde"
    if mercado == "DC":
        return "gana" if res in sel else "pierde"
    if mercado == "DNB":
        return "devuelve" if res == "X" else ("gana" if res == sel else "pierde")
    if mercado.startswith("OU"):
        linea = float(mercado.split()[1])
        tot = gh + ga
        if tot == linea:
            return "devuelve"
        return "gana" if (tot > linea) == (sel == "over") else "pierde"
    if mercado == "BTTS":
        ambos = gh > 0 and ga > 0
        return "gana" if ambos == (sel == "si") else "pierde"
    raise ValueError(f"Mercado no soportado: {codigo}")


def liquidar_pendientes() -> Dict[str, Any]:
    """Liquida las apuestas cuyos partidos ya terminaron."""
    ahora = datetime.now(timezone.utc)
    pendientes = _q("SELECT * FROM simulacion_apuestas WHERE estado = 'pendiente'")
    liquidadas = []
    for ap in pendientes:
        ult = ap.get("ultimo_inicio")
        if ult and (ult.replace(tzinfo=timezone.utc) if ult.tzinfo is None else ult) > ahora - timedelta(hours=2, minutes=15):
            continue  # algun partido aun no termino
        patas = ap["patas"] if isinstance(ap["patas"], list) else json.loads(ap["patas"])
        resultados, falta = [], False
        for p in patas:
            r = buscar_resultado(p["partido"], p.get("inicio"), (p.get("ref_home"), p.get("ref_away")))
            vieja = ult and (ahora - (ult.replace(tzinfo=timezone.utc) if ult.tzinfo is None else ult)) > timedelta(days=4)
            if r and r["estado"] in _ANULADO:
                resultados.append("devuelve")
            elif r and r["estado"] in _FINAL and r["gh"] is not None and r["ga"] is not None:
                p["marcador"] = f"{r['gh']}-{r['ga']}"
                resultados.append(resultado_pata(p["codigo"], r["gh"], r["ga"]))
            elif vieja:
                resultados.append("devuelve")  # sin resultado tras 4 dias: se anula la pata
                p["marcador"] = "sin resultado"
            else:
                falta = True
                break
        if falta:
            continue
        for p, r in zip(patas, resultados):
            p["resultado"] = r
        if "pierde" in resultados:
            estado, pago = "perdida", 0.0
        else:
            mult = math.prod(p["cuota"] if r == "gana" else 1.0 for p, r in zip(patas, resultados))
            pago = round(ap["monto"] * mult)
            estado = "devuelta" if all(r == "devuelve" for r in resultados) else "ganada"
        _q("""UPDATE simulacion_apuestas SET estado=%s, pago=%s, patas=%s, resuelto=CURRENT_TIMESTAMP
              WHERE id=%s""", (estado, pago, json.dumps(patas, ensure_ascii=False), ap["id"]), fetch=False)
        liquidadas.append({"id": ap["id"], "estado": estado, "monto": ap["monto"], "pago": pago})
    return {"liquidadas": liquidadas, "saldo": estado_saldo()}


def listar(limite: int = 100) -> List[Dict[str, Any]]:
    filas = _q("SELECT * FROM simulacion_apuestas ORDER BY creado DESC LIMIT %s", (limite,))
    for f in filas:
        for k in ("creado", "primer_inicio", "ultimo_inicio", "resuelto"):
            if f.get(k):
                f[k] = f[k].isoformat()
    return filas


def ciclo_diario() -> Dict[str, Any]:
    """Liquida lo terminado y registra las recomendaciones del dia."""
    liq = liquidar_pendientes()
    reg = registrar_recomendaciones()
    return {"liquidadas": liq["liquidadas"], "registradas": reg["registradas"], "saldo": reg["saldo"]}


_DDL_EJEC = """
CREATE TABLE IF NOT EXISTS simulacion_ejecuciones (
    fecha     DATE PRIMARY KEY,
    creado    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resultado JSONB
);
"""


def tick() -> Dict[str, Any]:
    """Llamado cada hora por la API: liquida lo terminado y, una vez al dia a partir de
    SIM_HORA (hora de Paraguay, por defecto 9), registra las recomendaciones del dia."""
    if os.getenv("SIM_ACTIVA", "1") != "1":
        return {"activa": False}
    out: Dict[str, Any] = {"liquidadas": liquidar_pendientes()["liquidadas"]}
    local = datetime.now(timezone(timedelta(hours=-3)))
    if local.hour < int(os.getenv("SIM_HORA", "9")):
        return out
    hecho = _q(_DDL_EJEC + "SELECT 1 FROM simulacion_ejecuciones WHERE fecha = %s", (local.date(),))
    if hecho:
        return out
    reg = registrar_recomendaciones()
    _q(_DDL_EJEC + "INSERT INTO simulacion_ejecuciones (fecha, resultado) VALUES (%s, %s) ON CONFLICT DO NOTHING",
       (local.date(), json.dumps(reg["registradas"], ensure_ascii=False)), fetch=False)
    out["registradas"] = reg["registradas"]
    return out
