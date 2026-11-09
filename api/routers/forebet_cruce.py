"""
Router REST para el Cruce Forebet vs Aposta.la y Detección de Value Bets (+EV).
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool


from model.forebet_cruce import execute_forebet_aposta_cross, _CACHE

router = APIRouter(prefix="/forebet-cruce", tags=["Value Bets Forebet"])


@router.get("", response_model=Dict[str, Any])
async def get_cruce_analisis(
    refresh: bool = Query(False, description="Forzar nuevo escaneo en tiempo real"),
    solo_valor: bool = Query(False, description="Filtrar únicamente apuestas con EV positivo"),
    min_ev: float = Query(0.0, description="Mínimo EV % requerido"),
    liga: Optional[str] = Query(None, description="Filtrar por nombre o etiqueta de liga"),
    q: Optional[str] = Query(None, description="Búsqueda por nombre de equipo")
):
    """
    Retorna el cruce de partidos entre Forebet y Aposta.la con el cálculo de
    valor esperado (+EV), cuotas justas, ventaja estadística y Criterio de Kelly.
    """
    try:
        data = await run_in_threadpool(execute_forebet_aposta_cross, refresh)
        items = data.get("items", [])

        # Aplicar filtros
        if solo_valor:
            items = [item for item in items if item.get("has_value")]

        if min_ev > 0.0:
            items = [
                item for item in items
                if item.get("best_pick") and (item["best_pick"].get("ev_pct") or 0.0) >= min_ev
            ]

        if liga:
            liga_clean = liga.lower().strip()
            items = [
                item for item in items
                if liga_clean in (item.get("forebet", {}).get("tournament", "").lower())
                or liga_clean in (item.get("aposta", {}).get("league", "").lower())
            ]

        if q:
            query_clean = q.lower().strip()
            items = [
                item for item in items
                if query_clean in item.get("forebet", {}).get("home", "").lower()
                or query_clean in item.get("forebet", {}).get("away", "").lower()
                or query_clean in item.get("aposta", {}).get("home", "").lower()
                or query_clean in item.get("aposta", {}).get("away", "").lower()
            ]

        return {
            "cached": data.get("cached", False),
            "last_updated": data.get("last_updated"),
            "summary": data.get("summary", {}),
            "total_items": len(items),
            "items": items
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el cruce Forebet vs Aposta.la: {str(e)}"
        )


@router.post("/escanear", response_model=Dict[str, Any])
async def post_forzar_escaneo():
    """Fuerza un escaneo en vivo completo en Forebet y Aposta.la."""
    try:
        data = await run_in_threadpool(execute_forebet_aposta_cross, True)
        return {
            "message": "Escaneo completado exitosamente",
            "last_updated": data.get("last_updated"),
            "summary": data.get("summary", {}),
            "total_matched": len(data.get("items", []))
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante el escaneo en vivo: {str(e)}"
        )


class ImportarForebetRequest(BaseModel):
    matches: List[Dict[str, Any]]


@router.post("/importar", response_model=Dict[str, Any])
async def post_importar_predicciones(req: ImportarForebetRequest):
    """Importa predicciones de Forebet (ej. desde cliente residencial) y ejecuta el cruce contra cuotas de Aposta.la."""
    try:
        from model.forebet_cruce import importar_forebet_matches_manual
        data = await run_in_threadpool(importar_forebet_matches_manual, req.matches)
        return {
            "message": f"{len(req.matches)} predicciones de Forebet importadas y cruzadas con éxito",
            "last_updated": data.get("last_updated"),
            "summary": data.get("summary", {}),
            "total_matched": len(data.get("items", []))
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al importar predicciones: {str(e)}"
        )


@router.get("/status", response_model=Dict[str, Any])
async def get_cruce_status():
    """Retorna el estado de la caché, métricas del último análisis y de las fuentes oficiales."""
    # Se lee el módulo (no el nombre importado) porque _CACHE se reasigna en cada cruce.
    from model import forebet_cruce as fc
    from model.fuentes_oficiales import estado_fuentes
    cache = fc._CACHE
    return {
        "cache_has_data": bool(cache.get("recommendations")),
        "last_updated": cache.get("timestamp"),
        "summary": cache.get("summary", {}),
        "total_recommendations": len(cache.get("recommendations", [])),
        "fuentes": estado_fuentes(),
    }



@router.get("/combinadas", response_model=Dict[str, Any])
async def get_combinadas(
    bankroll: float = Query(0.0, ge=0, description="Bankroll para calcular montos (1/4 Kelly, tope 3%)"),
    prob_min_pata: float = Query(0.70, ge=0.5, le=0.99, description="Probabilidad minima de no perder cada pata"),
    max_patas: int = Query(4, ge=2, le=6),
    cuota_min: float = Query(1.50, ge=1.01),
    cuota_max: float = Query(4.0, ge=1.1),
    horas_max: float = Query(72.0, ge=1, le=24 * 14, description="Solo partidos que empiezan en las proximas N horas"),
    refrescar: bool = Query(False, description="Forzar nueva descarga de probabilidades (gasta creditos de The Odds API)"),
):
    """Selecciones seguras con valor (+EV) en Aposta.la y las mejores combinadas entre ellas."""
    from model.combinadas import recomendar
    try:
        return await run_in_threadpool(
            lambda: recomendar(bankroll=bankroll, refrescar=refrescar, prob_min_pata=prob_min_pata,
                               max_patas=max_patas, cuota_min=cuota_min, cuota_max=cuota_max,
                               horas_max=horas_max))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando combinadas: {e}")
