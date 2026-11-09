"""
Router REST del modo simulacion (paper trading) del motor de combinadas.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from model import simulacion_apuestas as sim

router = APIRouter(prefix="/simulacion-apuestas", tags=["Simulacion de apuestas"])


@router.get("/estado", response_model=Dict[str, Any])
async def get_estado():
    """Saldo simulado, beneficio, ROI y apuestas pendientes."""
    return await run_in_threadpool(sim.estado_saldo)


@router.get("", response_model=List[Dict[str, Any]])
async def get_apuestas(limite: int = Query(100, ge=1, le=1000)):
    return await run_in_threadpool(sim.listar, limite)


@router.post("/liquidar", response_model=Dict[str, Any])
async def post_liquidar():
    """Liquida ya las apuestas cuyos partidos terminaron (resultados de ESPN)."""
    try:
        return await run_in_threadpool(sim.liquidar_pendientes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/registrar", response_model=Dict[str, Any])
async def post_registrar():
    """Registra ya las recomendaciones actuales del motor (no duplica las existentes)."""
    try:
        return await run_in_threadpool(sim.registrar_recomendaciones)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
