"""
Router para Snapshots e Hitos de Predicción.
"""

from typing import List, Optional, Any
from types import SimpleNamespace
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from model.database import (
    guardar_snapshot,
    registrar_hito,
    listar_hitos,
    listar_snapshots,
)

router = APIRouter()


class SnapshotCreateRequest(BaseModel):
    cuarto_snapshot: int = Field(..., ge=1, le=5)
    minutos_jugados: float = Field(..., ge=0.0)
    pts_local_actual: int = Field(..., ge=0)
    pts_visitante_actual: int = Field(..., ge=0)
    # Valores de la simulación
    total_mean: float
    total_median: float
    total_p05: float
    total_p95: float
    total_std: float
    team_a_mean: float
    team_b_mean: float
    win_prob_a: float
    overtime_prob: float
    observed_pace_per_min: float
    prior_pace_per_min: float
    linea_apuesta: Optional[float] = None
    prob_over: Optional[float] = None
    prob_under: Optional[float] = None
    num_simulaciones: int = 5000
    match_pace_expected: float = 0.0
    eff_a_expected: float = 0.0
    eff_b_expected: float = 0.0
    total_p10: float = 0.0
    total_p90: float = 0.0
    total_p025: float = 0.0
    total_p975: float = 0.0
    cuota_over: Optional[float] = None
    cuota_under: Optional[float] = None


class HitoCreateRequest(SnapshotCreateRequest):
    nombre_hito: str = Field(..., min_length=1, max_length=100)


@router.get("/partidos/{partido_id}/snapshots")
async def get_snapshots(partido_id: int):
    """Lista todos los snapshots registrados para un partido en orden cronológico."""
    try:
        return listar_snapshots(partido_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar snapshots: {str(e)}"
        )


@router.post("/partidos/{partido_id}/snapshots", status_code=status.HTTP_201_CREATED)
async def post_snapshot(partido_id: int, req: SnapshotCreateRequest):
    """Guarda un nuevo snapshot del estado del modelo durante el partido."""
    try:
        summary_adapter = SimpleNamespace(
            total_mean=req.total_mean,
            total_median=req.total_median,
            total_p05=req.total_p05,
            total_p95=req.total_p95,
            total_std=req.total_std,
            team_a_mean=req.team_a_mean,
            team_b_mean=req.team_b_mean,
            win_prob_a=req.win_prob_a,
            overtime_prob=req.overtime_prob,
            observed_pace_per_min=req.observed_pace_per_min,
            prior_pace_per_min=req.prior_pace_per_min,
            match_pace_expected=req.match_pace_expected,
            eff_a_expected=req.eff_a_expected,
            eff_b_expected=req.eff_b_expected,
            total_p10=req.total_p10,
            total_p90=req.total_p90,
            total_p025=req.total_p025,
            total_p975=req.total_p975,
        )

        snap_id = guardar_snapshot(
            partido_id=partido_id,
            cuarto_snapshot=req.cuarto_snapshot,
            minutos_jugados=req.minutos_jugados,
            pts_local_actual=req.pts_local_actual,
            pts_visitante_actual=req.pts_visitante_actual,
            summary=summary_adapter,
            linea_apuesta=req.linea_apuesta,
            prob_over=req.prob_over,
            prob_under=req.prob_under,
            num_simulaciones=req.num_simulaciones,
            cuota_over=req.cuota_over,
            cuota_under=req.cuota_under,
        )
        return {"id": snap_id, "message": "Snapshot guardado exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar snapshot: {str(e)}"
        )


@router.get("/partidos/{partido_id}/hitos")
async def get_hitos_partido(partido_id: int, limit: int = Query(100, ge=1, le=500)):
    """Lista los hitos de predicción para un partido."""
    try:
        return listar_hitos(partido_id=partido_id, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar hitos: {str(e)}"
        )


@router.get("/hitos")
async def get_todos_hitos(limit: int = Query(100, ge=1, le=500)):
    """Lista los hitos más recientes en toda la base de datos."""
    try:
        return listar_hitos(partido_id=None, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar hitos globales: {str(e)}"
        )


@router.post("/partidos/{partido_id}/hitos", status_code=status.HTTP_201_CREATED)
async def post_hito(partido_id: int, req: HitoCreateRequest):
    """Registra un hito formal de predicción (Checkpoint pre-game, HT, etc.) para auditoría."""
    try:
        summary_adapter = SimpleNamespace(
            total_mean=req.total_mean,
            total_median=req.total_median,
            total_p05=req.total_p05,
            total_p95=req.total_p95,
            total_std=req.total_std,
            team_a_mean=req.team_a_mean,
            team_b_mean=req.team_b_mean,
            win_prob_a=req.win_prob_a,
            overtime_prob=req.overtime_prob,
            observed_pace_per_min=req.observed_pace_per_min,
            prior_pace_per_min=req.prior_pace_per_min,
            match_pace_expected=req.match_pace_expected,
            eff_a_expected=req.eff_a_expected,
            eff_b_expected=req.eff_b_expected,
            total_p10=req.total_p10,
            total_p90=req.total_p90,
            total_p025=req.total_p025,
            total_p975=req.total_p975,
        )

        hito_id = registrar_hito(
            partido_id=partido_id,
            nombre_hito=req.nombre_hito,
            cuarto_snapshot=req.cuarto_snapshot,
            minutos_jugados=req.minutos_jugados,
            pts_local_actual=req.pts_local_actual,
            pts_visitante_actual=req.pts_visitante_actual,
            summary=summary_adapter,
            linea_apuesta=req.linea_apuesta,
            prob_over=req.prob_over,
            prob_under=req.prob_under,
            cuota_over=req.cuota_over,
            cuota_under=req.cuota_under,
            num_simulaciones=req.num_simulaciones
        )
        return {"id": hito_id, "message": f"Hito '{req.nombre_hito}' registrado exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar hito: {str(e)}"
        )
