import pytest
import io
import wave
from model.audio_alerts import (
    generate_sound_wav,
    get_audio_base64_data_uri,
    evaluate_betting_alert,
    SOUND_PRESETS,
    TRIGGER_MODES,
)


def test_generate_sound_wav_all_presets():
    """Verifica que todos los presets generen archivos WAV válidos."""
    for preset in SOUND_PRESETS.keys():
        wav_bytes = generate_sound_wav(preset, volume=0.8)
        assert len(wav_bytes) > 1000
        # Validar cabecera WAV con módulo estándar
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44100
            assert wf.getnframes() > 0


def test_get_audio_base64_data_uri():
    """Verifica que el data URI base64 comience correctamente y contenga datos."""
    uri = get_audio_base64_data_uri("chime", volume=0.5)
    assert uri.startswith("data:audio/wav;base64,")
    assert len(uri) > 500


def test_evaluate_betting_alert_prob_only_above_90():
    """Verifica el disparo de alerta cuando la probabilidad supera el 90% en modo PROB_ONLY."""
    alert = evaluate_betting_alert(
        prob_over=0.92,
        prob_under=0.08,
        line=215.5,
        bet_grade="GRADO A",
        threshold_pct=90.0,
        trigger_mode="PROB_ONLY",
    )
    assert alert.should_trigger is True
    assert alert.direction == "OVER"
    assert alert.probability == 0.92
    assert "90%" in alert.reason
    assert "ALERT_OVER_215.5" in alert.signature


def test_evaluate_betting_alert_prob_only_below_90():
    """Verifica que no dispare si la probabilidad no alcanza el 90% en modo PROB_ONLY."""
    alert = evaluate_betting_alert(
        prob_over=0.88,
        prob_under=0.12,
        line=215.5,
        bet_grade="GRADO A",
        threshold_pct=90.0,
        trigger_mode="PROB_ONLY",
    )
    assert alert.should_trigger is False
    assert alert.direction == "OVER"
    assert alert.signature == ""


def test_evaluate_betting_alert_prob_or_grade_a():
    """Verifica que dispare en modo PROB_OR_GRADE_A con Grado A aunque prob < 90%."""
    alert = evaluate_betting_alert(
        prob_over=0.62,
        prob_under=0.38,
        line=210.0,
        bet_grade="GRADO A (FUERTE)",
        threshold_pct=90.0,
        trigger_mode="PROB_OR_GRADE_A",
    )
    assert alert.should_trigger is True
    assert alert.direction == "OVER"
    assert "GRADO A" in alert.reason


def test_evaluate_betting_alert_under_trigger():
    """Verifica que la dirección UNDER funcione correctamente con > 90%."""
    alert = evaluate_betting_alert(
        prob_over=0.05,
        prob_under=0.95,
        line=230.5,
        bet_grade="GRADO A+ (MÁXIMO VALOR)",
        threshold_pct=90.0,
        trigger_mode="PROB_ONLY",
    )
    assert alert.should_trigger is True
    assert alert.direction == "UNDER"
    assert alert.probability == 0.95
    assert "UNDER" in alert.signature
