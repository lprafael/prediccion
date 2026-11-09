"""
Registro de cupones (boletos) apostados en Aposta.la y métricas de rendimiento.

Los cupones se importan desde el historial de "Mis Apuestas" de Aposta.la
(extraido del navegador con sesion iniciada) y se guardan por su ID de cupon,
asi que reimportar el mismo historial solo actualiza estados (abierta -> ganada...).
"""

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from model.database import get_connection

_DDL = """
CREATE TABLE IF NOT EXISTS cupones_aposta (
    cupon_id      TEXT PRIMARY KEY,
    fecha         TIMESTAMP,
    tipo          TEXT,
    estado        TEXT,            -- ganada | perdida | cobro_anticipado | abierta | anulada
    cuota         FLOAT,
    monto         FLOAT,
    pago          FLOAT,
    gratuita      BOOLEAN DEFAULT FALSE,
    n_selecciones INT,
    selecciones   JSONB,
    origen        TEXT DEFAULT 'historial_aposta',
    actualizado   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def guardar_cupones(cupones: List[Dict[str, Any]]) -> Dict[str, int]:
    nuevos = actualizados = 0
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                for c in cupones:
                    if not c.get("cupon_id"):
                        continue
                    sels = c.get("selecciones") or []
                    cur.execute("""
                        INSERT INTO cupones_aposta (cupon_id, fecha, tipo, estado, cuota, monto, pago,
                                                    gratuita, n_selecciones, selecciones, actualizado)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (cupon_id) DO UPDATE SET
                            estado = EXCLUDED.estado, cuota = COALESCE(EXCLUDED.cuota, cupones_aposta.cuota),
                            pago = EXCLUDED.pago, selecciones = EXCLUDED.selecciones,
                            n_selecciones = EXCLUDED.n_selecciones, actualizado = CURRENT_TIMESTAMP
                        RETURNING (xmax = 0) AS insertado;
                    """, (
                        str(c["cupon_id"]), c.get("fecha"), c.get("tipo"), c.get("estado"),
                        c.get("cuota"), c.get("monto") or 0.0, c.get("pago") or 0.0,
                        bool(c.get("gratuita")), len(sels) or c.get("n_selecciones") or 1,
                        json.dumps(sels, ensure_ascii=False),
                    ))
                    if cur.fetchone()["insertado"]:
                        nuevos += 1
                    else:
                        actualizados += 1
    finally:
        conn.close()
    return {"nuevos": nuevos, "actualizados": actualizados}


def listar_cupones(limite: int = 500) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                cur.execute("SELECT * FROM cupones_aposta ORDER BY fecha DESC NULLS LAST LIMIT %s", (limite,))
                rows = cur.fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["fecha"] = d["fecha"].isoformat() if d.get("fecha") else None
        d["actualizado"] = d["actualizado"].isoformat() if d.get("actualizado") else None
        out.append(d)
    return out


def _tramo_cuota(c: Optional[float]) -> str:
    if not c:
        return "sin dato"
    for lim, nombre in ((1.30, "< 1.30"), (1.60, "1.30-1.59"), (2.50, "1.60-2.49"), (10.0, "2.50-9.99")):
        if c < lim:
            return nombre
    return ">= 10"


def _tramo_patas(n: int) -> str:
    return "1 (sencilla)" if n <= 1 else "2-3" if n <= 3 else "4-8" if n <= 8 else "9+"


def metricas(cupones: List[Dict[str, Any]]) -> Dict[str, Any]:
    cerrados = [c for c in cupones if c.get("estado") in ("ganada", "perdida", "cobro_anticipado")]

    def agrupar(clave) -> Dict[str, Dict[str, Any]]:
        g: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"n": 0, "ganadas": 0, "apostado": 0.0, "retorno": 0.0})
        for c in cerrados:
            k = clave(c)
            g[k]["n"] += 1
            g[k]["ganadas"] += c["estado"] == "ganada"
            g[k]["apostado"] += 0.0 if c.get("gratuita") else (c.get("monto") or 0.0)
            g[k]["retorno"] += c.get("pago") or 0.0
        for v in g.values():
            v["beneficio"] = round(v["retorno"] - v["apostado"])
            v["roi_pct"] = round(100 * v["beneficio"] / v["apostado"], 1) if v["apostado"] else None
            v["acierto_pct"] = round(100 * v["ganadas"] / v["n"], 1) if v["n"] else None
        return dict(sorted(g.items()))

    total = agrupar(lambda c: "total").get("total", {})
    cobros = [c for c in cerrados if c["estado"] == "cobro_anticipado"]
    montos = sorted((c.get("monto") or 0.0) for c in cerrados if not c.get("gratuita"))
    por_dia = agrupar(lambda c: (c.get("fecha") or "")[:10])
    alertas = []
    if cobros:
        ap = sum(c.get("monto") or 0 for c in cobros)
        rec = sum(c.get("pago") or 0 for c in cobros)
        alertas.append(f"Cobros anticipados: {len(cobros)} cupones, apostado {ap:,.0f}, recuperado {rec:,.0f}.")
    largas = [c for c in cerrados if (c.get("n_selecciones") or 1) >= 6]
    if largas:
        alertas.append(f"Combinadas de 6+ selecciones: {sum(c['estado'] == 'ganada' for c in largas)} ganadas de {len(largas)}.")
    if montos:
        mediana = montos[len(montos) // 2]
        grandes = [m for m in montos if m >= 5 * mediana]
        if grandes:
            alertas.append(f"{len(grandes)} apuestas de 5x o mas el monto habitual ({mediana:,.0f}).")
    dias_cargados = [d for d, v in por_dia.items() if v["n"] >= 8]
    if dias_cargados:
        alertas.append(f"Dias con 8+ apuestas (posible persecucion de perdidas): {', '.join(dias_cargados)}.")

    return {
        "total": total,
        "abiertas": sum(c.get("estado") == "abierta" for c in cupones),
        "por_selecciones": agrupar(lambda c: _tramo_patas(c.get("n_selecciones") or 1)),
        "por_cuota": agrupar(lambda c: _tramo_cuota(c.get("cuota"))),
        "por_dia": por_dia,
        "cobros_anticipados": {
            "n": len(cobros),
            "apostado": sum(c.get("monto") or 0 for c in cobros),
            "recuperado": sum(c.get("pago") or 0 for c in cobros),
        },
        "alertas": alertas,
    }
