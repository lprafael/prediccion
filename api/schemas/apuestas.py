"""
Pydantic schemas para Apuestas — creación, actualización, recomendaciones y métricas.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RegistrarApuestaRequest(BaseModel):
    partido_id: Optional[int] = None
    tipo_apuesta: str = Field(..., description="'OVER', 'UNDER', 'SPREAD', 'MONEYLINE', 'TEAM_TOTAL'")
    linea: float
    cuota: float = Field(..., gt=1.0)
    monto: float = Field(..., gt=0.0)
    prob_modelo: Optional[float] = Field(None, ge=0.0, le=1.0)
    ev_estimado: Optional[float] = None
    kelly_sugerido: Optional[float] = None
    momento_cuarto: Optional[int] = None
    minuto_partido: Optional[float] = None
    marcador_momento: Optional[str] = None
    es_ficticia: bool = True
    notas: Optional[str] = None
    grado_apuesta: Optional[str] = None
    spread_edge: Optional[float] = None
    equipo_apostado: Optional[str] = None
    linea_cierre_casa: Optional[float] = None
    cuota_cierre_casa: Optional[float] = None


class ActualizarApuestaRequest(BaseModel):
    monto: Optional[float] = Field(None, gt=0.0)
    cuota: Optional[float] = Field(None, gt=1.0)
    linea: Optional[float] = None
    tipo_apuesta: Optional[str] = None
    resultado: Optional[str] = Field(None, description="'PENDIENTE', 'GANADA', 'PERDIDA', 'PUSH'")
    ganancia_neta: Optional[float] = None
    notas: Optional[str] = None


class ActualizarResultadoRequest(BaseModel):
    resultado: str = Field(..., description="'GANADA', 'PERDIDA', 'PUSH'")
    ganancia_neta: Optional[float] = None


class ActualizarCLVRequest(BaseModel):
    linea_cierre_casa: float
    cuota_cierre_casa: float


class ApuestaResponse(BaseModel):
    id: int
    partido_id: int
    tipo_apuesta: str
    linea: float
    cuota: float
    monto: float
    prob_modelo: Optional[float] = None
    ev_estimado: Optional[float] = None
    kelly_sugerido: Optional[float] = None
    momento_cuarto: Optional[int] = None
    minuto_partido: Optional[float] = None
    marcador_momento: Optional[str] = None
    es_ficticia: bool
    resultado: str
    ganancia_neta: Optional[float] = None
    notas: Optional[str] = None
    grado_apuesta: Optional[str] = None
    spread_edge: Optional[float] = None
    equipo_apostado: Optional[str] = None
    linea_cierre_casa: Optional[float] = None
    cuota_cierre_casa: Optional[float] = None
    clv_delta_pts: Optional[float] = None
    clv_beat_ratio: Optional[float] = None
    creado_en: Optional[str] = None
    equipo_local: Optional[str] = None
    equipo_visitante: Optional[str] = None
    torneo: Optional[str] = None


class ResumenApuestasResponse(BaseModel):
    total_apuestas: int
    ganadas: int
    perdidas: int
    pushes: int
    pendientes: int
    total_apostado: float
    retorno_total: float
    beneficio_neto: float
    roi_porcentaje: float
    win_rate: float


class RecomendacionApuestaRequest(BaseModel):
    prob_over: float = Field(..., ge=0.0, le=1.0)
    cuota_over: float = Field(..., gt=1.0)
    cuota_under: float = Field(..., gt=1.0)
    linea: float
    bankroll: float = Field(1000.0, gt=0.0)
    quarter: int = Field(..., ge=1, le=5)
    elapsed_minutes: float = Field(..., ge=0.0)
    quarter_duration: int = Field(10, ge=8, le=15)
    plays: Optional[List[Dict[str, Any]]] = None
    p_win_a: Optional[float] = None
    p_win_b: Optional[float] = None
    cuota_gana_a: Optional[float] = None
    cuota_gana_b: Optional[float] = None
    spread_line: Optional[float] = None
    cuota_spread_home: Optional[float] = None
    cuota_spread_away: Optional[float] = None


class RecomendacionApuestaResponse(BaseModel):
    recommendation: str
    edge: float
    ev: float
    stake_amount: float
    reasons: List[str]
    kelly_f: float
    signals: Optional[Dict[str, Any]] = None
    spread_recommendation: Optional[Dict[str, Any]] = None
    moneyline_recommendation: Optional[Dict[str, Any]] = None
    optimal_stopping_action: Optional[str] = None
    overreaction_detected: bool = False
    xai_factors: Optional[Dict[str, float]] = None
    bet_grade: Optional[str] = None
    suggested_paper_bet: Optional[Dict[str, Any]] = None
