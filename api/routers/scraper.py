"""
Router para Scraping e Integración Automática con Aposta.la (Kambi Sportsbook API).
Permite extraer partidos en vivo con 1 clic: equipos, cuartos, reloj, puntos y cuotas.
"""

from typing import Optional, List, Tuple, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from model.scraper import scrape_aposta_la, LiveMatchData
from model.database import (
    crear_partido,
    actualizar_partido,
    obtener_partido,
    guardar_jugadas,
    _fetchone
)
from model.config import TOURNAMENT_PRESETS
from api.websocket.manager import manager

router = APIRouter()


class ScrapeUrlRequest(BaseModel):
    url: str = Field(..., description="URL del evento en vivo de aposta.la o ID numérico")


class CrearDesdeApostaRequest(BaseModel):
    url: str = Field(..., description="URL del evento en vivo de aposta.la")
    notas: Optional[str] = "Importado automáticamente desde Aposta.la"


def _format_match_data(data: LiveMatchData) -> Dict[str, Any]:
    """Convierte LiveMatchData en un diccionario seguro para JSON."""
    return {
        "team_home": data.team_home,
        "team_away": data.team_away,
        "score_home": data.score_home,
        "score_away": data.score_away,
        "quarter": data.quarter,
        "clock_min": data.clock_min,
        "clock_sec": data.clock_sec,
        "quarter_scores": data.quarter_scores,
        "odds_line": data.odds_line,
        "odds_over": data.odds_over,
        "odds_under": data.odds_under,
        "league_name": data.league_name,
        "quarter_duration": data.quarter_duration,
        "tournament_key": data.tournament_key,
        "current_run_team": data.current_run_team,
        "current_run_pts": data.current_run_pts,
        "plays_count": len(data.plays),
        "status": data.status,
        "error_msg": data.error_msg
    }


@router.post("/scraper/extraer")
async def post_extraer_datos(req: ScrapeUrlRequest):
    """Extrae todos los detalles en vivo de un evento de aposta.la sin guardarlo en DB."""
    try:
        data: LiveMatchData = await run_in_threadpool(scrape_aposta_la, req.url)
        if data.status == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=data.error_msg or "No se pudieron extraer datos del evento"
            )
        return _format_match_data(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la extracción: {str(e)}"
        )


@router.post("/partidos/crear-desde-aposta", status_code=status.HTTP_201_CREATED)
async def post_crear_desde_aposta(req: CrearDesdeApostaRequest):
    """
    Extrae los datos en vivo de Aposta.la y crea automáticamente el partido
    en la base de datos con nombres de equipo, cuartos y tiempo actual.
    """
    try:
        data: LiveMatchData = await run_in_threadpool(scrape_aposta_la, req.url)
        if data.status == "error" or not data.team_home or not data.team_away:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=data.error_msg or "No se detectaron equipos válidos en la URL de aposta.la proporcionada"
            )

        # Seleccionar nombre de torneo adecuado
        torneo_nombre = "FIBA / Euroliga / Ligas Locales (10 min/cuarto)"
        if data.tournament_key == "NBA" or data.quarter_duration == 12:
            torneo_nombre = "NBA (12 min/cuarto)"
        elif data.tournament_key == "NBL":
            torneo_nombre = "NBL Australia (10 min/cuarto)"

        partido_id = crear_partido(
            equipo_local=data.team_home,
            equipo_visitante=data.team_away,
            torneo_nombre=torneo_nombre,
            cuarto_actual=data.quarter,
            min_restantes=data.clock_min,
            seg_restantes=data.clock_sec,
            quarters_data=data.quarter_scores,
            notas=f"{req.notas} | URL: {req.url}"
        )

        if data.plays:
            guardar_jugadas(partido_id, data.plays)

        return {
            "id": partido_id,
            "message": f"Partido '{data.team_home} vs {data.team_away}' creado y sincronizado con éxito",
            "extracted_data": _format_match_data(data)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear partido desde Aposta.la: {str(e)}"
        )


@router.post("/partidos/{partido_id}/sync-aposta")
async def post_sync_partido_aposta(partido_id: int, req: ScrapeUrlRequest):
    """
    Consulta en vivo aposta.la y actualiza el marcador, cuartos y tiempo
    del partido especificado, emitiendo una notificación por WebSocket.
    """
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido ID {partido_id} no encontrado"
        )

    try:
        data: LiveMatchData = await run_in_threadpool(scrape_aposta_la, req.url)
        if data.status != "live":
            is_at_end = (
                (partido.get("cuarto_actual") or 1) >= 4 and
                (partido.get("min_restantes") or 0) == 0 and
                (partido.get("seg_restantes") or 0) == 0 and
                ((partido.get("total_local") or 0) > 0 or (partido.get("total_visitante") or 0) > 0)
            )
            return {
                "success": False,
                "event_finished": data.status == "finished" or is_at_end,
                "message": data.error_msg or "No se encontraron datos en vivo para el evento en Aposta.la.",
                "partido": partido,
                "live_odds": None
            }

        actualizar_partido(
            partido_id=partido_id,
            cuarto_actual=data.quarter,
            min_restantes=data.clock_min,
            seg_restantes=data.clock_sec,
            quarters_data=data.quarter_scores,
            notas=partido.get("notas", "")
        )

        if data.plays:
            guardar_jugadas(partido_id, data.plays)

        partido_actualizado = obtener_partido(partido_id)

        # Si en este scrape puntual Kambi no devolvió cuotas (ej. mercado suspendido 10s por falta/tiros),
        # consultar último snapshot con cuotas para no enviar null y borrar las cuotas del frontend
        odds_line = data.odds_line
        odds_over = data.odds_over
        odds_under = data.odds_under
        if odds_line is None:
            last_snap = _fetchone(
                "SELECT linea_apuesta, cuota_over, cuota_under FROM snapshots_prediccion WHERE partido_id = %s AND linea_apuesta IS NOT NULL ORDER BY guardado_en DESC LIMIT 1",
                (partido_id,)
            )
            if last_snap and last_snap.get("linea_apuesta"):
                odds_line = last_snap["linea_apuesta"]
                odds_over = last_snap.get("cuota_over") or odds_over
                odds_under = last_snap.get("cuota_under") or odds_under

        # Notificar por WebSocket a los clientes conectados
        await manager.broadcast_to_match(partido_id, {
            "type": "match_updated",
            "partido_id": partido_id,
            "partido": partido_actualizado,
            "live_odds": {
                "line": odds_line,
                "over": odds_over,
                "under": odds_under
            }
        })

        return {
            "success": True,
            "event_finished": False,
            "message": "Partido sincronizado con éxito desde Aposta.la",
            "partido": partido_actualizado,
            "live_odds": {
                "line": odds_line,
                "over": odds_over,
                "under": odds_under
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la sincronización: {str(e)}"
        )
