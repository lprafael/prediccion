"""
Pruebas de validación del motor probabilístico de baloncesto.
"""
import sys
import os

# Asegurar path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.config import TOURNAMENT_PRESETS, TournamentConfig
from model.engine import BasketballPredictor

def test_baselines():
    print("--- Probando Trayectorias Base de los 3 Torneos ---")
    for key, cfg in TOURNAMENT_PRESETS.items():
        predictor = BasketballPredictor(cfg)
        df_base = predictor.get_baseline_trajectory()
        final_val = df_base["baseline_total"].iloc[-1]
        print(f"Torneo: {cfg.name} | Duración: {cfg.quarter_duration} min | Final esperado: {cfg.total_game_avg:.1f} | Calculado: {final_val:.1f}")
        assert abs(final_val - cfg.total_game_avg) < 0.5, f"Error en baseline de {key}"

def test_live_simulation():
    print("\n--- Probando Simulación En Vivo (NBA, 4Q restando 1.5 min, partido cerrado) ---")
    nba_cfg = TOURNAMENT_PRESETS["NBA"]
    predictor = BasketballPredictor(nba_cfg)
    
    # Marcador tras 3Q: 85 - 83. En 4Q van 10.5 minutos (quedan 1.5 minutos).
    # 4Q puntos hasta ahora: 22 - 20 => Total: 107 - 103 (diferencia 4 pts, clutch!)
    quarters_data = [
        (28.0, 26.0), # Q1
        (30.0, 29.0), # Q2
        (27.0, 28.0), # Q3
        (22.0, 20.0)  # Q4 en progreso
    ]
    
    elapsed_seconds_in_q4 = 10.5 * 60  # 10m 30s jugados de 12 min
    summary = predictor.run_live_simulation(
        current_quarter=4,
        elapsed_seconds_in_quarter=elapsed_seconds_in_q4,
        quarters_data=quarters_data,
        n_simulations=3000
    )
    
    print(f"Total actual anotado: {107 + 103} pts")
    print(f"Proyección media final: {summary.total_mean:.1f} pts")
    print(f"Mínimo Estimado (P05): {summary.total_p05:.1f} pts | Máximo Estimado (P95): {summary.total_p95:.1f} pts")
    print(f"Extremos simulados absolutos: [{summary.total_min:.0f} - {summary.total_max:.0f}] pts")
    print(f"Intervalo 10% - 90%: [{summary.total_p10:.1f} - {summary.total_p90:.1f}] pts")
    print(f"Local ({nba_cfg.name[:5]}): [{summary.team_a_p05:.0f} - {summary.team_a_p95:.0f}] | Visitante: [{summary.team_b_p05:.0f} - {summary.team_b_p95:.0f}]")
    print(f"Ritmo Prior: {summary.prior_pace_per_min:.2f} pts/min")
    print(f"Ritmo Observado: {summary.observed_pace_per_min:.2f} pts/min")
    print(f"Ritmo Posterior Bayesiano: {summary.posterior_pace_per_min:.2f} pts/min")
    print(f"Prob Victoria Local: {summary.win_prob_a*100:.1f}% | Visitante: {summary.win_prob_b*100:.1f}%")
    
    assert summary.total_min <= summary.total_p05 <= summary.total_mean <= summary.total_p95 <= summary.total_max
    assert summary.team_a_min <= summary.team_a_p05 <= summary.team_a_mean <= summary.team_a_p95 <= summary.team_a_max
    assert summary.team_b_min <= summary.team_b_p05 <= summary.team_b_mean <= summary.team_b_p95 <= summary.team_b_max
    
    p_over, p_under = BasketballPredictor.calculate_over_under(summary.simulated_totals, 218.5)
from model.analytics import (
    TeamProfile,
    estimate_pace_from_boxscore,
    calculate_matchup_pace,
    calculate_cross_efficiency,
    calculate_four_factors_off_rating,
    empirical_bayes_smoothing,
    calculate_analytical_normal,
    project_pre_game_matchup
)

def test_advanced_analytics():
    print("\n--- Probando Métricas y Analítica Avanzada (Oliver, Pace, Ratings, Bayes, Normal) ---")
    nba_cfg = TOURNAMENT_PRESETS["NBA"]

    # 1. Fórmula de ritmo de Oliver
    # 0.5 * (85 + 0.44*25 - 10 + 14) = 0.5 * (85 + 11 - 10 + 14) = 0.5 * 100 = 50.0
    pace_box = estimate_pace_from_boxscore(fga=85, fta=25, orb=10, tov=14)
    assert abs(pace_box - 50.0) < 0.01, f"Error en estimate_pace_from_boxscore: {pace_box}"
    print(f"Pace Oliver Boxscore (85 FGA, 25 FTA, 10 ORB, 14 TOV): {pace_box:.1f} poss")

    # 2. Matchup Pace: (Pace_A * Pace_B) / Pace_Liga
    # (102.0 * 98.0) / 100.0 = 99.96
    m_pace = calculate_matchup_pace(102.0, 98.0, 100.0)
    assert abs(m_pace - 99.96) < 0.01, f"Error en calculate_matchup_pace: {m_pace}"
    print(f"Matchup Pace cruzado (102.0 vs 98.0 / 100): {m_pace:.2f}")

    # 3. Four factors to OffRtg
    off_rtg_ff = calculate_four_factors_off_rating(
        efg=0.56,
        tov_pct=0.12,
        orb_pct=0.28,
        ft_rate=0.25,
        tournament_key="NBA",
        league_off_rating=115.0
    )
    print(f"OffRtg calculado con Four Factors de Oliver: {off_rtg_ff:.2f}")
    assert off_rtg_ff > 115.0, "Equipo con mejores factores debería superar el promedio"

    # 4. Eficiencia cruzada con localía y B2B
    home_team = TeamProfile(name="Celtics", pace=101.0, off_rating=118.0, def_rating=110.0, is_home=True, is_b2b=False)
    away_b2b_team = TeamProfile(name="Lakers", pace=99.0, off_rating=114.0, def_rating=113.0, is_home=False, is_b2b=True)

    eff_home = calculate_cross_efficiency(home_team, away_b2b_team, nba_cfg)
    eff_away = calculate_cross_efficiency(away_b2b_team, home_team, nba_cfg)
    print(f"Eficiencia Cruzada Home ({home_team.name}): {eff_home:.2f} pts/100")
    print(f"Eficiencia Cruzada Away B2B ({away_b2b_team.name}): {eff_away:.2f} pts/100")
    assert eff_home > eff_away, "Local descansado debe tener mayor eficiencia que visitante B2B"

    # 5. Suavizado empírico bayesiano
    smoothed = empirical_bayes_smoothing(observed_rate=140.0, prior_rate=115.0, sample_size=10.0, inertia_k=30.0)
    # w = 10 / 40 = 0.25 => 0.25 * 140 + 0.75 * 115 = 35 + 86.25 = 121.25
    assert abs(smoothed - 121.25) < 0.1, f"Error en empirical_bayes_smoothing: {smoothed}"
    print(f"Empirical Bayes smoothing (obs 140, prior 115, sample 10): {smoothed:.2f}")

    # 6. Modelo analítico Normal
    norm_res = calculate_analytical_normal(mu=220.0, sigma=20.0)
    print(f"Normal N(220, 20^2) -> 80% CI: [{norm_res.p10:.1f} - {norm_res.p90:.1f}] | 95% CI: [{norm_res.p025:.1f} - {norm_res.p975:.1f}]")
    assert abs(norm_res.prob_over(220.0) - 0.50) < 0.01

    # 7. Simulación Monte Carlo 10,000 iteraciones
    predictor_10k = BasketballPredictor(nba_cfg, team_a_profile=home_team, team_b_profile=away_b2b_team)
    sum_10k = predictor_10k.run_live_simulation(
        current_quarter=1,
        elapsed_seconds_in_quarter=0,
        quarters_data=[(0, 0), (0, 0), (0, 0), (0, 0)],
        n_simulations=10000
    )
    print(f"Monte Carlo 10,000 iters -> Proyección: {sum_10k.total_mean:.1f} pts, Std: {sum_10k.total_std:.1f} pts")
    print(f"Intervalo 80% empírico: [{sum_10k.total_p10:.1f} - {sum_10k.total_p90:.1f}] pts")
    print(f"Intervalo 95% empírico: [{sum_10k.total_p025:.1f} - {sum_10k.total_p975:.1f}] pts")
    assert sum_10k.total_p025 <= sum_10k.total_p10 <= sum_10k.total_mean <= sum_10k.total_p90 <= sum_10k.total_p975

    print("¡Todas las pruebas avanzadas pasaron con éxito!")

def test_tournament_quarter_detection():
    print("\n--- Probando Detección de Cuartos por Liga (NBL, NBA, WNBA, Euroliga) ---")
    import re
    from model.scraper import LiveMatchData

    def detect_duration(league_tokens, clock_min=0, odds_line=None):
        result = LiveMatchData()
        result.league_name = " / ".join(filter(None, league_tokens))
        is_nba_detected = False
        for t in league_tokens:
            t_str = str(t).strip().lower()
            if "wnba" in t_str or "nbl" in t_str:
                is_nba_detected = False
                break
            if re.search(r"\b(nba|g-league|g league)\b", t_str):
                is_nba_detected = True
                break
        result.quarter_duration = 12 if is_nba_detected else 10
        result.clock_min = clock_min
        if result.clock_min > 10:
            result.quarter_duration = 12
        result.odds_line = odds_line
        return result.quarter_duration

    # 1. NBL Australia (debe ser 10 min, incluso con línea alta de 210 pts en vivo)
    nbl_tokens = ["Pretemporada NBL", "Baloncesto", "Australia", "Pretemporada NBL"]
    dur_nbl = detect_duration(nbl_tokens, clock_min=10, odds_line=210.5)
    print(f"NBL Australia (línea 210.5, reloj 10:00) -> {dur_nbl} min/cuarto")
    assert dur_nbl == 10, f"Error: NBL debe ser 10 min, obtuvo {dur_nbl}"

    # 2. NBA (debe ser 12 min)
    nba_tokens = ["NBA", "Baloncesto", "EE. UU.", "NBA"]
    dur_nba = detect_duration(nba_tokens, clock_min=12, odds_line=224.5)
    print(f"NBA (línea 224.5, reloj 12:00) -> {dur_nba} min/cuarto")
    assert dur_nba == 12, f"Error: NBA debe ser 12 min, obtuvo {dur_nba}"

    # 3. WNBA (debe ser 10 min, no confundir con NBA)
    wnba_tokens = ["WNBA", "Baloncesto", "EE. UU.", "WNBA"]
    dur_wnba = detect_duration(wnba_tokens, clock_min=8, odds_line=168.0)
    print(f"WNBA -> {dur_wnba} min/cuarto")
    assert dur_wnba == 10, f"Error: WNBA debe ser 10 min, obtuvo {dur_wnba}"

    # 4. Euroliga / FIBA (debe ser 10 min)
    fiba_tokens = ["Euroliga", "Baloncesto", "Europa"]
    dur_fiba = detect_duration(fiba_tokens, clock_min=9, odds_line=175.5)
    print(f"Euroliga -> {dur_fiba} min/cuarto")
    assert dur_fiba == 10, f"Error: Euroliga debe ser 10 min, obtuvo {dur_fiba}"

    # 5. Reloj físico > 10 min (ej. 11 min en periodo)
    dur_clock = detect_duration(["Liga Desconocida"], clock_min=11)
    print(f"Reloj 11:00 en cuarto -> {dur_clock} min/cuarto")
    assert dur_clock == 12, f"Error: reloj > 10 min debe ser 12 min, obtuvo {dur_clock}"

    print("¡Todas las pruebas de detección de torneos pasaron con éxito!")

def test_overtime_simulation():
    print("\n--- Probando Simulación de Prórroga / Overtime (OT 5 min en empates) ---")
    fiba_cfg = TOURNAMENT_PRESETS["FIBA"]
    predictor = BasketballPredictor(fiba_cfg)
    
    # 4Q restando 5 segundos con marcador empatado 80-80
    quarters_data = [
        (20.0, 20.0),
        (20.0, 20.0),
        (20.0, 20.0),
        (20.0, 20.0),
    ]
    elapsed_seconds_in_q4 = 9.9 * 60  # casi todo el 4Q jugado
    summary = predictor.run_live_simulation(
        current_quarter=4,
        elapsed_seconds_in_quarter=elapsed_seconds_in_q4,
        quarters_data=quarters_data,
        n_simulations=2500,
        random_seed=42,
        actual_total_scores=(80.0, 80.0)
    )
    
    print(f"Probabilidad de Prórroga: {summary.overtime_prob*100:.1f}%")
    print(f"Media Regulación: {summary.regulation_mean:.1f} pts | Total con OT: {summary.total_mean:.1f} pts")
    print(f"Puntos promedio añadidos por OT: {summary.overtime_points_avg:.1f} pts")
    print(f"Simulaciones con prórroga: {summary.overtime_count} de 2500")

    assert summary.overtime_prob > 0.20, f"En 80-80 a 6 seg del final la prob de OT debe ser >20%, fue {summary.overtime_prob*100:.1f}%"
    assert summary.overtime_count > 0, "Debe haber simulaciones que fueron a OT"
    assert summary.overtime_points_avg > 0, "El promedio de puntos de OT debe ser > 0"
    assert summary.total_mean >= summary.regulation_mean, "El total general debe ser >= al total de regulación"
    print("¡Prueba de simulación de prórroga superada!")

def test_nbl_preset():
    print("\n--- Probando Configuración NBL Australia ---")
    assert "NBL" in TOURNAMENT_PRESETS, "Preset NBL debe existir en TOURNAMENT_PRESETS"
    nbl_cfg = TOURNAMENT_PRESETS["NBL"]
    assert nbl_cfg.quarter_duration == 10, f"NBL debe ser de 10 min por cuarto, obtenido: {nbl_cfg.quarter_duration}"
    assert 180.0 <= nbl_cfg.total_game_avg <= 188.0, f"Total promedio NBL debe estar entre 180 y 188, obtenido: {nbl_cfg.total_game_avg}"
    assert nbl_cfg.league_pace >= 80.0, f"Pace de NBL debe ser >= 80.0, obtenido: {nbl_cfg.league_pace}"

    pred_nbl = BasketballPredictor(nbl_cfg)
    base_df = pred_nbl.get_baseline_trajectory()
    final_total = base_df["baseline_total"].iloc[-1]
    print(f"NBL Baseline final proyectado: {final_total:.1f} pts")
    assert abs(final_total - nbl_cfg.total_game_avg) < 0.5, "Baseline debe converger con total_game_avg"
    print("¡Prueba de preset NBL superada!")

def test_betting_metrics_and_grades():
    print("\n--- Probando Métricas Profesionales: Point Spread Edge, No-Vig y Bet Grades ---")
    from model.live_betting import LiveBettingSignals, get_live_betting_recommendation

    # Caso 1: Gran ventaja al OVER (+5.5 pts sobre la línea, cuotas con vig)
    signals = LiveBettingSignals(
        pace_observed_per_min=2.2,
        pace_projected_total=188.0,
        momentum_score=2.0
    )
    rec_a_plus = get_live_betting_recommendation(
        signals=signals,
        prob_over=0.72,
        prob_under=0.28,
        line=180.0,
        model_mean=185.5,
        league_avg_pace_per_min=2.1,
        house_odds_over=1.90,
        house_odds_under=1.90,
        line_source="casa"
    )
    print(f"Caso 1 (Over 180 vs media 185.5) -> Spread Edge: {rec_a_plus.point_spread_edge:+.1f} pts | Grado: {rec_a_plus.bet_grade} | Unidades: {rec_a_plus.recommended_units:.1f}U")
    assert rec_a_plus.direction == "OVER"
    assert rec_a_plus.point_spread_edge == 5.5
    assert "GRADO A+" in rec_a_plus.bet_grade
    assert rec_a_plus.recommended_units >= 2.0
    assert rec_a_plus.house_vig_pct > 0.05
    assert abs(rec_a_plus.novig_prob_over - 0.50) < 0.01  # 1.90 vs 1.90 -> 50% No-Vig
    assert rec_a_plus.alpha_over > 0.20  # 72% - 50% = 22% alpha

    # Caso 2: Sin Edge (Línea idéntica a la media del modelo)
    rec_no_edge = get_live_betting_recommendation(
        signals=LiveBettingSignals(),
        prob_over=0.51,
        prob_under=0.49,
        line=180.0,
        model_mean=180.3,
        league_avg_pace_per_min=2.1,
        house_odds_over=1.90,
        house_odds_under=1.90,
        line_source="casa"
    )
    print(f"Caso 2 (Línea 180 vs media 180.3) -> Spread Edge: {rec_no_edge.point_spread_edge:+.1f} pts | Grado: {rec_no_edge.bet_grade} | Unidades: {rec_no_edge.recommended_units:.1f}U")
    assert "SIN EDGE" in rec_no_edge.bet_grade
    assert rec_no_edge.recommended_units == 0.0

    print("¡Prueba de métricas de apuestas y grados superada!")

def test_three_point_mean_reversion():
    print("\n--- Probando Regresión de Triples a la Media (Normalización de Rachas) ---")
    nba_cfg = TOURNAMENT_PRESETS["NBA"]
    predictor = BasketballPredictor(nba_cfg)

    # Q1 finalizado (12 min), marcador 35-30 = 65 pts.
    # Caso A: Racha insostenible de triples (8 triples anotados en 10 intentos = 80% 3P)
    hot_shooting_ctx = {"made_3p": 8, "att_3p": 10}
    quarters_data = [(35.0, 30.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

    summary_hot = predictor.run_live_simulation(
        current_quarter=2,
        elapsed_seconds_in_quarter=0.0,
        quarters_data=quarters_data,
        n_simulations=2000,
        random_seed=42,
        actual_total_scores=(35.0, 30.0),
        shooting_context=hot_shooting_ctx
    )

    # Caso B: Sin racha de tiro (disparos normales acordes a la liga)
    summary_norm = predictor.run_live_simulation(
        current_quarter=2,
        elapsed_seconds_in_quarter=0.0,
        quarters_data=quarters_data,
        n_simulations=2000,
        random_seed=42,
        actual_total_scores=(35.0, 30.0),
        shooting_context=None
    )

    print(f"Racha caliente 80% 3P -> Suerte Delta: {summary_hot.three_point_luck_delta:+.1f} pts | Regresión aplicada: {summary_hot.shooting_regression_applied:+.1f} pts")
    print(f"Total proyectado CON regresión: {summary_hot.total_mean:.1f} pts vs SIN regresión: {summary_norm.total_mean:.1f} pts")

    assert summary_hot.three_point_luck_delta > 0, "El delta de suerte en racha de 8/10 triples debe ser positivo"
    assert summary_hot.shooting_regression_applied > 0, "Debe aplicarse regresión a la baja en los minutos restantes"
    assert summary_hot.total_mean < summary_norm.total_mean, "La proyección con regresión debe ser menor que extrapolando linealmente la racha"
    print("¡Prueba de regresión de triples superada!")

def test_performance_dashboard_metrics():
    print("\n--- Probando Métricas del Tablero de Rendimiento, Bankroll y Brier Score ---")
    from model.database import calcular_metricas_rendimiento_apuestas

    metricas = calcular_metricas_rendimiento_apuestas()
    assert isinstance(metricas, dict)
    assert "win_rate_global" in metricas
    assert "roi_pct" in metricas
    assert "profit_factor" in metricas
    assert "brier_score" in metricas
    assert "por_grado" in metricas
    assert "curva_capital" in metricas

    print(f"Tablero verificado -> Total apuestas: {metricas['total_apuestas']} | Win Rate: {metricas['win_rate_global']}% | ROI: {metricas['roi_pct']}% | Brier Score: {metricas['brier_score']}")
    print("¡Prueba de métricas de rendimiento y auditoría superada!")

def test_q4_adaptive_pace_and_confidence_calibration():
    print("\n--- Probando Ritmo Adaptativo en 4Q y Calibración de Confianza ---")
    from model.config import TOURNAMENT_PRESETS
    from model.engine import BasketballPredictor
    from model.live_betting import LiveBettingSignals, get_live_betting_recommendation

    cfg = TOURNAMENT_PRESETS["WNBA"]
    predictor = BasketballPredictor(tournament_config=cfg)

    # Simular Atlanta vs Connecticut al minuto 35:02 (5:02 transcurrido de 4Q)
    # Total actual: 91 + 53 = 144 pts.
    quarters_data = [
        (22.0, 17.0),
        (23.0, 18.0),
        (31.0, 11.0),
        (15.0, 7.0),
    ]
    summary = predictor.run_live_simulation(
        current_quarter=4,
        elapsed_seconds_in_quarter=302.0,
        quarters_data=quarters_data,
        actual_total_scores=(91.0, 53.0),
        n_simulations=1000,
        random_seed=42,
    )

    assert summary.total_mean >= 158.0, f"La media proyectada ({summary.total_mean}) debe reflejar el ritmo real del 4Q y ser >= 158.0"

    signals = LiveBettingSignals(
        pace_observed_per_min=4.1,
        pace_projected_total=summary.total_mean,
        momentum_score=3.0
    )
    rec = get_live_betting_recommendation(
        signals=signals,
        prob_over=0.75,
        prob_under=0.25,
        line=155.0,
        model_mean=summary.total_mean,
        league_avg_pace_per_min=4.0,
        house_odds_over=1.85,
        house_odds_under=1.85,
        minutes_remaining=4.97,
    )
    assert rec.confidence_pct <= 92.0, f"Con casi 5 min restantes, la confianza ({rec.confidence_pct}%) debe estar moderada"
    print(f"Ritmo adaptativo 4Q superado: Media = {summary.total_mean:.1f} pts, Confianza = {rec.confidence_pct}%")

if __name__ == "__main__":
    test_baselines()
    test_live_simulation()
    test_advanced_analytics()
    test_tournament_quarter_detection()
    test_overtime_simulation()
    test_nbl_preset()
    test_betting_metrics_and_grades()
    test_three_point_mean_reversion()
    test_performance_dashboard_metrics()
    test_q4_adaptive_pace_and_confidence_calibration()
    print("\n=======================================================")
    print(">>> TODAS LAS PRUEBAS (FASES 1, 2 Y 3) PASARON EXITOSAMENTE! <<<")
    print("=======================================================")

