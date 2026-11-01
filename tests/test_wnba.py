"""
🏀 Tests para la Integración de la WNBA (Women's National Basketball Association).
Verifica presets reglamentarios de 40 minutos, endpoints de equipos,
ingesta de play-by-play y simulación Monte Carlo con parámetros de la liga femenina.
"""

import pytest
from fastapi.testclient import TestClient

from model.config import TOURNAMENT_PRESETS, TournamentConfig
from model.engine import BasketballPredictor
from model.data_ingestion import (
    WNBADataIngestion,
    obtener_equipos_wnba,
    poblar_jugadores_estrella_wnba,
)
from api.main import app


client = TestClient(app)


def test_wnba_preset_configuration():
    """Valida los parámetros de configuración oficial de la WNBA en TOURNAMENT_PRESETS."""
    assert "WNBA" in TOURNAMENT_PRESETS
    cfg = TOURNAMENT_PRESETS["WNBA"]

    assert cfg.quarter_duration == 10
    assert cfg.total_game_duration == 40
    assert cfg.league_pace == 81.2
    assert cfg.league_off_rating == 102.5
    assert cfg.typical_total_std == 14.8
    assert cfg.team_avg_quarter_min == 20.0
    assert cfg.team_avg_quarter_max == 21.5
    assert 160.0 <= cfg.total_game_avg <= 175.0


def test_obtener_equipos_wnba():
    """Valida la consulta de las 13 franquicias oficiales de la WNBA."""
    equipos = obtener_equipos_wnba()
    assert len(equipos) >= 12  # Mínimo 12 franquicias activas (13 con GS Valkyries)

    nombres = [e["full_name"] for e in equipos]
    assert "New York Liberty" in nombres
    assert "Las Vegas Aces" in nombres
    assert "Indiana Fever" in nombres
    assert "Minnesota Lynx" in nombres


def test_wnba_data_ingestion_class():
    """Valida la instanciación e hiperparámetros de WNBADataIngestion."""
    ingestor = WNBADataIngestion(season="2024")
    assert ingestor.league_id == "10"
    assert ingestor.quarter_duration == 10
    assert ingestor.season == "2024"
    assert "WNBA" in ingestor.torneo_nombre


def test_poblar_jugadoras_estrella_wnba():
    """Valida el sembrado de jugadoras estrella de la WNBA en PostgreSQL."""
    total = poblar_jugadores_estrella_wnba()
    assert total >= 20  # Al menos 25 jugadoras registradas con métricas avanzadas


def test_monte_carlo_simulation_wnba():
    """Valida que el motor Monte Carlo corra correctamente con el preset WNBA (40 min)."""
    cfg = TOURNAMENT_PRESETS["WNBA"]
    predictor = BasketballPredictor(tournament_config=cfg)

    quarters_data = [
        (22.0, 19.0),   # Q1
        (18.0, 21.0),   # Q2
        (0.0, 0.0),     # Q3
        (0.0, 0.0),     # Q4
    ]

    # En el medio tiempo (Q3 iniciando, 10:00 restantes = 0 transcurridos en Q3)
    summary = predictor.run_live_simulation(
        current_quarter=3,
        elapsed_seconds_in_quarter=0.0,
        quarters_data=quarters_data,
        n_simulations=1000,
    )

    linea_apuesta = 164.5
    prob_over = float((summary.simulated_totals > linea_apuesta).mean())
    prob_under = float((summary.simulated_totals < linea_apuesta).mean())

    assert summary.total_mean > 120.0
    assert 0.0 <= prob_over <= 1.0
    assert 0.0 <= prob_under <= 1.0
    assert abs(prob_over + prob_under - 1.0) < 0.01
    assert 0.0 <= summary.win_prob_a <= 1.0
    assert 0.0 <= summary.win_prob_b <= 1.0


def test_api_torneos_includes_wnba():
    """Valida que GET /api/torneos incluya la WNBA."""
    resp = client.get("/api/torneos")
    assert resp.status_code == 200
    torneos = resp.json()
    keys = [t["key"] for t in torneos]
    assert "WNBA" in keys

    wnba = next(t for t in torneos if t["key"] == "WNBA")
    assert wnba["quarter_duration"] == 10
    assert wnba["total_game_duration"] == 40


def test_api_wnba_equipos():
    """Valida el endpoint GET /api/torneos/wnba/equipos."""
    resp = client.get("/api/torneos/wnba/equipos")
    assert resp.status_code == 200
    equipos = resp.json()
    assert len(equipos) >= 12
    team_abbrevs = [e["abbreviation"] for e in equipos]
    assert "NYL" in team_abbrevs
    assert "LVA" in team_abbrevs
    assert "IND" in team_abbrevs
