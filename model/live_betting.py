"""
🎯 Módulo de Análisis de Apuestas en Vivo (Live Betting)
Extrae señales estadísticas del historial de jugadas (play-by-play) para
generar recomendaciones de apuestas integradas con la simulación Monte Carlo.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import re


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses de Salida
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LiveBettingSignals:
    """Señales estadísticas derivadas del play-by-play."""

    # Ritmo real observado (pts totales / minuto jugado)
    pace_observed_per_min: float = 0.0
    # Pts totales proyectados a partido completo usando solo el ritmo observado
    pace_projected_total: float = 0.0

    # Distribución de tipos de anotación
    total_plays: int = 0
    triple_pct_a: float = 0.0   # % de jugadas que son triples del equipo A
    triple_pct_b: float = 0.0
    double_pct_a: float = 0.0
    double_pct_b: float = 0.0
    ft_pct_a: float = 0.0       # % de jugadas que son TL (1 pt) del equipo A
    ft_pct_b: float = 0.0

    # Momentum ponderado en las últimas N jugadas
    # Positivo = local dominando, Negativo = visitante dominando
    momentum_score: float = 0.0
    momentum_label: str = "NEUTRO"
    last_n_pts_home: int = 0
    last_n_pts_away: int = 0
    last_n: int = 10

    # Racha activa sin respuesta del rival
    run_team: str = ""
    run_pts: int = 0

    # Ritmo por cuarto (pts totales por minuto en cada cuarto)
    pace_by_quarter: Dict[int, float] = field(default_factory=dict)

    # Volatilidad del marcador (desviación estándar de los bloques de puntos)
    volatility: float = 0.0

    # Calor reciente: puntos totales en el último ~3 minutos (últimas 6 jugadas)
    recent_heat: int = 0

    # Puntos por cuarto (desglose observado)
    pts_by_quarter_home: Dict[int, int] = field(default_factory=dict)
    pts_by_quarter_away: Dict[int, int] = field(default_factory=dict)


@dataclass
class BettingRecommendation:
    """Recomendación de apuesta integrada con todos los metadatos necesarios."""

    direction: str = "NEUTRO"     # "OVER", "UNDER", "NEUTRO"
    confidence_pct: float = 0.0   # 0-100%
    signal_color: str = "🟡"      # 🟢 alta confianza, 🟡 media, 🔴 sin edge

    prob_over: float = 0.0
    prob_under: float = 0.0

    line: float = 0.0
    line_source: str = ""

    # Expected Value por $1 apostado
    ev_over: float = 0.0
    ev_under: float = 0.0

    # Cuotas justas del modelo
    fair_odds_over: float = 0.0
    fair_odds_under: float = 0.0

    # Comparación con cuotas de la casa
    house_odds_over: Optional[float] = None
    house_odds_under: Optional[float] = None
    house_edge_over: float = 0.0
    house_edge_under: float = 0.0

    reasons: List[str] = field(default_factory=list)

    pace_signal: str = "NEUTRO"
    momentum_signal: str = "NEUTRO"

    # Métrica de Ventaja de Puntos (Point Spread Edge)
    point_spread_edge: float = 0.0     # Media del modelo - Línea de la casa (ej. +4.5 pts)
    model_mean: float = 0.0            # Media de la simulación

    # Métricas de mercado Desmargenadas (No-Vig / True Market Implied Probability)
    house_vig_pct: float = 0.0         # Margen/overround cobrado por la casa (ej: 8.5%)
    novig_prob_over: float = 0.0       # Probabilidad pura del mercado sin margen
    novig_prob_under: float = 0.0
    alpha_over: float = 0.0            # prob_over - novig_prob_over
    alpha_under: float = 0.0           # prob_under - novig_prob_under

    # Calificación Profesional de la Apuesta y Gestión de Bankroll
    bet_grade: str = "SIN EDGE"        # "GRADO A+", "GRADO A", "GRADO B", "SIN EDGE"
    recommended_units: float = 0.0     # Unidades recomendadas (0.0 a 2.0u)

    # Análisis de Pago de la Casa y Apuesta Ficticia Sugerida
    is_high_payout: bool = False       # True si la casa paga cuota >= 2.10 con valor
    payout_ratio: float = 0.0          # Retorno por unidad apostada
    suggested_paper_bet: Optional[dict] = None

    # ─── Nuevos Mercados: Spread / Hándicap en Vivo ───
    spread_line: Optional[float] = None
    spread_cover_prob_home: float = 0.50
    spread_cover_prob_away: float = 0.50
    spread_fair_odds_home: float = 2.00
    spread_fair_odds_away: float = 2.00
    spread_ev_home: float = 0.0
    spread_ev_away: float = 0.0
    spread_direction: str = "NEUTRO"    # "LOCAL", "VISITANTE", "NEUTRO"
    spread_grade: str = "SIN EDGE"      # "GRADO A+", "GRADO A", "GRADO B", "SIN EDGE"
    spread_edge_pts: float = 0.0

    # ─── Nuevos Mercados: Moneyline (Ganador Directo) ───
    moneyline_prob_home: float = 0.50
    moneyline_prob_away: float = 0.50
    moneyline_fair_odds_home: float = 2.00
    moneyline_fair_odds_away: float = 2.00
    moneyline_ev_home: float = 0.0
    moneyline_ev_away: float = 0.0
    moneyline_direction: str = "NEUTRO" # "LOCAL", "VISITANTE", "NEUTRO"
    moneyline_grade: str = "SIN EDGE"

    # ─── Explicabilidad XAI y Política de Ejecución (Optimal Stopping) ───
    optimal_stopping_action: str = "ENTRAR_AHORA"  # "ENTRAR_AHORA", "ESPERAR_MEJOR_LINEA", "PASAR"
    overreaction_detected: bool = False
    xai_factors: Dict[str, float] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Función Principal: Analizar el play-by-play
# ─────────────────────────────────────────────────────────────────────────────

def _extract_quarter(info: str) -> Optional[int]:
    """Extrae el número de cuarto del campo 'info' de una jugada."""
    if not info:
        return None
    m = re.search(r"[QTP](\d)|(\d)[QTP]|cuarto\s*(\d)|periodo\s*(\d)", info, re.IGNORECASE)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    return None


def analyze_plays(
    plays: List[dict],
    team_a: str,
    team_b: str,
    total_elapsed_min: float,
    total_game_min: float = 40.0,
    last_n: int = 10
) -> "LiveBettingSignals":
    """
    Analiza la lista de jugadas del play-by-play y extrae señales estadísticas.

    Args:
        plays: Lista de dicts con keys: score_home, score_away, team, who, pts, info
        team_a: Nombre del equipo local
        team_b: Nombre del equipo visitante
        total_elapsed_min: Minutos totales transcurridos del partido
        total_game_min: Duración total del partido (40 o 48 min)
        last_n: Número de jugadas recientes para momentum

    Returns:
        LiveBettingSignals con todas las métricas calculadas.
    """
    signals = LiveBettingSignals(last_n=last_n)

    if not plays:
        return signals

    signals.total_plays = len(plays)

    # ── 1. Ritmo observado ─────────────────────────────────────────────────
    last_play = plays[-1]
    total_pts_now = last_play.get("score_home", 0) + last_play.get("score_away", 0)
    elapsed = max(0.5, total_elapsed_min)
    signals.pace_observed_per_min = round(total_pts_now / elapsed, 3)
    signals.pace_projected_total = round(signals.pace_observed_per_min * total_game_min, 1)

    # ── 2. Distribución de tipos de anotación ─────────────────────────────
    plays_a = [p for p in plays if (p.get("team") == team_a or p.get("who") == "HOME") and p.get("pts", 0) > 0]
    plays_b = [p for p in plays if (p.get("team") == team_b or p.get("who") == "AWAY") and p.get("pts", 0) > 0]

    def _dist(pl: list) -> Tuple[float, float, float]:
        if not pl:
            return 0.0, 0.0, 0.0
        total = len(pl)
        t3 = sum(1 for p in pl if p.get("pts") == 3) / total
        t2 = sum(1 for p in pl if p.get("pts") == 2) / total
        tl = sum(1 for p in pl if p.get("pts") == 1) / total
        return t3, t2, tl

    signals.triple_pct_a, signals.double_pct_a, signals.ft_pct_a = _dist(plays_a)
    signals.triple_pct_b, signals.double_pct_b, signals.ft_pct_b = _dist(plays_b)

    # ── 3. Momentum — últimas N jugadas ponderadas ────────────────────────
    recent = plays[-last_n:]
    signals.last_n_pts_home = sum(
        p.get("pts", 0) for p in recent
        if p.get("team") == team_a or p.get("who") == "HOME"
    )
    signals.last_n_pts_away = sum(
        p.get("pts", 0) for p in recent
        if p.get("team") == team_b or p.get("who") == "AWAY"
    )

    weighted_momentum = 0.0
    for i, p in enumerate(recent):
        weight = (i + 1) / last_n
        pts = p.get("pts", 0)
        is_home = (p.get("team") == team_a or p.get("who") == "HOME")
        weighted_momentum += weight * pts * (1 if is_home else -1)

    signals.momentum_score = round(weighted_momentum, 2)
    if signals.momentum_score > 2:
        signals.momentum_label = f"⬆ {team_a[:12]}"
    elif signals.momentum_score < -2:
        signals.momentum_label = f"⬇ {team_b[:12]}"
    else:
        signals.momentum_label = "EQUILIBRADO"

    # ── 4. Racha activa ────────────────────────────────────────────────────
    run_team = ""
    run_pts = 0
    for p in reversed(plays):
        if not run_team:
            run_team = p.get("team", "")
            run_pts = p.get("pts", 0)
        elif p.get("team") == run_team:
            run_pts += p.get("pts", 0)
        else:
            break
    signals.run_team = run_team
    signals.run_pts = run_pts

    # ── 5. Ritmo y pts por cuarto ─────────────────────────────────────────
    q_pts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    q_pts_home: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    q_pts_away: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}

    for p in plays:
        q = _extract_quarter(p.get("info", ""))
        if q and 1 <= q <= 4:
            pts_p = p.get("pts", 0)
            q_pts[q] += pts_p
            is_home = (p.get("team") == team_a or p.get("who") == "HOME")
            if is_home:
                q_pts_home[q] += pts_p
            else:
                q_pts_away[q] += pts_p

    q_dur = total_game_min / 4.0
    signals.pace_by_quarter = {
        q: round(q_pts[q] / q_dur, 2)
        for q in q_pts if q_pts[q] > 0
    }
    signals.pts_by_quarter_home = {k: v for k, v in q_pts_home.items() if v > 0}
    signals.pts_by_quarter_away = {k: v for k, v in q_pts_away.items() if v > 0}

    # ── 6. Volatilidad ────────────────────────────────────────────────────
    pts_events = [p.get("pts", 0) for p in plays if p.get("pts", 0) > 0]
    if len(pts_events) >= 3:
        signals.volatility = round(float(np.std(pts_events)), 3)

    # ── 7. Calor reciente (últimas 6 jugadas) ─────────────────────────────
    heat_n = min(6, len(plays))
    signals.recent_heat = sum(p.get("pts", 0) for p in plays[-heat_n:])

    return signals


# ─────────────────────────────────────────────────────────────────────────────
# Función de Recomendación Integrada
# ─────────────────────────────────────────────────────────────────────────────

def get_live_betting_recommendation(
    signals: LiveBettingSignals,
    prob_over: float,
    prob_under: float,
    line: float,
    league_avg_pace_per_min: float,
    house_odds_over: Optional[float] = None,
    house_odds_under: Optional[float] = None,
    line_source: str = "manual",
    model_mean: Optional[float] = None,
    spread_line: Optional[float] = None,
    house_odds_spread_home: Optional[float] = None,
    house_odds_spread_away: Optional[float] = None,
    house_odds_ml_home: Optional[float] = None,
    house_odds_ml_away: Optional[float] = None,
    simulated_margins: Optional[np.ndarray] = None,
    projected_margin_dl: Optional[float] = None,
    spread_std_dl: Optional[float] = None,
    xai_factors: Optional[Dict[str, float]] = None,
    minutes_remaining: Optional[float] = None,
) -> BettingRecommendation:
    """
    Combina señales del play-by-play con probabilidades Monte Carlo, Point Spread Edge
    y desmargenado No-Vig para emitir una recomendación cuantitativa profesional.
    """
    rec = BettingRecommendation(
        prob_over=prob_over,
        prob_under=prob_under,
        line=line,
        line_source=line_source,
        house_odds_over=house_odds_over,
        house_odds_under=house_odds_under,
        spread_line=spread_line,
    )

    if model_mean is not None:
        rec.model_mean = round(float(model_mean), 1)
        rec.point_spread_edge = round(float(model_mean) - line, 1)

    # Cuotas justas puras del modelo
    rec.fair_odds_over = round(1.0 / prob_over, 3) if prob_over > 0.01 else 99.0
    rec.fair_odds_under = round(1.0 / prob_under, 3) if prob_under > 0.01 else 99.0

    # Desmargenado de cuotas (No-Vig / True Market Probability)
    if house_odds_over and house_odds_under and house_odds_over > 1.0 and house_odds_under > 1.0:
        inv_o = 1.0 / house_odds_over
        inv_u = 1.0 / house_odds_under
        sum_inv = inv_o + inv_u
        rec.house_vig_pct = round((sum_inv - 1.0) * 100.0, 2)
        rec.novig_prob_over = round(inv_o / sum_inv, 4)
        rec.novig_prob_under = round(inv_u / sum_inv, 4)
        rec.alpha_over = round(prob_over - rec.novig_prob_over, 4)
        rec.alpha_under = round(prob_under - rec.novig_prob_under, 4)

    # Expected Value contra cuotas de la casa
    if house_odds_over and house_odds_over > 1.0:
        rec.ev_over = round(prob_over * house_odds_over - 1.0, 4)
        rec.house_edge_over = rec.ev_over
    else:
        rec.ev_over = 0.0

    if house_odds_under and house_odds_under > 1.0:
        rec.ev_under = round(prob_under * house_odds_under - 1.0, 4)
        rec.house_edge_under = rec.ev_under
    else:
        rec.ev_under = 0.0

    # Señal de ritmo observado vs promedio de liga
    if league_avg_pace_per_min > 0:
        pace_ratio = signals.pace_observed_per_min / league_avg_pace_per_min
        if pace_ratio > 1.07:
            rec.pace_signal = "ALTO"
        elif pace_ratio < 0.93:
            rec.pace_signal = "BAJO"
        else:
            rec.pace_signal = "NORMAL"
    else:
        rec.pace_signal = "NORMAL"

    # Señal de momentum
    if abs(signals.momentum_score) < 2:
        rec.momentum_signal = "EQUILIBRADO"
    elif signals.momentum_score > 0:
        rec.momentum_signal = "LOCAL_DOMINANDO"
    else:
        rec.momentum_signal = "VISITANTE_DOMINANDO"

    # ─── Mercados de Spread / Hándicap en Vivo ───
    if simulated_margins is not None and len(simulated_margins) > 0:
        calc_spread = spread_line if spread_line is not None else 0.0
        cov_home = float(np.mean(simulated_margins + calc_spread > 0))
        cov_away = float(np.mean(simulated_margins + calc_spread < 0))
        rec.spread_cover_prob_home = round(cov_home, 4)
        rec.spread_cover_prob_away = round(cov_away, 4)

        mean_sim_margin = float(np.mean(simulated_margins))
        rec.spread_edge_pts = round(mean_sim_margin - (-calc_spread), 1)

        rec.spread_fair_odds_home = round(1.0 / cov_home, 2) if cov_home > 0.02 else 50.0
        rec.spread_fair_odds_away = round(1.0 / cov_away, 2) if cov_away > 0.02 else 50.0

        odd_sp_h = house_odds_spread_home or 1.90
        odd_sp_a = house_odds_spread_away or 1.90
        rec.spread_ev_home = round(cov_home * odd_sp_h - 1.0, 4)
        rec.spread_ev_away = round(cov_away * odd_sp_a - 1.0, 4)

        if cov_home >= 0.53 or rec.spread_edge_pts >= 1.5:
            rec.spread_direction = "LOCAL"
            chosen_sp_ev = rec.spread_ev_home
            chosen_sp_edge = rec.spread_edge_pts
        elif cov_away >= 0.53 or rec.spread_edge_pts <= -1.5:
            rec.spread_direction = "VISITANTE"
            chosen_sp_ev = rec.spread_ev_away
            chosen_sp_edge = -rec.spread_edge_pts
        else:
            rec.spread_direction = "NEUTRO"
            chosen_sp_ev = max(rec.spread_ev_home, rec.spread_ev_away)
            chosen_sp_edge = abs(rec.spread_edge_pts)

        if rec.spread_direction != "NEUTRO" and chosen_sp_ev >= 0.04 and chosen_sp_edge >= 2.5:
            rec.spread_grade = "GRADO A+ (MÁXIMO VALOR)"
        elif rec.spread_direction != "NEUTRO" and chosen_sp_ev >= 0.02 and chosen_sp_edge >= 1.5:
            rec.spread_grade = "GRADO A (FUERTE)"
        elif rec.spread_direction != "NEUTRO" and chosen_sp_ev >= 0.01:
            rec.spread_grade = "GRADO B (MODERADO)"
        else:
            rec.spread_grade = "SIN EDGE"
    elif projected_margin_dl is not None:
        rec.spread_edge_pts = round(float(projected_margin_dl), 1)
        rec.spread_direction = "LOCAL" if projected_margin_dl > 2.0 else ("VISITANTE" if projected_margin_dl < -2.0 else "NEUTRO")

    # ─── Mercados de Moneyline (Ganador Directo) ───
    if simulated_margins is not None and len(simulated_margins) > 0:
        ml_h = float(np.mean(simulated_margins > 0))
        ml_a = float(np.mean(simulated_margins < 0))
        rec.moneyline_prob_home = round(ml_h, 4)
        rec.moneyline_prob_away = round(ml_a, 4)
        rec.moneyline_fair_odds_home = round(1.0 / ml_h, 2) if ml_h > 0.01 else 99.0
        rec.moneyline_fair_odds_away = round(1.0 / ml_a, 2) if ml_a > 0.01 else 99.0

        if house_odds_ml_home and house_odds_ml_home > 1.0:
            rec.moneyline_ev_home = round(ml_h * house_odds_ml_home - 1.0, 4)
        if house_odds_ml_away and house_odds_ml_away > 1.0:
            rec.moneyline_ev_away = round(ml_a * house_odds_ml_away - 1.0, 4)

        if ml_h >= 0.55:
            rec.moneyline_direction = "LOCAL"
            ml_ev = rec.moneyline_ev_home
        elif ml_a >= 0.55:
            rec.moneyline_direction = "VISITANTE"
            ml_ev = rec.moneyline_ev_away
        else:
            rec.moneyline_direction = "NEUTRO"
            ml_ev = max(rec.moneyline_ev_home, rec.moneyline_ev_away)

        if rec.moneyline_direction != "NEUTRO" and ml_ev >= 0.05:
            rec.moneyline_grade = "GRADO A"
        elif rec.moneyline_direction != "NEUTRO" and ml_ev >= 0.02:
            rec.moneyline_grade = "GRADO B"
        else:
            rec.moneyline_grade = "SIN EDGE"

    # Razones analíticas
    reasons = []
    if model_mean is not None and abs(rec.point_spread_edge) >= 0.5:
        reasons.append(f"📏 Point Spread Edge: {rec.point_spread_edge:+.1f} pts de margen (Modelo {rec.model_mean:.1f} vs Casa {line:.1f})")

    if rec.house_vig_pct > 0:
        reasons.append(f"🛡️ Desmargenado No-Vig: Margen casa {rec.house_vig_pct:.1f}% | Alpha Over: {rec.alpha_over*100:+.1f}%, Under: {rec.alpha_under*100:+.1f}%")

    if rec.pace_signal == "ALTO":
        reasons.append(f"⚡ Ritmo ALTO ({signals.pace_observed_per_min:.1f} pts/min) → apunta a OVER")
    elif rec.pace_signal == "BAJO":
        reasons.append(f"🐢 Ritmo BAJO ({signals.pace_observed_per_min:.1f} pts/min) → apunta a UNDER")

    triple_combined = (signals.triple_pct_a + signals.triple_pct_b) / 2.0
    if triple_combined > 0.32:
        reasons.append(f"🎯 Alto % triples ({triple_combined*100:.0f}%) → mayor varianza")
    elif triple_combined < 0.20 and signals.total_plays >= 5:
        reasons.append(f"🏋 Bajo % triples ({triple_combined*100:.0f}%), juego físico → menor varianza")

    if signals.run_pts >= 7:
        reasons.append(f"🔥 Racha activa: {signals.run_pts} pts de {signals.run_team} sin respuesta")

    if signals.recent_heat >= 8:
        reasons.append(f"🌡 Calor anotador ALTO ({signals.recent_heat} pts en últimas 6 jugadas)")
    elif signals.recent_heat <= 3 and signals.total_plays >= 6:
        reasons.append(f"❄ Ritmo frío ({signals.recent_heat} pts en últimas 6 jugadas)")

    if rec.ev_over > 0.03 and house_odds_over:
        reasons.append(f"💰 Valor positivo en OVER: EV +{rec.ev_over*100:.1f}% (casa {house_odds_over:.2f} vs modelo {rec.fair_odds_over:.2f})")
    if rec.ev_under > 0.03 and house_odds_under:
        reasons.append(f"💰 Valor positivo en UNDER: EV +{rec.ev_under*100:.1f}% (casa {house_odds_under:.2f} vs modelo {rec.fair_odds_under:.2f})")

    if rec.spread_direction != "NEUTRO" and rec.spread_grade != "SIN EDGE":
        reasons.append(f"🎯 Hándicap con Valor: {rec.spread_direction} (Edge: {rec.spread_edge_pts:+.1f} pts | {rec.spread_grade})")

    rec.reasons = reasons

    # Clasificación Profesional de la Apuesta (Point Spread Edge + EV + Alpha)
    if prob_over > prob_under and (prob_over >= 0.52 or rec.point_spread_edge >= 1.5):
        rec.direction = "OVER"
        chosen_prob = prob_over
        chosen_ev = rec.ev_over
        chosen_alpha = rec.alpha_over
        edge_pts = rec.point_spread_edge
    elif prob_under > prob_over and (prob_under >= 0.52 or rec.point_spread_edge <= -1.5):
        rec.direction = "UNDER"
        chosen_prob = prob_under
        chosen_ev = rec.ev_under
        chosen_alpha = rec.alpha_under
        edge_pts = -rec.point_spread_edge
    else:
        rec.direction = "NEUTRO"
        chosen_prob = max(prob_over, prob_under)
        chosen_ev = max(rec.ev_over, rec.ev_under)
        chosen_alpha = max(rec.alpha_over, rec.alpha_under)
        edge_pts = abs(rec.point_spread_edge)

    # Criterio Cuantitativo de Grado de Apuesta y Calibración de Confianza
    rem_min = float(minutes_remaining) if minutes_remaining is not None else 0.0
    # Factor de moderación cuando aún restan más de 5 minutos de partido
    time_damping = 0.50 if rem_min > 5.0 else (0.75 if rem_min > 3.0 else 1.0)
    max_conf_cap = 88.0 if rem_min > 6.0 else (92.0 if rem_min > 3.0 else 96.0)

    if rec.direction != "NEUTRO" and edge_pts >= 4.5 and (chosen_ev >= 0.05 or chosen_alpha >= 0.045) and chosen_prob >= 0.56:
        rec.bet_grade = "GRADO A+ (MÁXIMO VALOR)"
        rec.recommended_units = 2.0
        rec.signal_color = "🟢"
        raw_conf = chosen_prob * 100.0 + (edge_pts * 1.0 * time_damping)
        rec.confidence_pct = round(min(max_conf_cap, raw_conf), 1)
    elif rec.direction != "NEUTRO" and edge_pts >= 3.0 and (chosen_ev >= 0.03 or chosen_alpha >= 0.025) and chosen_prob >= 0.535:
        rec.bet_grade = "GRADO A (FUERTE)"
        rec.recommended_units = 1.5
        rec.signal_color = "🟢"
        raw_conf = chosen_prob * 100.0 + (edge_pts * 0.8 * time_damping)
        rec.confidence_pct = round(min(min(90.0, max_conf_cap), raw_conf), 1)
    elif rec.direction != "NEUTRO" and edge_pts >= 1.5 and (chosen_ev >= 0.015 or chosen_alpha >= 0.01) and chosen_prob >= 0.52:
        rec.bet_grade = "GRADO B (MODERADO)"
        rec.recommended_units = 0.75
        rec.signal_color = "🟡"
        raw_conf = chosen_prob * 100.0 + (edge_pts * 0.5 * time_damping)
        rec.confidence_pct = round(min(min(80.0, max_conf_cap), raw_conf), 1)
    else:
        rec.bet_grade = "SIN EDGE / EVITAR"
        rec.recommended_units = 0.0
        rec.signal_color = "🔴"
        rec.confidence_pct = round(chosen_prob * 100.0, 1)
        if rec.direction == "NEUTRO" or edge_pts < 1.0:
            rec.direction = "NEUTRO"

    # Análisis del monto que paga la casa y generación de propuesta de apuesta ficticia
    chosen_odds = house_odds_over if rec.direction == "OVER" else (
        house_odds_under if rec.direction == "UNDER" else (
            max(house_odds_over or 0.0, house_odds_under or 0.0) or None
        )
    )

    if chosen_odds and chosen_odds > 1.0:
        rec.payout_ratio = round(chosen_odds, 2)
        # Pago elevado: cuota >= 2.10 con probabilidad sólida (>= 38%) y EV positivo
        if chosen_odds >= 2.10 and chosen_prob >= 0.38 and chosen_ev >= 0.02:
            rec.is_high_payout = True
            rec.reasons.append(
                f"🔥 Pago elevado detectado: Cuota {chosen_odds:.2f} (+{(chosen_odds-1)*100:.0f}% retorno) con EV {chosen_ev*100:+.1f}%"
            )

    if rec.direction != "NEUTRO" and chosen_odds and chosen_odds > 1.0:
        rule_name = "PAGO_ELEVADO" if rec.is_high_payout else ("ALTO_EV" if chosen_ev >= 0.06 else "VALOR_MODELO")
        rec.suggested_paper_bet = {
            "tipo": rec.direction,
            "linea": line,
            "cuota": round(chosen_odds, 2),
            "monto": 100000.0,  # 100.000 Gs.
            "prob_modelo": round(chosen_prob, 4),
            "ev": round(chosen_ev, 4),
            "regla": rule_name,
            "grado": rec.bet_grade,
            "spread_edge": round(edge_pts, 1),
            "es_pago_elevado": rec.is_high_payout
        }

    # ─── Detección de Sobre-reacción y Política de Parada Óptima ───
    if signals.run_pts >= 7 or signals.recent_heat >= 9:
        rec.overreaction_detected = True
        rec.reasons.append("⚡ Sobre-reacción del mercado por racha activa en vivo")

    has_any_edge = (rec.bet_grade in ["GRADO A+ (MÁXIMO VALOR)", "GRADO A (FUERTE)", "GRADO B (MODERADO)"] or
                    rec.spread_grade in ["GRADO A+ (MÁXIMO VALOR)", "GRADO A (FUERTE)", "GRADO B (MODERADO)"])

    if has_any_edge:
        rec.optimal_stopping_action = "ENTRAR_AHORA"
    else:
        if rec.overreaction_detected:
            rec.optimal_stopping_action = "ESPERAR_MEJOR_LINEA"
        else:
            rec.optimal_stopping_action = "PASAR"

    # ─── Explicabilidad XAI (Pesos de Atención Normalizados) ───
    if xai_factors and isinstance(xai_factors, dict) and len(xai_factors) > 0:
        rec.xai_factors = xai_factors
    else:
        atn_mom = round(min(1.0, abs(signals.momentum_score) / 10.0 + (0.3 if signals.run_pts >= 6 else 0.1)), 2)
        atn_lin = 0.25
        atn_3p = round(min(1.0, triple_combined * 2.0), 2)
        rem_pct = round(max(0.1, min(1.0, (minutes_remaining if minutes_remaining is not None else 24.0) / 48.0)), 2)
        rec.xai_factors = {
            "atencion_momentum": atn_mom,
            "impacto_alineaciones": atn_lin,
            "varianza_triples": atn_3p,
            "factor_tiempo_restante": rem_pct
        }

    return rec



def kelly_fraction(prob: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """
    Calcula la fracción Kelly para el tamaño de apuesta óptimo (Kelly fraccionado al 25%).

    Returns:
        Fracción del bankroll a apostar (0-1). 0 si sin edge.
    """
    if decimal_odds <= 1.0 or prob <= 0:
        return 0.0
    b = decimal_odds - 1.0
    q = 1.0 - prob
    kelly = (b * prob - q) / b
    return round(max(0.0, kelly * fraction), 4)
