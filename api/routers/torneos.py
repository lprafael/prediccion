"""
Router para Torneos y Configuración de Reglas por Liga.
"""

from typing import List, Dict, Any
from fastapi import APIRouter
from model.config import TOURNAMENT_PRESETS

router = APIRouter()


@router.get("/torneos", response_model=List[Dict[str, Any]])
async def listar_torneos():
    """
    Retorna la lista de presets de torneos soportados con sus
    parámetros reglamentarios (duración de cuarto, ritmo medio, ratings).
    """
    torneos = []
    for key, cfg in TOURNAMENT_PRESETS.items():
        torneos.append({
            "key": cfg.key,
            "name": cfg.name,
            "quarter_duration": cfg.quarter_duration,
            "team_avg_quarter_min": cfg.team_avg_quarter_min,
            "team_avg_quarter_max": cfg.team_avg_quarter_max,
            "total_game_duration": cfg.total_game_duration,
            "total_game_avg": cfg.total_game_avg,
            "description": cfg.description,
            "league_pace": cfg.league_pace,
            "league_off_rating": cfg.league_off_rating,
            "typical_total_std": cfg.typical_total_std,
            "home_court_advantage": cfg.home_court_advantage,
        })
    return torneos


@router.get("/torneos/wnba/equipos", response_model=List[Dict[str, Any]])
async def listar_equipos_wnba():
    """
    Retorna la lista oficial de las 13 franquicias de la WNBA (ID, Nombre, Sigla, Ciudad).
    """
    from model.data_ingestion import obtener_equipos_wnba
    return obtener_equipos_wnba()

