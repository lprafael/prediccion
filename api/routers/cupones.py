"""
Router REST para el registro de cupones apostados en Aposta.la.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from model.cupones import guardar_cupones, listar_cupones, metricas

router = APIRouter(prefix="/cupones", tags=["Cupones Aposta.la"])


class Seleccion(BaseModel):
    mercado: Optional[str] = None
    seleccion: Optional[str] = None
    partido: Optional[str] = None


class Cupon(BaseModel):
    cupon_id: str
    fecha: Optional[str] = Field(None, description="ISO 8601")
    tipo: Optional[str] = None
    estado: str = Field(..., pattern="^(ganada|perdida|cobro_anticipado|abierta|anulada)$")
    cuota: Optional[float] = None
    monto: float = 0.0
    pago: float = 0.0
    gratuita: bool = False
    selecciones: List[Seleccion] = []


class ImportarCuponesRequest(BaseModel):
    cupones: List[Cupon]


@router.post("/importar", response_model=Dict[str, Any])
async def post_importar(req: ImportarCuponesRequest):
    """Guarda o actualiza cupones (por ID de cupon)."""
    try:
        return await run_in_threadpool(guardar_cupones, [c.model_dump() for c in req.cupones])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando cupones: {e}")


@router.get("", response_model=List[Dict[str, Any]])
async def get_cupones(limite: int = Query(500, ge=1, le=5000)):
    return await run_in_threadpool(listar_cupones, limite)


@router.get("/resumen", response_model=Dict[str, Any])
async def get_resumen(desde: Optional[str] = Query(None, description="Fecha minima YYYY-MM-DD")):
    """ROI, acierto y beneficio por numero de selecciones, tramo de cuota y dia, mas alertas."""
    cupones = await run_in_threadpool(listar_cupones, 5000)
    if desde:
        cupones = [c for c in cupones if (c.get("fecha") or "") >= desde]
    return metricas(cupones)
