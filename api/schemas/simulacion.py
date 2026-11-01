"""
Pydantic schemas para Simulación Monte Carlo — validación de entrada/salida.
"""

from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field


class TeamProfileRequest(BaseModel):
    """Perfil estadístico avanzado de un equipo (opcional para simulaciones analíticas)."""
    name: str = "Equipo"
    pace: float = Field(99.5, ge=40.0, le=140.0)
    off_rating: float = Field(114.0, ge=60.0, le=160.0)
    def_rating: float = Field(114.0, ge=60.0, le=160.0)
    efg: Optional[float] = None
    tov_pct: Optional[float] = None
    orb_pct: Optional[float] = None
    ft_rate: Optional[float] = None
    is_home: bool = False
    is_b2b: bool = False
    rest_days: int = 1
    usg_lost_pct: float = 0.0


class PlayRequest(BaseModel):
    """Jugada individual del play-by-play."""
    team: str = ""
    who: str = ""          # "HOME" o "AWAY"
    pts: int = 0
    info: str = ""
    score_home: int = 0
    score_away: int = 0


class ShootingContextRequest(BaseModel):
    """Contexto de tiro para regresión de triples a la media."""
    att_3p: float = 0.0
    made_3p: float = 0.0


class SimularRequest(BaseModel):
    """Request completo para correr la simulación Monte Carlo en vivo."""
    torneo_key: str = Field("NBA", description="Clave del torneo: NBA, FIBA, NBL, NCAA_FEMENIL")
    current_quarter: int = Field(..., ge=1, le=10)
    elapsed_seconds_in_quarter: float = Field(..., ge=0.0)
    quarters_data: List[Tuple[float, float]] = Field(
        ...,
        description="Puntos por cuarto [(A1,B1),(A2,B2),(A3,B3),(A4,B4)]"
    )
    n_simulations: int = Field(5000, ge=500, le=50000)
    random_seed: Optional[int] = Field(None, description="Semilla para reproducibilidad de la simulación")
    actual_total_scores: Optional[Tuple[float, float]] = None
    shooting_context: Optional[ShootingContextRequest] = None
    plays: Optional[List[PlayRequest]] = None
    use_deep_learning: bool = True
    linea_apuesta: Optional[float] = None
    spread_line: Optional[float] = None
    house_odds_over: Optional[float] = None
    house_odds_under: Optional[float] = None
    house_odds_spread_home: Optional[float] = None
    house_odds_spread_away: Optional[float] = None
    house_odds_ml_home: Optional[float] = None
    house_odds_ml_away: Optional[float] = None
    lineup_local: Optional[List[int]] = None
    lineup_visitante: Optional[List[int]] = None
    fouls_local: int = 0
    fouls_visitante: int = 0
    team_a_profile: Optional[TeamProfileRequest] = None
    team_b_profile: Optional[TeamProfileRequest] = None
    inertia_minutes: float = Field(12.0, ge=1.0, le=60.0)

    model_config = {"json_schema_extra": {
        "example": {
            "torneo_key": "NBA",
            "current_quarter": 3,
            "elapsed_seconds_in_quarter": 360.0,
            "quarters_data": [[28, 25], [30, 27], [14, 12], [0, 0]],
            "n_simulations": 5000,
            "actual_total_scores": [72, 64],
            "linea_apuesta": 220.5,
            "spread_line": -4.5
        }
    }}


class SimulationResultResponse(BaseModel):
    """Resultado completo de la simulación, serializable a JSON."""
    # Estadísticas Equipo A
    team_a_mean: float
    team_a_median: float
    team_a_min: float
    team_a_max: float
    team_a_p05: float
    team_a_p10: float
    team_a_p90: float
    team_a_p95: float

    # Estadísticas Equipo B
    team_b_mean: float
    team_b_median: float
    team_b_min: float
    team_b_max: float
    team_b_p05: float
    team_b_p10: float
    team_b_p90: float
    team_b_p95: float

    # Total
    total_mean: float
    total_median: float
    total_std: float
    total_min: float
    total_max: float
    total_p025: float
    total_p05: float
    total_p10: float
    total_p25: float
    total_p75: float
    total_p90: float
    total_p95: float
    total_p975: float

    # Probabilidades
    win_prob_a: float
    win_prob_b: float
    overtime_prob: float

    # Ritmo
    prior_pace_per_min: float
    observed_pace_per_min: float
    posterior_pace_per_min: float
    shrinkage_weight: float

    # Descomposición analítica
    pre_game_total: float
    match_pace_expected: float
    eff_a_expected: float
    eff_b_expected: float

    # Métricas de regulación
    regulation_mean: float
    overtime_points_avg: float
    overtime_count: int

    # Regresión de tiro
    shooting_regression_applied: float
    three_point_luck_delta: float

    # Deep Learning Residual & Transformer Attention
    dl_active: bool
    dl_delta_pace: float
    dl_pace_multiplier: float
    dl_uncertainty_pts: float
    dl_win_prob: Optional[float]
    dl_momentum_label: str
    dl_details: str
    dl_spread_margin: Optional[float] = None
    dl_spread_std: Optional[float] = None
    dl_xai_factors: Dict[str, float] = Field(default_factory=dict)

    # Multimercados: Totales, Spread, Moneyline
    spread_mean: float = 0.0
    spread_std: float = 0.0
    prob_over: Optional[float] = None
    prob_under: Optional[float] = None
    prob_spread_home: Optional[float] = None
    prob_spread_away: Optional[float] = None
    prob_ml_home: Optional[float] = None
    prob_ml_away: Optional[float] = None
    optimal_stopping_action: Optional[str] = None
    overreaction_detected: bool = False

    # Timeline (lista de puntos para el gráfico)
    timeline: Optional[List[Dict[str, Any]]] = None

    # Distribución (histograma de totales simulados)
    histogram_totals: Optional[List[float]] = None


class BaselineResponse(BaseModel):
    tournament_key: str
    tournament_name: str
    quarter_duration: int
    timeline: List[Dict[str, Any]]

