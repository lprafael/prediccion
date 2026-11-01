"""
Router para Simulación Monte Carlo y Trayectorias Basales.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, status
import numpy as np
import pandas as pd

from model.config import TOURNAMENT_PRESETS, TournamentConfig
from model.engine import BasketballPredictor, SimulationSummary
from model.analytics import TeamProfile
from model.database import obtener_partido, listar_jugadas
from api.schemas.simulacion import (
    SimularRequest,
    SimulationResultResponse,
    BaselineResponse,
)


def sanitize_nans(obj: Any) -> Any:
    """Reemplaza recursivamente NaN e Inf con None para compatibilidad JSON estándar."""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_nans(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_nans(v) for v in obj]
    return obj


router = APIRouter()


@router.post("/simular", response_model=SimulationResultResponse)
async def post_simular(req: SimularRequest):
    """
    Ejecuta la simulación Monte Carlo bayesiana en vivo con deep learning residual,
    regresión a la media y clutch timing.
    """
    torneo_cfg = TOURNAMENT_PRESETS.get(req.torneo_key)
    if not torneo_cfg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Torneo '{req.torneo_key}' no soportado. Valores válidos: {list(TOURNAMENT_PRESETS.keys())}"
        )

    # Convertir perfiles de equipo si fueron proporcionados
    team_a_profile = None
    if req.team_a_profile:
        team_a_profile = TeamProfile(**req.team_a_profile.model_dump())

    team_b_profile = None
    if req.team_b_profile:
        team_b_profile = TeamProfile(**req.team_b_profile.model_dump())

    # Formatear contexto de tiro
    shooting_ctx = None
    if req.shooting_context:
        shooting_ctx = req.shooting_context.model_dump()

    # Formatear jugadas si existen
    plays_dicts = None
    if req.plays:
        plays_dicts = [p.model_dump() for p in req.plays]

    try:
        predictor = BasketballPredictor(
            tournament_config=torneo_cfg,
            team_a_profile=team_a_profile,
            team_b_profile=team_b_profile,
            inertia_minutes=getattr(req, "inertia_minutes", 12.0),
        )

        summary: SimulationSummary = predictor.run_live_simulation(
            current_quarter=req.current_quarter,
            elapsed_seconds_in_quarter=req.elapsed_seconds_in_quarter,
            quarters_data=req.quarters_data,
            n_simulations=req.n_simulations,
            random_seed=getattr(req, "random_seed", None),
            actual_total_scores=req.actual_total_scores,
            shooting_context=shooting_ctx,
            plays=plays_dicts,
            use_deep_learning=req.use_deep_learning,
        )

        # Calcular probabilidades Over / Under si hay línea de apuesta
        prob_over = None
        prob_under = None
        if req.linea_apuesta is not None and len(summary.simulated_totals) > 0:
            prob_over = float(np.mean(summary.simulated_totals > req.linea_apuesta))
            prob_under = float(np.mean(summary.simulated_totals < req.linea_apuesta))

        # Serializar timeline dataframe a lista de dicts limpia sin NaNs
        timeline_records = []
        if summary.timeline_df is not None and not summary.timeline_df.empty:
            timeline_records = summary.timeline_df.where(pd.notnull(summary.timeline_df), None).to_dict(orient="records")

        # Muestreo representativo de totales simulados para graficar histograma sin sobrecargar el payload
        hist_totals = None
        if summary.simulated_totals is not None and len(summary.simulated_totals) > 0:
            if len(summary.simulated_totals) > 2000:
                indices = np.linspace(0, len(summary.simulated_totals) - 1, 2000, dtype=int)
                hist_totals = [float(x) for x in summary.simulated_totals[indices]]
            else:
                hist_totals = [float(x) for x in summary.simulated_totals]

        return SimulationResultResponse(
            team_a_mean=float(summary.team_a_mean),
            team_a_median=float(summary.team_a_median),
            team_a_min=float(summary.team_a_min),
            team_a_max=float(summary.team_a_max),
            team_a_p05=float(summary.team_a_p05),
            team_a_p10=float(summary.team_a_p10),
            team_a_p90=float(summary.team_a_p90),
            team_a_p95=float(summary.team_a_p95),

            team_b_mean=float(summary.team_b_mean),
            team_b_median=float(summary.team_b_median),
            team_b_min=float(summary.team_b_min),
            team_b_max=float(summary.team_b_max),
            team_b_p05=float(summary.team_b_p05),
            team_b_p10=float(summary.team_b_p10),
            team_b_p90=float(summary.team_b_p90),
            team_b_p95=float(summary.team_b_p95),

            total_mean=float(summary.total_mean),
            total_median=float(summary.total_median),
            total_std=float(summary.total_std),
            total_min=float(summary.total_min),
            total_max=float(summary.total_max),
            total_p025=float(summary.total_p025),
            total_p05=float(summary.total_p05),
            total_p10=float(summary.total_p10),
            total_p25=float(summary.total_p25),
            total_p75=float(summary.total_p75),
            total_p90=float(summary.total_p90),
            total_p95=float(summary.total_p95),
            total_p975=float(summary.total_p975),

            win_prob_a=float(summary.win_prob_a),
            win_prob_b=float(summary.win_prob_b),
            overtime_prob=float(summary.overtime_prob),

            prior_pace_per_min=float(summary.prior_pace_per_min),
            observed_pace_per_min=float(summary.observed_pace_per_min),
            posterior_pace_per_min=float(summary.posterior_pace_per_min),
            shrinkage_weight=float(summary.shrinkage_weight),

            pre_game_total=float(summary.pre_game_total),
            match_pace_expected=float(summary.match_pace_expected),
            eff_a_expected=float(summary.eff_a_expected),
            eff_b_expected=float(summary.eff_b_expected),

            regulation_mean=float(summary.regulation_mean),
            overtime_points_avg=float(summary.overtime_points_avg),
            overtime_count=int(summary.overtime_count),

            shooting_regression_applied=float(summary.shooting_regression_applied),
            three_point_luck_delta=float(summary.three_point_luck_delta),

            dl_active=bool(summary.dl_active),
            dl_delta_pace=float(summary.dl_delta_pace),
            dl_pace_multiplier=float(summary.dl_pace_multiplier),
            dl_uncertainty_pts=float(summary.dl_uncertainty_pts),
            dl_win_prob=float(summary.dl_win_prob) if summary.dl_win_prob is not None else None,
            dl_momentum_label=str(summary.dl_momentum_label),
            dl_details=str(summary.dl_details),

            prob_over=prob_over,
            prob_under=prob_under,
            timeline=timeline_records,
            histogram_totals=hist_totals,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en ejecución de simulación: {str(e)}"
        )


@router.get("/baseline", response_model=BaselineResponse)
async def get_baseline(torneo_key: str = Query("NBA", description="NBA, FIBA, NBL, NCAA_FEMENIL")):
    """Retorna la trayectoria de puntuación esperada minuto a minuto para un torneo."""
    torneo_cfg = TOURNAMENT_PRESETS.get(torneo_key)
    if not torneo_cfg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Torneo '{torneo_key}' no encontrado"
        )
    predictor = BasketballPredictor(torneo_cfg)
    df = predictor.get_baseline_trajectory()
    return BaselineResponse(
        tournament_key=torneo_cfg.key,
        tournament_name=torneo_cfg.name,
        quarter_duration=torneo_cfg.quarter_duration,
        timeline=df.to_dict(orient="records")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint todo-en-uno: Lee jugadas de BD → Simula → Analiza Apuestas
# ─────────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel as _PydanticBase


class SimularLiveRequest(_PydanticBase):
    """Parámetros opcionales para el ciclo de simulación live automático."""
    linea_apuesta: Optional[float] = None
    cuota_over: Optional[float] = None
    cuota_under: Optional[float] = None
    spread_line: Optional[float] = None
    cuota_spread_local: Optional[float] = None
    cuota_spread_visitante: Optional[float] = None
    cuota_ml_local: Optional[float] = None
    cuota_ml_visitante: Optional[float] = None
    lineup_local: Optional[List[int]] = None
    lineup_visitante: Optional[List[int]] = None
    fouls_local: Optional[int] = None
    fouls_visitante: Optional[int] = None
    n_simulations: int = 5000
    use_deep_learning: bool = True


@router.post("/partidos/{partido_id}/simular-live")
async def post_simular_live(partido_id: int, req: SimularLiveRequest = SimularLiveRequest()):
    """
    🏀 Ciclo de Predicción en Vivo (Todo-en-Uno):

    1. Lee el estado actual del partido desde la BD.
    2. Carga TODAS las jugadas play-by-play acumuladas en la BD.
    3. Ejecuta Monte Carlo (5000 sim) + Deep Learning con el contexto completo y lineups.
    4. Analiza señales live betting: momentum, ritmo, rachas, calor, volatilidad.
    5. Calcula EV, Point Spread Edge, Grado A+/A/B, Criterio de Kelly y Multimercados.
    6. Retorna predicción completa + veredicto de apuesta en una sola respuesta.

    Diseñado para ejecutarse cada 15s en el ciclo de auto-sync.
    """
    from model.live_betting import analyze_plays, get_live_betting_recommendation

    # 1. Obtener estado del partido
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido ID {partido_id} no encontrado"
        )

    # 2. Cargar jugadas acumuladas de la BD
    plays_db = listar_jugadas(partido_id)

    # 3. Construir parámetros de simulación a partir del estado del partido
    torneo_nombre = str(partido.get("torneo", "FIBA / Euroliga / Ligas Locales (10 min/cuarto)")).upper()
    team_a_str = str(partido.get("equipo_local", "")).lower()
    team_b_str = str(partido.get("equipo_visitante", "")).lower()

    # Detección inteligente de WNBA por torneo o nombres de equipos
    wnba_identifiers = ["wnba", "dream", "sun", "fever", "aces", "liberty", "lynx", "sky", "storm", "wings", "mercury", "mystics", "sparks"]
    is_wnba = ("WNBA" in torneo_nombre) or any(w in team_a_str or w in team_b_str for w in wnba_identifiers)

    torneo_key = "NBA"
    if "12" in torneo_nombre or ("NBA" in torneo_nombre and not is_wnba):
        torneo_key = "NBA"
    elif is_wnba:
        torneo_key = "WNBA"
    elif "NBL" in torneo_nombre:
        torneo_key = "NBL"
    elif "NCAA" in torneo_nombre:
        torneo_key = "NCAA_FEMENIL"
    else:
        torneo_key = "FIBA"

    torneo_cfg = TOURNAMENT_PRESETS.get(torneo_key)
    if not torneo_cfg:
        torneo_cfg = TOURNAMENT_PRESETS["FIBA"]

    q_dur = torneo_cfg.quarter_duration
    cuarto = min(int(partido.get("cuarto_actual", 1)), 4)
    min_rest = float(partido.get("min_restantes", q_dur))
    seg_rest = float(partido.get("seg_restantes", 0))
    elapsed_sec = max(0.0, (q_dur * 60) - (min_rest * 60 + seg_rest))

    # Lineups y faltas (prioridad al request, luego BD del partido)
    lineup_a = req.lineup_local or partido.get("lineup_local")
    lineup_b = req.lineup_visitante or partido.get("lineup_visitante")
    fouls_a = req.fouls_local if req.fouls_local is not None else int(partido.get("fouls_local") or 0)
    fouls_b = req.fouls_visitante if req.fouls_visitante is not None else int(partido.get("fouls_visitante") or 0)

    # Reconstruir quarters_data desde marcadores
    quarters: list = [[0, 0], [0, 0], [0, 0], [0, 0]]
    marcadores = partido.get("marcadores") or []
    for m in marcadores:
        q_idx = int(m.get("cuarto", 1)) - 1
        if 0 <= q_idx <= 3:
            quarters[q_idx] = [int(m.get("pts_local", 0)), int(m.get("pts_visitante", 0))]

    sum_q_local = sum(q[0] for q in quarters)
    sum_q_visit = sum(q[1] for q in quarters)
    total_local = max(int(partido.get("total_local") or 0), sum_q_local)
    total_visitante = max(int(partido.get("total_visitante") or 0), sum_q_visit)

    # 4. Ejecutar simulación Monte Carlo + DL con jugadas y quintetos
    try:
        predictor = BasketballPredictor(torneo_cfg)
        summary: SimulationSummary = predictor.run_live_simulation(
            current_quarter=cuarto,
            elapsed_seconds_in_quarter=elapsed_sec,
            quarters_data=quarters,
            n_simulations=req.n_simulations,
            random_seed=None,       # sin seed para mayor aleatoriedad real
            actual_total_scores=(total_local, total_visitante),
            shooting_context=None,
            plays=plays_db if plays_db else None,
            use_deep_learning=req.use_deep_learning,
            lineup_a=lineup_a,
            lineup_b=lineup_b,
            fouls_a=fouls_a,
            fouls_b=fouls_b,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en simulación live: {str(e)}"
        )

    # 5. Calcular prob Over/Under
    prob_over = None
    prob_under = None
    if req.linea_apuesta is not None and summary.simulated_totals is not None and len(summary.simulated_totals) > 0:
        prob_over = float(np.mean(summary.simulated_totals > req.linea_apuesta))
        prob_under = float(np.mean(summary.simulated_totals < req.linea_apuesta))

    # 6. Analizar señales live betting con las jugadas acumuladas
    team_a = partido.get("equipo_local", "LOCAL")
    team_b = partido.get("equipo_visitante", "VISITANTE")
    total_elapsed_min = (cuarto - 1) * q_dur + (q_dur - min_rest - seg_rest / 60.0)
    total_elapsed_min = max(0.5, total_elapsed_min)

    signals = analyze_plays(
        plays=plays_db or [],
        team_a=team_a,
        team_b=team_b,
        total_elapsed_min=total_elapsed_min,
        total_game_min=float(q_dur * 4),
    )

    # Señales resumidas
    signals_data = {
        "total_plays": signals.total_plays,
        "pace_observed_per_min": round(signals.pace_observed_per_min, 3),
        "pace_projected_total": round(signals.pace_projected_total, 1),
        "momentum_score": round(signals.momentum_score, 2),
        "momentum_label": signals.momentum_label,
        "run_team": signals.run_team,
        "run_pts": signals.run_pts,
        "recent_heat": signals.recent_heat,
        "volatility": round(signals.volatility, 3),
        "last_n_pts_home": signals.last_n_pts_home,
        "last_n_pts_away": signals.last_n_pts_away,
        "triple_pct_local": round(signals.triple_pct_a * 100, 1),
        "triple_pct_visitante": round(signals.triple_pct_b * 100, 1),
        "pts_by_quarter_home": signals.pts_by_quarter_home,
        "pts_by_quarter_away": signals.pts_by_quarter_away,
    }

    # Recomendación de apuesta integrada multimercado
    betting_recommendation = {}
    league_pace = 100.0 / 48.0 if q_dur == 12 else 75.0 / 40.0
    active_line = req.linea_apuesta if req.linea_apuesta is not None else float(summary.total_mean)
    p_ov = prob_over if prob_over is not None else 0.50
    p_un = prob_under if prob_under is not None else 0.50

    rec = get_live_betting_recommendation(
        signals=signals,
        prob_over=p_ov,
        prob_under=p_un,
        line=active_line,
        league_avg_pace_per_min=league_pace,
        house_odds_over=req.cuota_over,
        house_odds_under=req.cuota_under,
        line_source="auto_sync_15s",
        model_mean=float(summary.total_mean),
        spread_line=req.spread_line,
        house_odds_spread_home=req.cuota_spread_local,
        house_odds_spread_away=req.cuota_spread_visitante,
        house_odds_ml_home=req.cuota_ml_local,
        house_odds_ml_away=req.cuota_ml_visitante,
        simulated_margins=summary.simulated_margins,
        projected_margin_dl=summary.dl_spread_margin,
        spread_std_dl=summary.dl_spread_std,
        xai_factors=summary.dl_xai_factors,
        minutes_remaining=float((4 - cuarto) * q_dur + min_rest + seg_rest / 60.0),
    )

    from model.live_betting import kelly_fraction
    best_prob = rec.prob_over if rec.direction == "OVER" else rec.prob_under
    best_odds = req.cuota_over if rec.direction == "OVER" else (req.cuota_under or 1.9)
    kelly_f = kelly_fraction(best_prob, best_odds or 1.9)
    chosen_ev = rec.ev_over if rec.direction == "OVER" else rec.ev_under

    spread_rec = {
        "spread_line": rec.spread_line,
        "direction": rec.spread_direction,
        "grade": rec.spread_grade,
        "edge_pts": rec.spread_edge_pts,
        "cover_prob_home": rec.spread_cover_prob_home,
        "cover_prob_away": rec.spread_cover_prob_away,
        "fair_odds_home": rec.spread_fair_odds_home,
        "fair_odds_away": rec.spread_fair_odds_away,
        "ev_home": rec.spread_ev_home,
        "ev_away": rec.spread_ev_away,
    }

    ml_rec = {
        "direction": rec.moneyline_direction,
        "grade": rec.moneyline_grade,
        "prob_home": rec.moneyline_prob_home,
        "prob_away": rec.moneyline_prob_away,
        "fair_odds_home": rec.moneyline_fair_odds_home,
        "fair_odds_away": rec.moneyline_fair_odds_away,
        "ev_home": rec.moneyline_ev_home,
        "ev_away": rec.moneyline_ev_away,
    }

    betting_recommendation = {
        "direction": rec.direction,
        "bet_grade": rec.bet_grade,
        "signal_color": rec.signal_color,
        "confidence_pct": rec.confidence_pct,
        "prob_over": round(rec.prob_over, 4),
        "prob_under": round(rec.prob_under, 4),
        "point_spread_edge": rec.point_spread_edge,
        "model_mean": rec.model_mean,
        "ev_over": round(rec.ev_over, 4),
        "ev_under": round(rec.ev_under, 4),
        "ev_elegido": round(chosen_ev, 4),
        "fair_odds_over": rec.fair_odds_over,
        "fair_odds_under": rec.fair_odds_under,
        "house_vig_pct": rec.house_vig_pct,
        "novig_prob_over": rec.novig_prob_over,
        "novig_prob_under": rec.novig_prob_under,
        "alpha_over": rec.alpha_over,
        "alpha_under": rec.alpha_under,
        "kelly_fraction": round(kelly_f, 4),
        "recommended_units": rec.recommended_units,
        "is_high_payout": rec.is_high_payout,
        "reasons": rec.reasons,
        "pace_signal": rec.pace_signal,
        "momentum_signal": rec.momentum_signal,
        "spread_recommendation": spread_rec,
        "moneyline_recommendation": ml_rec,
        "optimal_stopping_action": rec.optimal_stopping_action,
        "overreaction_detected": rec.overreaction_detected,
        "xai_factors": rec.xai_factors,
        "suggested_paper_bet": rec.suggested_paper_bet,
    }

    # 7. Serializar histograma y timeline limpio de NaNs
    hist_totals = None
    if summary.simulated_totals is not None and len(summary.simulated_totals) > 0:
        if len(summary.simulated_totals) > 2000:
            indices = np.linspace(0, len(summary.simulated_totals) - 1, 2000, dtype=int)
            hist_totals = [float(x) for x in summary.simulated_totals[indices]]
        else:
            hist_totals = [float(x) for x in summary.simulated_totals]

    timeline_records = []
    if summary.timeline_df is not None and not summary.timeline_df.empty:
        timeline_records = summary.timeline_df.where(pd.notnull(summary.timeline_df), None).to_dict(orient="records")

    res = {
        # ─ Identificación
        "partido_id": partido_id,
        "equipo_local": partido.get("equipo_local"),
        "equipo_visitante": partido.get("equipo_visitante"),
        "cuarto_actual": cuarto,
        "min_restantes": min_rest,
        "seg_restantes": seg_rest,
        "total_local_actual": total_local,
        "total_visitante_actual": total_visitante,
        "total_jugadas_analizadas": len(plays_db),
        "lineup_local": lineup_a,
        "lineup_visitante": lineup_b,
        "fouls_local": fouls_a,
        "fouls_visitante": fouls_b,

        # ─ Predicción Monte Carlo
        "total_mean": round(float(summary.total_mean), 2),
        "total_median": round(float(summary.total_median), 2),
        "total_std": round(float(summary.total_std), 2),
        "total_p10": round(float(summary.total_p10), 2),
        "total_p25": round(float(summary.total_p25), 2),
        "total_p75": round(float(summary.total_p75), 2),
        "total_p90": round(float(summary.total_p90), 2),
        "team_a_mean": round(float(summary.team_a_mean), 2),
        "team_b_mean": round(float(summary.team_b_mean), 2),
        "win_prob_a": round(float(summary.win_prob_a), 4),
        "win_prob_b": round(float(summary.win_prob_b), 4),
        "overtime_prob": round(float(summary.overtime_prob), 4),

        # ─ Multimercado Margen y Hándicap
        "spread_mean": round(float(summary.spread_mean), 2),
        "spread_std": round(float(summary.spread_std), 2),
        "dl_spread_margin": round(float(summary.dl_spread_margin), 2) if summary.dl_spread_margin is not None else None,
        "dl_xai_factors": summary.dl_xai_factors,

        # ─ Ritmo Bayesiano
        "prior_pace_per_min": round(float(summary.prior_pace_per_min), 3),
        "observed_pace_per_min": round(float(summary.observed_pace_per_min), 3),
        "posterior_pace_per_min": round(float(summary.posterior_pace_per_min), 3),
        "shrinkage_weight": round(float(summary.shrinkage_weight), 4),

        # ─ Deep Learning
        "dl_active": bool(summary.dl_active),
        "dl_delta_pace": round(float(summary.dl_delta_pace), 3),
        "dl_pace_multiplier": round(float(summary.dl_pace_multiplier), 3),
        "dl_uncertainty_pts": round(float(summary.dl_uncertainty_pts), 2),
        "dl_win_prob": round(float(summary.dl_win_prob), 4) if summary.dl_win_prob is not None else None,
        "dl_momentum_label": str(summary.dl_momentum_label),

        # ─ Línea de Apuesta
        "linea_apuesta": req.linea_apuesta,
        "spread_line": req.spread_line,
        "prob_over": round(prob_over, 4) if prob_over is not None else None,
        "prob_under": round(prob_under, 4) if prob_under is not None else None,

        # ─ Señales Play-by-Play (Live Betting Intelligence)
        "signals": signals_data,

        # ─ Veredicto de Apuesta (Grado A+/A/B/Sin Edge + Kelly)
        "betting_recommendation": betting_recommendation,
        "optimal_stopping_action": rec.optimal_stopping_action,
        "overreaction_detected": rec.overreaction_detected,

        # ─ Gráficos
        "histogram_totals": hist_totals,
        "timeline": timeline_records,
    }

    return sanitize_nans(res)
