"""
🏀 Predictor Probabilístico Avanzado de Baloncesto
Aplicación Interactiva en Streamlit para cálculo de proyecciones en vivo,
análisis de ritmo por cuarto, simulación Monte Carlo y probabilidades Over/Under.
"""

import os
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import threading
import time as _time

try:
    from model.scraper import scrape_aposta_la, LiveMatchData
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

from model.database import (
    crear_partido,
    actualizar_partido,
    listar_partidos,
    obtener_partido,
    eliminar_partido,
    guardar_snapshot,
    listar_snapshots,
    guardar_jugadas,
    registrar_apuesta,
    listar_apuestas,
    actualizar_resultado_apuesta,
    actualizar_apuesta,
    eliminar_apuesta,
    resumen_apuestas,
    calcular_metricas_rendimiento_apuestas,
    registrar_hito,
    listar_hitos,
    finalizar_partido_y_liquidar,
    listar_apuestas_ficticias,
    obtener_calibracion_activa,
    guardar_calibracion,
)

from model.learning import (
    calibrar_probabilidad,
    cotejar_hitos_partido,
    clasificar_pago_casa,
    ejecutar_auto_entrenamiento_ml,
)

from model.live_betting import (
    analyze_plays,
    get_live_betting_recommendation,
    kelly_fraction,
)

from model.audio_alerts import (
    BettingAlert,
    generate_sound_wav,
    evaluate_betting_alert,
    render_betting_alert_ui,
    SOUND_PRESETS,
    TRIGGER_MODES,
)

from model.config import (
    TournamentConfig,
    TOURNAMENT_PRESETS,
    QUARTER_PACE_FACTORS,
    CLUTCH_THRESHOLD_MINUTES,
    CLUTCH_POINT_DIFF_CLOSE,
    CLUTCH_SURGE_MULTIPLIER,
    BLOWOUT_DIFF_THRESHOLD,
    GARBAGE_TIME_Q4_THRESHOLD,
    BLOWOUT_DECAY_MULTIPLIER,
    FOUR_FACTORS_WEIGHTS,
    FOUR_FACTORS_BENCHMARKS
)
from model.analytics import (
    TeamProfile,
    calculate_four_factors_off_rating,
    estimate_pace_from_boxscore,
    project_pre_game_matchup,
    calculate_matchup_pace,
    calculate_cross_efficiency
)
from model.engine import BasketballPredictor, SimulationSummary

# Configuración de página Streamlit
st.set_page_config(
    page_title="Predictor Probabilístico de Baloncesto",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Resetear control de audio para el ciclo actual de renderizado
st.session_state["_alert_audio_played_in_current_render"] = False

# Estilos CSS modernos (Dark Glassmorphism deportivo)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }

    /* Contenedor de métricas */
    .metric-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.85) 0%, rgba(18, 21, 33, 0.95) 100%);
        border: 1px solid rgba(255, 138, 0, 0.2);
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(10px);
        margin-bottom: 12px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: rgba(255, 138, 0, 0.5);
        transform: translateY(-2px);
    }
    .metric-title {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #9aa5b1;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #f7fafc;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1.1;
    }
    .metric-subtext {
        font-size: 0.82rem;
        color: #cbd5e0;
        margin-top: 6px;
    }
    
    /* Marcador digital */
    .scoreboard-container {
        background: radial-gradient(circle at center, #1b2438 0%, #0d121d 100%);
        border: 2px solid #ff7700;
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 0 30px rgba(255, 119, 0, 0.18);
        margin-bottom: 24px;
    }
    .team-name {
        font-size: 1.35rem;
        font-weight: 700;
        color: #e2e8f0;
        letter-spacing: 0.5px;
    }
    .team-score {
        font-size: 3.6rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: #ffaa00;
        text-shadow: 0 0 15px rgba(255, 170, 0, 0.4);
    }
    .game-clock-badge {
        display: inline-block;
        background: #e53e3e;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
        letter-spacing: 1.5px;
        box-shadow: 0 0 12px rgba(229, 62, 62, 0.5);
    }
    
    .badge-q {
        background: rgba(49, 130, 206, 0.25);
        color: #63b3ed;
        border: 1px solid #3182ce;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# SIDEBAR: CONFIGURACIÓN GENERAL Y TORNEO
# ==========================================
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1546519638-68e109498ffc?w=600&auto=format&fit=crop&q=80", width="stretch")
    st.title("🏀 Parámetros")

    # ==========================================
    # PANEL: CARGA AUTOMÁTICA DESDE URL LIVE
    # ==========================================
    st.markdown("---")
    st.subheader("🌐 Cargar desde URL en Vivo")
    st.caption("Pegá el link de aposta.la para sincronizar el marcador y cuotas en tiempo real.")

    live_url = st.text_input(
        "URL del partido:",
        value=st.session_state.get("live_url", ""),
        placeholder="https://aposta.la/bets#event/live/XXXXXXXXXX",
        key="live_url_input",
        help="Soporta URLs de aposta.la con eventos en vivo."
    )

    col_scr1, col_scr2 = st.columns([2, 1])
    with col_scr1:
        auto_refresh_sec = st.selectbox(
            "Auto-actualizar cada:",
            options=[0, 15, 30, 60, 120],
            format_func=lambda x: "Desactivado" if x == 0 else f"{x} segundos",
            index=0,
            key="auto_refresh_sel"
        )
    with col_scr2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔄 Cargar", width="stretch", key="btn_fetch_live")

    # Auto-refresh activo en segundo plano mediante st_autorefresh
    is_auto_refresh = False
    if auto_refresh_sec > 0 and live_url and AUTOREFRESH_AVAILABLE:
        refresh_tick = st_autorefresh(interval=auto_refresh_sec * 1000, key="live_auto_refresh_ticker")
        if refresh_tick > 0:
            fetch_btn = True
            is_auto_refresh = True

    # Ejecutar scraping
    if fetch_btn and live_url:
        if not SCRAPER_AVAILABLE:
            st.sidebar.error("❌ Módulo scraper no disponible.")
        else:
            with st.sidebar:
                with st.spinner("Consultando evento en vivo..."):
                    live_data: LiveMatchData = scrape_aposta_la(live_url)

            if live_data.status == "error":
                st.sidebar.error(f"❌ {live_data.error_msg}")
            else:
                # Guardar en session_state para ser usados en todo el app
                st.session_state["scraped_team_a"] = live_data.team_home
                st.session_state["scraped_team_b"] = live_data.team_away
                st.session_state["scraped_q"] = live_data.quarter
                st.session_state["scraped_min"] = live_data.clock_min
                st.session_state["scraped_sec"] = live_data.clock_sec
                st.session_state["scraped_scores"] = live_data.quarter_scores
                st.session_state["scraped_score_home"] = live_data.score_home
                st.session_state["scraped_score_away"] = live_data.score_away
                st.session_state["scraped_odds_line"] = live_data.odds_line
                st.session_state["scraped_odds_over"] = live_data.odds_over
                st.session_state["scraped_odds_under"] = live_data.odds_under
                st.session_state["scraped_plays"] = live_data.plays
                st.session_state["scraped_run_team"] = live_data.current_run_team
                st.session_state["scraped_run_pts"] = live_data.current_run_pts
                st.session_state["live_url"] = live_url
                st.session_state["scraped_league"] = getattr(live_data, "league_name", "")
                st.session_state["scraped_quarter_duration"] = getattr(live_data, "quarter_duration", 10)
                st.session_state["_last_refresh"] = _time.time()

                # Auto-sincronizar el tipo de torneo según la reglamentación detectada (NBL vs FIBA vs NBA)
                detected_duration = getattr(live_data, "quarter_duration", 10)
                detected_key = getattr(live_data, "tournament_key", "FIBA")
                is_new_url = (st.session_state.get("_last_synced_url") != live_url)
                if is_new_url or not is_auto_refresh or "torneo_preset_sel" not in st.session_state:
                    if detected_key == "NBL":
                        st.session_state["torneo_preset_sel"] = "NBL Australia (10 min/cuarto)"
                    elif detected_duration == 12 or detected_key == "NBA":
                        st.session_state["torneo_preset_sel"] = "NBA (12 min/cuarto)"
                    else:
                        st.session_state["torneo_preset_sel"] = "FIBA / Euroliga / Ligas Locales (10 min/cuarto)"
                st.session_state["_last_synced_url"] = live_url

                # Sincronizar inputs de cuartos
                for qi, (pts_h, pts_a) in enumerate(live_data.quarter_scores):
                    st.session_state[f"q{qi+1}_a"] = int(pts_h)
                    st.session_state[f"q{qi+1}_b"] = int(pts_a)

                # Sincronizar nombres y reloj para widgets
                st.session_state["team_a_name_input"] = live_data.team_home
                st.session_state["team_b_name_input"] = live_data.team_away
                st.session_state["ctrl_rem_min"] = int(live_data.clock_min)
                st.session_state["ctrl_rem_sec"] = int(live_data.clock_sec)
                q_opts = ["1° Cuarto (Q1)", "2° Cuarto (Q2)", "3° Cuarto (Q3)", "4° Cuarto (Q4)", "Partido Finalizado"]
                target_qi = min(max(0, live_data.quarter - 1), 4)
                st.session_state["ctrl_current_q"] = q_opts[target_qi]

                if live_data.odds_line is not None:
                    # Sincronizar solo si la línea en vivo varió respecto a la última registrada
                    if st.session_state.get("_last_synced_line") != float(live_data.odds_line):
                        st.session_state["direct_bet_input"] = float(live_data.odds_line)
                        st.session_state["_last_synced_line"] = float(live_data.odds_line)

                league_info = f" ({live_data.league_name})" if getattr(live_data, "league_name", "") else ""
                st.sidebar.success(
                    f"✅ Conectado{league_info}: **{live_data.team_home}** {live_data.score_home} – "
                    f"{live_data.score_away} **{live_data.team_away}**"
                )

    # Mostrar estado actual y botón de desconectar
    if st.session_state.get("scraped_team_a"):
        st.sidebar.markdown(
            f"""
            <div style="background: rgba(49, 130, 206, 0.15); border: 1px solid #3182ce; border-radius: 8px; padding: 8px 12px; margin-top: 10px;">
                <div style="font-size: 0.8rem; color: #63b3ed; font-weight: 700; text-transform: uppercase;">📡 Conectado en Vivo</div>
                <div style="font-size: 0.95rem; color: #fff; font-weight: 600; margin-top: 2px;">
                    {st.session_state.get('scraped_team_a')} {st.session_state.get('scraped_score_home')} – {st.session_state.get('scraped_score_away')} {st.session_state.get('scraped_team_b')}
                </div>
                <div style="font-size: 0.8rem; color: #a0aec0; margin-top: 2px;">
                    Q{st.session_state.get('scraped_q', 1)} | {st.session_state.get('scraped_min', 0):02d}:{st.session_state.get('scraped_sec', 0):02d}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.sidebar.button("⏹️ Desvincular Link en Vivo", width="stretch", key="btn_clear_live"):
            for k in [
                "live_url", "scraped_team_a", "scraped_team_b", "scraped_q", 
                "scraped_min", "scraped_sec", "scraped_scores", "scraped_score_home", 
                "scraped_score_away", "scraped_odds_line", "scraped_odds_over", 
                "scraped_odds_under", "scraped_plays", "scraped_run_team", "scraped_run_pts",
                "scraped_league", "scraped_quarter_duration",
                "_last_synced_line", "_last_synced_url", "ctrl_current_q", 
                "ctrl_rem_min", "ctrl_rem_sec", "team_a_name_input", "team_b_name_input"
            ]:
                st.session_state.pop(k, None)
            st.rerun()

    # Selección de Torneo (Por defecto FIBA para evitar proyectar 48 min de NBA en ligas de 40 min)
    torneo_opciones = [
        "NBL Australia (10 min/cuarto)",
        "FIBA / Euroliga / Ligas Locales (10 min/cuarto)",
        "NBA (12 min/cuarto)",
        "NCAA Femenil (10 min/cuarto)",
        "Personalizado"
    ]
    if "torneo_preset_sel" not in st.session_state:
        st.session_state["torneo_preset_sel"] = "FIBA / Euroliga / Ligas Locales (10 min/cuarto)"
    elif st.session_state["torneo_preset_sel"] not in torneo_opciones:
        if "NBL" in st.session_state["torneo_preset_sel"]:
            st.session_state["torneo_preset_sel"] = "NBL Australia (10 min/cuarto)"
        elif "NBA" in st.session_state["torneo_preset_sel"]:
            st.session_state["torneo_preset_sel"] = "NBA (12 min/cuarto)"
        elif "NCAA" in st.session_state["torneo_preset_sel"]:
            st.session_state["torneo_preset_sel"] = "NCAA Femenil (10 min/cuarto)"
        else:
            st.session_state["torneo_preset_sel"] = "FIBA / Euroliga / Ligas Locales (10 min/cuarto)"

    torneo_sel = st.selectbox("Tipo de Torneo / Competencia:", torneo_opciones, key="torneo_preset_sel")

    if torneo_sel.startswith("NBL"):
        cfg_actual = TOURNAMENT_PRESETS["NBL"]
        duracion_defecto = 10
        pts_min_def, pts_max_def = 22.0, 24.0
    elif torneo_sel.startswith("NBA"):
        cfg_actual = TOURNAMENT_PRESETS["NBA"]
        duracion_defecto = 12
        pts_min_def, pts_max_def = 28.0, 29.0
    elif torneo_sel.startswith("FIBA"):
        cfg_actual = TOURNAMENT_PRESETS["FIBA"]
        duracion_defecto = 10
        pts_min_def, pts_max_def = 20.0, 22.0
    elif torneo_sel.startswith("NCAA"):
        cfg_actual = TOURNAMENT_PRESETS["NCAA_FEMENIL"]
        duracion_defecto = 10
        pts_min_def, pts_max_def = 16.0, 18.0
    else:
        cfg_actual = None
        duracion_defecto = 10
        pts_min_def, pts_max_def = 22.0, 24.0

    st.markdown("---")
    st.subheader("⚙️ Configuración Reglamentaria")

    # Duración de cuarto
    col_dur1, col_dur2 = st.columns(2)
    with col_dur1:
        quarter_duration = st.radio(
            "Minutos por cuarto:",
            [10, 12],
            index=0 if duracion_defecto == 10 else 1,
            key=f"q_dur_radio_{duracion_defecto}",
            help="12 minutos para NBA, 10 minutos para FIBA, Euroliga y ligas universitarias."
        )

    with col_dur2:
        num_sims = st.select_slider(
            "Iteraciones Monte Carlo:",
            options=[1000, 3000, 5000, 10000],
            value=10000,
            help="Número de partidos virtuales simulados (10,000 iteraciones garantiza máxima precisión en colas y percentiles)."
        )

    # Promedio de puntos por equipo
    st.markdown("**Promedio esperado por equipo (1 cuarto):**")
    col_pts1, col_pts2 = st.columns(2)
    with col_pts1:
        team_avg_min = st.number_input("Mínimo (pts):", min_value=10.0, max_value=40.0, value=float(pts_min_def), step=0.5)
    with col_pts2:
        team_avg_max = st.number_input("Máximo (pts):", min_value=10.0, max_value=40.0, value=float(pts_max_def), step=0.5)

    # Configuración de Torneo en Tiempo de Ejecución
    active_config = TournamentConfig(
        name=torneo_sel,
        quarter_duration=quarter_duration,
        team_avg_quarter_min=team_avg_min,
        team_avg_quarter_max=team_avg_max,
        description="Configuración activa",
        key="CUSTOM" if cfg_actual is None else cfg_actual.key,
        league_pace=cfg_actual.league_pace if cfg_actual else (99.5 if quarter_duration == 12 else 74.5),
        league_off_rating=cfg_actual.league_off_rating if cfg_actual else 110.0,
        typical_total_std=cfg_actual.typical_total_std if cfg_actual else (20.0 if quarter_duration == 12 else 15.5),
        home_court_advantage=cfg_actual.home_court_advantage if cfg_actual else 3.0,
        b2b_penalty_per_100=cfg_actual.b2b_penalty_per_100 if cfg_actual else 2.0
    )

    st.markdown("---")
    st.subheader("🧠 Deep Learning Residual")
    use_dl = st.toggle(
        "Activar Red Neuronal (Momentum)",
        value=True,
        key="use_deep_learning",
        help="Ajusta finamente el ritmo de simulación usando la red neuronal GRU entrenada con la secuencia de jugadas."
    )
    if st.button("🔄 Re-entrenar Red Neuronal", width="stretch", key="btn_train_dl_sidebar"):
        with st.spinner("Entrenando red Deep Learning con jugadas y física de juego..."):
            from model.deep_learning import entrenar_modelo_deep_learning
            res_dl = entrenar_modelo_deep_learning(epochs=30)
            if res_dl.get("exito"):
                st.success(f"✅ Red entrenada (Pérdida: {res_dl.get('perdida_final')})")
                st.rerun()
            else:
                st.error(res_dl.get("error", "Error"))

    st.markdown("---")
    st.subheader("🔔 Alertas Sonoras de Apuesta")
    st.caption("Emite una señal sonora y visual cuando el modelo detecte una oportunidad clara para apostar.")

    audio_alerts_enabled = st.toggle(
        "Activar Alertas Sonoras",
        value=True,
        key="cfg_audio_alerts_enabled",
        help="Reproduce un sonido de alerta cuando la probabilidad o edge cuantitativo superan tus criterios."
    )

    if audio_alerts_enabled:
        alert_threshold_pct = st.slider(
            "🎯 Umbral de Probabilidad (%):",
            min_value=60,
            max_value=98,
            value=int(st.session_state.get("cfg_alert_threshold_pct", 90)),
            step=1,
            key="cfg_alert_threshold_pct",
            help="Probabilidad mínima requerida (Over o Under) para emitir la alerta. (Por defecto 90%)."
        )

        alert_mode_key = st.selectbox(
            "Criterio de Activación:",
            options=list(TRIGGER_MODES.keys()),
            format_func=lambda k: TRIGGER_MODES[k],
            index=0,
            key="cfg_alert_trigger_mode",
            help="Selecciona si deseas alertar solo por probabilidad pura (>= umbral) o también cuando el modelo cuantitativo califique una oportunidad como Grado A/A+."
        )

        alert_sound_type = st.selectbox(
            "Tono de Alerta:",
            options=list(SOUND_PRESETS.keys()),
            format_func=lambda k: SOUND_PRESETS[k],
            index=0,
            key="cfg_alert_sound_type"
        )

        col_vol, col_test = st.columns([1.2, 1.0])
        with col_vol:
            alert_volume = st.slider(
                "Volumen:",
                min_value=10,
                max_value=100,
                value=int(st.session_state.get("cfg_alert_volume", 80)),
                step=10,
                key="cfg_alert_volume",
                format="%d%%"
            ) / 100.0

        with col_test:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔊 Probar", width="stretch", key="btn_test_audio_alert", help="Prueba el sonido y habilita permisos de audio en el navegador"):
                st.session_state["_play_test_sound"] = True

        alert_repeat_mode = st.selectbox(
            "Frecuencia de Alerta:",
            options=["ONCE_PER_EVENT", "EVERY_REFRESH"],
            format_func=lambda x: "Sonar 1 vez por oportunidad (Recomendado)" if x == "ONCE_PER_EVENT" else "Repetir en cada actualización",
            index=0,
            key="cfg_alert_repeat_mode",
            help="En partidos con auto-refresco activo, evita sonar cada pocos segundos si la misma oportunidad persiste."
        )

        if st.session_state.get("_play_test_sound"):
            try:
                test_wav = generate_sound_wav(sound_type=alert_sound_type, volume=alert_volume)
                st.audio(test_wav, format="audio/wav", autoplay=True)
                st.sidebar.success(f"🔊 Sonido de prueba emitido ({SOUND_PRESETS[alert_sound_type]})")
            except Exception as e:
                st.sidebar.error(f"Error al reproducir audio: {e}")
            st.session_state["_play_test_sound"] = False
    else:
        alert_threshold_pct = 90.0
        alert_mode_key = "PROB_ONLY"
        alert_sound_type = "chime"
        alert_volume = 0.8
        alert_repeat_mode = "ONCE_PER_EVENT"

    st.markdown("---")
    st.caption("ℹ️ **Pesos dinámicos por cuarto:**")
    st.caption(f"• **1Q / 2Q:** +{int((QUARTER_PACE_FACTORS[1]-1)*100)}% / +{int((QUARTER_PACE_FACTORS[2]-1)*100)}% ritmo")
    st.caption(f"• **3Q:** {int((QUARTER_PACE_FACTORS[3]-1)*100)}% defensa post-descanso")
    st.caption(f"• **4Q Clutch (<2m, ≤8 pts dif):** +{int((CLUTCH_SURGE_MULTIPLIER-1)*100)}% tiros libres y faltas")


# ==========================================
# CONTENIDO PRINCIPAL
# ==========================================
st.title("🏀 Predictor Probabilístico Avanzado de Baloncesto")
st.markdown("""
Sistema estocástico de alta precisión basado en **Actualización Bayesiana en Tiempo Real** y **Simulación Monte Carlo (5,000+ trayectorias)**, 
adaptado a la dinámica de juego reglamentaria (10 o 12 minutos) y al comportamiento táctico de cada cuarto.
""")

# Selector de Modo / Presets Rápidos
preset_col1, preset_col2 = st.columns([2, 1])
with preset_col1:
    st.subheader("⏱️ Estado del Partido en Tiempo Real")
with preset_col2:
    demo_preset = st.selectbox(
        "🚀 Cargar Ejemplo / Preset:",
        [
            "Personalizado (Manual)",
            "Inicio de Partido (0 - 0)",
            "Medio Tiempo NBA Alto Ritmo (65 - 61)",
            "Final de 3Q FIBA Táctico (58 - 56)",
            "4Q Clutch NBA (<2 min, 109 - 106)",
            "Paliza / Desbalanceado (88 - 62)"
        ]
    )

# Inicialización de variables según preset
game_data = None
if st.session_state.get("loaded_game_id"):
    game_data = obtener_partido(st.session_state["loaded_game_id"])
    st.session_state["loaded_game_id"] = None

if game_data:
    init_team_a, init_team_b = game_data['equipo_local'], game_data['equipo_visitante']
    init_q = game_data['cuarto_actual']
    init_rem_m, init_rem_s = game_data['min_restantes'], game_data['seg_restantes']
    init_scores = [(0, 0), (0, 0), (0, 0), (0, 0)]
    for m in game_data.get('marcadores', []):
        q_idx = m['cuarto'] - 1
        if 0 <= q_idx < 4:
            init_scores[q_idx] = (m['pts_local'], m['pts_visitante'])
    
    # Forzar actualización en session_state para inputs que usan key
    for q_idx in range(4):
        st.session_state[f"q{q_idx+1}_a"] = int(init_scores[q_idx][0])
        st.session_state[f"q{q_idx+1}_b"] = int(init_scores[q_idx][1])
        
    st.toast("✅ Partido cargado para su edición")
elif demo_preset == "Inicio de Partido (0 - 0)":
    init_team_a, init_team_b = "Boston Celtics", "LA Lakers"
    init_q = 1
    init_rem_m, init_rem_s = quarter_duration, 0
    init_scores = [(0, 0), (0, 0), (0, 0), (0, 0)]
elif demo_preset == "Medio Tiempo NBA Alto Ritmo (65 - 61)":
    init_team_a, init_team_b = "Golden State", "Indiana Pacers"
    init_q = 3
    init_rem_m, init_rem_s = quarter_duration, 0
    init_scores = [(33, 31), (32, 30), (0, 0), (0, 0)]
elif demo_preset == "Final de 3Q FIBA Táctico (58 - 56)":
    init_team_a, init_team_b = "Real Madrid", "Panathinaikos"
    init_q = 4
    init_rem_m, init_rem_s = quarter_duration, 0
    init_scores = [(20, 18), (19, 21), (19, 17), (0, 0)]
elif demo_preset == "4Q Clutch NBA (<2 min, 109 - 106)":
    init_team_a, init_team_b = "Miami Heat", "Denver Nuggets"
    init_q = 4
    init_rem_m, init_rem_s = 1, 45
    init_scores = [(29, 27), (28, 29), (27, 26), (25, 24)]
elif demo_preset == "Paliza / Desbalanceado (88 - 62)":
    init_team_a, init_team_b = "Local Dominante", "Visitante Frío"
    init_q = 4
    init_rem_m, init_rem_s = 3, 0
    init_scores = [(32, 20), (28, 19), (28, 23), (0, 0)]
else:
    init_team_a, init_team_b = "Equipo Local", "Equipo Visitante"
    init_q = 2
    init_rem_m, init_rem_s = max(0, quarter_duration // 2), 0
    init_scores = [(27, 25), (14, 12), (0, 0), (0, 0)]

# ── Sobreescribir con datos scrapeados si existen ──
if st.session_state.get("scraped_team_a"):
    init_team_a = st.session_state["scraped_team_a"]
    init_team_b = st.session_state["scraped_team_b"]
    init_q = st.session_state.get("scraped_q", init_q)
    init_rem_m = st.session_state.get("scraped_min", init_rem_m)
    init_rem_s = st.session_state.get("scraped_sec", init_rem_s)
    scraped_scores = st.session_state.get("scraped_scores")
    if scraped_scores:
        init_scores = scraped_scores
    # Pre-rellenar las keys de inputs de cuarto
    for q_idx in range(4):
        st.session_state[f"q{q_idx+1}_a"] = int(init_scores[q_idx][0])
        st.session_state[f"q{q_idx+1}_b"] = int(init_scores[q_idx][1])

# Inputs de Equipos
col_team1, col_team2 = st.columns(2)
with col_team1:
    if st.session_state.get("scraped_team_a"):
        st.session_state["team_a_name_input"] = str(st.session_state["scraped_team_a"])
    team_a_name = st.text_input("Nombre Equipo Local:", value=init_team_a, key="team_a_name_input")
with col_team2:
    if st.session_state.get("scraped_team_b"):
        st.session_state["team_b_name_input"] = str(st.session_state["scraped_team_b"])
    team_b_name = st.text_input("Nombre Equipo Visitante:", value=init_team_b, key="team_b_name_input")

# ==========================================
# PARÁMETROS AVANZADOS DEL ENFRENTAMIENTO (PACE, RATINGS, B2B, OLIVER)
# ==========================================
with st.expander("🔬 Métricas Predictivas y Factores Avanzados (Pace, Eficiencia Off/Def, Cuatro Factores, Fatiga B2B y Bajas)", expanded=False):
    st.markdown("""
    Configura el ritmo de juego proyectado, la eficiencia ofensiva/defensiva y los sesgos contextuales.
    El total esperado se descompone en:
    $$\\text{Puntos Totales} = (\\text{Posesiones Totales}) \\times (\\text{Eficiencia Combinada})$$
    """)
    
    col_adv_a, col_adv_b = st.columns(2)
    benchmarks_t = FOUR_FACTORS_BENCHMARKS.get(active_config.key, FOUR_FACTORS_BENCHMARKS["FIBA"])

    with col_adv_a:
        st.markdown(f"**🏠 {team_a_name} (Local)**")
        pace_a = st.number_input(
            f"Ritmo / Pace {team_a_name} (posesiones/partido):",
            min_value=50.0, max_value=130.0, value=float(active_config.league_pace), step=0.5,
            key="adv_pace_a", help="Posesiones por partido reglamentario."
        )
        col_rtg_a1, col_rtg_a2 = st.columns(2)
        with col_rtg_a1:
            off_rtg_a = st.number_input(
                f"OffRtg {team_a_name}:",
                min_value=60.0, max_value=150.0, value=float(active_config.league_off_rating), step=0.5,
                key="adv_off_a", help="Puntos anotados por cada 100 posesiones."
            )
        with col_rtg_a2:
            def_rtg_a = st.number_input(
                f"DefRtg {team_a_name}:",
                min_value=60.0, max_value=150.0, value=float(active_config.league_off_rating), step=0.5,
                key="adv_def_a", help="Puntos permitidos por cada 100 posesiones."
            )
        
        b2b_a = st.checkbox("💤 Noches consecutivas (Back-to-Back / Fatiga)", value=False, key="adv_b2b_a")
        usg_lost_a = st.slider(f"% Uso (USG%) ausente en {team_a_name}:", 0, 40, 0, step=5, key="adv_usg_a",
                               help="Porcentaje de uso ofensivo que finalizaban jugadores clave lesionados hoy.")
        
        with st.expander("🎯 Cuatro Factores de Dean Oliver (Opcional - Local)", expanded=False):
            col_ff1, col_ff2 = st.columns(2)
            with col_ff1:
                efg_a = st.number_input("eFG% (Tiro efectivo):", min_value=0.30, max_value=0.75, value=float(benchmarks_t["efg"]), step=0.005, format="%.3f", key="ff_efg_a")
                tov_a = st.number_input("TOV% (Tasa pérdidas):", min_value=0.05, max_value=0.30, value=float(benchmarks_t["tov"]), step=0.005, format="%.3f", key="ff_tov_a")
            with col_ff2:
                orb_a = st.number_input("ORB% (Rebote ofensivo):", min_value=0.10, max_value=0.50, value=float(benchmarks_t["orb"]), step=0.005, format="%.3f", key="ff_orb_a")
                ftr_a = st.number_input("FT Rate (TL / FGA):", min_value=0.10, max_value=0.50, value=float(benchmarks_t["ftr"]), step=0.005, format="%.3f", key="ff_ftr_a")
            def _cb_apply_ff_a():
                efg = float(st.session_state.get("ff_efg_a", benchmarks_t["efg"]))
                tov = float(st.session_state.get("ff_tov_a", benchmarks_t["tov"]))
                orb = float(st.session_state.get("ff_orb_a", benchmarks_t["orb"]))
                ftr = float(st.session_state.get("ff_ftr_a", benchmarks_t["ftr"]))
                calc_off = calculate_four_factors_off_rating(efg, tov, orb, ftr, active_config.key, active_config.league_off_rating)
                st.session_state["adv_off_a"] = round(calc_off, 1)

            st.button("Aplicar 4 Factores al OffRtg Local", key="btn_apply_ff_a", on_click=_cb_apply_ff_a)

    with col_adv_b:
        st.markdown(f"**✈️ {team_b_name} (Visitante)**")
        pace_b = st.number_input(
            f"Ritmo / Pace {team_b_name} (posesiones/partido):",
            min_value=50.0, max_value=130.0, value=float(active_config.league_pace), step=0.5,
            key="adv_pace_b", help="Posesiones por partido reglamentario."
        )
        col_rtg_b1, col_rtg_b2 = st.columns(2)
        with col_rtg_b1:
            off_rtg_b = st.number_input(
                f"OffRtg {team_b_name}:",
                min_value=60.0, max_value=150.0, value=float(active_config.league_off_rating), step=0.5,
                key="adv_off_b", help="Puntos anotados por cada 100 posesiones."
            )
        with col_rtg_b2:
            def_rtg_b = st.number_input(
                f"DefRtg {team_b_name}:",
                min_value=60.0, max_value=150.0, value=float(active_config.league_off_rating), step=0.5,
                key="adv_def_b", help="Puntos permitidos por cada 100 posesiones."
            )
        
        b2b_b = st.checkbox("💤 Noches consecutivas (Back-to-Back / Fatiga)", value=False, key="adv_b2b_b")
        usg_lost_b = st.slider(f"% Uso (USG%) ausente en {team_b_name}:", 0, 40, 0, step=5, key="adv_usg_b",
                               help="Porcentaje de uso ofensivo que finalizaban jugadores clave lesionados hoy.")
        
        with st.expander("🎯 Cuatro Factores de Dean Oliver (Opcional - Visitante)", expanded=False):
            col_ffb1, col_ffb2 = st.columns(2)
            with col_ffb1:
                efg_b = st.number_input("eFG% (Tiro efectivo):", min_value=0.30, max_value=0.75, value=float(benchmarks_t["efg"]), step=0.005, format="%.3f", key="ff_efg_b")
                tov_b = st.number_input("TOV% (Tasa pérdidas):", min_value=0.05, max_value=0.30, value=float(benchmarks_t["tov"]), step=0.005, format="%.3f", key="ff_tov_b")
            with col_ffb2:
                orb_b = st.number_input("ORB% (Rebote ofensivo):", min_value=0.10, max_value=0.50, value=float(benchmarks_t["orb"]), step=0.005, format="%.3f", key="ff_orb_b")
                ftr_b = st.number_input("FT Rate (TL / FGA):", min_value=0.10, max_value=0.50, value=float(benchmarks_t["ftr"]), step=0.005, format="%.3f", key="ff_ftr_b")
            def _cb_apply_ff_b():
                efg = float(st.session_state.get("ff_efg_b", benchmarks_t["efg"]))
                tov = float(st.session_state.get("ff_tov_b", benchmarks_t["tov"]))
                orb = float(st.session_state.get("ff_orb_b", benchmarks_t["orb"]))
                ftr = float(st.session_state.get("ff_ftr_b", benchmarks_t["ftr"]))
                calc_off = calculate_four_factors_off_rating(efg, tov, orb, ftr, active_config.key, active_config.league_off_rating)
                st.session_state["adv_off_b"] = round(calc_off, 1)

            st.button("Aplicar 4 Factores al OffRtg Visitante", key="btn_apply_ff_b", on_click=_cb_apply_ff_b)

    st.markdown("---")
    col_hca1, col_hca2 = st.columns(2)
    with col_hca1:
        home_adv_val = st.slider(
            "Ventaja neta de localía (puntos):",
            0.0, 6.0, float(active_config.home_court_advantage), step=0.2,
            help="Diferencial histórico otorgado al equipo local por confort y arbitraje."
        )
        active_config.home_court_advantage = home_adv_val
    with col_hca2:
        b2b_pen_val = st.slider(
            "Penalización por Fatiga Back-to-Back (pts / 100 poss):",
            0.5, 4.0, float(active_config.b2b_penalty_per_100), step=0.1,
            help="Reducción en el rating ofensivo para equipos que juegan sin descanso."
        )
        active_config.b2b_penalty_per_100 = b2b_pen_val

# Construcción de perfiles avanzados de equipo
team_profile_a = TeamProfile(
    name=team_a_name,
    pace=pace_a,
    off_rating=off_rtg_a,
    def_rating=def_rtg_a,
    is_home=True,
    is_b2b=b2b_a,
    usg_lost_pct=usg_lost_a / 100.0
)
team_profile_b = TeamProfile(
    name=team_b_name,
    pace=pace_b,
    off_rating=off_rtg_b,
    def_rating=def_rtg_b,
    is_home=False,
    is_b2b=b2b_b,
    usg_lost_pct=usg_lost_b / 100.0
)

# Cálculo previo del cruce para mostrar en tarjeta
pre_matchup = project_pre_game_matchup(team_profile_a, team_profile_b, active_config)

# Banner visual de descomposición del cruce
st.markdown(f"""
<div style="background: rgba(22, 28, 44, 0.7); border: 1px solid rgba(255, 149, 0, 0.25); border-radius: 12px; padding: 12px 18px; margin-top: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
    <div>
        <span style="color: #a0aec0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Posesiones Proyectadas:</span><br>
        <b style="color: #00e5ff; font-size: 1.25rem;">{pre_matchup['match_pace']:.1f} poss</b>
        <span style="color: #718096; font-size: 0.8rem;">(Liga: {active_config.league_pace:.1f})</span>
    </div>
    <div>
        <span style="color: #a0aec0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Eficiencia Cruzada:</span><br>
        <b style="color: #63b3ed;">{team_a_name[:10]}: {pre_matchup['eff_a']:.1f}</b> <span style="color: #718096;">vs</span> <b style="color: #f687b3;">{team_b_name[:10]}: {pre_matchup['eff_b']:.1f}</b>
        <span style="color: #718096; font-size: 0.8rem;">pts/100</span>
    </div>
    <div>
        <span style="color: #a0aec0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Total Pre-Partido Base:</span><br>
        <b style="color: #ff9800; font-size: 1.25rem;">{pre_matchup['total_expected']:.1f} pts</b>
        <span style="color: #a0aec0; font-size: 0.82rem;">(σ ≈ ±{pre_matchup['sigma']:.1f})</span>
    </div>
    <div>
        <span style="color: #a0aec0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Sesgos Activos:</span><br>
        <span style="background: rgba(72,187,120,0.2); color: #48bb78; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">Local +{active_config.home_court_advantage:.1f}</span>
        {' <span style="background: rgba(245,101,101,0.2); color: #f56565; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">Fatiga B2B</span>' if (b2b_a or b2b_b) else ''}
        {' <span style="background: rgba(237,137,54,0.2); color: #ed8936; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">Bajas USG</span>' if (usg_lost_a > 0 or usg_lost_b > 0) else ''}
    </div>
</div>
""", unsafe_allow_html=True)

# Selector de Cuarto Actual y Cronómetro
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 1.5])
q_options = ["1° Cuarto (Q1)", "2° Cuarto (Q2)", "3° Cuarto (Q3)", "4° Cuarto (Q4)", "Partido Finalizado"]
target_q_idx = min(max(0, init_q - 1), 4)

with col_ctrl1:
    if st.session_state.get("scraped_q") is not None:
        st.session_state["ctrl_current_q"] = q_options[target_q_idx]

    current_q_label = st.selectbox(
        "Cuarto en Juego:",
        q_options,
        index=target_q_idx,
        key="ctrl_current_q"
    )
    if "1°" in current_q_label:
        current_quarter = 1
    elif "2°" in current_q_label:
        current_quarter = 2
    elif "3°" in current_q_label:
        current_quarter = 3
    elif "4°" in current_q_label:
        current_quarter = 4
    else:
        current_quarter = 5

with col_ctrl2:
    if current_quarter <= 4:
        if st.session_state.get("scraped_min") is not None:
            st.session_state["ctrl_rem_min"] = min(quarter_duration, int(st.session_state["scraped_min"]))

        rem_min = st.number_input(
            f"Minutos restantes en Q{current_quarter}:",
            min_value=0,
            max_value=quarter_duration,
            value=st.session_state.get("ctrl_rem_min", min(quarter_duration, init_rem_m)),
            key="ctrl_rem_min"
        )
    else:
        rem_min = 0
        st.info("Partido Finalizado")

with col_ctrl3:
    if current_quarter <= 4:
        if st.session_state.get("scraped_sec") is not None:
            st.session_state["ctrl_rem_sec"] = int(st.session_state["scraped_sec"])

        rem_sec = st.number_input(
            f"Segundos restantes en Q{current_quarter}:",
            min_value=0,
            max_value=59,
            value=st.session_state.get("ctrl_rem_sec", init_rem_s),
            key="ctrl_rem_sec"
        )
    else:
        rem_sec = 0

# Minutos jugados en el cuarto actual
rem_total_sec_in_q = rem_min * 60 + rem_sec
elapsed_sec_in_q = max(0, (quarter_duration * 60) - rem_total_sec_in_q)
elapsed_total_min = ((current_quarter - 1) * quarter_duration + (elapsed_sec_in_q / 60.0)) if current_quarter <= 4 else (quarter_duration * 4)

# Inputs de Marcadores por Cuarto
st.markdown("#### 🔢 Puntos Anotados por Cuarto")
st.caption("Ingresa los puntos sumados en cada periodo. Si el cuarto está en juego, anota los puntos registrados hasta este segundo.")

col_q1, col_q2, col_q3, col_q4 = st.columns(4)

def render_q_inputs(col, q_num, current_q, init_pts_a, init_pts_b):
    with col:
        is_active = (q_num == current_q)
        is_past = (q_num < current_q)
        badge_text = "🟢 En Juego" if is_active else ("✅ Culminado" if is_past else "⏳ Pendiente")
        st.markdown(f"**{q_num}° Cuarto** `{badge_text}`")
        
        pts_a = st.number_input(
            f"{team_a_name} (Q{q_num})",
            min_value=0,
            max_value=80,
            value=int(init_pts_a),
            key=f"q{q_num}_a",
            disabled=(q_num > current_q)
        )
        pts_b = st.number_input(
            f"{team_b_name} (Q{q_num})",
            min_value=0,
            max_value=80,
            value=int(init_pts_b),
            key=f"q{q_num}_b",
            disabled=(q_num > current_q)
        )
        total_q = int(pts_a) + int(pts_b)
        st.markdown(f"<div style='text-align:center; padding: 5px; background: rgba(255,255,255,0.05); border-radius: 5px; margin-top: 5px; margin-bottom: 10px;'><b>Total Q{q_num}: {total_q}</b></div>", unsafe_allow_html=True)
        return float(pts_a), float(pts_b)

q1_a, q1_b = render_q_inputs(col_q1, 1, current_quarter, init_scores[0][0], init_scores[0][1])
q2_a, q2_b = render_q_inputs(col_q2, 2, current_quarter, init_scores[1][0], init_scores[1][1])
q3_a, q3_b = render_q_inputs(col_q3, 3, current_quarter, init_scores[2][0], init_scores[2][1])
q4_a, q4_b = render_q_inputs(col_q4, 4, current_quarter, init_scores[3][0], init_scores[3][1])

quarters_data = [(q1_a, q1_b), (q2_a, q2_b), (q3_a, q3_b), (q4_a, q4_b)]

# Puntos totales reales acumulados
if st.session_state.get("scraped_team_a") and st.session_state.get("scraped_score_home") is not None:
    score_a_total = float(st.session_state["scraped_score_home"])
    score_b_total = float(st.session_state["scraped_score_away"])
    # Ajustar el cuarto en juego en quarters_data para que la suma sea idéntica al marcador en vivo
    if 1 <= current_quarter <= 4:
        pts_prev_h = sum(quarters_data[i][0] for i in range(current_quarter - 1))
        pts_prev_a = sum(quarters_data[i][1] for i in range(current_quarter - 1))
        # Si los valores por defecto de cuartos anteriores superan el total real, escalar
        if pts_prev_h > score_a_total or pts_prev_a > score_b_total:
            ratio_h = (score_a_total / pts_prev_h) if pts_prev_h > 0 else 0.0
            ratio_a = (score_b_total / pts_prev_a) if pts_prev_a > 0 else 0.0
            for i in range(current_quarter - 1):
                quarters_data[i] = (round(quarters_data[i][0] * ratio_h, 1), round(quarters_data[i][1] * ratio_a, 1))
            pts_prev_h = sum(quarters_data[i][0] for i in range(current_quarter - 1))
            pts_prev_a = sum(quarters_data[i][1] for i in range(current_quarter - 1))
        curr_q_h = max(0.0, score_a_total - pts_prev_h)
        curr_q_a = max(0.0, score_b_total - pts_prev_a)
        quarters_data[current_quarter - 1] = (curr_q_h, curr_q_a)
else:
    score_a_total = sum(q[0] for q in quarters_data[:current_quarter])
    score_b_total = sum(q[1] for q in quarters_data[:current_quarter])

total_points_now = score_a_total + score_b_total

# ==========================================
# CÁLCULO PROBABILÍSTICO Y SIMULACIÓN
# ==========================================
# Contexto de tiro exterior del play-by-play para regresión a la media
shooting_ctx = None
live_plays_for_sim = st.session_state.get("scraped_plays", [])
if live_plays_for_sim:
    m_3p = sum(1 for p in live_plays_for_sim if p.get("pts") == 3)
    att_3p = max(m_3p, int(len(live_plays_for_sim) * 0.40))
    shooting_ctx = {"made_3p": m_3p, "att_3p": att_3p}

predictor = BasketballPredictor(
    active_config,
    team_a_profile=team_profile_a,
    team_b_profile=team_profile_b
)
summary: SimulationSummary = predictor.run_live_simulation(
    current_quarter=current_quarter,
    elapsed_seconds_in_quarter=elapsed_sec_in_q,
    quarters_data=quarters_data,
    n_simulations=num_sims,
    random_seed=42,
    actual_total_scores=(score_a_total, score_b_total),
    shooting_context=shooting_ctx,
    plays=live_plays_for_sim,
    use_deep_learning=st.session_state.get("use_deep_learning", True)
)

# ==========================================
# 🎯 CALCULADORA DESTACADA DE APUESTAS (MÁS DE / MENOS DE)
# ==========================================
st.markdown("""
<div style="background: linear-gradient(135deg, rgba(20, 26, 40, 0.95) 0%, rgba(13, 17, 28, 0.98) 100%); 
            border: 2px solid #ff7700; border-radius: 16px; padding: 22px; margin-bottom: 25px; 
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);">
    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
        <div>
            <h3 style="margin: 0; color: #ff9800; font-size: 1.4rem; display: flex; align-items: center; gap: 8px;">
                🎯 Calculadora de Apuesta Directa: Más (+) o Menos (-)
            </h3>
            <p style="margin: 4px 0 0 0; color: #cbd5e0; font-size: 0.92rem;">
                Ingresa el número total de puntos de tu casa de apuestas (ej. <b>177</b>, <b>218.5</b>, etc.) para calcular al instante la probabilidad de superarlo o quedar por debajo y saber a cuál apostar.
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

calc_col1, calc_col2 = st.columns([1.2, 2.8])

with calc_col1:
    # Obtener la línea de puntos en vivo de la página si existe
    scraped_line_val = st.session_state.get("scraped_odds_line")
    
    # Determinar valor por defecto inteligente (Prioridad 1: Página en vivo, Prioridad 2: Configuración de liga)
    if scraped_line_val is not None:
        default_bet_line = float(scraped_line_val)
    elif active_config.key == "FIBA":
        default_bet_line = 177.0
    else:
        default_bet_line = round(summary.total_mean * 2) / 2.0

    # Auto-sincronizar el estado si la línea en vivo cambió en la página o si es la primera carga
    if "direct_bet_input" not in st.session_state:
        st.session_state["direct_bet_input"] = float(default_bet_line)
    elif scraped_line_val is not None and st.session_state.get("_last_synced_line") != float(scraped_line_val):
        st.session_state["direct_bet_input"] = float(scraped_line_val)
        st.session_state["_last_synced_line"] = float(scraped_line_val)

    is_live_active = (scraped_line_val is not None)
    status_tag = " 🔴 [En Vivo: Aposta.la]" if is_live_active else ""

    # Asegurar rango válido dentro de session_state
    if st.session_state["direct_bet_input"] < 5.0 or st.session_state["direct_bet_input"] > 400.0:
        st.session_state["direct_bet_input"] = max(5.0, min(400.0, float(st.session_state["direct_bet_input"])))

    bet_number = st.number_input(
        f"Ingresa el número a evaluar:{status_tag}",
        min_value=5.0,
        max_value=400.0,
        step=0.5,
        format="%.1f",
        key="direct_bet_input",
        help="Sincronizado automáticamente con la línea oficial del partido en aposta.la o editable libremente."
    )

    # 🛡️ Detección Inteligente de Incoherencia Reglamentaria (40 min vs 48 min)
    league_str = str(st.session_state.get("scraped_league", "")).lower()
    is_known_10m = any(kw in league_str for kw in ["fiba", "euroliga", "euroleague", "nbl", "australia", "acb", "wnba", "lnb", "liga"])
    is_known_12m = any(kw in league_str for kw in ["nba"]) and not any(kw in league_str for kw in ["wnba", "nbl"])
    pts_already_scored = total_points_now

    # Solo alertar si el partido está en pre-partido o con muy pocos puntos (< 25 pts),
    # ya que en partidos en vivo de alto ritmo (ej. 111 pts al descanso) la línea sube de 208 pts con total naturalidad sin cambiar la reglamentación.
    def _cb_switch_torneo(preset_str):
        st.session_state["torneo_preset_sel"] = preset_str

    def _cb_set_direct_bet(val, update_sync=False):
        st.session_state["direct_bet_input"] = float(val)
        if update_sync:
            st.session_state["_last_synced_line"] = float(val)

    if not is_known_12m and quarter_duration == 12 and bet_number < 190.0 and pts_already_scored < 25:
        st.warning(f"""
        ⚠️ **Incoherencia reglamentaria:** Línea baja (**{bet_number:.1f} pts**) evaluada con duración de **NBA (48 min)**. 
        Las líneas menores a 190 pts son típicas de torneos de **40 min** (FIBA / Euroliga / NBL / Ligas Locales). Proyectar 48 min infla la media hacia el OVER.
        """)
        st.button(
            "🔄 Cambiar a 10 min/cuarto",
            width="stretch",
            key="btn_switch_fiba_alert",
            on_click=_cb_switch_torneo,
            args=("FIBA / Euroliga / Ligas Locales (10 min/cuarto)",)
        )
    elif not is_known_10m and quarter_duration == 10 and bet_number > 218.0 and pts_already_scored < 25:
        st.warning(f"""
        ⚠️ **Incoherencia reglamentaria:** Línea de apertura muy alta (**{bet_number:.1f} pts**) evaluada con duración de **40 min**. 
        Líneas pre-partido mayores a 218 pts suelen pertenecer a la **NBA (48 min)**.
        """)
        st.button(
            "🔄 Cambiar a NBA (12 min/cuarto)",
            width="stretch",
            key="btn_switch_nba_alert",
            on_click=_cb_switch_torneo,
            args=("NBA (12 min/cuarto)",)
        )

    # Accesos rápidos adaptativos
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    if is_live_active and scraped_line_val is not None:
        with col_btn1:
            st.button(
                f"🎯 Casa ({scraped_line_val:.1f})",
                width="stretch",
                key="btn_quick_live_casa",
                help="Restablecer exactamente a la línea en vivo de la casa de apuestas",
                on_click=_cb_set_direct_bet,
                args=(float(scraped_line_val), True)
            )
        with col_btn2:
            media_redondeada = round(summary.total_mean * 2) / 2.0
            st.button(
                f"Media ({media_redondeada:.0f})",
                width="stretch",
                key="btn_quick_live_media",
                help="Establecer la media matemática proyectada",
                on_click=_cb_set_direct_bet,
                args=(float(media_redondeada), False)
            )
        with col_btn3:
            bench_val = 218.5 if "NBA" in active_config.name else 177.0
            bench_lbl = "NBA 218.5" if "NBA" in active_config.name else "FIBA 177"
            st.button(
                bench_lbl,
                width="stretch",
                key="btn_quick_live_bench",
                help="Línea estándar promedio",
                on_click=_cb_set_direct_bet,
                args=(float(bench_val), False)
            )
    else:
        with col_btn1:
            st.button(
                "177 pts",
                width="stretch",
                key="btn_quick_177",
                on_click=_cb_set_direct_bet,
                args=(177.0, False)
            )
        with col_btn2:
            media_redondeada = round(summary.total_mean * 2) / 2.0
            st.button(
                f"Media ({media_redondeada:.0f})",
                width="stretch",
                key="btn_quick_media",
                on_click=_cb_set_direct_bet,
                args=(float(media_redondeada), False)
            )
        with col_btn3:
            st.button(
                "218.5",
                width="stretch",
                key="btn_quick_218",
                on_click=_cb_set_direct_bet,
                args=(218.5, False)
            )

# Carga de calibración activa del modelo (Machine Learning)
cal_activa = obtener_calibracion_activa()
aplicar_cal_ml = st.session_state.get("toggle_calibracion_ml", True)

# Cálculo estocástico sobre las 5,000 simulaciones
prob_mas_raw, prob_menos_raw = BasketballPredictor.calculate_over_under(summary.simulated_totals, bet_number)

# Aplicar calibración aprendida Platt Scaling
if aplicar_cal_ml and cal_activa and cal_activa.get("platt_a") is not None:
    prob_mas = calibrar_probabilidad(prob_mas_raw, cal_activa.get("platt_a", 1.0), cal_activa.get("platt_b", 0.0))
    prob_menos = round(1.0 - prob_mas, 4)
else:
    prob_mas, prob_menos = prob_mas_raw, prob_menos_raw

diff_con_media = summary.total_mean - bet_number


# Cálculo de No-Vig y Edge en puntos
is_same_line = (scraped_line_val is not None) and (abs(bet_number - float(scraped_line_val)) < 0.01)
house_ov = st.session_state.get("scraped_odds_over")
house_un = st.session_state.get("scraped_odds_under")

house_vig_pct = 0.0
novig_p_mas, novig_p_menos = 0.5, 0.5
alpha_mas, alpha_menos = 0.0, 0.0
if house_ov and house_un and house_ov > 1.0 and house_un > 1.0:
    sum_inv = (1.0 / house_ov) + (1.0 / house_un)
    house_vig_pct = sum_inv - 1.0
    novig_p_mas = (1.0 / house_ov) / sum_inv
    novig_p_menos = (1.0 / house_un) / sum_inv
    alpha_mas = prob_mas - novig_p_mas
    alpha_menos = prob_menos - novig_p_menos

with calc_col2:
    # Tarjetas gigantes de MÁS (+) y MENOS (-)
    b_col_mas, b_col_menos = st.columns(2)
    
    is_mas_fav = prob_mas >= prob_menos
    cuota_mas = (1.0 / prob_mas) if prob_mas > 0 else 99.0
    cuota_menos = (1.0 / prob_menos) if prob_menos > 0 else 99.0

    sub_mas = f"Cuota justa: <b>{cuota_mas:.2f}</b> | Spread Edge: <b style='color:#48bb78;'>{diff_con_media:+.1f} pts</b>"
    if is_same_line and house_ov:
        ev_mas = (prob_mas * house_ov - 1.0) * 100.0
        ev_color = "#48bb78" if ev_mas > 0 else "#f56565"
        alpha_col_m = "#48bb78" if alpha_mas > 0 else "#f56565"
        sub_mas += f"<br><span style='color: #63b3ed; font-size: 0.85rem;'>Casa: <b>{house_ov:.2f}</b> | EV: <b style='color:{ev_color};'>{'+' if ev_mas>0 else ''}{ev_mas:.1f}%</b> | Alpha No-Vig: <b style='color:{alpha_col_m};'>{alpha_mas*100:+.1f}%</b></span>"

    sub_menos = f"Cuota justa: <b>{cuota_menos:.2f}</b> | Spread Edge: <b style='color:#f56565;'>{-diff_con_media:+.1f} pts</b>"
    if is_same_line and house_un:
        ev_un = (prob_menos * house_un - 1.0) * 100.0
        ev_color_un = "#48bb78" if ev_un > 0 else "#f56565"
        alpha_col_u = "#48bb78" if alpha_menos > 0 else "#f56565"
        sub_menos += f"<br><span style='color: #63b3ed; font-size: 0.85rem;'>Casa: <b>{house_un:.2f}</b> | EV: <b style='color:{ev_color_un};'>{'+' if ev_un>0 else ''}{ev_un:.1f}%</b> | Alpha No-Vig: <b style='color:{alpha_col_u};'>{alpha_menos*100:+.1f}%</b></span>"

    with b_col_mas:
        border_color_mas = "#48bb78" if is_mas_fav else "#2d3748"
        bg_mas = "rgba(72, 187, 120, 0.18)" if is_mas_fav else "rgba(45, 55, 72, 0.3)"
        st.markdown(f"""
        <div style="background: {bg_mas}; border: 2px solid {border_color_mas}; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 1rem; font-weight: 700; color: #48bb78; text-transform: uppercase;">
                🟢 MÁS DE {bet_number:.1f} (OVER)
            </div>
            <div style="font-size: 2.7rem; font-weight: 900; font-family: 'JetBrains Mono', monospace; color: #f7fafc; margin: 5px 0;">
                +{prob_mas*100:.1f}%
            </div>
            <div style="color: #cbd5e0; font-size: 0.85rem;">
                {sub_mas}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with b_col_menos:
        border_color_menos = "#f56565" if not is_mas_fav else "#2d3748"
        bg_menos = "rgba(245, 101, 101, 0.18)" if not is_mas_fav else "rgba(45, 55, 72, 0.3)"
        st.markdown(f"""
        <div style="background: {bg_menos}; border: 2px solid {border_color_menos}; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 1rem; font-weight: 700; color: #f56565; text-transform: uppercase;">
                🔴 MENOS DE {bet_number:.1f} (UNDER)
            </div>
            <div style="font-size: 2.7rem; font-weight: 900; font-family: 'JetBrains Mono', monospace; color: #f7fafc; margin: 5px 0;">
                {prob_menos*100:.1f}%
            </div>
            <div style="color: #cbd5e0; font-size: 0.85rem;">
                {sub_menos}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Veredicto de Recomendación Inteligente y Grado de Apuesta
    spread_pts = abs(diff_con_media)
    max_prob = max(prob_mas, prob_menos)
    fav_side = "MÁS DE" if prob_mas >= prob_menos else "MENOS DE"
    
    if spread_pts >= 4.0 and max_prob >= 0.65:
        calc_grade = "GRADO A+ (VENTAJA EXCELENTE)"
        calc_badge_color = "#38a169"
        calc_units = "2.5 – 3.0 U"
    elif spread_pts >= 2.5 and max_prob >= 0.60:
        calc_grade = "GRADO A (VENTAJA SÓLIDA)"
        calc_badge_color = "#48bb78"
        calc_units = "1.5 – 2.0 U"
    elif spread_pts >= 1.5 and max_prob >= 0.55:
        calc_grade = "GRADO B (VENTAJA MODERADA)"
        calc_badge_color = "#ecc94b"
        calc_units = "0.5 – 1.0 U"
    else:
        calc_grade = "SIN EDGE (LÍNEA AJUSTADA / 50-50)"
        calc_badge_color = "#a0aec0"
        calc_units = "0.0 U (NO APOSTAR)"

    # ── Alerta Sonora y Visual de Oportunidad de Apuesta ─────────
    calc_alert = evaluate_betting_alert(
        prob_over=prob_mas,
        prob_under=prob_menos,
        line=bet_number,
        bet_grade=calc_grade,
        ev_over=((prob_mas * house_ov - 1.0) if (is_same_line and house_ov) else 0.0),
        ev_under=((prob_menos * house_un - 1.0) if (is_same_line and house_un) else 0.0),
        threshold_pct=float(alert_threshold_pct),
        trigger_mode=alert_mode_key,
    )

    render_betting_alert_ui(
        alert=calc_alert,
        sound_type=alert_sound_type,
        volume=alert_volume,
        repeat_mode=alert_repeat_mode,
        is_enabled=audio_alerts_enabled,
        key_suffix="calc",
    )

    if prob_mas >= 0.65:
        st.success(f"""
        **💡 VEREDICTO [{calc_grade}]:** Apostar a **MÁS DE {bet_number:.1f}** (Probabilidad: **+{prob_mas*100:.1f}%** | Stake sugerido: **{calc_units}**).  
        El modelo proyecta una media de **{summary.total_mean:.1f} pts** (Ventaja de **{diff_con_media:+.1f} pts** sobre la línea).
        """)
    elif prob_menos >= 0.65:
        st.error(f"""
        **💡 VEREDICTO [{calc_grade}]:** Apostar a **MENOS DE {bet_number:.1f}** (Probabilidad: **{prob_menos*100:.1f}%** | Stake sugerido: **{calc_units}**).  
        El modelo proyecta una media de **{summary.total_mean:.1f} pts** (Ventaja de **{-diff_con_media:+.1f} pts** por debajo de la línea).
        """)
    elif 0.55 <= prob_mas < 0.65:
        st.info(f"""
        **⚖️ TENDENCIA [{calc_grade}]:** Ligera ventaja a **MÁS DE {bet_number:.1f}** (+{prob_mas*100:.1f}% | Stake: **{calc_units}**).  
        Media esperada: **{summary.total_mean:.1f} pts** ({diff_con_media:+.1f} pts vs línea).
        """)
    elif 0.55 <= prob_menos < 0.65:
        st.info(f"""
        **⚖️ TENDENCIA [{calc_grade}]:** Ligera ventaja a **MENOS DE {bet_number:.1f}** ({prob_menos*100:.1f}% | Stake: **{calc_units}**).  
        Media esperada: **{summary.total_mean:.1f} pts** ({-diff_con_media:+.1f} pts vs línea).
        """)
    else:
        st.warning(f"""
        **⚠️ LÍNEA AJUSTADA [{calc_grade}]:** Tu número ({bet_number:.1f}) coincide con la media proyectada ({summary.total_mean:.1f} pts).  
        No hay ventaja matemática clara para superar el margen de la casa.
        """)

st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# BANNER DEL MARCADOR EN VIVO
# ==========================================
total_game_min = active_config.total_game_duration
time_badge_str = "FINAL" if current_quarter > 4 else f"Q{current_quarter} | {rem_min:02d}:{rem_sec:02d}"

if st.session_state.get("live_url") and st.session_state.get("scraped_team_a"):
    odds_sub = ""
    if st.session_state.get("scraped_odds_line"):
        line_val = st.session_state.get("scraped_odds_line")
        ov_val = st.session_state.get("scraped_odds_over", 0.0)
        un_val = st.session_state.get("scraped_odds_under", 0.0)
        odds_sub = f" | Línea Casa: <b>{line_val} pts</b> (Over: {ov_val:.2f} | Under: {un_val:.2f})"

    st.markdown(f"""
    <div style="background: linear-gradient(90deg, rgba(235, 87, 87, 0.2), rgba(49, 130, 206, 0.2)); border: 1px solid rgba(235, 87, 87, 0.5); border-radius: 10px; padding: 10px 16px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
        <div>
            <span style="background: #e53e3e; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 0.75rem; letter-spacing: 1px;">EN VIVO 🔴</span>
            <span style="color: #f7fafc; margin-left: 10px; font-weight: 700; font-size: 0.95rem;">Sincronizado con Aposta.la</span>
            <span style="color: #ffaa00; margin-left: 12px; font-size: 0.9rem;">{odds_sub}</span>
        </div>
        <div style="color: #a0aec0; font-size: 0.85rem;">
            <a href="{st.session_state.get('live_url')}" target="_blank" style="color: #63b3ed; text-decoration: underline; font-weight: 600;">Ver en Aposta.la ↗</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="scoreboard-container">
    <div style="margin-bottom: 12px;">
        <span class="game-clock-badge">⏱️ {time_badge_str}</span>
        <span style="color: #a0aec0; margin-left: 15px; font-weight: 600;">
            {elapsed_total_min:.1f} / {total_game_min} min jugados ({(elapsed_total_min/total_game_min)*100:.0f}%)
        </span>
    </div>
    <div style="display: flex; justify-content: space-around; align-items: center;">
        <div style="flex: 1;">
            <div class="team-name">🏠 {team_a_name}</div>
            <div class="team-score">{int(score_a_total)}</div>
        </div>
        <div style="font-size: 2rem; font-weight: 900; color: #718096; padding: 0 20px;">VS</div>
        <div style="flex: 1;">
            <div class="team-name">✈️ {team_b_name}</div>
            <div class="team-score">{int(score_b_total)}</div>
        </div>
    </div>
    <div style="margin-top: 10px; color: #ffaa00; font-weight: 700; font-size: 1.15rem;">
        Total Actual: {int(total_points_now)} pts
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🚩 BARRA DE HITOS DE PREDICCIÓN & APUESTA FICTICIA (PAPER BETTING)
# ==========================================
with st.container():
    active_partidos_list = [p for p in listar_partidos(30) if p["estado"] == "en_curso"]
    match_matched = next(
        (p for p in active_partidos_list
         if p["equipo_local"].strip().lower() == team_a_name.strip().lower()
         and p["equipo_visitante"].strip().lower() == team_b_name.strip().lower()),
        None
    )
    active_pid_for_hitos = match_matched["id"] if match_matched else st.session_state.get("loaded_game_id")

    h_col_left, h_col_right = st.columns([3, 2])
    with h_col_left:
        st.markdown("""
        <div style="font-weight: 700; color: #ff9800; font-size: 1.05rem; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            🚩 Registro de Hitos de Predicción (Checkpoints para Cotejo)
        </div>
        <div style="color: #a0aec0; font-size: 0.83rem; margin-bottom: 10px;">
            Guarda la fotografía predictiva en momentos clave para cotejar la precisión al terminar el partido.
        </div>
        """, unsafe_allow_html=True)

        hito_btns_cols = st.columns(5)
        hitos_defs = [
            ("🚩 Pre-Partido", "PRE_PARTIDO", 1, 0.0),
            ("🚩 Fin 1Q", "FIN_Q1", 1, float(quarter_duration)),
            ("🚩 Medio Tiempo", "MEDIO_TIEMPO", 2, float(quarter_duration * 2)),
            ("🚩 Fin 3Q", "FIN_Q3", 3, float(quarter_duration * 3)),
            ("🚩 Clutch (<2m)", "CLUTCH", 4, float(total_game_min - 2.0)),
        ]

        def _guardar_hito_click(h_name, h_cuarto, h_min_default):
            pid = active_pid_for_hitos
            if not pid:
                pid = crear_partido(
                    equipo_local=team_a_name,
                    equipo_visitante=team_b_name,
                    torneo_nombre=torneo_sel,
                    cuarto_actual=current_quarter,
                    min_restantes=rem_min,
                    seg_restantes=rem_sec,
                    quarters_data=quarters_data,
                    notas=f"Auto-creado para {h_name}"
                )
                st.session_state["loaded_game_id"] = pid

            m_jug = elapsed_total_min if elapsed_total_min > 0 else h_min_default
            q_snap = current_quarter if current_quarter > 0 else h_cuarto
            hid = registrar_hito(
                partido_id=pid,
                nombre_hito=h_name,
                cuarto_snapshot=q_snap,
                minutos_jugados=m_jug,
                pts_local_actual=int(score_a_total),
                pts_visitante_actual=int(score_b_total),
                summary=summary,
                linea_apuesta=bet_number,
                prob_over=prob_mas,
                prob_under=prob_menos,
                cuota_over=house_ov,
                cuota_under=house_un,
                num_simulaciones=num_sims
            )
            st.session_state["_toast_msg"] = f"✅ Hito '{h_name}' guardado en partido #{pid}"

        for b_idx, (btn_lbl, h_key, h_q, h_m) in enumerate(hitos_defs):
            with hito_btns_cols[b_idx]:
                if st.button(btn_lbl, width="stretch", key=f"btn_hito_{h_key}"):
                    _guardar_hito_click(h_key, h_q, h_m)
                    st.rerun()

    with h_col_right:
        best_cuota = max(house_ov or 0.0, house_un or 0.0)
        pago_info = clasificar_pago_casa(best_cuota, max(prob_mas, prob_menos))
        is_high = pago_info.get("es_pago_elevado", False) or best_cuota >= 2.10

        fav_tipo = "OVER" if prob_mas >= prob_menos else "UNDER"
        fav_cuota = house_ov if fav_tipo == "OVER" else house_un
        fav_prob = prob_mas if fav_tipo == "OVER" else prob_menos
        fav_ev = ((fav_prob * fav_cuota) - 1.0) if (fav_cuota and fav_cuota > 1.0) else (summary.total_mean - bet_number) / 100.0

        pago_border = "#48bb78" if is_high else "rgba(255, 138, 0, 0.4)"
        pago_bg = "rgba(72, 187, 120, 0.12)" if is_high else "rgba(26, 31, 46, 0.85)"
        cuota_str = f"{fav_cuota:.2f}" if fav_cuota else "—"

        st.markdown(f"""
        <div style="background:{pago_bg}; border:1.5px solid {pago_border}; border-radius:10px; padding:10px 14px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#ff9800; font-weight:800; font-size:0.85rem; text-transform:uppercase;">
                    {'🔥 PAGO ELEVADO DE LA CASA' if is_high else '🎲 APUESTA FICTICIA (PAPER BETTING)'}
                </span>
                <span style="color:#63b3ed; font-weight:700; font-size:0.85rem;">Cuota: {cuota_str}</span>
            </div>
            <div style="color:#cbd5e0; font-size:0.82rem; margin-top:3px;">
                Recomendación: <b>{fav_tipo} {bet_number:.1f}</b> | Prob: <b>{fav_prob*100:.1f}%</b> | EV: <b style="color:{'#48bb78' if fav_ev>0 else '#f56565'};">{fav_ev*100:+.1f}%</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🎲 Registrar Apuesta Ficticia (100.000 Gs.)", width="stretch", key="btn_quick_paper_bet", type="secondary"):
            pid_target = active_pid_for_hitos
            if not pid_target:
                pid_target = crear_partido(
                    equipo_local=team_a_name,
                    equipo_visitante=team_b_name,
                    torneo_nombre=torneo_sel,
                    cuarto_actual=current_quarter,
                    min_restantes=rem_min,
                    seg_restantes=rem_sec,
                    quarters_data=quarters_data,
                    notas="Creado para Apuesta Ficticia"
                )
                st.session_state["loaded_game_id"] = pid_target

            aid = registrar_apuesta(
                partido_id=pid_target,
                cuarto_apuesta=current_quarter,
                minutos_jugados=elapsed_total_min,
                linea=bet_number,
                tipo=fav_tipo,
                monto=100000.0,
                cuota_casa=fav_cuota or 1.85,
                prob_modelo=fav_prob,
                ev=fav_ev if isinstance(fav_ev, float) else 0.0,
                notas=f"Apuesta ficticia rápida (100.000 Gs.) en {fav_tipo} {bet_number:.1f}",
                grado_apuesta=f"{'GRADO A+ (PAGO ELEVADO)' if is_high else 'GRADO A'}",
                spread_edge=abs(diff_con_media),
                es_ficticia=True,
                hito_origen=f"Q{current_quarter}",
                regla_activacion="PAGO_ELEVADO" if is_high else "VALOR_MODELO"
            )
            st.success(f"✅ Apuesta ficticia #{aid} de 100.000 Gs. registrada en {fav_tipo} {bet_number:.1f} @ {cuota_str}")
            st.rerun()

    if st.session_state.get("_toast_msg"):
        st.toast(st.session_state.pop("_toast_msg"))

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# TARJETAS DE MÉTRICAS PROBABILÍSTICAS
# ==========================================
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

with m_col1:
    ot_add_text = f" (+{summary.overtime_points_avg:.1f} OT)" if summary.overtime_prob >= 0.01 else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">🎯 Total Proyectado</div>
        <div class="metric-value" style="color: #ff9800;">{summary.total_mean:.1f}{ot_add_text}</div>
        <div class="metric-subtext">
            Regulación: <b>{summary.regulation_mean:.1f}</b> pts<br>
            Mediana: <b>{summary.total_median:.1f}</b> | Desv: <b>±{summary.total_std:.1f}</b> pts
        </div>
    </div>
    """, unsafe_allow_html=True)

with m_col2:
    st.markdown(f"""
    <div class="metric-card" style="border-color: rgba(0, 229, 255, 0.4);">
        <div class="metric-title" style="color: #00e5ff;">📉 Intervalos 80% y 95%</div>
        <div class="metric-value" style="font-size: 1.85rem; color: #00e5ff;">
            {summary.total_p10:.0f} – {summary.total_p90:.0f}
        </div>
        <div class="metric-subtext">
            Confianza 80%: <b>[{summary.total_p10:.0f} – {summary.total_p90:.0f}] pts</b><br>
            Confianza 95%: <b>[{summary.total_p025:.0f} – {summary.total_p975:.0f}] pts</b><br>
            Extremos: [{summary.total_min:.0f} – {summary.total_max:.0f}]
        </div>
    </div>
    """, unsafe_allow_html=True)

with m_col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">📊 Marcador Final Estimado</div>
        <div class="metric-value" style="font-size: 1.7rem; color: #63b3ed;">
            {summary.team_a_mean:.0f} - {summary.team_b_mean:.0f}
        </div>
        <div class="metric-subtext">
            {team_a_name[:12]}: <b>[{summary.team_a_p05:.0f} – {summary.team_a_p95:.0f}]</b><br>
            {team_b_name[:12]}: <b>[{summary.team_b_p05:.0f} – {summary.team_b_p95:.0f}]</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

with m_col4:
    win_a_pct = summary.win_prob_a * 100
    win_b_pct = summary.win_prob_b * 100
    leader_name = team_a_name if win_a_pct >= win_b_pct else team_b_name
    leader_pct = max(win_a_pct, win_b_pct)
    ot_pts_str = f" (+{summary.overtime_points_avg:.1f} pts)" if summary.overtime_prob >= 0.005 else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">🏆 Probabilidad Victoria</div>
        <div class="metric-value" style="color: #48bb78; font-size: 1.85rem;">
            {leader_pct:.1f}%
        </div>
        <div class="metric-subtext">
            Líder: <b>{leader_name[:14]}</b><br>
            Prórroga: <b>{summary.overtime_prob*100:.1f}%</b>{ot_pts_str}
        </div>
    </div>
    """, unsafe_allow_html=True)

with m_col5:
    pace_status = "🔥 Acelerado" if summary.observed_pace_per_min > summary.prior_pace_per_min * 1.05 else ("❄️ Lento" if summary.observed_pace_per_min < summary.prior_pace_per_min * 0.95 else "⚖️ Normal")
    reg_note = f"<br><span style='color:#a0aec0; font-size:0.75rem;'>Regr. 3P: <b style='color:#63b3ed;'>{summary.shooting_regression_applied:+.1f} pts</b></span>" if abs(summary.shooting_regression_applied) >= 0.3 else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">⚡ Ritmo y Posesiones</div>
        <div class="metric-value" style="font-size: 1.7rem; color: #e2e8f0;">
            {summary.match_pace_expected:.1f} <span style="font-size: 0.95rem; color: #a0aec0;">poss</span>
        </div>
        <div class="metric-subtext">
            Pts/min obs: <b>{summary.observed_pace_per_min:.2f}</b><br>
            Bayesiano: <b>{pace_status}</b> ({summary.shrinkage_weight*100:.0f}%){reg_note}
        </div>
    </div>
    """, unsafe_allow_html=True)

if summary.dl_active:
    dl_color = "#48bb78" if summary.dl_delta_pace > 0 else ("#f56565" if summary.dl_delta_pace < 0 else "#63b3ed")
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(20, 24, 45, 0.95) 0%, rgba(12, 16, 32, 0.98) 100%); 
                border: 1.5px solid #9f7aea; border-radius: 12px; padding: 14px 18px; margin: 12px 0 18px 0; 
                box-shadow: 0 4px 20px rgba(159, 122, 234, 0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="background: #9f7aea; color: #1a202c; padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 0.8rem; letter-spacing: 0.5px;">
                    🧠 DEEP LEARNING ACTIVO
                </span>
                <span style="color: #e2e8f0; font-weight: 700; font-size: 0.95rem;">
                    Ajuste Fino de Momentum ({summary.dl_momentum_label})
                </span>
            </div>
            <div style="color: #a0aec0; font-size: 0.85rem;">
                Incertidumbre Neuronal: <b style="color: #00e5ff;">±{summary.dl_uncertainty_pts:.1f} pts</b> | 
                Win Prob DL: <b style="color: #48bb78;">{summary.dl_win_prob*100:.1f}%</b>
            </div>
        </div>
        <div style="display: flex; gap: 20px; margin-top: 8px; font-size: 0.88rem; color: #cbd5e0; flex-wrap: wrap;">
            <div>⚡ Delta Ritmo: <b style="color: {dl_color};">{summary.dl_delta_pace:+.2f} pts/min</b></div>
            <div>🎚️ Multiplicador de Ritmo: <b style="color: #ffd700;">{summary.dl_pace_multiplier:.3f}x</b></div>
            <div>ℹ️ <i>{summary.dl_details}</i></div>
        </div>
    </div>
    """, unsafe_allow_html=True)



# ==========================================
# PESTAÑAS DE VISUALIZACIÓN
# ==========================================
tab_live, tab_plays, tab_baselines, tab_prob, tab_explain, tab_betting, tab_historial, tab_ml = st.tabs([
    "📈 Estimación Real en Vivo & Cono de Incertidumbre",
    "⚡ Jugadas en Vivo & Posesiones (Play-by-Play)",
    "📊 Comparativa de Promedios Generales por Torneo",
    "🎲 Distribución de Probabilidades & Over / Under",
    "🧠 Explicación del Modelo & Dinámica de Cuartos",
    "🎰 Apuesta en Vivo (Recomendaciones)",
    "📋 Historial de Partidos & Cotejo",
    "🤖 Aprendizaje Automático & Calibración (ML)"
])

# ------------------------------------------
# TAB 1: GRÁFICO DE ESTIMACIÓN REAL EN VIVO
# ------------------------------------------
with tab_live:
    st.subheader("📈 Trayectoria Real y Cono de Incertidumbre en Tiempo Real")
    st.caption("Muestra la progresión real minuto a minuto, la proyección esperada hacia el final del partido y las bandas de confianza del 80% y 90% (Mínimo y Máximo esperados).")

    # Banner destacado de Intervalos de Confianza y Media
    st.markdown(f"""
    <div style="background: rgba(26, 32, 44, 0.75); border: 1px solid #2d3748; border-radius: 12px; padding: 14px 18px; margin-bottom: 18px; display: flex; justify-content: space-around; flex-wrap: wrap; gap: 10px;">
        <div>📉 <span style="color: #a0aec0;">Intervalo 95% Confianza:</span> <b style="color: #00e5ff; font-size: 1.2rem;">[{summary.total_p025:.0f} – {summary.total_p975:.0f}] pts</b></div>
        <div>🎯 <span style="color: #a0aec0;">Media Proyectada:</span> <b style="color: #ff9900; font-size: 1.2rem;">{summary.total_mean:.1f} pts</b></div>
        <div>📊 <span style="color: #a0aec0;">Intervalo 80% Confianza:</span> <b style="color: #ffd700; font-size: 1.2rem;">[{summary.total_p10:.0f} – {summary.total_p90:.0f}] pts</b></div>
        <div>🔍 <span style="color: #a0aec0;">Rango Intercuartil 50%:</span> <b style="color: #e2e8f0; font-size: 1.2rem;">[{summary.total_p25:.0f} – {summary.total_p75:.0f}] pts</b></div>
    </div>
    """, unsafe_allow_html=True)

    timeline_df = summary.timeline_df
    
    fig_live = go.Figure()

    # 1. Envolvente de Confianza 95% (P025 a P975)
    future_mask = timeline_df["minute"] >= elapsed_total_min
    future_df = timeline_df[future_mask]

    if not future_df.empty and elapsed_total_min < total_game_min:
        fig_live.add_trace(go.Scatter(
            x=pd.concat([future_df["minute"], future_df["minute"][::-1]]),
            y=pd.concat([future_df["proj_p975"], future_df["proj_p025"][::-1]]),
            fill='toself',
            fillcolor='rgba(0, 229, 255, 0.08)',
            line=dict(color='rgba(0, 229, 255, 0.4)', width=1, dash='dot'),
            hoverinfo="skip",
            showlegend=True,
            name='Intervalo Confianza 95% (P02.5 – P97.5)'
        ))

        # 2. Banda de Confianza 80% (P10 a P90)
        fig_live.add_trace(go.Scatter(
            x=pd.concat([future_df["minute"], future_df["minute"][::-1]]),
            y=pd.concat([future_df["proj_p90"], future_df["proj_p10"][::-1]]),
            fill='toself',
            fillcolor='rgba(255, 149, 0, 0.18)',
            line=dict(color='rgba(255,149,0,0)'),
            hoverinfo="skip",
            showlegend=True,
            name='Intervalo Confianza 80% (P10 – P90)'
        ))

        # 3. Banda de Confianza 50% (P25 a P75)
        fig_live.add_trace(go.Scatter(
            x=pd.concat([future_df["minute"], future_df["minute"][::-1]]),
            y=pd.concat([future_df["proj_p75"], future_df["proj_p25"][::-1]]),
            fill='toself',
            fillcolor='rgba(255, 149, 0, 0.28)',
            line=dict(color='rgba(255,149,0,0)'),
            hoverinfo="skip",
            showlegend=True,
            name='Rango Central 50% (P25 – P75)'
        ))

    # 3. Línea de Promedio Base del Torneo
    fig_live.add_trace(go.Scatter(
        x=timeline_df["minute"],
        y=timeline_df["baseline_total"],
        mode='lines',
        name=f'Promedio Histórico Base ({active_config.name.split()[0]})',
        line=dict(color='#718096', width=2, dash='dot'),
        hovertemplate="Min %{x:.1f}: %{y:.1f} pts base<extra></extra>"
    ))

    # 4. Proyección Dinámica Estimada (Media de Monte Carlo)
    if elapsed_total_min < total_game_min and not future_df.empty:
        fig_live.add_trace(go.Scatter(
            x=future_df["minute"],
            y=future_df["proj_mean"],
            mode='lines',
            name='Proyección Estimada Real',
            line=dict(color='#ff9900', width=3, dash='dash'),
            hovertemplate="Min %{x:.1f}: Proyección %{y:.1f} pts<extra></extra>"
        ))

    # 5. Puntos Reales Observados hasta el Momento
    past_mask = timeline_df["minute"] <= elapsed_total_min
    past_df = timeline_df[past_mask]
    if not past_df.empty:
        fig_live.add_trace(go.Scatter(
            x=past_df["minute"],
            y=past_df["actual_total"],
            mode='lines+markers',
            name='Marcación Real Registrada',
            line=dict(color='#00e5ff', width=3.5),
            marker=dict(size=5, color='#00e5ff'),
            hovertemplate="Min %{x:.1f}: <b>%{y:.1f} pts reales</b><extra></extra>"
        ))

    # Marcador de Minuto Actual
    fig_live.add_vline(
        x=elapsed_total_min,
        line_width=2,
        line_dash="dash",
        line_color="#e53e3e",
        annotation_text=f"Reloj Actual ({elapsed_total_min:.1f} min)",
        annotation_position="top left",
        annotation_font_color="#e53e3e"
    )

    # Líneas divisorias de cuartos
    for q_idx in range(1, 4):
        q_min = q_idx * quarter_duration
        fig_live.add_vline(
            x=q_min,
            line_width=1,
            line_dash="dot",
            line_color="rgba(255, 255, 255, 0.2)",
            annotation_text=f"Fin Q{q_idx}",
            annotation_position="bottom right",
            annotation_font_color="#a0aec0"
        )

    fig_live.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(15, 20, 32, 0.7)",
        plot_bgcolor="rgba(10, 14, 23, 0.7)",
        height=520,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(
            title="Minutos de Juego Transcurridos",
            range=[0, total_game_min + 1],
            tickmode="linear",
            tick0=0,
            dtick=quarter_duration
        ),
        yaxis=dict(
            title="Puntos Combinados Totales",
            rangemode="tozero"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode="x unified"
    )

    st.plotly_chart(fig_live, width="stretch")


# ------------------------------------------
# TAB 2: JUGADAS EN VIVO & POSESIONES (PLAY-BY-PLAY)
# ------------------------------------------
with tab_plays:
    st.subheader("⚡ Registro de Jugadas en Vivo (Play-by-Play) y Dinámica de Posesión")
    st.caption("Seguimiento punto a punto de cada anotación extraída en tiempo real de aposta.la, con análisis de ritmo, tiempo por posesión y rachas activas.")

    scraped_plays = st.session_state.get("scraped_plays", [])
    run_team = st.session_state.get("scraped_run_team", "")
    run_pts = st.session_state.get("scraped_run_pts", 0)

    # 1. Cálculos de Posesiones y Ritmo
    poss_combined_est = max(1.0, (total_points_now / 1.08)) if total_points_now > 0 else 1.0
    poss_per_team_est = poss_combined_est / 2.0
    
    elapsed_sec = max(1.0, elapsed_total_min * 60.0)
    sec_per_poss_team = elapsed_sec / max(1.0, poss_per_team_est)
    
    # Ritmo proyectado a partido completo
    live_pace_proj = (poss_per_team_est / max(0.5, elapsed_total_min)) * total_game_min if elapsed_total_min > 0 else active_config.league_pace
    
    # Eficiencia ofensiva observada (puntos / 100 posesiones)
    live_off_rtg = (total_points_now / max(1.0, poss_combined_est)) * 100.0

    # 4 Tarjetas de Dinámica de Posesión
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    with p_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-color: rgba(0, 229, 255, 0.4);">
            <div class="metric-title" style="color: #00e5ff;">⏱️ Tiempo por Posesión</div>
            <div class="metric-value" style="color: #00e5ff; font-size: 2rem;">{sec_per_poss_team:.1f} <span style="font-size: 1rem; color: #a0aec0;">seg</span></div>
            <div class="metric-subtext">
                Duración media del ataque<br>
                <b>{poss_per_team_est:.1f} posesiones</b> por equipo
            </div>
        </div>
        """, unsafe_allow_html=True)

    with p_col2:
        pace_delta = live_pace_proj - active_config.league_pace
        pace_color = "#48bb78" if pace_delta > 0 else "#f56565"
        st.markdown(f"""
        <div class="metric-card" style="border-color: rgba(255, 149, 0, 0.4);">
            <div class="metric-title" style="color: #ff9800;">⚡ Ritmo en Vivo (Pace)</div>
            <div class="metric-value" style="color: #ff9800; font-size: 2rem;">{live_pace_proj:.1f} <span style="font-size: 1rem; color: #a0aec0;">poss</span></div>
            <div class="metric-subtext">
                Proyección a {total_game_min}m | Liga: {active_config.league_pace:.1f}<br>
                Diferencial: <b style="color: {pace_color};">{'+' if pace_delta>0 else ''}{pace_delta:.1f} poss</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with p_col3:
        if run_pts >= 4:
            run_badge = f"<b style='color: #48bb78;'>🔥 {run_team[:14]}</b><br>Racha activa: <b style='color: #ff9800;'>+{run_pts} pts seguidos</b>"
        elif run_team:
            run_badge = f"<b>{run_team[:14]}</b><br>Última anotación (+{run_pts} pts)"
        else:
            run_badge = "Sin racha registrada"
            
        st.markdown(f"""
        <div class="metric-card" style="border-color: rgba(72, 187, 120, 0.4);">
            <div class="metric-title" style="color: #48bb78;">🔥 Momentum / Racha</div>
            <div class="metric-value" style="color: #48bb78; font-size: 1.8rem;">+{run_pts} pts</div>
            <div class="metric-subtext">{run_badge}</div>
        </div>
        """, unsafe_allow_html=True)

    with p_col4:
        st.markdown(f"""
        <div class="metric-card" style="border-color: rgba(159, 122, 234, 0.4);">
            <div class="metric-title" style="color: #b794f4;">📈 Eficiencia Ofensiva</div>
            <div class="metric-value" style="color: #b794f4; font-size: 2rem;">{live_off_rtg:.1f}</div>
            <div class="metric-subtext">
                Puntos / 100 posesiones<br>
                Total actual: <b>{int(total_points_now)} pts</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. Historial de Jugadas (Play-by-Play Feed)
    st.markdown("#### 📋 Registro Detallado de Canastas y Marcador (Cronología)")
    if scraped_plays:
        col_flt1, col_flt2 = st.columns([2, 1])
        with col_flt1:
            filtro_equipo = st.radio(
                "Filtrar jugadas por:",
                ["Todos los equipos", f"Solo {team_a_name}", f"Solo {team_b_name}"],
                horizontal=True,
                key="filter_plays_team"
            )
        with col_flt2:
            st.markdown(f"<div style='text-align: right; color: #a0aec0; padding-top: 10px;'><b>{len(scraped_plays)} jugadas</b> registradas</div>", unsafe_allow_html=True)

        filtered_plays = scraped_plays
        if filtro_equipo == f"Solo {team_a_name}":
            filtered_plays = [p for p in scraped_plays if p["team"] == team_a_name or p.get("who") == "HOME"]
        elif filtro_equipo == f"Solo {team_b_name}":
            filtered_plays = [p for p in scraped_plays if p["team"] == team_b_name or p.get("who") == "AWAY"]

        # Mostrar en lista cronológica inversa (las más recientes primero)
        plays_html = '<div style="max-height: 420px; overflow-y: auto; padding-right: 8px; border: 1px solid #2d3748; border-radius: 10px; background: rgba(15, 20, 32, 0.6);">'
        for idx, p in enumerate(reversed(filtered_plays)):
            is_home = (p["team"] == team_a_name or p.get("who") == "HOME")
            pts_val = p.get("pts", 2)
            pts_badge_color = "#9f7aea" if pts_val == 3 else ("#48bb78" if pts_val == 2 else "#ecc94b")
            pts_label = f"+{pts_val} pts ({'Triple' if pts_val==3 else ('Doble' if pts_val==2 else 'TL')})"
            team_icon = "🏠" if is_home else "✈️"
            team_color = "#63b3ed" if is_home else "#f687b3"
            info_label = p.get('info', 'Q')
            team_name_str = p.get('team', '')
            score_h = p.get('score_home', 0)
            score_a = p.get('score_away', 0)
            
            plays_html += (
                f'<div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; border-bottom:1px solid rgba(255,255,255,0.06); font-family:\'JetBrains Mono\', monospace;">'
                f'<div style="display:flex; align-items:center; gap:10px;">'
                f'<span style="background:rgba(255,255,255,0.1); color:#cbd5e0; padding:2px 6px; border-radius:4px; font-size:0.8rem;">{info_label}</span>'
                f'<span style="color:{team_color}; font-weight:700;">{team_icon} {team_name_str}</span>'
                f'<span style="background:{pts_badge_color}22; color:{pts_badge_color}; border:1px solid {pts_badge_color}66; padding:1px 6px; border-radius:4px; font-size:0.8rem; font-weight:700;">{pts_label}</span>'
                f'</div>'
                f'<div style="font-size:1.1rem; font-weight:800; color:#f7fafc;">{score_h} – {score_a}</div>'
                f'</div>'
            )
        plays_html += '</div>'
        st.markdown(plays_html, unsafe_allow_html=True)
    else:
        st.info("ℹ️ Para ver las jugadas en vivo y el desglose de posesiones, conectá un link de partido en vivo de aposta.la en la barra lateral.")


# ------------------------------------------
# TAB 3: PROMEDIOS GENERALES POR TORNEO
# ------------------------------------------
with tab_baselines:
    st.subheader("📊 Comparativa de Promedios Generales por Torneo")
    st.markdown("""
    Comparación de las trayectorias estándar de los **torneos reglamentarios**, 
    demostrando la diferencia estructural debida a la duración del periodo (12 min vs 10 min) y al ritmo ofensivo.
    """)

    all_traj = BasketballPredictor.get_all_tournaments_baseline_trajectories()

    fig_tournaments = make_subplots(
        rows=1, cols=2,
        column_widths=[0.65, 0.35],
        subplot_titles=("Curva de Progresión Acumulada (Puntos por Minuto)", "Puntos Promedio por Cuarto Combinados")
    )

    colors_map = {
        "NBA": "#ff7700",
        "FIBA": "#3182ce",
        "NBL": "#10b981",
        "NCAA_FEMENIL": "#9f7aea"
    }

    # Gráfico de líneas acumuladas
    for key, cfg in TOURNAMENT_PRESETS.items():
        sub_df = all_traj[all_traj["tournament_key"] == key]
        fig_tournaments.add_trace(
            go.Scatter(
                x=sub_df["minute"],
                y=sub_df["baseline_total"],
                name=cfg.name.split()[0],
                mode='lines',
                line=dict(color=colors_map.get(key, "#10b981"), width=3),
                hovertemplate=f"<b>{cfg.name.split()[0]}</b><br>Min %{{x}}: %{{y:.1f}} pts<extra></extra>"
            ),
            row=1, col=1
        )

    # Gráfico de barras por cuarto
    quarters_labels = ["1° Q", "2° Q", "3° Q", "4° Q", "Total Partido"]
    for key, cfg in TOURNAMENT_PRESETS.items():
        q_avg = cfg.total_avg_quarter
        # Ponderación por factor de cuarto
        q_vals = [
            q_avg * QUARTER_PACE_FACTORS[1],
            q_avg * QUARTER_PACE_FACTORS[2],
            q_avg * QUARTER_PACE_FACTORS[3],
            q_avg * QUARTER_PACE_FACTORS[4],
            cfg.total_game_avg
        ]
        fig_tournaments.add_trace(
            go.Bar(
                x=quarters_labels,
                y=q_vals,
                name=cfg.name.split()[0],
                marker_color=colors_map.get(key, "#10b981"),
                opacity=0.85,
                hovertemplate="%{x}: %{y:.1f} pts<extra></extra>"
            ),
            row=1, col=2
        )

    fig_tournaments.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(15, 20, 32, 0.7)",
        plot_bgcolor="rgba(10, 14, 23, 0.7)",
        height=500,
        margin=dict(l=30, r=30, t=50, b=40),
        barmode='group'
    )
    fig_tournaments.update_xaxes(title_text="Minutos de Juego", row=1, col=1)
    fig_tournaments.update_yaxes(title_text="Puntos Totales", row=1, col=1)
    fig_tournaments.update_yaxes(title_text="Puntos", row=1, col=2)

    st.plotly_chart(fig_tournaments, width="stretch")

    # Tabla resumen de parámetros
    st.markdown("#### 📋 Parámetros de los Torneos Reglamentarios")
    summary_data = []
    for key, cfg in TOURNAMENT_PRESETS.items():
        summary_data.append({
            "Competencia / Formato": cfg.name,
            "Duración Cuarto": f"{cfg.quarter_duration} minutos",
            "Duración Total": f"{cfg.total_game_duration} minutos",
            "Promedio x Equipo (1 Q)": f"{cfg.team_avg_quarter_min:.0f} – {cfg.team_avg_quarter_max:.0f} pts",
            "Total Combinado (1 Q)": f"{cfg.team_avg_quarter_min*2:.0f} – {cfg.team_avg_quarter_max*2:.0f} pts",
            "Total Esperado Partido": f"~{cfg.total_game_avg:.0f} pts",
            "Ritmo Teórico": f"{(cfg.total_game_avg/cfg.total_game_duration):.2f} pts/min"
        })
    st.dataframe(pd.DataFrame(summary_data), hide_index=True, width="stretch")


# ------------------------------------------
# TAB 3: PROBABILIDADES & OVER / UNDER
# ------------------------------------------
with tab_prob:
    st.subheader("🎲 Análisis de Líneas de Apuestas y Probabilidad Over / Under")
    st.markdown("Simula cualquier línea de puntos total del mercado y calcula las probabilidades exactas derivadas de las 5,000 iteraciones.")

    col_ou1, col_ou2 = st.columns([1, 2])

    with col_ou1:
        st.markdown("#### 🎯 Definir Línea Objetivo")
        # Sugerir la línea redondeada a .5 de la media proyectada
        suggested_line = round(summary.total_mean * 2) / 2.0
        val_ou = max(5.0, min(400.0, float(suggested_line)))
        line_input = st.number_input(
            "Línea de Puntos Totales (Over / Under):",
            min_value=5.0,
            max_value=400.0,
            value=val_ou,
            step=0.5
        )

        p_over, p_under = BasketballPredictor.calculate_over_under(summary.simulated_totals, line_input)

        st.markdown(f"""
        <div style="margin-top: 15px; display: flex; gap: 10px;">
            <div style="flex: 1; background: rgba(72, 187, 120, 0.15); border: 1px solid #48bb78; border-radius: 10px; padding: 15px; text-align: center;">
                <div style="color: #48bb78; font-weight: 700; font-size: 0.9rem;">OVER {line_input}</div>
                <div style="color: #f7fafc; font-size: 2.2rem; font-weight: 800; font-family: 'JetBrains Mono';">{p_over*100:.1f}%</div>
                <div style="color: #cbd5e0; font-size: 0.8rem;">Cuota Justa: <b>{(1/p_over if p_over > 0 else 99):.2f}</b></div>
            </div>
            <div style="flex: 1; background: rgba(245, 101, 101, 0.15); border: 1px solid #f56565; border-radius: 10px; padding: 15px; text-align: center;">
                <div style="color: #f56565; font-weight: 700; font-size: 0.9rem;">UNDER {line_input}</div>
                <div style="color: #f7fafc; font-size: 2.2rem; font-weight: 800; font-family: 'JetBrains Mono';">{p_under*100:.1f}%</div>
                <div style="color: #cbd5e0; font-size: 0.8rem;">Cuota Justa: <b>{(1/p_under if p_under > 0 else 99):.2f}</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Tabla de Probabilidades Rápidas:**")
        quick_lines = [suggested_line - 5.5, suggested_line - 2.5, suggested_line, suggested_line + 2.5, suggested_line + 5.5]
        quick_rows = []
        for ql in quick_lines:
            po, pu = BasketballPredictor.calculate_over_under(summary.simulated_totals, ql)
            quick_rows.append({
                "Línea": f"{ql:.1f}",
                "Over %": f"{po*100:.1f}%",
                "Under %": f"{pu*100:.1f}%",
                "Cuota Over": f"{(1/po if po > 0 else 99):.2f}",
                "Cuota Under": f"{(1/pu if pu > 0 else 99):.2f}"
            })
        st.dataframe(pd.DataFrame(quick_rows), hide_index=True, width="stretch")

    with col_ou2:
        # Histograma de Distribución Monte Carlo
        fig_dist = go.Figure()

        totals = summary.simulated_totals
        under_points = totals[totals <= line_input]
        over_points = totals[totals > line_input]

        fig_dist.add_trace(go.Histogram(
            x=under_points,
            name=f'Under {line_input}',
            marker_color='#f56565',
            opacity=0.75,
            nbinsx=40
        ))
        fig_dist.add_trace(go.Histogram(
            x=over_points,
            name=f'Over {line_input}',
            marker_color='#48bb78',
            opacity=0.75,
            nbinsx=40
        ))

        # Superposición de la campana de Gauss teórica Normal N(mu, sigma^2)
        if summary.analytical_normal is not None and summary.total_std > 0:
            bin_width = (np.max(totals) - np.min(totals)) / 40.0 if np.max(totals) > np.min(totals) else 1.0
            norm_y_scaled = summary.analytical_normal.pdf_y * len(totals) * bin_width
            fig_dist.add_trace(go.Scatter(
                x=summary.analytical_normal.pdf_x,
                y=norm_y_scaled,
                mode='lines',
                name='Campana Normal Teórica N(μ, σ²)',
                line=dict(color='#00e5ff', width=2.5, dash='dash'),
                hovertemplate="Puntos: %{x:.1f}<br>Densidad Teórica: %{y:.0f}<extra></extra>"
            ))

        # Línea de umbral Over/Under
        fig_dist.add_vline(
            x=line_input,
            line_width=3,
            line_color="#ffd700",
            annotation_text=f"Línea: {line_input}",
            annotation_position="top"
        )

        # Línea de la Media Proyectada
        fig_dist.add_vline(
            x=summary.total_mean,
            line_width=2,
            line_dash="dash",
            line_color="#ff9900",
            annotation_text=f"Media: {summary.total_mean:.1f}",
            annotation_position="bottom right",
            annotation_font_color="#ff9900"
        )

        # Líneas de Intervalo 95% (P025 y P975)
        fig_dist.add_vline(
            x=summary.total_p025,
            line_width=1.5,
            line_dash="dot",
            line_color="#00e5ff",
            annotation_text=f"95% Inf: {summary.total_p025:.0f}",
            annotation_position="top left",
            annotation_font_color="#00e5ff"
        )
        fig_dist.add_vline(
            x=summary.total_p975,
            line_width=1.5,
            line_dash="dot",
            line_color="#00e5ff",
            annotation_text=f"95% Sup: {summary.total_p975:.0f}",
            annotation_position="top right",
            annotation_font_color="#00e5ff"
        )

        fig_dist.update_layout(
            title=f"Distribución Estocástica ({num_sims:,} simulaciones) vs Aproximación Gaussiana",
            template="plotly_dark",
            paper_bgcolor="rgba(15, 20, 32, 0.7)",
            plot_bgcolor="rgba(10, 14, 23, 0.7)",
            height=460,
            barmode='stack',
            xaxis=dict(title="Puntos Combinados Totales"),
            yaxis=dict(title="Frecuencia Simulada"),
            margin=dict(l=30, r=30, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_dist, width="stretch")

        # Tabla comparativa de Modelos
        if summary.analytical_normal is not None:
            norm_over = summary.analytical_normal.prob_over(line_input)
            norm_under = summary.analytical_normal.prob_under(line_input)
            comp_df = pd.DataFrame([
                {
                    "Modelo": "Simulación Monte Carlo (Empírico)",
                    "Media (μ)": f"{summary.total_mean:.1f}",
                    "Desv. Est. (σ)": f"±{summary.total_std:.1f}",
                    "Intervalo 80%": f"[{summary.total_p10:.0f} – {summary.total_p90:.0f}]",
                    "Intervalo 95%": f"[{summary.total_p025:.0f} – {summary.total_p975:.0f}]",
                    f"Over {line_input}": f"{p_over*100:.1f}%",
                    f"Under {line_input}": f"{p_under*100:.1f}%"
                },
                {
                    "Modelo": "Distribución Normal N(μ, σ²)",
                    "Media (μ)": f"{summary.analytical_normal.mu:.1f}",
                    "Desv. Est. (σ)": f"±{summary.analytical_normal.sigma:.1f}",
                    "Intervalo 80%": f"[{summary.analytical_normal.p10:.0f} – {summary.analytical_normal.p90:.0f}]",
                    "Intervalo 95%": f"[{summary.analytical_normal.p025:.0f} – {summary.analytical_normal.p975:.0f}]",
                    f"Over {line_input}": f"{norm_over*100:.1f}%",
                    f"Under {line_input}": f"{norm_under*100:.1f}%"
                }
            ])
            st.markdown("##### ⚖️ Comparativa: Monte Carlo (Discreto) vs Gaussiano (Analítico)")
            st.dataframe(comp_df, hide_index=True, width="stretch")


# ------------------------------------------
# TAB 4: EXPLICACIÓN TÁCTICA & MATEMÁTICA
# ------------------------------------------
with tab_explain:
    st.subheader("🧠 Metodología del Modelo Probabilístico Avanzado")
    st.markdown("""
    Este sistema modela la anotación total a partir de los fundamentos de la analítica moderna de baloncesto:
    los puntos brutos son una variable secundaria; **el total es el producto del volumen de posesiones por la eficiencia de cada una**.
    """)
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.markdown(r"""
        ### 🏀 1. Descomposición Fundamental: Ritmo × Eficiencia
        Modelar a partir de esta descomposición aísla el ritmo del acierto y reduce el ruido estocástico:
        
        $$\text{Puntos Totales} = (\text{Posesiones Totales}) \times (\text{Eficiencia Ofensiva Combinada})$$

        - **Ritmo de Juego (Pace):** Define la cantidad de oportunidades ofensivas.
          $$\text{Pace} \approx 0.5 \times (\text{FGA} + 0.44 \times \text{FTA} - \text{ORB} + \text{TOV})$$
          La proyección cruzada del enfrentamiento se obtiene mediante:
          $$\text{Pace}_{\text{match}} = \frac{\text{Pace}_A \times \text{Pace}_B}{\text{Pace}_{\text{Liga}}}$$
          *La correlación entre el Pace combinado estimado y los puntos totales supera típicamente $r \approx 0.65$.*

        - **Eficiencia Cruzada (Off/Def Rating):** Puntos anotados o concedidos por 100 posesiones.
          $$\text{OffRtg}_{A \to B} = \frac{\text{OffRtg}_A \times \text{DefRtg}_B}{\text{Promedio}_{\text{Liga}}}$$
          Un equipo con 115 OffRtg enfrentando a una defensa de 115 DefRtg proyecta cerca de 1.15 puntos por posesión.
        """)

        st.markdown(r"""
        ### 🎯 2. Los Cuatro Factores de Dean Oliver
        Explican más del 90% de la varianza en la eficiencia ofensiva y defensiva de un equipo:
        1. **eFG% (Tiro Efectivo - 40% del peso total):** $\frac{\text{FGM} + 0.5 \times \text{3PM}}{\text{FGA}}$
        2. **TOV% (Tasa de Pérdidas - 25% del peso):** Pérdidas cometidas por cada 100 jugadas.
        3. **ORB% (Rebote Ofensivo - 20% del peso):** Segundas oportunidades capturadas tras fallo.
        4. **FT Rate (Tasa de Tiros Libres - 15% del peso):** $\frac{\text{FT}}{\text{FGA}}$ (capacidad de forzar faltas y tiros fáciles).
        """)

        st.markdown(r"""
        ### 🔄 3. Actualización Bayesiana en Vivo & Regresión a la Media
        El porcentaje de tiro (especialmente el triple) tiene una alta varianza estocástica a corto plazo. Aplicamos **suavizado empírico bayesiano (Empirical Bayes)**:
        
        $$\lambda_{\text{posterior}}(t) = w(t) \cdot \lambda_{\text{observado}} + (1 - w(t)) \cdot \lambda_{\text{prior}}, \quad w(t) = \frac{t}{t + k}$$
        
        Evita sobreajustar por rachas cortas de 3 o 4 minutos de acierto o sequía anormal.
        """)

    with col_exp2:
        st.markdown(r"""
        ### ⚖️ 4. Factores de Ajuste Contextual y Sesgos Críticos
        - **Efecto Back-to-Back y Fatiga:** Jugar en noches consecutivas reduce la eficiencia ofensiva entre **1.5 y 2.5 puntos / 100 posesiones**, afectando con mayor severidad al acierto exterior (3P%) en el **3.° y 4.° cuarto**.
        - **Ventaja de Localía (Home-Court Advantage):** Aporta históricamente entre **+2.5 y +3.2 pts** en NBA y entre **+3.0 y +4.5 pts** en ligas FIBA/locales, impulsado por confort de tiro y arbitraje (tiros libres concedidos).
        - **El "Efecto Garbage Time":** Partidos con diferenciales **$> 20$ puntos al entrar al 4.° cuarto** sufren una caída drástica del rating ofensivo y un aumento de pérdidas no forzadas debido al ingreso de suplentes, recortando las colas altas.
        - **Dinámica Clutch (< 2 min de 4Q, $\le 8$ pts):** Las faltas tácticas intencionales y el reloj detenido disparan la tasa anotadora por minuto un **$+32\%$**.
        """)

        st.markdown(r"""
        ### 🎲 5. Distribuciones Probabilísticas: Normal vs Monte Carlo
        - **Distribución Normal ($\mathcal{N}(\mu, \sigma^2)$):**
          Excelente aproximación analítica de primer orden para los puntos totales de partido completo.
          - $\sigma$ típica NBA: **18 a 22 puntos**.
          - $\sigma$ típica FIBA: **14 a 17 puntos**.
          - Proporciona intervalos de confianza cerrados del **80%** ($\mu \pm 1.282\sigma$) y **95%** ($\mu \pm 1.960\sigma$).
        - **Simulaciones Monte Carlo ($N=10\,000$ iteraciones):**
          Genera no solo la media esperada sino la campana completa discretizada con **distribución Binomial Negativa** con sobre-dispersión ($\sigma^2 \approx 1.25\mu$) para modelar de forma realista canastas de 1, 2 o 3 puntos.
        """)


# ==========================================
# TAB 5: HISTORIAL DE PARTIDOS (BD SQLite)
# ==========================================
with tab_historial:
    st.subheader("📋 Historial de Partidos Registrados")
    st.caption("Guarda el estado actual del partido en la base de datos local para consultarlo o compararlo más adelante.")

    # ── Sección: GUARDAR PARTIDO ACTUAL ──────────────────
    with st.expander("💾 Guardar / Actualizar Partido Actual en la BD", expanded=True):
        col_save1, col_save2 = st.columns([2, 1])
        with col_save1:
            notas_partido = st.text_area(
                "Notas opcionales (apuntes, contexto, línea de apuesta):",
                placeholder="Ej: Cuotas casas apuestas 177 pts, clima frío, lesionados...",
                height=80,
                key="notas_partido_input"
            )
        with col_save2:
            st.markdown("**Partido en pantalla:**")
            st.markdown(f"🏠 **{team_a_name}** {int(score_a_total)} – {int(score_b_total)} **{team_b_name}** ✈️")
            estado_label = "✅ Finalizado" if current_quarter > 4 else f"🟢 Q{current_quarter} | {rem_min:02d}:{rem_sec:02d}"
            st.markdown(f"Estado: {estado_label}")

        btn_col1, btn_col2 = st.columns(2)
        existing_en_curso = next(
            (p for p in listar_partidos(30)
             if p["estado"] == "en_curso"
             and p["equipo_local"].strip().lower() == team_a_name.strip().lower()
             and p["equipo_visitante"].strip().lower() == team_b_name.strip().lower()),
            None
        )

        with btn_col1:
            if existing_en_curso:
                st.caption(f"💡 Ya existe este partido en curso (#{existing_en_curso['id']}). Al guardar se actualizará sin duplicar.")
                btn_save_lbl = f"🔄 Actualizar Partido #{existing_en_curso['id']}"
            else:
                btn_save_lbl = "💾 Guardar Partido Nuevo"

            if st.button(btn_save_lbl, width="stretch", type="primary", key="btn_save_or_upd_match"):
                if existing_en_curso:
                    pid = existing_en_curso["id"]
                    actualizar_partido(
                        partido_id=pid,
                        cuarto_actual=current_quarter,
                        min_restantes=rem_min,
                        seg_restantes=rem_sec,
                        quarters_data=quarters_data,
                        notas=notas_partido
                    )
                    st.session_state["loaded_game_id"] = pid
                    action_txt = "actualizado"
                else:
                    pid = crear_partido(
                        equipo_local=team_a_name,
                        equipo_visitante=team_b_name,
                        torneo_nombre=torneo_sel,
                        cuarto_actual=current_quarter,
                        min_restantes=rem_min,
                        seg_restantes=rem_sec,
                        quarters_data=quarters_data,
                        notas=notas_partido
                    )
                    st.session_state["loaded_game_id"] = pid
                    action_txt = "guardado con ID"

                # Guardar snapshot de predicción
                guardar_snapshot(
                    partido_id=pid,
                    cuarto_snapshot=current_quarter,
                    minutos_jugados=elapsed_total_min,
                    pts_local_actual=int(score_a_total),
                    pts_visitante_actual=int(score_b_total),
                    summary=summary,
                    linea_apuesta=bet_number,
                    prob_over=prob_mas,
                    prob_under=prob_menos,
                    num_simulaciones=num_sims
                )
                # Guardar historial de jugadas (play-by-play)
                plays_now = st.session_state.get("scraped_plays", [])
                if plays_now:
                    guardar_jugadas(pid, plays_now)
                st.success(f"✅ Partido #{pid} {action_txt} correctamente.")
                st.rerun()

        with btn_col2:
            partidos_en_curso = [p for p in listar_partidos(20) if p["estado"] == "en_curso"]
            if partidos_en_curso:
                opciones_update = {
                    f"#{p['id']} — {p['equipo_local']} vs {p['equipo_visitante']}": p["id"]
                    for p in partidos_en_curso
                }
                partido_a_actualizar = st.selectbox(
                    "Actualizar partido existente:",
                    list(opciones_update.keys()),
                    key="select_update_partido"
                )
                if st.button("🔄 Actualizar partido seleccionado", width="stretch"):
                    pid_upd = opciones_update[partido_a_actualizar]
                    actualizar_partido(
                        partido_id=pid_upd,
                        cuarto_actual=current_quarter,
                        min_restantes=rem_min,
                        seg_restantes=rem_sec,
                        quarters_data=quarters_data,
                        notas=notas_partido
                    )
                    guardar_snapshot(
                        partido_id=pid_upd,
                        cuarto_snapshot=current_quarter,
                        minutos_jugados=elapsed_total_min,
                        pts_local_actual=int(score_a_total),
                        pts_visitante_actual=int(score_b_total),
                        summary=summary,
                        linea_apuesta=bet_number,
                        prob_over=prob_mas,
                        prob_under=prob_menos,
                        num_simulaciones=num_sims
                    )
                    # Actualizar historial de jugadas (play-by-play)
                    plays_now_upd = st.session_state.get("scraped_plays", [])
                    if plays_now_upd:
                        guardar_jugadas(pid_upd, plays_now_upd)
                    st.success(f"✅ Partido #{pid_upd} actualizado")
                    st.rerun()
            else:
                st.info("No hay partidos 'en curso' para actualizar.")

    st.markdown("---")

    # ── Sección: LISTADO DE PARTIDOS ──────────────────────
    todos_partidos = listar_partidos(100)

    if not todos_partidos:
        st.info("📭 Todavía no hay partidos guardados. Usa el botón de arriba para registrar el partido actual.")
    else:
        # Filtros
        filt_col1, filt_col2 = st.columns(2)
        with filt_col1:
            filtro_estado = st.selectbox(
                "Filtrar por estado:",
                ["Todos", "en_curso", "finalizado"],
                key="filtro_estado_hist"
            )
        with filt_col2:
            filtro_buscar = st.text_input(
                "🔍 Buscar equipo:",
                placeholder="Ej: Lakers, Real Madrid...",
                key="filtro_buscar_hist"
            )

        # Aplicar filtros
        partidos_filtrados = todos_partidos
        if filtro_estado != "Todos":
            partidos_filtrados = [p for p in partidos_filtrados if p["estado"] == filtro_estado]
        if filtro_buscar.strip():
            q = filtro_buscar.strip().lower()
            partidos_filtrados = [
                p for p in partidos_filtrados
                if q in p["equipo_local"].lower() or q in p["equipo_visitante"].lower()
            ]

        st.markdown(f"**{len(partidos_filtrados)} partido(s) encontrado(s)**")

        for p in partidos_filtrados:
            estado_icon = "✅" if p["estado"] == "finalizado" else "🟢"
            total_pts = p["total_local"] + p["total_visitante"]
            cuarto_str = "Final" if p["cuarto_actual"] > 4 else f"Q{p['cuarto_actual']} {p['min_restantes']:02d}:{p['seg_restantes']:02d}"

            with st.expander(
                f"{estado_icon} #{p['id']} — {p['equipo_local']} {p['total_local']} – {p['total_visitante']} {p['equipo_visitante']}  |  {cuarto_str}  |  Total: {total_pts} pts"
            ):
                det_col1, det_col2, det_col3 = st.columns(3)
                with det_col1:
                    st.markdown(f"**Torneo:** {p['torneo']}")
                    st.markdown(f"**Estado:** {p['estado']}")
                    st.markdown(f"**Creado:** {p['creado_en'][:16]}")
                with det_col2:
                    st.markdown(f"**Actualizado:** {p['actualizado_en'][:16]}")
                    if p.get("notas"):
                        st.markdown(f"**Notas:** {p['notas']}")
                with det_col3:
                    # Ver marcadores por cuarto
                    partido_det = obtener_partido(p["id"])
                    if partido_det and partido_det.get("marcadores"):
                        marcadores_df = pd.DataFrame(partido_det["marcadores"])
                        marcadores_df.columns = ["Cuarto", p['equipo_local'][:10], p['equipo_visitante'][:10]]
                        st.dataframe(marcadores_df, hide_index=True, width="stretch")

                # Finalizar y Liquidar Partido (si está en curso)
                if p["estado"] == "en_curso":
                    st.markdown("##### 🏁 Finalizar Partido y Liquidar Apuestas")
                    fin_col1, fin_col2, fin_col3 = st.columns([1.2, 1.2, 1.6])
                    with fin_col1:
                        pts_fin_loc = st.number_input(
                            f"Marcador Final {p['equipo_local']}:",
                            min_value=0, max_value=300,
                            value=int(p['total_local']),
                            key=f"fin_loc_{p['id']}"
                        )
                    with fin_col2:
                        pts_fin_vis = st.number_input(
                            f"Marcador Final {p['equipo_visitante']}:",
                            min_value=0, max_value=300,
                            value=int(p['total_visitante']),
                            key=f"fin_vis_{p['id']}"
                        )
                    with fin_col3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🏆 Finalizar y Liquidar", key=f"btn_fin_{p['id']}", type="primary"):
                            res_liq = finalizar_partido_y_liquidar(p['id'], int(pts_fin_loc), int(pts_fin_vis))
                            st.success(f"✅ Partido #{p['id']} finalizado ({pts_fin_loc}-{pts_fin_vis}). Apuestas liquidadas: {res_liq['apuestas_liquidadas']} (Ganadas: {res_liq['ganadas']}, Perdidas: {res_liq['perdidas']})")
                            st.rerun()

                # Cotejo de Hitos de Predicción vs Marcador Final
                cotejo = cotejar_hitos_partido(p["id"])
                if cotejo and cotejo.get("hitos"):
                    st.markdown("##### 🎯 Cotejo de Hitos de Predicción vs Marcador Final")
                    c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
                    with c_kpi1:
                        st.metric("Total Final Real", f"{cotejo['total_real']} pts", f"{cotejo['marcador_final']}")
                    with c_kpi2:
                        st.metric("Error Medio (MAE)", f"±{cotejo['mae_promedio']:.1f} pts")
                    with c_kpi3:
                        st.metric("Acierto Ganador", f"{cotejo['pct_acierto_ganador']:.1f}%")
                    with c_kpi4:
                        st.metric("Cobertura Rango 80%", f"{cotejo['pct_cobertura_80']:.1f}%")

                    df_cotejo = pd.DataFrame(cotejo["hitos"])[[
                        "nombre", "minutos_jugados", "marcador_momento", "total_proyectado",
                        "total_real", "error_puntos", "rango_80", "calificacion"
                    ]].copy()
                    df_cotejo.columns = [
                        "Hito", "Min Jugados", "Marcador En Hito", "Proy. Modelo",
                        "Total Final", "Error (pts)", "Rango 80%", "Calificación"
                    ]
                    st.dataframe(df_cotejo, hide_index=True, width="stretch")
                else:
                    snaps = listar_snapshots(p["id"])
                    if snaps:
                        st.markdown(f"**{len(snaps)} snapshot(s) guardados:**")
                        snaps_df = pd.DataFrame(snaps)[[
                            "guardado_en", "cuarto_snapshot", "total_actual",
                            "total_proyectado", "total_p05", "total_p95",
                            "prob_victoria_local", "linea_apuesta", "prob_over", "prob_under"
                        ]].copy()
                        snaps_df.columns = [
                            "Guardado", "Q", "Total Real",
                            "Proy.", "P05", "P95",
                            "% Vic Local", "Línea", "% Over", "% Under"
                        ]
                        snaps_df["Guardado"] = snaps_df["Guardado"].str[:16]
                        st.dataframe(snaps_df, hide_index=True, width="stretch")

                # Botones de Acción
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button(f"📂 Cargar para editar", key=f"load_{p['id']}", type="secondary"):
                        st.session_state["loaded_game_id"] = p["id"]
                        st.rerun()
                with btn_col2:
                    if st.button(f"🗑️ Eliminar partido", key=f"del_{p['id']}", type="secondary"):
                        eliminar_partido(p["id"])
                        st.warning(f"Partido #{p['id']} eliminado.")
                        st.rerun()


# ------------------------------------------
# TAB 6: 🎰 APUESTA EN VIVO
# ------------------------------------------
with tab_betting:
    st.subheader("🎰 Análisis Probabilístico en Vivo & Recomendación de Apuesta")
    st.caption("Combina el historial de jugadas (play-by-play) con la simulación Monte Carlo para emitir señales de apuesta en tiempo real.")

    scraped_plays_betting = st.session_state.get("scraped_plays", [])
    has_plays = len(scraped_plays_betting) > 0

    # Calcular señales del play-by-play
    if has_plays:
        lb_signals = analyze_plays(
            plays=scraped_plays_betting,
            team_a=team_a_name,
            team_b=team_b_name,
            total_elapsed_min=max(0.5, elapsed_total_min),
            total_game_min=float(total_game_min),
        )
    else:
        from model.live_betting import LiveBettingSignals
        lb_signals = LiveBettingSignals()

    # Cuotas de la casa (desde scraping)
    house_odds_over_val = st.session_state.get("scraped_odds_over", None)
    house_odds_under_val = st.session_state.get("scraped_odds_under", None)
    scraped_line_bet = st.session_state.get("scraped_odds_line", None)

    # Recomendación integrada
    bet_line_for_rec = float(scraped_line_bet) if scraped_line_bet else float(bet_number)
    line_source_rec = "casa" if scraped_line_bet else "manual"
    league_pace_per_min = active_config.total_game_avg / float(total_game_min)

    prob_o_rec, prob_u_rec = BasketballPredictor.calculate_over_under(
        summary.simulated_totals, bet_line_for_rec
    )
    lb_rec = get_live_betting_recommendation(
        signals=lb_signals,
        prob_over=prob_o_rec,
        prob_under=prob_u_rec,
        line=bet_line_for_rec,
        model_mean=summary.total_mean,
        league_avg_pace_per_min=league_pace_per_min,
        house_odds_over=house_odds_over_val,
        house_odds_under=house_odds_under_val,
        line_source=line_source_rec,
    )

    # ── Alerta Sonora y Visual de Apuesta en Vivo ────────────────
    live_alert = evaluate_betting_alert(
        prob_over=prob_o_rec,
        prob_under=prob_u_rec,
        line=bet_line_for_rec,
        bet_grade=lb_rec.bet_grade,
        ev_over=lb_rec.ev_over,
        ev_under=lb_rec.ev_under,
        threshold_pct=float(alert_threshold_pct),
        trigger_mode=alert_mode_key,
    )

    render_betting_alert_ui(
        alert=live_alert,
        sound_type=alert_sound_type,
        volume=alert_volume,
        repeat_mode=alert_repeat_mode,
        is_enabled=audio_alerts_enabled,
        key_suffix="live",
    )

    # ── FILA SUPERIOR: Señales principales ───────────────────────
    bt_col1, bt_col2, bt_col3, bt_col4 = st.columns(4)

    direction_bg = "rgba(72,187,120,0.15)" if lb_rec.direction == "OVER" else (
        "rgba(245,101,101,0.15)" if lb_rec.direction == "UNDER" else "rgba(128,128,128,0.15)"
    )
    direction_border = "#48bb78" if lb_rec.direction == "OVER" else (
        "#f56565" if lb_rec.direction == "UNDER" else "#718096"
    )
    direction_label = lb_rec.direction if lb_rec.direction != "NEUTRO" else "SIN EDGE"

    with bt_col1:
        if "GRADO A+" in lb_rec.bet_grade:
            g_border, g_bg = "#38a169", "rgba(56, 161, 105, 0.25)"
        elif "GRADO A" in lb_rec.bet_grade:
            g_border, g_bg = "#48bb78", "rgba(72, 187, 120, 0.2)"
        elif "GRADO B" in lb_rec.bet_grade:
            g_border, g_bg = "#ecc94b", "rgba(236, 201, 75, 0.2)"
        else:
            g_border, g_bg = "#a0aec0", "rgba(160, 174, 192, 0.15)"
        st.markdown(f"""
        <div style="background:{direction_bg}; border:2px solid {direction_border}; border-radius:14px; padding:18px; text-align:center;">
            <div style="font-size:2.2rem; margin-bottom:2px;">{lb_rec.signal_color}</div>
            <div style="color:{direction_border}; font-weight:900; font-size:1.5rem; font-family:'JetBrains Mono';">{direction_label}</div>
            <div style="margin-top: 5px;">
                <span style="background:{g_bg}; border:1px solid {g_border}; color:{g_border}; padding:2px 8px; border-radius:6px; font-weight:800; font-size:0.75rem; letter-spacing:0.5px;">
                    {lb_rec.bet_grade}
                </span>
            </div>
            <div style="color:#a0aec0; font-size:0.85rem; margin-top:6px;">
                Spread Edge: <b style="color:#f7fafc;">{lb_rec.point_spread_edge:+.1f} pts</b> | Stake: <b style="color:#48bb78;">{lb_rec.recommended_units:.1f}U</b>
            </div>
            <div style="color:#a0aec0; font-size:0.8rem; margin-top:2px;">
                Confianza: <b style="color:#f7fafc;">{lb_rec.confidence_pct:.1f}%</b> | Línea: <b style="color:#f7fafc;">{bet_line_for_rec:.1f}</b> ({line_source_rec})
            </div>
        </div>
        """, unsafe_allow_html=True)

    with bt_col2:
        pace_color_map = {"ALTO": "#48bb78", "BAJO": "#f56565", "NORMAL": "#ecc94b"}
        pace_col = pace_color_map.get(lb_rec.pace_signal, "#ecc94b")
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.7); border:1px solid {pace_col}66; border-radius:14px; padding:18px; text-align:center;">
            <div style="color:{pace_col}; font-weight:700; font-size:0.85rem; text-transform:uppercase;">⚡ Ritmo Observado</div>
            <div style="color:{pace_col}; font-size:2rem; font-weight:800; font-family:'JetBrains Mono';">{lb_signals.pace_observed_per_min:.1f}</div>
            <div style="color:#a0aec0; font-size:0.8rem;">pts/min | Señal: <b style="color:{pace_col};">{lb_rec.pace_signal}</b></div>
            <div style="color:#a0aec0; font-size:0.75rem;">Proyección lineal: <b style="color:#f7fafc;">{lb_signals.pace_projected_total:.0f} pts</b></div>
        </div>
        """, unsafe_allow_html=True)

    with bt_col3:
        mom_color = "#63b3ed" if lb_signals.momentum_score > 2 else (
            "#f687b3" if lb_signals.momentum_score < -2 else "#ecc94b"
        )
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.7); border:1px solid {mom_color}66; border-radius:14px; padding:18px; text-align:center;">
            <div style="color:{mom_color}; font-weight:700; font-size:0.85rem;">🌊 Momentum</div>
            <div style="color:{mom_color}; font-size:2rem; font-weight:800; font-family:'JetBrains Mono';">{lb_signals.momentum_score:+.1f}</div>
            <div style="color:#a0aec0; font-size:0.8rem;">{lb_signals.momentum_label}</div>
            <div style="color:#a0aec0; font-size:0.75rem;">Jugó {lb_signals.last_n}j: Local <b>{lb_signals.last_n_pts_home}</b> | Visit <b>{lb_signals.last_n_pts_away}</b></div>
        </div>
        """, unsafe_allow_html=True)

    with bt_col4:
        heat_color = "#f56565" if lb_signals.recent_heat >= 8 else (
            "#48bb78" if lb_signals.recent_heat >= 5 else "#a0aec0"
        )
        triple_pct_comb = (lb_signals.triple_pct_a + lb_signals.triple_pct_b) / 2.0 * 100
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.7); border:1px solid {heat_color}66; border-radius:14px; padding:18px; text-align:center;">
            <div style="color:{heat_color}; font-weight:700; font-size:0.85rem;">🌡 Calor Reciente</div>
            <div style="color:{heat_color}; font-size:2rem; font-weight:800; font-family:'JetBrains Mono';">{lb_signals.recent_heat} pts</div>
            <div style="color:#a0aec0; font-size:0.8rem;">en las últimas 6 jugadas</div>
            <div style="color:#a0aec0; font-size:0.75rem;">% Triples: <b style="color:#9f7aea;">{triple_pct_comb:.0f}%</b> | Volatilidad: <b>{lb_signals.volatility:.2f}</b></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── FILA MEDIA: EV + Razones + Kelly ──────────────────────────
    mid_col1, mid_col2 = st.columns([1.1, 0.9])

    with mid_col1:
        st.markdown("#### 📊 Valores Esperados & Análisis de Cuotas Justas")

        ev_rows = []
        for tipo, p_mc, h_odds, fair_o, p_nv, alpha_val, ev_val in [
            ("OVER",  prob_o_rec, house_odds_over_val,  lb_rec.fair_odds_over,  lb_rec.novig_prob_over,  lb_rec.alpha_over,  lb_rec.ev_over),
            ("UNDER", prob_u_rec, house_odds_under_val, lb_rec.fair_odds_under, lb_rec.novig_prob_under, lb_rec.alpha_under, lb_rec.ev_under),
        ]:
            kelly = kelly_fraction(p_mc, h_odds or fair_o)
            ev_rows.append({
                "Tipo":        tipo,
                "Prob Modelo": f"{p_mc*100:.1f}%",
                "Cuota Casa":  f"{h_odds:.2f}" if h_odds else "—",
                "Cuota Justa": f"{fair_o:.2f}",
                "Prob No-Vig": f"{p_nv*100:.1f}%" if h_odds else "—",
                "Alpha No-Vig": f"{alpha_val*100:+.1f}%" if h_odds else "—",
                "EV Casa":     f"+{ev_val*100:.1f}%" if ev_val > 0 else f"{ev_val*100:.1f}%",
                "Kelly 25%":   f"{kelly*100:.1f}% bank" if kelly > 0 else "— sin edge",
            })
        st.dataframe(pd.DataFrame(ev_rows), hide_index=True, width="stretch")

        if lb_rec.house_vig_pct > 0:
            st.caption(f"🛡️ **Comisión de la casa (Vig / Juice):** {lb_rec.house_vig_pct*100:.1f}% | Descontada matemáticamente en la columna **Prob No-Vig** y **Alpha**.")

        # Razones
        st.markdown("#### 📝 Razones del Modelo")
        if lb_rec.reasons:
            for r in lb_rec.reasons:
                st.markdown(f"- {r}")
        else:
            st.info("Sin señales adicionales del play-by-play. Conectá un partido en vivo para ver análisis detallado.")

    with mid_col2:
        st.markdown("#### 📑 Distribución de Tiro por Equipo")
        if lb_signals.total_plays > 0:
            shot_data = pd.DataFrame([
                {"Equipo": team_a_name[:15], "Triples": f"{lb_signals.triple_pct_a*100:.0f}%",
                 "Dobles": f"{lb_signals.double_pct_a*100:.0f}%", "TL": f"{lb_signals.ft_pct_a*100:.0f}%"},
                {"Equipo": team_b_name[:15], "Triples": f"{lb_signals.triple_pct_b*100:.0f}%",
                 "Dobles": f"{lb_signals.double_pct_b*100:.0f}%", "TL": f"{lb_signals.ft_pct_b*100:.0f}%"},
            ])
            st.dataframe(shot_data, hide_index=True, width="stretch")
        else:
            st.caption("Sin jugadas disponibles aún.")

        if lb_signals.pace_by_quarter:
            st.markdown("#### ⏱ Ritmo por Cuarto (pts/min observado)")
            q_data = pd.DataFrame([
                {"Cuarto": f"Q{q}", "pts/min": f"{v:.2f}",
                 "Local": lb_signals.pts_by_quarter_home.get(q, 0),
                 "Visitante": lb_signals.pts_by_quarter_away.get(q, 0)}
                for q, v in sorted(lb_signals.pace_by_quarter.items())
            ])
            st.dataframe(q_data, hide_index=True, width="stretch")

    st.markdown("---")

    # ── PANEL: REGISTRAR APUESTA ───────────────────────────────
    st.markdown("### 📌 Registrar Apuesta en la Base de Datos")
    with st.expander("📌 Registrar una apuesta de este partido", expanded=True):
        partidos_activos = [p for p in listar_partidos(50)]

        # Buscar si el partido en pantalla ya existe en la base de datos
        s_local = team_a_name.strip().lower()
        s_visit = team_b_name.strip().lower()
        partido_en_pantalla_obj = None

        for p in partidos_activos:
            p_loc = p["equipo_local"].strip().lower()
            p_vis = p["equipo_visitante"].strip().lower()
            if (p_loc == s_local and p_vis == s_visit) or (st.session_state.get("loaded_game_id") == p["id"]):
                partido_en_pantalla_obj = p
                break

        # Construir opciones del selector:
        # Opción 1 (Por defecto siempre): El partido que está en pantalla
        lbl_pantalla = f"🎯 [En Pantalla] {team_a_name} vs {team_b_name}"
        if partido_en_pantalla_obj:
            lbl_pantalla += f" (#{partido_en_pantalla_obj['id']})"

        opciones_partidos = {lbl_pantalla: "CURRENT_SCREEN"}

        # Agregar otros partidos guardados para permitir apuestas cruzadas si el usuario quiere
        for p in partidos_activos:
            if partido_en_pantalla_obj and p["id"] == partido_en_pantalla_obj["id"]:
                continue
            lbl = f"#{p['id']} {p['equipo_local']} vs {p['equipo_visitante']}"
            opciones_partidos[lbl] = p["id"]

        # Sincronizar automáticamente cuando cambia el partido en pantalla
        clave_pantalla_actual = f"{team_a_name.strip()} vs {team_b_name.strip()}"
        if st.session_state.get("_last_synced_screen_match") != clave_pantalla_actual:
            st.session_state["_last_synced_screen_match"] = clave_pantalla_actual
            st.session_state["bet_partido_sel"] = lbl_pantalla

        keys_partidos = list(opciones_partidos.keys())
        sel_idx = 0
        if st.session_state.get("bet_partido_sel") in keys_partidos:
            sel_idx = keys_partidos.index(st.session_state["bet_partido_sel"])

        reg_col1, reg_col2, reg_col3 = st.columns(3)
        with reg_col1:
            partido_sel_apuesta = st.selectbox(
                "Partido:",
                keys_partidos,
                index=sel_idx,
                key="bet_partido_sel"
            )
            partido_sel_val = opciones_partidos[partido_sel_apuesta]

            if partido_sel_val == "CURRENT_SCREEN":
                if partido_en_pantalla_obj:
                    st.caption(f"⚡ *Partido vinculado en BD (#{partido_en_pantalla_obj['id']}).*")
                else:
                    st.caption("⚡ *Se registrará automáticamente en BD al confirmar la apuesta.*")
            else:
                st.caption(f"⚠️ *Nota: Guardando en partido histórico #{partido_sel_val}.*")

            modalidad_apuesta = st.radio(
                "Modalidad de Apuesta:",
                ["🎲 Ficticia (Paper Trading)", "💵 Real (Dinero Real)"],
                horizontal=True,
                key="bet_modalidad",
                index=0
            )
            es_ficticia_bool = modalidad_apuesta.startswith("🎲")

            tipo_apuesta = st.radio(
                "Tipo de apuesta:",
                ["OVER", "UNDER"],
                horizontal=True,
                key="bet_tipo",
                index=0 if lb_rec.direction != "UNDER" else 1
            )

        with reg_col2:
            linea_apuesta_reg = st.number_input(
                "Línea apostada:",
                min_value=5.0, max_value=400.0,
                value=float(bet_line_for_rec),
                step=0.5, key="bet_linea_reg"
            )
            monto_apuesta = st.number_input(
                "Monto de apuesta (Gs.):",
                min_value=1000.0, max_value=50000000.0,
                value=100000.0, step=10000.0,
                format="%.0f",
                key="bet_monto"
            )
            cuota_apostada = st.number_input(
                "Cuota decimal de la casa:",
                min_value=1.0, max_value=20.0,
                value=float(house_odds_over_val or house_odds_under_val or 1.85),
                step=0.01, key="bet_cuota"
            )

        with reg_col3:
            notas_apuesta = st.text_area(
                "Notas / Contexto (opcional):",
                placeholder="Ej: Cuota alta, ritmo elevado en 3Q...",
                key="bet_notas",
                height=80
            )
            prob_para_kelly = prob_o_rec if tipo_apuesta == "OVER" else prob_u_rec
            ev_para_reg = round(prob_para_kelly * cuota_apostada - 1.0, 4)
            kelly_r = kelly_fraction(prob_para_kelly, cuota_apostada)
            ganancia_potencial = monto_apuesta * (cuota_apostada - 1)

            st.markdown(f"""
            <div style="background: rgba(26,31,46,0.9); border: 1px solid rgba(255,138,0,0.3); border-radius:10px; padding:12px; margin-top:4px;">
                <div style="color:#9aa5b1; font-size:0.8rem;">Prob. modelo: <b style="color:#f7fafc;">{prob_para_kelly*100:.1f}%</b></div>
                <div style="color:#9aa5b1; font-size:0.8rem;">EV: <b style="color:{'#48bb78' if ev_para_reg > 0 else '#f56565'};">{ev_para_reg*100:+.1f}%</b></div>
                <div style="color:#9aa5b1; font-size:0.8rem;">Kelly 25%: <b style="color:#f7fafc;">{kelly_r*100:.1f}% bankroll</b></div>
                <div style="color:#9aa5b1; font-size:0.8rem;">Ganancia si gana: <b style="color:#48bb78;">Gs. {ganancia_potencial:,.0f}</b></div>
            </div>
            """, unsafe_allow_html=True)

        regla_activacion_default = "PAGO_ELEVADO" if (cuota_apostada >= 2.10 or lb_rec.is_high_payout) else "MODELO_LIVE"

        if st.button("📌 Registrar apuesta en BD", type="primary", key="btn_reg_apuesta"):
            try:
                # Determinar o crear automáticamente el ID del partido
                if partido_sel_val == "CURRENT_SCREEN":
                    if partido_en_pantalla_obj:
                        pid_apuesta = partido_en_pantalla_obj["id"]
                    else:
                        # Creación 100% transparente y automática
                        pid_apuesta = crear_partido(
                            equipo_local=team_a_name,
                            equipo_visitante=team_b_name,
                            torneo_nombre=torneo_sel,
                            cuarto_actual=current_quarter,
                            min_restantes=rem_min,
                            seg_restantes=rem_sec,
                            quarters_data=quarters_data,
                            notas="Registrado automáticamente al apostar"
                        )
                        st.session_state["loaded_game_id"] = pid_apuesta
                        # Guardar snapshot inicial
                        guardar_snapshot(
                            partido_id=pid_apuesta,
                            cuarto_snapshot=current_quarter,
                            minutos_jugados=elapsed_total_min,
                            pts_local_actual=int(score_a_total),
                            pts_visitante_actual=int(score_b_total),
                            summary=summary,
                            linea_apuesta=bet_number,
                            prob_over=prob_mas,
                            prob_under=prob_menos,
                            num_simulaciones=num_sims
                        )
                else:
                    pid_apuesta = int(partido_sel_val)

                apuesta_id = registrar_apuesta(
                    partido_id=pid_apuesta,
                    cuarto_apuesta=current_quarter,
                    minutos_jugados=elapsed_total_min,
                    linea=linea_apuesta_reg,
                    tipo=tipo_apuesta,
                    monto=monto_apuesta,
                    cuota_casa=cuota_apostada,
                    prob_modelo=prob_para_kelly,
                    ev=ev_para_reg,
                    kelly_pct=kelly_r,
                    notas=st.session_state.get("bet_notas", ""),
                    grado_apuesta=lb_rec.bet_grade,
                    spread_edge=lb_rec.point_spread_edge,
                    es_ficticia=es_ficticia_bool,
                    hito_origen=f"Q{current_quarter}",
                    regla_activacion=regla_activacion_default
                )
                # Guardar jugadas del play-by-play junto con la apuesta
                if scraped_plays_betting:
                    guardar_jugadas(pid_apuesta, scraped_plays_betting)
                tipo_desc = "Ficticia 🎲" if es_ficticia_bool else "Real 💵"
                partido_desc = f"{team_a_name} vs {team_b_name}" if partido_sel_val == "CURRENT_SCREEN" else f"Partido #{pid_apuesta}"
                st.success(f"✅ Apuesta #{apuesta_id} [{tipo_desc}] registrada en '{partido_desc}' [{lb_rec.bet_grade}] — {tipo_apuesta} {linea_apuesta_reg:.1f} | Gs. {monto_apuesta:,.0f} @ {cuota_apostada:.2f}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al registrar la apuesta: {e}")

    st.markdown("---")

    # ── TABLERO DE RENDIMIENTO, BANKROLL & AUDITORÍA ───────────
    st.markdown("### 📊 Tablero de Rendimiento, Bankroll & Calibración")

    col_f1, col_f2 = st.columns([1.5, 2.5])
    with col_f1:
        filtro_modalidad_dash = st.selectbox(
            "Modalidad de Apuestas a Analizar:",
            ["Todas (Reales + Ficticias)", "🎲 Solo Ficticias (Paper Trading)", "💵 Solo Reales"],
            key="dash_filtro_modalidad"
        )
    filtro_ficticia_val = None
    if "Solo Ficticias" in filtro_modalidad_dash:
        filtro_ficticia_val = True
    elif "Solo Reales" in filtro_modalidad_dash:
        filtro_ficticia_val = False

    metricas_rend = calcular_metricas_rendimiento_apuestas(filtro_ficticia=filtro_ficticia_val)

    if metricas_rend and metricas_rend.get("total_apuestas", 0) > 0:
        # Fila 1: Tarjetas KPI Profesionales
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)

        wr_val = metricas_rend["win_rate_global"]
        roi_val = metricas_rend["roi_pct"]
        pf_val = metricas_rend["profit_factor"]
        brier_val = metricas_rend["brier_score"]
        net_total = metricas_rend["ganancia_neta_total"]
        roi_color = "#48bb78" if roi_val >= 0 else "#f56565"

        with kpi1:
            st.markdown(f"""
            <div style="background:rgba(15,20,32,0.8); border:1px solid #48bb7866; border-radius:12px; padding:14px; text-align:center;">
                <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">🎯 Acierto (Win Rate)</div>
                <div style="color:#48bb78; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{wr_val:.1f}%</div>
                <div style="color:#cbd5e0; font-size:0.75rem;">{metricas_rend['ganadas']}/{metricas_rend['total_resueltas']} resueltas ({metricas_rend['pendientes']} pendientes)</div>
                <div style="color:#a0aec0; font-size:0.75rem;">Over: <b>{metricas_rend['win_rate_over']:.1f}%</b> | Under: <b>{metricas_rend['win_rate_under']:.1f}%</b></div>
            </div>
            """, unsafe_allow_html=True)

        with kpi2:
            st.markdown(f"""
            <div style="background:rgba(15,20,32,0.8); border:1px solid {roi_color}66; border-radius:12px; padding:14px; text-align:center;">
                <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">💵 ROI / Yield Neto</div>
                <div style="color:{roi_color}; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{roi_val:+.1f}%</div>
                <div style="color:#cbd5e0; font-size:0.75rem;">G/P: <b>{'+' if net_total>=0 else ''}Gs. {net_total:,.0f}</b></div>
                <div style="color:#a0aec0; font-size:0.75rem;">Volumen apostado: <b>Gs. {metricas_rend['monto_total_apostado']:,.0f}</b></div>
            </div>
            """, unsafe_allow_html=True)

        with kpi3:
            pf_color = "#48bb78" if pf_val >= 1.5 else ("#ecc94b" if pf_val >= 1.0 else "#f56565")
            st.markdown(f"""
            <div style="background:rgba(15,20,32,0.8); border:1px solid {pf_color}66; border-radius:12px; padding:14px; text-align:center;">
                <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">⚖️ Profit Factor</div>
                <div style="color:{pf_color}; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{pf_val:.2f}</div>
                <div style="color:#cbd5e0; font-size:0.75rem;">Ganancias / Pérdidas brutas</div>
                <div style="color:#a0aec0; font-size:0.75rem;">{'⭐ Sano (>1.5)' if pf_val >= 1.5 else ('Rentable (>1.0)' if pf_val>=1.0 else 'Bajo revisión')}</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi4:
            brier_color = "#48bb78" if brier_val <= 0.20 else ("#ecc94b" if brier_val <= 0.25 else "#f56565")
            st.markdown(f"""
            <div style="background:rgba(15,20,32,0.8); border:1px solid {brier_color}66; border-radius:12px; padding:14px; text-align:center;">
                <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">🔬 Brier Score (Calibración)</div>
                <div style="color:{brier_color}; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{brier_val:.4f}</div>
                <div style="color:#cbd5e0; font-size:0.75rem;">Error cuadrático de probabilidad</div>
                <div style="color:#a0aec0; font-size:0.75rem;">0.00 = Óptimo | 0.25 = Azar 50/50</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Fila 2: Gráfico de Evolución del Bankroll & Tablas de Rendimiento
        dash_col1, dash_col2 = st.columns([1.3, 1.0])

        with dash_col1:
            st.markdown("#### 📈 Evolución del Bankroll (Balance Acumulado Gs.)")
            curva = metricas_rend.get("curva_capital", [])
            if len(curva) > 1:
                curva_df = pd.DataFrame(curva)
                col_balance = "Balance Acumulado ($)" if "Balance Acumulado ($)" in curva_df.columns else curva_df.columns[1]
                curva_df["Balance Acumulado (Gs.)"] = curva_df[col_balance]
                chart_data = curva_df.set_index("Operación")[["Balance Acumulado (Gs.)"]]
                st.line_chart(chart_data, height=220)
            elif len(curva) == 1:
                st.info(f"Primera operación resuelta: Balance actual **Gs. {curva[0].get('Balance Acumulado ($)', 0):,.0f}**")
            else:
                st.caption("Resolvé apuestas pendientes para ver la curva gráfica de capital acumulado.")

        with dash_col2:
            st.markdown("#### 🏆 Rendimiento Científico por Grado")
            df_grados = pd.DataFrame(metricas_rend.get("por_grado", []))
            if not df_grados.empty:
                st.dataframe(df_grados, hide_index=True, width="stretch")
            else:
                st.caption("Sin datos por grado aún.")

        # Fila 2b: Rendimiento por Rango de Cuotas de la Casa (Payout Tiers)
        st.markdown("#### 🎯 Rendimiento por Rango de Cuotas de la Casa (Payout Tiers)")
        df_cuotas = pd.DataFrame(metricas_rend.get("por_cuota", []))
        if not df_cuotas.empty:
            st.dataframe(df_cuotas, hide_index=True, width="stretch")
        else:
            st.caption("Sin datos por cuota aún.")

        st.markdown("---")

        # Fila 3: Filtro y Tabla de Historial Detallado
        st.markdown("#### 📋 Historial Completo de Apuestas")
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            filtro_res = st.selectbox(
                "Filtrar por resultado:",
                ["Todas", "GANADA", "PERDIDA", "PENDIENTE", "PUSH"],
                key="filtro_hist_res"
            )
        with f_col2:
            filtro_tipo = st.selectbox(
                "Filtrar por tipo:",
                ["Todos", "OVER", "UNDER"],
                key="filtro_hist_tipo"
            )
        with f_col3:
            filtro_mod_tab = st.selectbox(
                "Filtrar por modalidad:",
                ["Todas", "Solo Ficticias", "Solo Reales"],
                key="filtro_hist_mod"
            )

        f_bool = None
        if filtro_mod_tab == "Solo Ficticias":
            f_bool = True
        elif filtro_mod_tab == "Solo Reales":
            f_bool = False

        todas_apuestas = listar_apuestas(limit=200, filtro_ficticia=f_bool)
        apuestas_filtradas = todas_apuestas
        if filtro_res != "Todas":
            apuestas_filtradas = [a for a in apuestas_filtradas if a.get("resultado") == filtro_res]
        if filtro_tipo != "Todos":
            apuestas_filtradas = [a for a in apuestas_filtradas if a.get("tipo") == filtro_tipo]

        if apuestas_filtradas:
            df_hist = pd.DataFrame(apuestas_filtradas)
            if "es_ficticia" in df_hist.columns:
                df_hist["modalidad_txt"] = df_hist["es_ficticia"].apply(lambda x: "🎲 Ficticia" if x else "💵 Real")
            else:
                df_hist["modalidad_txt"] = "💵 Real"

            cols_map = {
                "id": "#",
                "registrado_en": "Fecha",
                "modalidad_txt": "Modalidad",
                "equipo_local": "Local",
                "equipo_visitante": "Visitante",
                "cuarto_apuesta": "Q",
                "tipo": "Tipo",
                "linea": "Línea",
                "grado_apuesta": "Grado",
                "regla_activacion": "Regla",
                "monto": "Monto (Gs.)",
                "cuota_casa": "Cuota",
                "prob_modelo": "Prob%",
                "ev": "EV",
                "resultado": "Resultado",
                "ganancia_neta": "G/P Neta (Gs.)"
            }
            existing_cols = [c for c in cols_map.keys() if c in df_hist.columns]
            df_display = df_hist[existing_cols].rename(columns=cols_map)
            if "Fecha" in df_display.columns:
                df_display["Fecha"] = df_display["Fecha"].astype(str).str[:16]
            if "Prob%" in df_display.columns:
                df_display["Prob%"] = df_display["Prob%"].apply(lambda x: f"{float(x)*100:.1f}%" if pd.notnull(x) else "—")
            if "EV" in df_display.columns:
                df_display["EV"] = df_display["EV"].apply(lambda x: f"{float(x)*100:+.1f}%" if pd.notnull(x) else "—")
            if "Monto (Gs.)" in df_display.columns:
                df_display["Monto (Gs.)"] = df_display["Monto (Gs.)"].apply(lambda x: f"Gs. {float(x):,.0f}" if pd.notnull(x) else "—")
            if "G/P Neta (Gs.)" in df_display.columns:
                df_display["G/P Neta (Gs.)"] = df_display["G/P Neta (Gs.)"].apply(lambda x: f"Gs. {float(x):+,.0f}" if pd.notnull(x) else "—")
            if "Grado" in df_display.columns:
                df_display["Grado"] = df_display["Grado"].fillna("—")
            if "Regla" in df_display.columns:
                df_display["Regla"] = df_display["Regla"].fillna("—")
            st.dataframe(df_display, hide_index=True, width="stretch")
        else:
            st.caption("No hay apuestas que coincidan con los filtros seleccionados.")

        # Gestión y edición
        st.markdown("#### 🛠️ Gestionar o Actualizar Resultado de Apuesta")
        todas_opciones_gestion = {
            f"#{a['id']} [{a.get('equipo_local', 'Local')} vs {a.get('equipo_visitante', 'Vis')}] ({'🎲Ficticia' if a.get('es_ficticia') else '💵Real'}) {a['tipo']} {a['linea']:.1f} | Gs. {float(a['monto']):,.0f} — {a.get('resultado','?')}" + (f" [{a.get('grado_apuesta')}]" if a.get('grado_apuesta') else ""): a["id"]
            for a in todas_apuestas
        }
        if todas_opciones_gestion:
            ap_sel_gestion = st.selectbox(
                "Seleccioná la apuesta a editar / calificar:",
                list(todas_opciones_gestion.keys()),
                key="sel_gestion_apuesta"
            )
            gid = todas_opciones_gestion[ap_sel_gestion]
            apt_gestion = next((a for a in todas_apuestas if a["id"] == gid), {})

            gc1, gc2, gc3 = st.columns([2, 2, 1])

            with gc1:
                resultado_gestion = st.radio(
                    "Resultado:",
                    ["PENDIENTE", "GANADA", "PERDIDA", "PUSH"],
                    index=["PENDIENTE", "GANADA", "PERDIDA", "PUSH"].index(apt_gestion.get("resultado", "PENDIENTE")) if apt_gestion.get("resultado") in ["PENDIENTE", "GANADA", "PERDIDA", "PUSH"] else 0,
                    horizontal=True,
                    key="radio_gestion_resultado"
                )
            with gc2:
                if resultado_gestion == "GANADA":
                    default_gp_g = float(apt_gestion.get("monto", 0)) * (float(apt_gestion.get("cuota_casa", 1.85)) - 1.0)
                elif resultado_gestion == "PERDIDA":
                    default_gp_g = -float(apt_gestion.get("monto", 0))
                elif resultado_gestion == "PUSH":
                    default_gp_g = 0.0
                else:
                    default_gp_g = float(apt_gestion.get("ganancia_neta") or 0.0)
                ganancia_gestion = st.number_input(
                    "G/P Neta (Gs.):",
                    value=round(default_gp_g, 0),
                    step=10000.0,
                    key="inp_gestion_gp"
                )
            with gc3:
                st.markdown("<br>", unsafe_allow_html=True)
                nuevo_resultado = resultado_gestion if resultado_gestion != "PENDIENTE" else "PENDIENTE"
                nueva_gp = ganancia_gestion if resultado_gestion != "PENDIENTE" else None
                if st.button("💾 Guardar Resultado", type="primary", key="btn_gestion_guardar"):
                    actualizar_resultado_apuesta(gid, nuevo_resultado, nueva_gp)
                    st.success(f"Apuesta #{gid} actualizada a {nuevo_resultado}")
                    st.rerun()

            # Edición completa de la apuesta
            with st.expander("✏️ Editar detalles completos de la apuesta (Reasignar Partido, Línea, Cuota, Monto, etc.)", expanded=False):
                ed_col1, ed_col2, ed_col3 = st.columns(3)
                with ed_col1:
                    partidos_catalogo = listar_partidos(100)
                    opciones_reasignar = {
                        f"#{p['id']} {p['equipo_local']} vs {p['equipo_visitante']}": p["id"]
                        for p in partidos_catalogo
                    }
                    keys_reasignar = list(opciones_reasignar.keys())

                    cur_pid = apt_gestion.get("partido_id")
                    idx_cur_partido = 0
                    for i, k in enumerate(keys_reasignar):
                        if opciones_reasignar[k] == cur_pid:
                            idx_cur_partido = i
                            break

                    partido_reasignado = st.selectbox(
                        "Reasignar a Partido:",
                        keys_reasignar,
                        index=idx_cur_partido,
                        key=f"ed_partido_{gid}"
                    )
                    nuevo_partido_id = opciones_reasignar[partido_reasignado]

                    modalidad_ed = st.radio(
                        "Modalidad:",
                        ["💵 Real", "🎲 Ficticia"],
                        index=1 if apt_gestion.get("es_ficticia") else 0,
                        horizontal=True,
                        key=f"ed_mod_{gid}"
                    )
                    es_ficticia_ed = modalidad_ed.startswith("🎲")

                    tipo_ed = st.radio(
                        "Tipo:",
                        ["OVER", "UNDER"],
                        index=0 if apt_gestion.get("tipo") == "OVER" else 1,
                        horizontal=True,
                        key=f"ed_tipo_{gid}"
                    )

                with ed_col2:
                    linea_ed = st.number_input(
                        "Línea apostada:",
                        min_value=5.0, max_value=400.0,
                        value=float(apt_gestion.get("linea", 150.0)),
                        step=0.5,
                        key=f"ed_linea_{gid}"
                    )
                    cuota_ed = st.number_input(
                        "Cuota de la casa:",
                        min_value=1.0, max_value=50.0,
                        value=float(apt_gestion.get("cuota_casa") or 1.85),
                        step=0.01,
                        key=f"ed_cuota_{gid}"
                    )
                    monto_ed = st.number_input(
                        "Monto apostado (Gs.):",
                        min_value=1000.0, max_value=100000000.0,
                        value=float(apt_gestion.get("monto") or 100000.0),
                        step=10000.0,
                        key=f"ed_monto_{gid}"
                    )

                with ed_col3:
                    cuarto_ed = st.number_input(
                        "Cuarto de la apuesta:",
                        min_value=1, max_value=5,
                        value=int(apt_gestion.get("cuarto_apuesta") or 1),
                        step=1,
                        key=f"ed_cuarto_{gid}"
                    )
                    notas_ed = st.text_area(
                        "Notas / Observaciones:",
                        value=str(apt_gestion.get("notas") or ""),
                        key=f"ed_notas_{gid}",
                        height=75
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Guardar Detalles Editados", type="primary", key=f"btn_save_edit_{gid}"):
                        actualizar_apuesta(
                            apuesta_id=gid,
                            partido_id=nuevo_partido_id,
                            linea=linea_ed,
                            tipo=tipo_ed,
                            monto=monto_ed,
                            cuota_casa=cuota_ed,
                            es_ficticia=es_ficticia_ed,
                            cuarto_apuesta=cuarto_ed,
                            notas=notas_ed
                        )
                        st.success(f"✅ Detalles de la apuesta #{gid} actualizados correctamente.")
                        st.rerun()

            # Borrado con confirmación
            with st.expander("🗑️ Eliminar esta apuesta permanentemente", expanded=False):
                confirmar_borrado = st.checkbox(
                    f"Confirmo que quiero borrar la apuesta #{gid}",
                    key="chk_confirmar_borrado"
                )
                if confirmar_borrado:
                    if st.button("🗑️ ELIMINAR APUESTA", type="secondary", key="btn_borrar_apuesta"):
                        eliminar_apuesta(gid)
                        st.warning(f"Apuesta #{gid} eliminada.")
                        st.rerun()
    else:
        st.info("ℹ️ Aún no hay apuestas registradas. Registrá tu primera apuesta usando el formulario superior para habilitar las métricas de rendimiento, el ROI y la curva de bankroll.")


# ==========================================
# TAB 8: 🤖 APRENDIZAJE AUTOMÁTICO & CALIBRACIÓN (ML)
# ==========================================
with tab_ml:
    st.subheader("🤖 Aprendizaje Automático & Calibración Continua del Modelo")
    st.caption("Ajuste adaptativo de probabilidades (Platt Scaling) y optimización bayesiana de ritmo basada en el cotejo de hitos y resultados reales.")

    # Explicación pedagógica
    st.markdown("""
    <div style="background: rgba(15, 20, 32, 0.7); border: 1px solid #3182ce44; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
        <h5 style="color: #63b3ed; margin-top:0;">🧠 ¿Cómo Aprende el Modelo? (Ciclo Continuo)</h5>
        <div style="color: #cbd5e0; font-size: 0.88rem; line-height: 1.5;">
            El sistema ejecuta un proceso de optimización supervisado en 2 etapas:
            <ol style="margin-bottom:0; padding-left: 20px;">
                <li><b>Calibración de Probabilidades (Platt Scaling):</b> Ajusta las probabilidades de Monte Carlo mediante regresión logística sigmoidal penalizada <i>σ(a · logit(p) + b)</i>, corrigiendo el sesgo de la casa de apuestas y minimizando el <b>Brier Score</b>.</li>
                <li><b>Optimización Bayesiana de Ritmo & Sesgo:</b> Re-calibra el factor de contracción <i>k</i> de cuartos y estima el desvío sistemático de puntos en base a los hitos guardados durante los partidos.</li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Tarjetas de Métricas de Calibración Activa
    calib_activa = obtener_calibracion_activa()

    ml_kpi1, ml_kpi2, ml_kpi3, ml_kpi4 = st.columns(4)

    with ml_kpi1:
        brier_train = calib_activa.get("brier_score_train")
        brier_str = f"{brier_train:.4f}" if brier_train is not None else "0.1980"
        brier_color = "#48bb78" if (brier_train and brier_train <= 0.20) else "#ecc94b"
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.8); border:1px solid {brier_color}66; border-radius:12px; padding:14px; text-align:center;">
            <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">🔬 Brier Score Modelo</div>
            <div style="color:{brier_color}; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{brier_str}</div>
            <div style="color:#cbd5e0; font-size:0.75rem;">Calibración de confianza</div>
            <div style="color:#a0aec0; font-size:0.75rem;">Azar = 0.2500 | Óptimo = 0.0000</div>
        </div>
        """, unsafe_allow_html=True)

    with ml_kpi2:
        pa = calib_activa.get("platt_a", 1.0)
        pb = calib_activa.get("platt_b", 0.0)
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.8); border:1px solid #4299e166; border-radius:12px; padding:14px; text-align:center;">
            <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">📐 Parámetros Platt</div>
            <div style="color:#63b3ed; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">a={pa:.2f}</div>
            <div style="color:#cbd5e0; font-size:0.75rem;">Intersección b = {pb:+.3f}</div>
            <div style="color:#a0aec0; font-size:0.75rem;">Transformación Sigmoidal Activa</div>
        </div>
        """, unsafe_allow_html=True)

    with ml_kpi3:
        bk = calib_activa.get("bayes_k_optimo", 20.0)
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.8); border:1px solid #9f7aea66; border-radius:12px; padding:14px; text-align:center;">
            <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">⚖️ Shrinkage Bayesiano (k)</div>
            <div style="color:#b794f4; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{bk:.1f}</div>
            <div style="color:#cbd5e0; font-size:0.75rem;">Inercia histórica vs ritmo vivo</div>
            <div style="color:#a0aec0; font-size:0.75rem;">k alto = más peso al torneo</div>
        </div>
        """, unsafe_allow_html=True)

    with ml_kpi4:
        bias_off = calib_activa.get("bias_offset", 0.0)
        n_samples = calib_activa.get("num_muestras_entrenamiento", 0)
        st.markdown(f"""
        <div style="background:rgba(15,20,32,0.8); border:1px solid #ecc94b66; border-radius:12px; padding:14px; text-align:center;">
            <div style="color:#a0aec0; font-size:0.8rem; font-weight:700; text-transform:uppercase;">🎯 Corrección de Sesgo</div>
            <div style="color:#ecc94b; font-size:2rem; font-weight:900; font-family:'JetBrains Mono';">{bias_off:+.1f} pts</div>
            <div style="color:#cbd5e0; font-size:0.75rem;">Muestras entrenadas: <b>{n_samples}</b></div>
            <div style="color:#a0aec0; font-size:0.75rem;">Offset compensatorio aplicado</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Diagrama de Confiabilidad / Curva de Calibración
    diag_col1, diag_col2 = st.columns([1.5, 1.0])

    with diag_col1:
        st.markdown("#### 📈 Diagrama de Confiabilidad (Curva de Calibración)")
        probs_teoricas = np.linspace(0.05, 0.95, 19)
        probs_calibradas = [calibrar_probabilidad(p, pa, pb) for p in probs_teoricas]

        fig_calib = go.Figure()
        # Línea 45° perfecta
        fig_calib.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode="lines",
            line=dict(color="#a0aec0", dash="dash", width=1.5),
            name="Calibración Ideal (45°)"
        ))
        # Curva de Monte Carlo Cruda
        fig_calib.add_trace(go.Scatter(
            x=probs_teoricas, y=probs_teoricas,
            mode="lines+markers",
            line=dict(color="#f6ad55", width=2),
            marker=dict(size=6),
            name="Prob. Cruda Monte Carlo"
        ))
        # Curva Calibrada Platt
        fig_calib.add_trace(go.Scatter(
            x=probs_teoricas, y=probs_calibradas,
            mode="lines+markers",
            line=dict(color="#48bb78", width=3),
            marker=dict(size=7),
            name="Prob. Calibrada (Platt ML)"
        ))

        fig_calib.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,20,32,0.6)",
            xaxis=dict(title="Probabilidad Estimada por el Modelo", range=[0, 1], tickformat=".0%"),
            yaxis=dict(title="Frecuencia Real Esperada (Observada)", range=[0, 1], tickformat=".0%"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=30, b=40),
            height=340
        )
        st.plotly_chart(fig_calib, width="stretch")

    with diag_col2:
        st.markdown("#### ⚙️ Re-entrenamiento del Modelo")
        st.markdown("""
        Cada vez que finalices partidos con sus marcadores reales en el tab **Historial de Partidos & Cotejo**, el sistema acumula nuevos datos para:
        - Re-optimizar los pesos logísticos $a$ y $b$.
        - Ajustar el ritmo $k$ por liga.
        - Eliminar sobre-confianza en cuotas extremas.
        """)
        if st.button("🧠 Ejecutar Auto-Calibración / Re-entrenar Modelo", type="primary", key="btn_run_train_ml", width="stretch"):
            with st.spinner("Optimizando hiperparámetros y calibración Platt vía SciPy L-BFGS-B..."):
                res_train = ejecutar_auto_entrenamiento_ml()
                if res_train.get("exito"):
                    st.success(f"🎉 ¡Modelo calibrado con éxito! ({res_train['muestras_usadas']} muestras)")
                    st.json({
                        "brier_nuevo": res_train.get("brier_nuevo"),
                        "brier_previo": res_train.get("brier_previo"),
                        "platt_a": res_train.get("platt_a"),
                        "platt_b": res_train.get("platt_b"),
                        "bayes_k": res_train.get("bayes_k_optimo"),
                        "bias_offset": res_train.get("bias_offset"),
                    })
                    st.rerun()
                else:
                    st.warning(f"⚠️ {res_train.get('mensaje', 'No se pudo completar el re-entrenamiento')}")

    st.markdown("---")

    # 2.1 Módulo de Red Neuronal Profunda de Momentum (Deep Learning)
    st.markdown("#### 🧠 Red Neuronal Profunda de Momentum (PyTorch Residual GRU)")
    st.markdown(r"""
    Complementa la física del juego de Monte Carlo prediciendo ajustes de ritmo no lineales $\Delta Pace$ 
    e incertidumbre heterocedástica a partir de la secuencia reciente de jugadas (*play-by-play*).
    """)

    dl_col1, dl_col2, dl_col3 = st.columns([1.2, 1.2, 1.6])
    with dl_col1:
        from model.deep_learning import TORCH_AVAILABLE, DEFAULT_MODEL_PATH
        model_exists = os.path.exists(DEFAULT_MODEL_PATH)
        status_txt = "🟢 Entrenado y Listo" if model_exists else "🟡 Pendiente de Entrenamiento"
        st.metric("Estado de la Red", status_txt, f"PyTorch {'2.14' if TORCH_AVAILABLE else 'No disp.'}")

    with dl_col2:
        mtime_str = "—"
        if os.path.exists(DEFAULT_MODEL_PATH):
            mtime = os.path.getmtime(DEFAULT_MODEL_PATH)
            import datetime
            mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
        st.metric("Última Actualización", mtime_str, "Pesos guardados en disco")

    with dl_col3:
        if st.button("🚀 Entrenar Red Neuronal (35 Épocas)", type="secondary", key="btn_train_dl_tab_ml", width="stretch"):
            with st.spinner("Extrayendo jugadas de PostgreSQL y entrenando arquitectura GRU..."):
                from model.deep_learning import entrenar_modelo_deep_learning
                res_deep = entrenar_modelo_deep_learning(epochs=35)
                if res_deep.get("exito"):
                    st.success(f"🎉 Red entrenada con éxito: {res_deep.get('total_muestras')} muestras | MAE Pace: {res_deep.get('mae_pace_final')}")
                    st.rerun()
                else:
                    st.error(f"Error: {res_deep.get('error')}")

    st.markdown("---")

    # 3. Historial de Hitos Cotejados en Partidos
    st.markdown("#### 📋 Auditoría de Hitos Guardados en la Base de Datos")
    hitos_totales = listar_hitos(limit=50)
    if hitos_totales:
        df_hitos_audit = pd.DataFrame(hitos_totales)[[
            "id", "guardado_en", "partido_id", "nombre_hito", "cuarto_snapshot",
            "minutos_jugados", "total_actual", "total_proyectado", "linea_apuesta",
            "cuota_over", "cuota_under"
        ]].copy()
        df_hitos_audit.columns = [
            "#", "Fecha", "Partido ID", "Hito", "Q",
            "Min", "Marcador", "Proy.", "Línea",
            "Cuota Over", "Cuota Under"
        ]
        df_hitos_audit["Fecha"] = df_hitos_audit["Fecha"].astype(str).str[:16]
        st.dataframe(df_hitos_audit, hide_index=True, width="stretch")
    else:
        st.info("ℹ️ Aún no hay hitos registrados. Usá la barra de hitos superiores (🚩 Pre-Partido, 🚩 Fin 1Q, 🚩 Medio Tiempo, etc.) durante los partidos.")


# ─────────────────────────────────────────────────────────────
# GUARDAR JUGADAS AUTOMÁTICAMENTE AL GUARDAR PARTIDO
# (Se llama desde el botón de guardar en tab_historial, el código del botón
# ya invoca guardar_jugadas mediante el flujo normal del app)
# ─────────────────────────────────────────────────────────────
