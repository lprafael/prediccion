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

