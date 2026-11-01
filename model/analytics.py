"""
📊 Módulo de Analítica Avanzada para Baloncesto:
Implementación de Descomposición Pace x Eficiencia, Cuatro Factores de Dean Oliver,
Regresión Bayesiana a la Media y Modelado Analítico Normal.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any
import numpy as np
from scipy import stats

from model.config import (
    TournamentConfig,
    FOUR_FACTORS_WEIGHTS,
    FOUR_FACTORS_BENCHMARKS
)


@dataclass
class TeamProfile:
    """Perfil estadístico avanzado de un equipo."""
    name: str
    pace: float                  # Posesiones por partido (ej: 99.5 en NBA, 74.5 en FIBA)
    off_rating: float            # Puntos anotados por cada 100 posesiones (OffRtg)
    def_rating: float            # Puntos permitidos por cada 100 posesiones (DefRtg)
    efg: Optional[float] = None        # Effective Field Goal % (eFG%)
    tov_pct: Optional[float] = None    # Turnover % (TOV%)
    orb_pct: Optional[float] = None    # Offensive Rebound % (ORB%)
    ft_rate: Optional[float] = None    # Free Throw Rate (FT/FGA)
    is_home: bool = False              # ¿Juega como local?
    is_b2b: bool = False               # ¿Juega en noches consecutivas (Back-to-Back)?
    rest_days: int = 1                 # Días de descanso previo
    usg_lost_pct: float = 0.0          # % de uso ofensivo ausente por lesiones (0.0 a 0.40)


def estimate_pace_from_boxscore(fga: float, fta: float, orb: float, tov: float) -> float:
    """
    Fórmula estándar de Dean Oliver para estimar posesiones a partir del boxscore:
    Pace ≈ 0.5 * (FGA + 0.44 * FTA - ORB + TOV)
    """
    return 0.5 * (fga + 0.44 * fta - orb + tov)


def calculate_matchup_pace(pace_a: float, pace_b: float, league_pace: float) -> float:
    """
    Estima el ritmo (número de posesiones) esperado para el cruce directo:
    Pace_match = (Pace_A * Pace_B) / Pace_Liga
    """
    if league_pace <= 0:
        return (pace_a + pace_b) / 2.0
    return (pace_a * pace_b) / league_pace


def calculate_four_factors_off_rating(
    efg: float,
    tov_pct: float,
    orb_pct: float,
    ft_rate: float,
    tournament_key: str,
    league_off_rating: float
) -> float:
    """
    Calcula el Offensive Rating estimado a partir de los Cuatro Factores de Dean Oliver
    ponderando la contribución relativa de cada uno respecto a los benchmarks de la liga:
    - eFG% (40%)
    - TOV% (25%) (inverso: menos pérdidas es mejor)
    - ORB% (20%)
    - FT Rate (15%)
    """
    benchmarks = FOUR_FACTORS_BENCHMARKS.get(
        tournament_key,
        FOUR_FACTORS_BENCHMARKS.get("FIBA")
    )
    
    # Desviación normalizada ponderada
    rel_efg = ((efg - benchmarks["efg"]) / benchmarks["efg"]) * FOUR_FACTORS_WEIGHTS["efg"]
    rel_tov = (- (tov_pct - benchmarks["tov"]) / benchmarks["tov"]) * FOUR_FACTORS_WEIGHTS["tov"]
    rel_orb = ((orb_pct - benchmarks["orb"]) / benchmarks["orb"]) * FOUR_FACTORS_WEIGHTS["orb"]
    rel_ftr = ((ft_rate - benchmarks["ftr"]) / benchmarks["ftr"]) * FOUR_FACTORS_WEIGHTS["ftr"]
    
    total_rel_shift = rel_efg + rel_tov + rel_orb + rel_ftr
    # Escalar hacia el rating ofensivo
    return league_off_rating * (1.0 + total_rel_shift)


def calculate_cross_efficiency(
    team: TeamProfile,
    opponent: TeamProfile,
    config: TournamentConfig
) -> float:
    """
    Calcula la eficiencia ofensiva esperada (puntos por 100 posesiones) del equipo
    enfrentando a la defensa del oponente:
    
    BaseEff = (OffRtg_Team * DefRtg_Opp) / League_Avg_Rtg
    
    Ajustes aplicados:
    1. Ventaja de Localía: añade aprox. la mitad del diferencial neto si es local (+1.4 a +1.8 pts/100).
    2. Penalización Back-to-Back: resta entre 1.5 y 2.5 pts/100 por fatiga acumulada.
    3. Ajuste por Bajas (USG% ausente): penalización cuadrática moderada por pérdida de creadores de juego.
    """
    league_rtg = config.league_off_rating
    base_eff = (team.off_rating * opponent.def_rating) / league_rtg
    
    # 1. Ventaja de localía
    home_court_delta = (config.home_court_advantage / 2.0)
    if team.is_home:
        base_eff += home_court_delta
    elif opponent.is_home:
        base_eff -= home_court_delta

    # 2. Penalización por Back-to-Back / Fatiga
    if team.is_b2b:
        base_eff -= config.b2b_penalty_per_100

    # 3. Penalización por ausencias clave según % de uso
    if team.usg_lost_pct > 0:
        # Una pérdida de 20% USG impacta ~3.0 pts/100 poss
        absence_penalty = 15.0 * team.usg_lost_pct
        base_eff -= absence_penalty

    return max(40.0, base_eff)


def empirical_bayes_smoothing(
    observed_rate: float,
    prior_rate: float,
    sample_size: float,
    inertia_k: float = 25.0
) -> float:
    """
    Aplica suavizado bayesiano empírico (Empirical Bayes / Regresión a la media)
    para evitar sobreajustar ante rachas estocásticas cortas (especialmente en acierto de 3P):
    
    Posterior = w * Observed + (1 - w) * Prior
    donde w = n / (n + k)
    """
    if sample_size <= 0:
        return prior_rate
    weight = sample_size / (sample_size + inertia_k)
    return weight * observed_rate + (1.0 - weight) * prior_rate


@dataclass
class AnalyticalNormalResult:
    """Resultados de la aproximación Normal N(mu, sigma^2)."""
    mu: float
    sigma: float
    p025: float  # 95% CI inferior
    p05: float   # 90% CI inferior
    p10: float   # 80% CI inferior
    p90: float   # 80% CI superior
    p95: float   # 90% CI superior
    p975: float  # 95% CI superior
    pdf_x: np.ndarray
    pdf_y: np.ndarray

    def prob_over(self, line: float) -> float:
        """Probabilidad analítica de Over: P(X > line)."""
        return float(1.0 - stats.norm.cdf(line, loc=self.mu, scale=self.sigma))

    def prob_under(self, line: float) -> float:
        """Probabilidad analítica de Under: P(X < line)."""
        return float(stats.norm.cdf(line, loc=self.mu, scale=self.sigma))


def calculate_analytical_normal(mu: float, sigma: float) -> AnalyticalNormalResult:
    """
    Genera el modelo analítico gaussiano N(mu, sigma^2) con intervalos del 80%, 90% y 95%.
    """
    p025 = float(mu - 1.95996 * sigma)
    p05  = float(mu - 1.64485 * sigma)
    p10  = float(mu - 1.28155 * sigma)
    p90  = float(mu + 1.28155 * sigma)
    p95  = float(mu + 1.64485 * sigma)
    p975 = float(mu + 1.95996 * sigma)

    # Coordenadas de la campana para graficar
    x_range = np.linspace(max(0.0, mu - 3.5 * sigma), mu + 3.5 * sigma, 120)
    pdf_y = stats.norm.pdf(x_range, loc=mu, scale=sigma)

    return AnalyticalNormalResult(
        mu=mu,
        sigma=sigma,
        p025=p025,
        p05=p05,
        p10=p10,
        p90=p90,
        p95=p95,
        p975=p975,
        pdf_x=x_range,
        pdf_y=pdf_y
    )


def project_pre_game_matchup(
    team_a: TeamProfile,
    team_b: TeamProfile,
    config: TournamentConfig
) -> Dict[str, Any]:
    """
    Pipeline completo de cálculo pre-partido:
    1. Posesiones esperadas: (Pace_A * Pace_B) / Pace_Liga
    2. Eficiencia cruzada A -> B y B -> A
    3. Puntos proyectados por equipo: (Pace_match * Eff / 100)
    4. Puntos Totales Esperados (mu) y Varianza (sigma)
    5. Distribución Normal analítica con intervalos 80% y 95%
    """
    match_pace = calculate_matchup_pace(team_a.pace, team_b.pace, config.league_pace)
    
    eff_a = calculate_cross_efficiency(team_a, team_b, config)
    eff_b = calculate_cross_efficiency(team_b, team_a, config)
    
    pts_expected_a = match_pace * (eff_a / 100.0)
    pts_expected_b = match_pace * (eff_b / 100.0)
    total_expected = pts_expected_a + pts_expected_b
    
    # Desviación estándar calibrada según torneo
    sigma = config.typical_total_std
    normal_model = calculate_analytical_normal(total_expected, sigma)
    
    return {
        "match_pace": match_pace,
        "eff_a": eff_a,
        "eff_b": eff_b,
        "pts_expected_a": pts_expected_a,
        "pts_expected_b": pts_expected_b,
        "total_expected": total_expected,
        "sigma": sigma,
        "normal_model": normal_model
    }
