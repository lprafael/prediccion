"""
Motor de Cálculo Probabilístico, Actualización Bayesiana y Simulación Monte Carlo
para Proyección de Partidos de Baloncesto.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats

from model.config import (
    TournamentConfig,
    TOURNAMENT_PRESETS,
    QUARTER_PACE_FACTORS,
    OVERTIME_MINUTES,
    OVERTIME_PACE_FACTOR,
    OVERTIME_FATIGUE_FACTOR,
    CLUTCH_THRESHOLD_MINUTES,
    CLUTCH_FOUL_DIFF_THRESHOLD,
    CLUTCH_MODERATE_DIFF_THRESHOLD,
    CLUTCH_SURGE_FOUL_MULT,
    CLUTCH_SURGE_MODERATE_MULT,
    CLUTCH_CLOCK_KILL_MULT,
    CLUTCH_POINT_DIFF_CLOSE,
    CLUTCH_SURGE_MULTIPLIER,
    BLOWOUT_DIFF_THRESHOLD,
    GARBAGE_TIME_Q4_THRESHOLD,
    BLOWOUT_DECAY_MULTIPLIER,
    Q4_FAST_PACE_THRESHOLD,
    Q4_ADAPTIVE_EVAL_MINUTES,
    THREE_POINT_REGRESSION_MIN_SHOTS,
    THREE_POINT_LUCK_SHRINKAGE
)
from model.analytics import (
    TeamProfile,
    project_pre_game_matchup,
    calculate_analytical_normal,
    AnalyticalNormalResult
)


@dataclass
class QuarterInput:
    quarter_num: int
    team_a_pts: float
    team_b_pts: float
    status: str  # "completed", "in_progress", "pending"


@dataclass
class SimulationSummary:
    # Métricas esperadas finales
    team_a_mean: float
    team_a_median: float
    team_a_min: float
    team_a_max: float
    team_a_p05: float
    team_a_p10: float
    team_a_p90: float
    team_a_p95: float

    team_b_mean: float
    team_b_median: float
    team_b_min: float
    team_b_max: float
    team_b_p05: float
    team_b_p10: float
    team_b_p90: float
    team_b_p95: float

    # Total de puntos
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

    # Ritmos calculados
    prior_pace_per_min: float
    observed_pace_per_min: float
    posterior_pace_per_min: float
    shrinkage_weight: float

    # Arrays para análisis visual
    simulated_totals: np.ndarray
    simulated_team_a: np.ndarray
    simulated_team_b: np.ndarray
    timeline_df: pd.DataFrame

    # Métricas de la descomposición Pace x Eficiencia
    pre_game_total: float = 0.0
    match_pace_expected: float = 0.0
    eff_a_expected: float = 0.0
    eff_b_expected: float = 0.0
    analytical_normal: Optional[AnalyticalNormalResult] = None

    # Métricas de Regulación y Prórroga (Overtime)
    regulation_mean: float = 0.0
    overtime_points_avg: float = 0.0
    overtime_count: int = 0

    # Métricas de Regresión de Tiro a la Media
    shooting_regression_applied: float = 0.0
    three_point_luck_delta: float = 0.0

    # Métricas de Deep Learning Residual (Momentum & Fine Adjustment)
    dl_active: bool = False
    dl_delta_pace: float = 0.0
    dl_pace_multiplier: float = 1.0
    dl_uncertainty_pts: float = 0.0
    dl_win_prob: Optional[float] = None
    dl_momentum_label: str = "INACTIVO"
    dl_details: str = ""

    # Nuevas métricas multimercado y Transformer XAI
    simulated_margins: Optional[np.ndarray] = None
    spread_mean: float = 0.0
    spread_std: float = 0.0
    dl_spread_margin: Optional[float] = None
    dl_spread_std: Optional[float] = None
    dl_xai_factors: Dict[str, float] = field(default_factory=dict)


class BasketballPredictor:
    """
    Motor matemático probabilístico para baloncesto.
    Implementa:
    1. Descomposición analítica de Ritmo (Pace) x Eficiencia Ofensiva Cruzada
    2. Calibración por torneo (NBA, FIBA, NCAA Femenil, etc.)
    3. Curvas de ritmo dinámicas por cuarto (Q1-Q4) y degradación de fatiga B2B
    4. Efecto 'Clutch' en los últimos 2 minutos de partidos cerrados (<= 8 pts)
    5. Efecto 'Garbage Time' en 4Q con ventajas > 20 pts (suplentes y pérdidas)
    6. Actualización Bayesiana en tiempo real con suavizado empírico
    7. Simulación Monte Carlo de alto rendimiento (10,000 caminos estocásticos)
    """

    def __init__(
        self,
        tournament_config: TournamentConfig,
        team_a_profile: Optional[TeamProfile] = None,
        team_b_profile: Optional[TeamProfile] = None,
        inertia_minutes: float = 12.0,
        team_a: Optional[TeamProfile] = None,
        team_b: Optional[TeamProfile] = None,
    ):
        self.config = tournament_config
        self.quarter_duration = tournament_config.quarter_duration
        self.total_game_minutes = tournament_config.quarter_duration * 4
        self.inertia_minutes = inertia_minutes  # Ponderación del prior bayesiano

        # Configuración de perfiles de equipos (admite alias team_a / team_b)
        resolved_team_a = team_a_profile or team_a
        resolved_team_b = team_b_profile or team_b

        self.team_a = resolved_team_a or TeamProfile(
            name="Equipo Local",
            pace=tournament_config.league_pace,
            off_rating=tournament_config.league_off_rating,
            def_rating=tournament_config.league_off_rating,
            is_home=True
        )
        self.team_b = resolved_team_b or TeamProfile(
            name="Equipo Visitante",
            pace=tournament_config.league_pace,
            off_rating=tournament_config.league_off_rating,
            def_rating=tournament_config.league_off_rating,
            is_home=False
        )

        # Proyección analítica pre-partido
        self.pre_game = project_pre_game_matchup(self.team_a, self.team_b, tournament_config)
        self.team_baseline_per_q = (self.pre_game["total_expected"] / 2.0) / 4.0
        self.total_baseline_per_q = self.pre_game["total_expected"] / 4.0


    def get_baseline_trajectory(self) -> pd.DataFrame:
        """
        Calcula la curva de trayectoria promedio minuto a minuto para el torneo actual,
        ponderando los factores dinámicos de ritmo por cuarto.
        """
        minutes = np.arange(0, self.total_game_minutes + 1)
        nominal_rate_per_min = self.total_baseline_per_q / self.quarter_duration

        cumulative_scores = [0.0]
        current_score = 0.0

        for m in range(1, self.total_game_minutes + 1):
            q = min(4, int((m - 1) // self.quarter_duration) + 1)
            pace_factor = QUARTER_PACE_FACTORS.get(q, 1.0)
            
            # Si es el último minuto del 4Q sin contexto de marcador, promediamos el clutch
            if q == 4 and (self.total_game_minutes - m) < CLUTCH_THRESHOLD_MINUTES:
                pace_factor = (QUARTER_PACE_FACTORS[4] + CLUTCH_SURGE_MULTIPLIER) / 2.0
            
            # Normalización para que la suma cuadre exactamente con el total del torneo
            current_score += nominal_rate_per_min * pace_factor
            cumulative_scores.append(current_score)

        # Ajuste de escala final para coincidir exactamente con el total esperado del torneo
        final_nominal = self.config.total_game_avg
        scale_ratio = final_nominal / cumulative_scores[-1] if cumulative_scores[-1] > 0 else 1.0
        adjusted_scores = [s * scale_ratio for s in cumulative_scores]

        df = pd.DataFrame({
            "minute": minutes,
            "quarter": [min(4, int(m // self.quarter_duration) + 1) if m < self.total_game_minutes else 4 for m in minutes],
            "baseline_total": adjusted_scores,
            "baseline_team": [s / 2.0 for s in adjusted_scores]
        })
        return df

    @staticmethod
    def get_all_tournaments_baseline_trajectories() -> pd.DataFrame:
        """
        Retorna la trayectoria promedio general para todos los torneos predefinidos
        para graficarlos conjuntamente.
        """
        records = []
        for key, t_cfg in TOURNAMENT_PRESETS.items():
            pred = BasketballPredictor(t_cfg)
            traj = pred.get_baseline_trajectory()
            traj["tournament_name"] = t_cfg.name
            traj["tournament_key"] = key
            traj["quarter_duration"] = t_cfg.quarter_duration
            records.append(traj)
        return pd.concat(records, ignore_index=True)

    def run_live_simulation(
        self,
        current_quarter: int,
        elapsed_seconds_in_quarter: float,
        quarters_data: List[Tuple[float, float]],  # Puntos por cuarto [(A1, B1), (A2, B2), (A3, B3), (A4, B4)]
        n_simulations: int = 5000,
        random_seed: Optional[int] = 42,
        actual_total_scores: Optional[Tuple[float, float]] = None,
        shooting_context: Optional[dict] = None,
        plays: Optional[List[dict]] = None,
        use_deep_learning: bool = True,
        lineup_a: Optional[List[int]] = None,
        lineup_b: Optional[List[int]] = None,
        fouls_a: int = 0,
        fouls_b: int = 0
    ) -> SimulationSummary:
        """
        Ejecuta la simulación probabilística Monte Carlo y actualización Bayesiana
        a partir del estado real del partido.
        """
        if random_seed is not None:
            np.random.seed(random_seed)

        q_dur = self.quarter_duration
        total_game_min = self.total_game_minutes

        # 1. Calcular minutos transcurridos totales exactos
        if current_quarter > 4:  # Partido finalizado
            t_elapsed = float(total_game_min)
            t_rem = 0.0
        else:
            q_prev_min = (current_quarter - 1) * q_dur
            q_curr_min = min(float(q_dur), max(0.0, elapsed_seconds_in_quarter / 60.0))
            t_elapsed = q_prev_min + q_curr_min
            t_rem = max(0.0, float(total_game_min) - t_elapsed)

        # 2. Puntos acumulados reales hasta el momento
        if actual_total_scores is not None:
            score_a_so_far = float(actual_total_scores[0])
            score_b_so_far = float(actual_total_scores[1])
        else:
            score_a_so_far = sum(q[0] for q in quarters_data[:current_quarter])
            score_b_so_far = sum(q[1] for q in quarters_data[:current_quarter])
        total_so_far = score_a_so_far + score_b_so_far

        # 3. Ritmo base (Prior de Pace x Eficiencia) y Ritmo Observado
        prior_team_rate_a = self.pre_game["pts_expected_a"] / total_game_min
        prior_team_rate_b = self.pre_game["pts_expected_b"] / total_game_min
        prior_total_rate = prior_team_rate_a + prior_team_rate_b

        if t_elapsed > 0.1:
            obs_rate_a = score_a_so_far / t_elapsed
            obs_rate_b = score_b_so_far / t_elapsed
            obs_rate_total = total_so_far / t_elapsed
            # Ponderador Bayesiano (shrinkage empírico hacia el ritmo observado)
            w = t_elapsed / (t_elapsed + self.inertia_minutes)
        else:
            obs_rate_a = prior_team_rate_a
            obs_rate_b = prior_team_rate_b
            obs_rate_total = prior_total_rate
            w = 0.0

        # 3.1 Regresión de Triples a la Media (Normalización de Rachas Calientes/Frías)
        luck_delta_pts = 0.0
        shooting_reg_applied = 0.0
        adj_obs_rate_a = obs_rate_a
        adj_obs_rate_b = obs_rate_b

        if shooting_context and t_elapsed > 1.0:
            league_3p_pct = getattr(self.config, "league_3pt_pct", 0.350)
            att_3p = float(shooting_context.get("att_3p", shooting_context.get("three_att", 0)))
            made_3p = float(shooting_context.get("made_3p", shooting_context.get("three_made", 0)))

            if att_3p >= THREE_POINT_REGRESSION_MIN_SHOTS:
                exp_made_3p = att_3p * league_3p_pct
                surplus_3p = made_3p - exp_made_3p
                luck_delta_pts = round(surplus_3p * 3.0, 1)
                luck_rate = luck_delta_pts / t_elapsed
                luck_shrinkage_rate = luck_rate * THREE_POINT_LUCK_SHRINKAGE

                ratio_a = (obs_rate_a / obs_rate_total) if obs_rate_total > 0 else 0.5
                ratio_b = 1.0 - ratio_a
                adj_obs_rate_a = max(0.2, obs_rate_a - luck_shrinkage_rate * ratio_a)
                adj_obs_rate_b = max(0.2, obs_rate_b - luck_shrinkage_rate * ratio_b)
                shooting_reg_applied = round(luck_shrinkage_rate * t_rem, 1)

        # Ritmos posteriores (Bayesian Posterior Pace con regresión de tiro)
        post_rate_a = w * adj_obs_rate_a + (1.0 - w) * prior_team_rate_a
        post_rate_b = w * adj_obs_rate_b + (1.0 - w) * prior_team_rate_b
        post_rate_total = post_rate_a + post_rate_b

        # 3.1b Ritmo Adaptativo Empírico en el 4° Cuarto (evita subestimar finales abiertos/rápidos)
        q4_is_fast = False
        q4_obs_rate = 0.0
        if current_quarter == 4 and elapsed_seconds_in_quarter >= (Q4_ADAPTIVE_EVAL_MINUTES * 60.0):
            pts_q1_to_q3_a = sum(q[0] for q in quarters_data[:3])
            pts_q1_to_q3_b = sum(q[1] for q in quarters_data[:3])
            q4_pts_a = max(0.0, score_a_so_far - pts_q1_to_q3_a)
            q4_pts_b = max(0.0, score_b_so_far - pts_q1_to_q3_b)
            q4_pts_total = q4_pts_a + q4_pts_b
            q4_min = max(0.1, elapsed_seconds_in_quarter / 60.0)
            q4_obs_rate = q4_pts_total / q4_min

            # Si el ritmo del 4Q supera el umbral rápido o no muestra signos de frenado respecto al partido:
            if q4_obs_rate >= Q4_FAST_PACE_THRESHOLD or q4_obs_rate >= (obs_rate_total * 0.90):
                q4_is_fast = True
                # Ponderar el ritmo demostrado en el 4Q hacia los minutos restantes
                q4_weight = min(0.60, q4_min / float(q_dur))
                rate_q4_a = q4_pts_a / q4_min
                rate_q4_b = q4_pts_b / q4_min
                post_rate_a = (1.0 - q4_weight) * post_rate_a + q4_weight * max(0.2, rate_q4_a)
                post_rate_b = (1.0 - q4_weight) * post_rate_b + q4_weight * max(0.2, rate_q4_b)
                post_rate_total = post_rate_a + post_rate_b

        # 3.2 Modulación Fina por Deep Learning Residual (Momentum de Jugadas y Lineups)
        dl_active = False
        dl_delta_p = 0.0
        dl_mult = 1.0
        dl_unc_pts = 0.0
        dl_win_p = None
        dl_label = "NEUTRO"
        dl_details = ""
        dl_spread_margin = None
        dl_spread_std = None
        dl_xai_factors = {}

        if use_deep_learning:
            try:
                from model.deep_learning import inferir_ajuste_momentum
                dl_res = inferir_ajuste_momentum(
                    plays=plays or [],
                    team_a=self.team_a.name,
                    team_b=self.team_b.name,
                    minutos_jugados=t_elapsed,
                    pts_local=score_a_so_far,
                    pts_visitante=score_b_so_far,
                    cuarto=current_quarter,
                    total_game_min=total_game_min,
                    ritmo_base=prior_total_rate,
                    ritmo_obs=obs_rate_total,
                    lineup_local=lineup_a,
                    lineup_visitante=lineup_b,
                    fouls_local=fouls_a,
                    fouls_visitante=fouls_b
                )
                if dl_res.get("activo"):
                    dl_active = True
                    dl_delta_p = float(dl_res.get("delta_pace", 0.0))
                    dl_mult = float(dl_res.get("multiplicador_ritmo", 1.0))
                    dl_unc_pts = float(dl_res.get("incertidumbre_pts", 0.0))
                    dl_win_p = dl_res.get("prob_victoria_dl")
                    dl_label = str(dl_res.get("etiqueta_momentum", "NEUTRO"))
                    dl_details = str(dl_res.get("detalle", ""))
                    dl_spread_margin = dl_res.get("spread_proyectado_dl")
                    dl_spread_std = dl_res.get("spread_std_dl")
                    dl_xai_factors = dl_res.get("xai_factores", {})

                    # Modular el ritmo posterior con el multiplicador de la red neuronal
                    post_rate_a = max(0.2, post_rate_a * dl_mult)
                    post_rate_b = max(0.2, post_rate_b * dl_mult)
                    post_rate_total = post_rate_a + post_rate_b
            except Exception:
                pass

        # Si el partido ya finalizó, no simulamos tiempo futuro
        if t_rem <= 0.001:
            final_a = np.full(n_simulations, score_a_so_far)
            final_b = np.full(n_simulations, score_b_so_far)
            final_tot = np.full(n_simulations, total_so_far)

            timeline_df = pd.DataFrame({
                "minute": [0.0, total_game_min],
                "actual_total": [0.0, total_so_far],
                "proj_mean": [0.0, total_so_far],
                "proj_p025": [0.0, total_so_far],
                "proj_p05": [0.0, total_so_far],
                "proj_p10": [0.0, total_so_far],
                "proj_p25": [0.0, total_so_far],
                "proj_p75": [0.0, total_so_far],
                "proj_p90": [0.0, total_so_far],
                "proj_p95": [0.0, total_so_far],
                "proj_p975": [0.0, total_so_far],
                "baseline_total": [0.0, self.pre_game["total_expected"]]
            })

            normal_res = calculate_analytical_normal(float(total_so_far), 0.001)

            return SimulationSummary(
                team_a_mean=score_a_so_far,
                team_a_median=score_a_so_far,
                team_a_min=score_a_so_far,
                team_a_max=score_a_so_far,
                team_a_p05=score_a_so_far,
                team_a_p10=score_a_so_far,
                team_a_p90=score_a_so_far,
                team_a_p95=score_a_so_far,
                team_b_mean=score_b_so_far,
                team_b_median=score_b_so_far,
                team_b_min=score_b_so_far,
                team_b_max=score_b_so_far,
                team_b_p05=score_b_so_far,
                team_b_p10=score_b_so_far,
                team_b_p90=score_b_so_far,
                team_b_p95=score_b_so_far,
                total_mean=total_so_far,
                total_median=total_so_far,
                total_std=0.0,
                total_min=total_so_far,
                total_max=total_so_far,
                total_p025=total_so_far,
                total_p05=total_so_far,
                total_p10=total_so_far,
                total_p25=total_so_far,
                total_p75=total_so_far,
                total_p90=total_so_far,
                total_p95=total_so_far,
                total_p975=total_so_far,
                win_prob_a=1.0 if score_a_so_far > score_b_so_far else (0.5 if score_a_so_far == score_b_so_far else 0.0),
                win_prob_b=1.0 if score_b_so_far > score_a_so_far else (0.5 if score_b_so_far == score_a_so_far else 0.0),
                overtime_prob=1.0 if score_a_so_far == score_b_so_far else 0.0,
                prior_pace_per_min=prior_total_rate,
                observed_pace_per_min=obs_rate_total,
                posterior_pace_per_min=post_rate_total,
                shrinkage_weight=w,
                simulated_totals=final_tot,
                simulated_team_a=final_a,
                simulated_team_b=final_b,
                timeline_df=timeline_df,
                pre_game_total=float(self.pre_game["total_expected"]),
                match_pace_expected=float(self.pre_game["match_pace"]),
                eff_a_expected=float(self.pre_game["eff_a"]),
                eff_b_expected=float(self.pre_game["eff_b"]),
                analytical_normal=normal_res,
                regulation_mean=float(total_so_far),
                overtime_points_avg=0.0,
                overtime_count=0,
                shooting_regression_applied=0.0,
                three_point_luck_delta=0.0,
                dl_active=dl_active,
                dl_delta_pace=dl_delta_p,
                dl_pace_multiplier=dl_mult,
                dl_uncertainty_pts=dl_unc_pts,
                dl_win_prob=dl_win_p,
                dl_momentum_label=dl_label,
                dl_details=dl_details,
                simulated_margins=final_a - final_b,
                spread_mean=float(score_a_so_far - score_b_so_far),
                spread_std=0.0,
                dl_spread_margin=dl_spread_margin,
                dl_spread_std=dl_spread_std,
                dl_xai_factors=dl_xai_factors
            )

        # 4. Simulación Monte Carlo paso a paso (minuto a minuto)
        dt = 1.0
        rem_steps = int(np.ceil(t_rem))
        time_points = [t_elapsed]
        sim_scores_a = np.full((n_simulations, rem_steps + 1), score_a_so_far, dtype=np.float64)
        sim_scores_b = np.full((n_simulations, rem_steps + 1), score_b_so_far, dtype=np.float64)

        current_t = t_elapsed
        for step in range(rem_steps):
            step_dt = min(dt, total_game_min - current_t)
            if step_dt <= 0:
                break

            current_t += step_dt
            time_points.append(current_t)

            sim_q = min(4, int(current_t // q_dur) + 1)
            base_q_factor = QUARTER_PACE_FACTORS.get(sim_q, 1.0)

            # Efecto de Fatiga por Back-to-Back acumulada en 3Q y 4Q
            fatigue_a = (0.98 if sim_q == 3 else (0.96 if sim_q == 4 else 1.0)) if self.team_a.is_b2b else 1.0
            fatigue_b = (0.98 if sim_q == 3 else (0.96 if sim_q == 4 else 1.0)) if self.team_b.is_b2b else 1.0

            pace_mult_a = np.full(n_simulations, base_q_factor * fatigue_a)
            pace_mult_b = np.full(n_simulations, base_q_factor * fatigue_b)

            time_to_end = total_game_min - current_t
            score_diff = np.abs(sim_scores_a[:, step] - sim_scores_b[:, step])

            # Parámetro de sobre-dispersión (por defecto 0.80)
            p_param = np.full(n_simulations, 0.80)

            if sim_q == 4:
                # Partidos decididos (Garbage Time / Blowout): diferencia > umbral al 4Q
                # Si el 4Q ha demostrado empíricamente ritmo alto (q4_is_fast), NO aplicamos freno artificial
                is_garbage = (score_diff > GARBAGE_TIME_Q4_THRESHOLD) & (not q4_is_fast)
                pace_mult_a[is_garbage] *= BLOWOUT_DECAY_MULTIPLIER
                pace_mult_b[is_garbage] *= BLOWOUT_DECAY_MULTIPLIER
                # Mayor dispersión y pérdidas imprevistas con suplentes
                p_param[is_garbage] = 0.74

                # Finales cerrados (Clutch) en los últimos minutos del 4Q:
                if time_to_end <= CLUTCH_THRESHOLD_MINUTES:
                    # 1. Carrusel de faltas intencionales (diferencia <= 5 pts):
                    # El equipo rezagado corta el reloj inmediatamente con faltas personales (4-7 seg por posesión)
                    # y constantes tiros libres con reloj detenido.
                    is_foul_clutch = score_diff <= CLUTCH_FOUL_DIFF_THRESHOLD
                    pace_mult_a[is_foul_clutch] = base_q_factor * fatigue_a * CLUTCH_SURGE_FOUL_MULT
                    pace_mult_b[is_foul_clutch] = base_q_factor * fatigue_b * CLUTCH_SURGE_FOUL_MULT

                    # 2. Ritmo acelerado / posesiones urgentes (diferencia 6 a 9 pts):
                    is_moderate_clutch = (score_diff > CLUTCH_FOUL_DIFF_THRESHOLD) & (score_diff <= CLUTCH_MODERATE_DIFF_THRESHOLD)
                    pace_mult_a[is_moderate_clutch] = base_q_factor * fatigue_a * CLUTCH_SURGE_MODERATE_MULT
                    pace_mult_b[is_moderate_clutch] = base_q_factor * fatigue_b * CLUTCH_SURGE_MODERATE_MULT

                    # 3. Drenado de posesión / Rendición (diferencia >= 10 pts en el último minuto):
                    if time_to_end <= 1.0:
                        is_clock_kill = score_diff >= 10
                        pace_mult_a[is_clock_kill] = base_q_factor * fatigue_a * CLUTCH_CLOCK_KILL_MULT
                        pace_mult_b[is_clock_kill] = base_q_factor * fatigue_b * CLUTCH_CLOCK_KILL_MULT

            # Medias de anotación esperadas en este paso
            mu_a = post_rate_a * pace_mult_a * step_dt
            mu_b = post_rate_b * pace_mult_b * step_dt

            # Muestreo con distribución Binomial Negativa (modela sobre-dispersión por canastas de 1, 2 o 3 pts)
            r_a = np.maximum(0.1, mu_a * (p_param / (1.0 - p_param)))
            r_b = np.maximum(0.1, mu_b * (p_param / (1.0 - p_param)))

            pts_a = np.random.negative_binomial(r_a, p_param)
            pts_b = np.random.negative_binomial(r_b, p_param)

            sim_scores_a[:, step + 1] = sim_scores_a[:, step] + pts_a
            sim_scores_b[:, step + 1] = sim_scores_b[:, step] + pts_b

        # Resultados de tiempo reglamentario (40 o 48 min)
        reg_final_a = sim_scores_a[:, -1].copy()
        reg_final_b = sim_scores_b[:, -1].copy()
        reg_totals = reg_final_a + reg_final_b
        regulation_mean = float(np.mean(reg_totals))

        # Detectar empates al término de la regulación
        tied_mask = (reg_final_a == reg_final_b)
        ot_prob = float(np.mean(tied_mask))
        ot_count = int(np.sum(tied_mask))

        final_a = reg_final_a.copy()
        final_b = reg_final_b.copy()

        # SIMULACIÓN DE PRÓRROGA (OVERTIME):
        # En las casas de apuestas (Kambi / Aposta.la), el Total de Puntos INCLUYE prórroga.
        # Si una simulación termina empatada en regulación, simulamos 5 minutos de tiempo extra.
        ot_pts_added = []
        if ot_count > 0:
            ot_mins = OVERTIME_MINUTES
            ot_rate_a = post_rate_a * OVERTIME_PACE_FACTOR * OVERTIME_FATIGUE_FACTOR
            ot_rate_b = post_rate_b * OVERTIME_PACE_FACTOR * OVERTIME_FATIGUE_FACTOR

            # Simular 1er OT (5 minutos)
            mu_ot_a = ot_rate_a * ot_mins
            mu_ot_b = ot_rate_b * ot_mins
            p_ot = 0.80

            r_ot_a = np.maximum(0.1, mu_ot_a * (p_ot / (1.0 - p_ot)))
            r_ot_b = np.maximum(0.1, mu_ot_b * (p_ot / (1.0 - p_ot)))

            pts_ot_a = np.random.negative_binomial(r_ot_a, p_ot, size=ot_count)
            pts_ot_b = np.random.negative_binomial(r_ot_b, p_ot, size=ot_count)

            # Si tras OT1 aún persisten empates, simular 2do OT
            still_tied = (pts_ot_a == pts_ot_b)
            if np.any(still_tied):
                n_tied2 = int(np.sum(still_tied))
                pts_ot2_a = np.random.negative_binomial(r_ot_a, p_ot, size=n_tied2)
                pts_ot2_b = np.random.negative_binomial(r_ot_b, p_ot, size=n_tied2)
                miracle_tie = (pts_ot2_a == pts_ot2_b)
                if np.any(miracle_tie):
                    decider = np.random.choice([1, 2], size=int(np.sum(miracle_tie)))
                    pts_ot2_a[miracle_tie] += (decider == 1).astype(int)
                    pts_ot2_b[miracle_tie] += (decider == 2).astype(int)
                pts_ot_a[still_tied] += pts_ot2_a
                pts_ot_b[still_tied] += pts_ot2_b

            final_a[tied_mask] += pts_ot_a
            final_b[tied_mask] += pts_ot_b
            ot_pts_added = pts_ot_a + pts_ot_b

        final_totals = final_a + final_b
        avg_ot_pts = float(np.mean(ot_pts_added)) if len(ot_pts_added) > 0 else 0.0

        # Probabilidades finales de victoria (el baloncesto define ganador en OT)
        win_a = float(np.mean(final_a > final_b))
        win_b = float(np.mean(final_b > final_a))

        # 5. Construcción de la línea de tiempo histórica y proyectada
        timeline_rows = []
        baseline_df = self.get_baseline_trajectory()
        base_scores_map = dict(zip(baseline_df["minute"], baseline_df["baseline_total"]))

        # Pasos pasados
        history_minutes = np.linspace(0, t_elapsed, num=max(2, int(t_elapsed) + 1))
        for m in history_minutes:
            fraction = m / t_elapsed if t_elapsed > 0 else 0.0
            actual_score = fraction * total_so_far
            baseline_val = base_scores_map.get(int(round(m)), (m / total_game_min) * self.pre_game["total_expected"])
            
            timeline_rows.append({
                "minute": round(m, 1),
                "actual_total": round(actual_score, 1),
                "proj_mean": round(actual_score, 1),
                "proj_p025": round(actual_score, 1),
                "proj_p05": round(actual_score, 1),
                "proj_p10": round(actual_score, 1),
                "proj_p25": round(actual_score, 1),
                "proj_p75": round(actual_score, 1),
                "proj_p90": round(actual_score, 1),
                "proj_p95": round(actual_score, 1),
                "proj_p975": round(actual_score, 1),
                "baseline_total": round(baseline_val, 1)
            })

        # Pasos futuros proyectados
        for s_idx, t_sim in enumerate(time_points):
            if s_idx == 0:
                continue
            sim_tot_step = sim_scores_a[:, s_idx] + sim_scores_b[:, s_idx]
            baseline_val = base_scores_map.get(int(round(t_sim)), (t_sim / total_game_min) * self.pre_game["total_expected"])
            
            timeline_rows.append({
                "minute": round(t_sim, 1),
                "actual_total": None,
                "proj_mean": float(np.mean(sim_tot_step)),
                "proj_p025": float(np.percentile(sim_tot_step, 2.5)),
                "proj_p05": float(np.percentile(sim_tot_step, 5)),
                "proj_p10": float(np.percentile(sim_tot_step, 10)),
                "proj_p25": float(np.percentile(sim_tot_step, 25)),
                "proj_p75": float(np.percentile(sim_tot_step, 75)),
                "proj_p90": float(np.percentile(sim_tot_step, 90)),
                "proj_p95": float(np.percentile(sim_tot_step, 95)),
                "proj_p975": float(np.percentile(sim_tot_step, 97.5)),
                "baseline_total": round(baseline_val, 1)
            })

        timeline_df = pd.DataFrame(timeline_rows).drop_duplicates(subset=["minute"])

        # Cálculo analítico Normal N(mu, sigma)
        tot_std = float(np.std(final_totals))
        normal_res = calculate_analytical_normal(float(np.mean(final_totals)), max(0.1, tot_std))

        return SimulationSummary(
            team_a_mean=float(np.mean(final_a)),
            team_a_median=float(np.median(final_a)),
            team_a_min=float(np.min(final_a)),
            team_a_max=float(np.max(final_a)),
            team_a_p05=float(np.percentile(final_a, 5)),
            team_a_p10=float(np.percentile(final_a, 10)),
            team_a_p90=float(np.percentile(final_a, 90)),
            team_a_p95=float(np.percentile(final_a, 95)),

            team_b_mean=float(np.mean(final_b)),
            team_b_median=float(np.median(final_b)),
            team_b_min=float(np.min(final_b)),
            team_b_max=float(np.max(final_b)),
            team_b_p05=float(np.percentile(final_b, 5)),
            team_b_p10=float(np.percentile(final_b, 10)),
            team_b_p90=float(np.percentile(final_b, 90)),
            team_b_p95=float(np.percentile(final_b, 95)),

            total_mean=float(np.mean(final_totals)),
            total_median=float(np.median(final_totals)),
            total_std=tot_std,
            total_min=float(np.min(final_totals)),
            total_max=float(np.max(final_totals)),
            total_p025=float(np.percentile(final_totals, 2.5)),
            total_p05=float(np.percentile(final_totals, 5)),
            total_p10=float(np.percentile(final_totals, 10)),
            total_p25=float(np.percentile(final_totals, 25)),
            total_p75=float(np.percentile(final_totals, 75)),
            total_p90=float(np.percentile(final_totals, 90)),
            total_p95=float(np.percentile(final_totals, 95)),
            total_p975=float(np.percentile(final_totals, 97.5)),

            win_prob_a=win_a,
            win_prob_b=win_b,
            overtime_prob=ot_prob,

            prior_pace_per_min=prior_total_rate,
            observed_pace_per_min=obs_rate_total,
            posterior_pace_per_min=post_rate_total,
            shrinkage_weight=w,

            simulated_totals=final_totals,
            simulated_team_a=final_a,
            simulated_team_b=final_b,
            timeline_df=timeline_df,

            pre_game_total=float(self.pre_game["total_expected"]),
            match_pace_expected=float(self.pre_game["match_pace"]),
            eff_a_expected=float(self.pre_game["eff_a"]),
            eff_b_expected=float(self.pre_game["eff_b"]),
            analytical_normal=normal_res,
            regulation_mean=regulation_mean,
            overtime_points_avg=avg_ot_pts,
            overtime_count=ot_count,
            shooting_regression_applied=shooting_reg_applied,
            three_point_luck_delta=luck_delta_pts,
            dl_active=dl_active,
            dl_delta_pace=dl_delta_p,
            dl_pace_multiplier=dl_mult,
            dl_uncertainty_pts=dl_unc_pts,
            dl_win_prob=dl_win_p,
            dl_momentum_label=dl_label,
            dl_details=dl_details,
            simulated_margins=final_a - final_b,
            spread_mean=float(np.mean(final_a - final_b)),
            spread_std=float(np.std(final_a - final_b)),
            dl_spread_margin=dl_spread_margin,
            dl_spread_std=dl_spread_std,
            dl_xai_factors=dl_xai_factors
        )

    @staticmethod
    def calculate_over_under(simulated_totals: np.ndarray, line: float) -> Tuple[float, float]:
        """
        Calcula la probabilidad exacta de Over y Under para una línea de puntos dada.
        """
        prob_over = float(np.mean(simulated_totals > line))
        prob_under = float(np.mean(simulated_totals < line))
        return prob_over, prob_under

    @staticmethod
    def calculate_spread_cover(simulated_margins: np.ndarray, spread_line: float) -> Tuple[float, float]:
        """
        Calcula la probabilidad de que el equipo local cubra el hándicap (spread_line)
        y de que el equipo visitante lo cubra.
        """
        prob_home = float(np.mean(simulated_margins + spread_line > 0))
        prob_away = float(np.mean(simulated_margins + spread_line < 0))
        return prob_home, prob_away

    @staticmethod
    def calculate_moneyline(simulated_margins: np.ndarray) -> Tuple[float, float]:
        """
        Calcula la probabilidad de victoria directa de cada equipo (Moneyline).
        """
        prob_home = float(np.mean(simulated_margins > 0))
        prob_away = float(np.mean(simulated_margins < 0))
        return prob_home, prob_away
