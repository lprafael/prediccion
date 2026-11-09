"""
Conector MCP de Poliverso PREDICCION para Claude.

Expone la API FastAPI (local o del VPS) como herramientas que Claude puede usar:
value bets Forebet x Aposta.la, lectura de eventos en vivo, prediccion Monte Carlo
de basquet en vivo y metricas de apuestas.

Variables de entorno:
  POLIVERSO_API_URL   URL base de la API (por defecto http://localhost:8000)
  POLIVERSO_API_KEY   Opcional: se envia como cabecera X-API-Key
"""

import os
from typing import Any, Optional

import httpx
try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP

API_URL = os.getenv("POLIVERSO_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("POLIVERSO_API_KEY")
TIMEOUT = httpx.Timeout(180.0, connect=10.0)

mcp = FastMCP("poliverso-prediccion")


def _headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def _call(method: str, path: str, params: Optional[dict] = None, body: Optional[dict] = None) -> Any:
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_headers()) as c:
            r = c.request(method, f"{API_URL}{path}", params=params, json=body)
        try:
            data = r.json()
        except ValueError:
            data = r.text
        if r.status_code >= 400:
            return {"error": True, "status": r.status_code, "detalle": data}
        return data
    except httpx.HTTPError as e:
        return {"error": True, "detalle": f"No se pudo contactar la API en {API_URL}: {e}"}


@mcp.tool()
def estado_sistema() -> Any:
    """Verifica que la API este en linea y el estado del cache Forebet x Aposta.la."""
    return {
        "api_url": API_URL,
        "health": _call("GET", "/api/health"),
        "forebet_cruce": _call("GET", "/api/forebet-cruce/status"),
    }


@mcp.tool()
def value_bets(
    solo_valor: bool = True,
    min_ev: float = 0.0,
    liga: Optional[str] = None,
    equipo: Optional[str] = None,
    refrescar: bool = False,
    max_items: int = 30,
) -> Any:
    """Cruce Forebet vs cuotas de Aposta.la con EV, edge, cuota justa y Kelly.

    solo_valor: solo picks con EV positivo. min_ev: EV minimo en %.
    liga / equipo: filtros de texto. refrescar: fuerza escaneo nuevo (lento).
    """
    params = {"solo_valor": solo_valor, "min_ev": min_ev, "refresh": refrescar}
    if liga:
        params["liga"] = liga
    if equipo:
        params["q"] = equipo
    data = _call("GET", "/api/forebet-cruce", params=params)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        data["items"] = data["items"][: max(1, max_items)]
    return data


@mcp.tool()
def leer_evento_aposta(url_o_id: str) -> Any:
    """Lee en vivo un evento de Aposta.la (URL o ID numerico): marcador, cuarto,
    reloj, parciales, linea y cuotas over/under. No guarda nada."""
    return _call("POST", "/api/scraper/extraer", body={"url": url_o_id})


@mcp.tool()
def listar_partidos() -> Any:
    """Lista los partidos registrados en la app."""
    return _call("GET", "/api/partidos")


@mcp.tool()
def ver_partido(partido_id: int) -> Any:
    """Detalle de un partido registrado (marcadores por cuarto, tiempo, lineups)."""
    return _call("GET", f"/api/partidos/{partido_id}")


@mcp.tool()
def importar_partido_aposta(url: str) -> Any:
    """Crea un partido en la app a partir de un evento en vivo de Aposta.la."""
    return _call("POST", "/api/partidos/crear-desde-aposta", body={"url": url})


@mcp.tool()
def sincronizar_partido(partido_id: int, url: str) -> Any:
    """Actualiza marcador, cuarto y reloj de un partido desde Aposta.la."""
    return _call("POST", f"/api/partidos/{partido_id}/sync-aposta", body={"url": url})


@mcp.tool()
def prediccion_en_vivo(partido_id: int, n_simulaciones: int = 5000, usar_deep_learning: bool = True) -> Any:
    """Ciclo completo de prediccion en vivo de basquet: Monte Carlo + Deep Learning,
    senales (ritmo, momentum, rachas), EV, grado A+/A/B y Kelly."""
    body = {"n_simulations": n_simulaciones, "use_deep_learning": usar_deep_learning}
    return _call("POST", f"/api/partidos/{partido_id}/simular-live", body=body)


@mcp.tool()
def recomendar_apuesta_basket(
    prob_over: float,
    linea: float,
    cuota_over: float,
    cuota_under: float,
    cuarto: int,
    minutos_jugados_en_cuarto: float,
    duracion_cuarto: int = 10,
    bankroll: float = 1000.0,
    cuota_gana_local: Optional[float] = None,
    cuota_gana_visitante: Optional[float] = None,
    spread_line: Optional[float] = None,
    cuota_spread_local: Optional[float] = None,
    cuota_spread_visitante: Optional[float] = None,
) -> Any:
    """Recomendacion multimercado (total, spread, ganador) con EV y Kelly a partir
    de la probabilidad de Over del modelo y las cuotas actuales."""
    body = {
        "prob_over": prob_over, "linea": linea, "cuota_over": cuota_over,
        "cuota_under": cuota_under, "quarter": cuarto,
        "elapsed_minutes": minutos_jugados_en_cuarto, "quarter_duration": duracion_cuarto,
        "bankroll": bankroll, "cuota_gana_a": cuota_gana_local,
        "cuota_gana_b": cuota_gana_visitante, "spread_line": spread_line,
        "cuota_spread_home": cuota_spread_local, "cuota_spread_away": cuota_spread_visitante,
    }
    return _call("POST", "/api/apuestas/recomendar", body={k: v for k, v in body.items() if v is not None})


@mcp.tool()
def resumen_apuestas() -> Any:
    """Resumen y metricas de rendimiento (ROI, yield, Brier, etc.) de las apuestas registradas."""
    return {
        "resumen": _call("GET", "/api/apuestas/resumen"),
        "metricas": _call("GET", "/api/apuestas/metricas"),
    }



@mcp.tool()
def actualizar_cruce() -> Any:
    """Fuerza en el servidor un nuevo calculo del cruce: baja probabilidades de las fuentes
    oficiales (The Odds API / API-Football) y cuotas actuales de Aposta.la."""
    return _call("POST", "/api/forebet-cruce/escanear")


@mcp.tool()
def combinadas_seguras(
    bankroll: float = 0.0,
    prob_min_pata: float = 0.70,
    max_patas: int = 4,
    cuota_min: float = 1.50,
    cuota_max: float = 4.0,
    horas_max: float = 72.0,
    refrescar: bool = False,
) -> Any:
    """Selecciones de alta probabilidad con valor (+EV) en Aposta.la (1X2, doble oportunidad,
    empate no apuesta, total de goles, ambos marcan) y las mejores combinadas entre partidos
    distintos, con probabilidad real de ganar, EV y monto sugerido (1/4 Kelly, tope 3%)."""
    params = {"bankroll": bankroll, "prob_min_pata": prob_min_pata, "max_patas": max_patas,
              "cuota_min": cuota_min, "cuota_max": cuota_max, "horas_max": horas_max,
              "refrescar": refrescar}
    return _call("GET", "/api/forebet-cruce/combinadas", params=params)


@mcp.tool()
def resumen_cupones_aposta(desde: Optional[str] = None) -> Any:
    """Rendimiento de los cupones reales apostados en Aposta.la (importados del historial):
    ROI y acierto por numero de selecciones, tramo de cuota y dia, cobros anticipados y alertas."""
    return _call("GET", "/api/cupones/resumen", params={"desde": desde} if desde else None)


@mcp.tool()
def importar_cupones_aposta(cupones: list) -> Any:
    """Guarda/actualiza cupones de Aposta.la (lista de objetos con cupon_id, fecha ISO, tipo,
    estado [ganada|perdida|cobro_anticipado|abierta|anulada], cuota, monto, pago, gratuita,
    selecciones [{mercado, seleccion, partido}])."""
    return _call("POST", "/api/cupones/importar", body={"cupones": cupones})


@mcp.tool()
def simulacion_apuestas(detalle: bool = False, limite: int = 20) -> Any:
    """Modo simulacion del motor: saldo simulado (inicia en 500.000 Gs), ROI, ganadas/perdidas
    y, con detalle=True, las ultimas apuestas registradas con sus patas y resultados."""
    out = {"estado": _call("GET", "/api/simulacion-apuestas/estado")}
    if detalle:
        out["apuestas"] = _call("GET", "/api/simulacion-apuestas", params={"limite": limite})
    return out


@mcp.tool()
def apuestas_del_dia(bankroll: float = 500000.0, horas_max: float = 30.0) -> Any:
    """Apuestas recomendadas para las proximas horas con montos para el saldo indicado
    (sencillas y combinadas seguras con valor en Aposta.la)."""
    return _call("GET", "/api/forebet-cruce/combinadas",
                 params={"bankroll": bankroll, "horas_max": horas_max})


if __name__ == "__main__":
    mcp.run()
