"""
🏀 Módulo de Alertas Sonoras y Cuantitativas para Oportunidades de Apuesta.
Generación nativa de audio en formato WAV (sin dependencias externas) y
evaluación estocástica de condiciones de apuesta en vivo.
"""

import io
import math
import struct
import base64
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


@dataclass
class BettingAlert:
    should_trigger: bool
    direction: str = "NEUTRO"        # "OVER", "UNDER", "NEUTRO"
    probability: float = 0.0         # 0.0 a 1.0
    line: float = 0.0
    bet_grade: str = ""
    reason: str = ""
    signature: str = ""              # Clave única para control anti-spam
    is_tested: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Generación de Tonos de Audio WAV Nativo (PCM 16-bit, 44.1 kHz)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_wav_pcm(sample_rate: int, duration_sec: float, sample_generator) -> bytes:
    """Genera bytes de un archivo WAV mono PCM de 16 bits."""
    n_frames = int(sample_rate * duration_sec)
    buffer = io.BytesIO()
    with wave_writer(buffer, sample_rate) as wf:
        data = bytearray()
        for i in range(n_frames):
            t = i / sample_rate
            sample_val = sample_generator(t)
            # Limitar entre -1.0 y 1.0
            clamped = max(-1.0, min(1.0, sample_val))
            int_sample = int(clamped * 32767)
            data.extend(struct.pack("<h", int_sample))
        wf.writeframes(data)
    return buffer.getvalue()


class wave_writer:
    """Envoltorio liviano sobre io.BytesIO para escribir encabezados WAV sin bloquear recursos."""
    def __init__(self, buffer: io.BytesIO, sample_rate: int):
        import wave
        self.wf = wave.open(buffer, "wb")
        self.sample_rate = sample_rate

    def __enter__(self):
        self.wf.setnchannels(1)
        self.wf.setsampwidth(2)
        self.wf.setframerate(self.sample_rate)
        return self.wf

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.wf.close()


def generate_sound_wav(sound_type: str = "chime", volume: float = 0.8) -> bytes:
    """
    Genera el archivo de audio en bytes WAV según el perfil seleccionado:
    - 'chime': Campana armónica de dos tonos elegantes (D5 -> A5).
    - 'radar': Ping metálico de alta frecuencia resonante (~1200 Hz).
    - 'fanfare': Arpegio de triunfo ascendente (C5 -> E5 -> G5 -> C6).
    - 'beep': Doble pulso digital limpio.
    """
    sample_rate = 44100
    vol = max(0.05, min(1.0, float(volume)))

    sound_type = (sound_type or "chime").lower().strip()

    if sound_type == "radar":
        # Ping de campana brillante resonante
        duration = 0.65
        def gen(t):
            env = math.exp(-7.5 * t)
            # Tono base 1174.66 Hz (D6) con armónicos cristalinos
            f1 = math.sin(2 * math.pi * 1174.66 * t)
            f2 = 0.4 * math.sin(2 * math.pi * 2349.32 * t)
            f3 = 0.2 * math.sin(2 * math.pi * 3520.0 * t)
            return (f1 + f2 + f3) * env * vol * 0.75
        return _generate_wav_pcm(sample_rate, duration, gen)

    elif sound_type == "fanfare":
        # Arpegio ascendente de victoria (C5 -> E5 -> G5 -> C6)
        duration = 0.85
        def gen(t):
            # 4 notas escalonadas
            notes = [
                (0.00, 0.20, 523.25),  # C5
                (0.18, 0.38, 659.25),  # E5
                (0.36, 0.56, 783.99),  # G5
                (0.54, 0.85, 1046.50), # C6
            ]
            val = 0.0
            for start, end, freq in notes:
                if start <= t < end:
                    sub_t = t - start
                    env = math.exp(-4.5 * sub_t)
                    val += math.sin(2 * math.pi * freq * sub_t) * env
            return val * vol * 0.70
        return _generate_wav_pcm(sample_rate, duration, gen)

    elif sound_type == "beep":
        # Doble bip digital sutil
        duration = 0.45
        def gen(t):
            val = 0.0
            # Beep 1: 0.0 a 0.12s a 880 Hz
            if 0.0 <= t < 0.12:
                env = math.sin(math.pi * (t / 0.12))
                val = math.sin(2 * math.pi * 880.0 * t) * env
            # Beep 2: 0.18 a 0.34s a 1174 Hz
            elif 0.18 <= t < 0.34:
                sub_t = t - 0.18
                env = math.sin(math.pi * (sub_t / 0.16))
                val = math.sin(2 * math.pi * 1174.66 * sub_t) * env
            return val * vol * 0.65
        return _generate_wav_pcm(sample_rate, duration, gen)

    elif sound_type == "bell":
        # Campana metálica resonante tubular (>90% de probabilidad)
        duration = 1.60
        def gen(t):
            val = 0.0
            # Toque 1: A5 (880 Hz) con armónicos metálicos y sustain largo
            env1 = math.exp(-4.2 * t)
            val += math.sin(2 * math.pi * 880.0 * t) * env1 * 0.70
            val += 0.35 * math.sin(2 * math.pi * 1760.0 * t) * env1
            val += 0.25 * math.sin(2 * math.pi * 1320.0 * t) * math.exp(-5.5 * t)
            val += 0.15 * math.sin(2 * math.pi * 2428.8 * t) * math.exp(-7.0 * t)
            # Toque 2: C6 (1046.5 Hz) a los 0.28 segundos
            if t >= 0.28:
                t2 = t - 0.28
                env2 = math.exp(-4.0 * t2)
                val += math.sin(2 * math.pi * 1046.50 * t2) * env2 * 0.85
                val += 0.35 * math.sin(2 * math.pi * 2093.00 * t2) * env2
                val += 0.20 * math.sin(2 * math.pi * 1569.75 * t2) * math.exp(-5.5 * t2)
            return val * vol * 0.65
        return _generate_wav_pcm(sample_rate, duration, gen)

    else:
        # Por defecto: Chime Armónico (D5 587.33Hz -> A5 880Hz)
        duration = 0.80
        def gen(t):
            val = 0.0
            # Tono 1 inicial
            if t < 0.50:
                env1 = math.exp(-6.0 * t)
                val += math.sin(2 * math.pi * 587.33 * t) * env1 * 0.9
                val += 0.3 * math.sin(2 * math.pi * 1174.66 * t) * env1
            # Tono 2 principal que resuelve hacia arriba
            if t >= 0.15:
                t2 = t - 0.15
                env2 = math.exp(-5.0 * t2)
                val += math.sin(2 * math.pi * 880.0 * t2) * env2 * 1.1
                val += 0.35 * math.sin(2 * math.pi * 1760.0 * t2) * env2
            return val * vol * 0.60
        return _generate_wav_pcm(sample_rate, duration, gen)


def get_audio_base64_data_uri(sound_type: str = "chime", volume: float = 0.8) -> str:
    """Retorna el data URI base64 codificado para incrustar en HTML5 audio."""
    wav_bytes = generate_sound_wav(sound_type, volume)
    b64 = base64.b64encode(wav_bytes).decode("ascii")
    return f"data:audio/wav;base64,{b64}"


# ─────────────────────────────────────────────────────────────────────────────
# Lógica de Evaluación de Oportunidades de Apuesta
# ─────────────────────────────────────────────────────────────────────────────

# Criterios disponibles
TRIGGER_MODES = {
    "PROB_ONLY": "Solo Probabilidad >= Umbral (ej. 90%)",
    "PROB_OR_GRADE_A": "Probabilidad >= Umbral O Grado A/A+ (Recomendado)",
    "GRADE_A_PLUS_ONLY": "Solo Grado A+ (Máximo Valor Cuantitativo)",
}

SOUND_PRESETS = {
    "chime": "🔔 Chime Armónico (Doble Tono Suave)",
    "bell": "🛎️ Campana Resonante (>90% de Probabilidad)",
    "radar": "🎯 Ping de Radar (Campana Resonante)",
    "fanfare": "🎺 Fanfarria Triunfal (Victoria)",
    "beep": "⚡ Bip Tecnológico (Doble Pulso)",
}


def evaluate_betting_alert(
    prob_over: float,
    prob_under: float,
    line: float,
    bet_grade: str = "",
    ev_over: float = 0.0,
    ev_under: float = 0.0,
    threshold_pct: float = 90.0,
    trigger_mode: str = "PROB_ONLY",
) -> BettingAlert:
    """
    Evalúa si la situación actual de juego califica para emitir una alerta sonora
    y visual de "Momento de Apostar".

    Parámetros:
        prob_over: Probabilidad de Over (0.0 a 1.0)
        prob_under: Probabilidad de Under (0.0 a 1.0)
        line: Línea de puntos evaluada
        bet_grade: Grado asignado por el modelo (ej. 'GRADO A+', 'GRADO A', 'SIN EDGE')
        ev_over: Valor esperado de Over
        ev_under: Valor esperado de Under
        threshold_pct: Umbral de probabilidad configurado (ej. 90.0)
        trigger_mode: Clave de activación ('PROB_ONLY', 'PROB_OR_GRADE_A', 'GRADE_A_PLUS_ONLY')
    """
    threshold = max(0.50, min(0.99, threshold_pct / 100.0))
    max_prob = max(prob_over, prob_under)
    direction = "OVER" if prob_over >= prob_under else "UNDER"
    chosen_ev = ev_over if direction == "OVER" else ev_under

    is_grade_a = any(g in bet_grade.upper() for g in ["GRADO A+", "GRADO A"])
    is_grade_a_plus = "GRADO A+" in bet_grade.upper()

    trigger = False
    reasons = []

    if trigger_mode == "GRADE_A_PLUS_ONLY":
        if is_grade_a_plus and direction != "NEUTRO":
            trigger = True
            reasons.append(f"Oportunidad de {bet_grade} con {max_prob*100:.1f}% de certeza")
    elif trigger_mode == "PROB_OR_GRADE_A":
        if max_prob >= threshold:
            trigger = True
            reasons.append(f"Probabilidad de {direction} ({max_prob*100:.1f}%) supera el umbral del {threshold_pct:.0f}%")
        elif is_grade_a and direction != "NEUTRO":
            trigger = True
            reasons.append(f"Señal de {bet_grade} detectada por el motor cuantitativo ({max_prob*100:.1f}%)")
    else:  # "PROB_ONLY" (Modo por defecto propuesto por el usuario: >= 90%)
        if max_prob >= threshold:
            trigger = True
            reasons.append(f"Probabilidad de {direction} ({max_prob*100:.1f}%) supera el umbral crítico del {threshold_pct:.0f}%")

    if trigger:
        # Firma única para deduplicación / anti-spam en auto-refresco
        # Agrupa en intervalos de 1% para evitar sonar por fluctuaciones de 0.01%
        prob_bin = int(max_prob * 100)
        signature = f"ALERT_{direction}_{line:.1f}_{prob_bin}_{bet_grade[:8].strip()}"
        reason_str = " | ".join(reasons)
        return BettingAlert(
            should_trigger=True,
            direction=direction,
            probability=max_prob,
            line=line,
            bet_grade=bet_grade,
            reason=reason_str,
            signature=signature,
        )

    return BettingAlert(
        should_trigger=False,
        direction=direction if max_prob > 0.5 else "NEUTRO",
        probability=max_prob,
        line=line,
        bet_grade=bet_grade,
        signature="",
    )


def render_betting_alert_ui(
    alert: BettingAlert,
    sound_type: str = "chime",
    volume: float = 0.8,
    repeat_mode: str = "ONCE_PER_EVENT",
    is_enabled: bool = True,
    key_suffix: str = "",
) -> bool:
    """
    Renderiza el banner interactivo y ejecuta la reproducción de audio si se cumplen
    las condiciones estocásticas y de anti-spam.
    """
    if not alert or not alert.should_trigger:
        return False

    import streamlit as st

    snooze_key = f"_snooze_sig_{key_suffix}" if key_suffix else "_snooze_sig"
    last_played_key = f"_last_played_sig_{key_suffix}" if key_suffix else "_last_played_sig"

    is_snoozed = (st.session_state.get(snooze_key) == alert.signature)
    last_sig = st.session_state.get(last_played_key, "")
    already_played_this_run = st.session_state.get("_alert_audio_played_in_current_render", False)

    should_play = (
        is_enabled
        and not is_snoozed
        and not already_played_this_run
        and ((repeat_mode == "EVERY_REFRESH") or (last_sig != alert.signature))
    )

    # Disparar audio en el navegador si corresponde
    if should_play:
        try:
            wav_bytes = generate_sound_wav(sound_type, volume)
            st.audio(wav_bytes, format="audio/wav", autoplay=True)
            st.session_state[last_played_key] = alert.signature
            st.session_state["_alert_audio_played_in_current_render"] = True
        except Exception:
            pass

    # Colores y estilos dinámicos
    is_over = alert.direction == "OVER"
    glow_color = "#38a169" if is_over else "#e53e3e"
    border_color = "#48bb78" if is_over else "#f56565"
    bg_gradient = (
        "linear-gradient(135deg, rgba(56, 161, 105, 0.22) 0%, rgba(26, 32, 44, 0.95) 100%)"
        if is_over else
        "linear-gradient(135deg, rgba(229, 62, 62, 0.22) 0%, rgba(26, 32, 44, 0.95) 100%)"
    )
    dir_badge_bg = "#2f855a" if is_over else "#c53030"
    dir_text = f"MÁS DE {alert.line:.1f} (OVER)" if is_over else f"MENOS DE {alert.line:.1f} (UNDER)"

    # Tarjeta de alerta destacada
    st.markdown(f"""
    <div style="background: {bg_gradient}; border: 2px solid {border_color}; border-radius: 14px; 
                padding: 16px 20px; margin: 16px 0; box-shadow: 0 0 20px {glow_color}40;
                animation: pulse 2s infinite;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.8rem;">🔔</span>
                <div>
                    <div style="color: {border_color}; font-weight: 900; font-size: 1.1rem; letter-spacing: 0.5px; text-transform: uppercase;">
                        ¡MOMENTO ÓPTIMO PARA APOSTAR!
                    </div>
                    <div style="color: #edf2f7; font-size: 0.9rem; margin-top: 2px;">
                        {alert.reason}
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: {dir_badge_bg}; color: white; padding: 6px 14px; border-radius: 8px; font-weight: 800; font-size: 1.1rem; font-family: 'JetBrains Mono', monospace;">
                    {dir_text}
                </span>
                <span style="background: rgba(255,255,255,0.1); border: 1px solid {border_color}88; color: #fff; padding: 6px 12px; border-radius: 8px; font-weight: 800; font-size: 1.1rem; font-family: 'JetBrains Mono', monospace;">
                    {alert.probability*100:.1f}%
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botones de control rápido de la alerta
    col_al1, col_al2 = st.columns([4, 1])
    with col_al2:
        if not is_snoozed:
            if st.button("🔕 Silenciar Alerta", key=f"btn_snooze_{alert.signature}_{key_suffix}", width="stretch"):
                st.session_state[snooze_key] = alert.signature
                st.rerun()
        else:
            if st.button("🔔 Reactivar Sonido", key=f"btn_unsnooze_{alert.signature}_{key_suffix}", width="stretch"):
                st.session_state[snooze_key] = None
                st.session_state[last_played_key] = None
                st.rerun()

    return True

