export interface Tournament {
  key: string;
  name: string;
  quarter_duration: number;
  team_avg_quarter_min: number;
  team_avg_quarter_max: number;
  total_game_duration: number;
  total_game_avg: number;
  description: string;
  league_pace: number;
  league_off_rating: number;
  typical_total_std: number;
  home_court_advantage: number;
}

export interface MarcadorCuarto {
  cuarto: number;
  pts_local: number;
  pts_visitante: number;
}

export interface Partido {
  id: number;
  torneo: string;
  equipo_local: string;
  equipo_visitante: string;
  estado: 'en_curso' | 'finalizado';
  cuarto_actual: number;
  min_restantes: number;
  seg_restantes: number;
  notas?: string;
  creado_en: string;
  actualizado_en: string;
  total_local: number;
  total_visitante: number;
  marcadores?: MarcadorCuarto[];
  pts_local_final?: number;
  pts_visitante_final?: number;
  total_final?: number;
  lineup_local?: number[];
  lineup_visitante?: number[];
  fouls_local?: number;
  fouls_visitante?: number;
}

export interface Jugador {
  id: number;
  nba_id?: number;
  nombre: string;
  equipo: string;
  posicion: string;
  dorsal?: number | string;
  es_titular: boolean;
  minutos_promedio: number;
  pts_promedio: number;
  off_rating: number;
  def_rating: number;
  usg_pct: number;
  ts_pct: number;
  bpm: number;
  box_plus_minus?: number;
  true_shooting_pct?: number;
  usage_rate?: number;
}

export interface TimelinePoint {
  minute: number;
  quarter: number;
  actual_total?: number;
  median_total?: number;
  p05_total?: number;
  p95_total?: number;
  baseline_total?: number;
  [key: string]: any;
}

export interface SimulationResult {
  team_a_mean: number;
  team_a_median: number;
  team_a_min: number;
  team_a_max: number;
  team_a_p05: number;
  team_a_p10: number;
  team_a_p90: number;
  team_a_p95: number;

  team_b_mean: number;
  team_b_median: number;
  team_b_min: number;
  team_b_max: number;
  team_b_p05: number;
  team_b_p10: number;
  team_b_p90: number;
  team_b_p95: number;

  total_mean: number;
  total_median: number;
  total_std: number;
  total_min: number;
  total_max: number;
  total_p025: number;
  total_p05: number;
  total_p10: number;
  total_p25: number;
  total_p75: number;
  total_p90: number;
  total_p95: number;
  total_p975: number;

  win_prob_a: number;
  win_prob_b: number;
  overtime_prob: number;

  prior_pace_per_min: number;
  observed_pace_per_min: number;
  posterior_pace_per_min: number;
  shrinkage_weight: number;

  pre_game_total: number;
  match_pace_expected: number;
  eff_a_expected: number;
  eff_b_expected: number;

  regulation_mean: number;
  overtime_points_avg: number;
  overtime_count: number;

  shooting_regression_applied: number;
  three_point_luck_delta: number;

  dl_active: boolean;
  dl_delta_pace: number;
  dl_pace_multiplier: number;
  dl_uncertainty_pts: number;
  dl_win_prob?: number;
  dl_momentum_label: string;
  dl_details: string;
  dl_spread_margin?: number;
  dl_spread_std?: number;
  dl_xai_factors?: Record<string, number>;

  spread_mean?: number;
  spread_std?: number;
  prob_over?: number;
  prob_under?: number;
  prob_spread_home?: number;
  prob_spread_away?: number;
  prob_ml_home?: number;
  prob_ml_away?: number;
  optimal_stopping_action?: string;
  overreaction_detected?: boolean;

  linea_apuesta?: number;
  spread_line?: number;
  timeline?: TimelinePoint[];
  histogram_totals?: number[];
}

export interface SpreadRecommendation {
  spread_line?: number;
  direction: string;
  grade: string;
  edge_pts: number;
  cover_prob_home: number;
  cover_prob_away: number;
  fair_odds_home: number;
  fair_odds_away: number;
  ev_home: number;
  ev_away: number;
}

export interface MoneylineRecommendation {
  direction: string;
  grade: string;
  prob_home: number;
  prob_away: number;
  fair_odds_home: number;
  fair_odds_away: number;
  ev_home: number;
  ev_away: number;
}

export interface LiveBettingRecommendation {
  direction: string;
  bet_grade: string;
  signal_color: string;
  confidence_pct: number;
  prob_over: number;
  prob_under: number;
  point_spread_edge: number;
  model_mean: number;
  ev_over: number;
  ev_under: number;
  ev_elegido: number;
  fair_odds_over: number;
  fair_odds_under: number;
  house_vig_pct: number;
  novig_prob_over: number;
  novig_prob_under: number;
  alpha_over: number;
  alpha_under: number;
  kelly_fraction: number;
  recommended_units: number;
  is_high_payout: boolean;
  reasons: string[];
  pace_signal: string;
  momentum_signal: string;
  spread_recommendation?: SpreadRecommendation;
  moneyline_recommendation?: MoneylineRecommendation;
  optimal_stopping_action?: string;
  overreaction_detected?: boolean;
  xai_factors?: Record<string, number>;
  suggested_paper_bet?: any;
}

export interface Apuesta {
  id: number;
  partido_id: number;
  tipo_apuesta: string;
  linea: number;
  cuota: number;
  monto: number;
  prob_modelo?: number;
  ev_estimado?: number;
  kelly_sugerido?: number;
  momento_cuarto?: number;
  minuto_partido?: number;
  marcador_momento?: string;
  es_ficticia: boolean;
  resultado: 'PENDIENTE' | 'GANADA' | 'PERDIDA' | 'PUSH';
  ganancia_neta?: number;
  notas?: string;
  grado_apuesta?: string;
  spread_edge?: number;
  equipo_apostado?: string;
  linea_cierre_casa?: number;
  cuota_cierre_casa?: number;
  clv_delta_pts?: number;
  clv_beat_ratio?: number;
  creado_en?: string;
  equipo_local?: string;
  equipo_visitante?: string;
  torneo?: string;
}

export interface ResumenApuestas {
  total_apuestas: number;
  ganadas: number;
  perdidas: number;
  pushes: number;
  pendientes: number;
  total_apostado: number;
  retorno_total: number;
  beneficio_neto: number;
  roi_porcentaje: number;
  win_rate: number;
}

export interface Hito {
  id: number;
  partido_id: number;
  nombre_hito: string;
  cuarto_snapshot: number;
  minutos_jugados: number;
  pts_local_actual: number;
  pts_visitante_actual: number;
  total_actual: number;
  total_proyectado: number;
  total_mediana: number;
  total_p05: number;
  total_p95: number;
  prob_victoria_local: number;
  prob_over?: number;
  prob_under?: number;
  linea_apuesta?: number;
  cuota_over?: number;
  cuota_under?: number;
  guardado_en?: string;
}

// ─── Forebet vs Aposta.la Value Betting Types ──────────────────────────────
export interface ForebetData {
  tournament: string;
  home: string;
  away: string;
  dateTime: string;
  p1: number | null;
  px: number | null;
  p2: number | null;
  pred: string;
  exactScore: string;
  avgGoals: number | null;
  fbOdd1: number | null;
  fbOddX: number | null;
  fbOdd2: number | null;
}

export interface ApostaData {
  id: number;
  home: string;
  away: string;
  league: string;
  start: string;
  state: string;
  odds: Record<string, number>;
}

export interface OutcomeEvaluation {
  pick: string;
  prob_fb_pct: number;
  cuota_aposta: number;
  prob_implied_pct: number;
  ev_pct: number;
  edge_pct: number;
  kelly_pct: number;
  is_value: boolean;
  is_high_value: boolean;
}

export interface ForebetCruceItem {
  forebet: ForebetData;
  aposta: ApostaData;
  evaluations: OutcomeEvaluation[];
  best_pick: OutcomeEvaluation | null;
  has_value: boolean;
  is_high_value: boolean;
  trap_favorite: boolean;
}

export interface ForebetCruceSummary {
  forebet_matches_found: number;
  aposta_events_available: number;
  total_matched: number;
  total_value_bets: number;
  high_value_bets: number;
  best_opportunity: string | null;
  best_ev: number | null;
}

export interface ForebetCruceResponse {
  cached: boolean;
  last_updated: number;
  summary: ForebetCruceSummary;
  total_items: number;
  items: ForebetCruceItem[];
}

