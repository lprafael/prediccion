"""
Router para Gestión de Apuestas, Métricas de Rendimiento y Recomendaciones Cuantitativas.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from model.database import (
    registrar_apuesta,
    listar_apuestas,
    actualizar_apuesta,
    actualizar_resultado_apuesta,
    eliminar_apuesta,
    resumen_apuestas,
    calcular_metricas_rendimiento_apuestas,
    actualizar_clv_apuesta,
    obtener_lineups_partido,
    actualizar_lineups_partido,
    obtener_jugadores_equipo,
    _fetchall,
)
from model.live_betting import (
    analyze_plays,
    get_live_betting_recommendation,
)
from api.schemas.apuestas import (
    RegistrarApuestaRequest,
    ActualizarApuestaRequest,
    ActualizarResultadoRequest,
    ActualizarCLVRequest,
    ApuestaResponse,
    ResumenApuestasResponse,
    RecomendacionApuestaRequest,
    RecomendacionApuestaResponse,
)

router = APIRouter()


@router.get("/partidos/{partido_id}/apuestas", response_model=List[dict])
async def get_apuestas_partido(
    partido_id: int,
    es_ficticia: Optional[bool] = Query(None, description="Filtrar por real (False) o simulada (True)"),
    limit: int = Query(100, ge=1, le=500)
):
    """Lista las apuestas registradas para un partido específico."""
    try:
        return listar_apuestas(partido_id=partido_id, filtro_ficticia=es_ficticia, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener apuestas del partido: {str(e)}"
        )


@router.get("/apuestas", response_model=List[dict])
async def get_todas_apuestas(
    es_ficticia: Optional[bool] = Query(None),
    limit: int = Query(200, ge=1, le=1000)
):
    """Lista todas las apuestas registradas en el sistema."""
    try:
        return listar_apuestas(partido_id=None, filtro_ficticia=es_ficticia, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar apuestas: {str(e)}"
        )


@router.post("/partidos/{partido_id}/apuestas", status_code=status.HTTP_201_CREATED)
async def post_apuesta(partido_id: int, req: RegistrarApuestaRequest):
    """Registra una nueva apuesta en el partido."""
    try:
        pid = req.partido_id if req.partido_id is not None else partido_id
        tipo = req.tipo_apuesta.upper().strip()
        if tipo not in ('OVER', 'UNDER', 'SPREAD', 'MONEYLINE', 'TEAM_TOTAL'):
            if 'OVER' in tipo or 'MÁS' in tipo or 'MAS' in tipo:
                tipo = 'OVER'
            elif 'UNDER' in tipo or 'MENOS' in tipo:
                tipo = 'UNDER'
            elif 'SPREAD' in tipo or 'HANDICAP' in tipo or 'HÁNDICAP' in tipo:
                tipo = 'SPREAD'
            elif 'MONEYLINE' in tipo or 'GANADOR' in tipo or 'ML' in tipo:
                tipo = 'MONEYLINE'
            else:
                tipo = 'OVER'

        apuesta_id = registrar_apuesta(
            partido_id=pid,
            cuarto_apuesta=req.momento_cuarto if req.momento_cuarto is not None else 1,
            minutos_jugados=req.minuto_partido or 0.0,
            linea=req.linea,
            tipo=tipo,
            monto=req.monto,
            cuota_casa=req.cuota,
            prob_modelo=req.prob_modelo,
            ev=req.ev_estimado,
            kelly_pct=req.kelly_sugerido,
            notas=req.notas or "",
            grado_apuesta=req.grado_apuesta,
            spread_edge=req.spread_edge,
            es_ficticia=req.es_ficticia,
            equipo_apostado=req.equipo_apostado,
            linea_cierre_casa=req.linea_cierre_casa,
            cuota_cierre_casa=req.cuota_cierre_casa
        )
        return {"id": apuesta_id, "message": "Apuesta registrada exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar apuesta: {str(e)}"
        )


@router.put("/apuestas/{apuesta_id}")
async def put_apuesta(apuesta_id: int, req: ActualizarApuestaRequest):
    """Actualiza datos o estado de una apuesta."""
    try:
        actualizar_apuesta(
            apuesta_id=apuesta_id,
            monto=req.monto,
            cuota=req.cuota,
            linea=req.linea,
            tipo_apuesta=req.tipo_apuesta,
            resultado=req.resultado,
            ganancia_neta=req.ganancia_neta,
            notas=req.notas
        )
        return {"message": "Apuesta actualizada exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar apuesta: {str(e)}"
        )


@router.put("/apuestas/{apuesta_id}/resultado")
async def put_resultado_apuesta(apuesta_id: int, req: ActualizarResultadoRequest):
    """Actualiza solo el resultado (GANADA/PERDIDA/PUSH) y ganancia neta."""
    try:
        actualizar_resultado_apuesta(
            apuesta_id=apuesta_id,
            resultado=req.resultado,
            ganancia_neta=req.ganancia_neta
        )
        return {"message": "Resultado de apuesta registrado exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al liquidar apuesta: {str(e)}"
        )


@router.delete("/apuestas/{apuesta_id}")
async def delete_apuesta(apuesta_id: int):
    """Elimina una apuesta por ID."""
    try:
        eliminar_apuesta(apuesta_id)
        return {"message": f"Apuesta {apuesta_id} eliminada exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar apuesta: {str(e)}"
        )


@router.put("/apuestas/{apuesta_id}/clv")
async def put_apuesta_clv(apuesta_id: int, req: ActualizarCLVRequest):
    """Actualiza la línea de cierre y cuota de cierre para auditar el CLV (Closing Line Value)."""
    try:
        actualizar_clv_apuesta(
            apuesta_id=apuesta_id,
            linea_cierre_casa=req.linea_cierre_casa,
            cuota_cierre_casa=req.cuota_cierre_casa
        )
        return {"message": "Métricas CLV actualizadas exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar CLV: {str(e)}"
        )


@router.get("/partidos/{partido_id}/lineups")
async def get_lineups(partido_id: int):
    """Retorna los quintetos actuales y faltas de equipo para el partido."""
    try:
        return obtener_lineups_partido(partido_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener lineups: {str(e)}"
        )


from pydantic import BaseModel as _PydanticBase


class ActualizarLineupsRequest(_PydanticBase):
    lineup_local: Optional[List[int]] = None
    lineup_visitante: Optional[List[int]] = None
    fouls_local: Optional[int] = None
    fouls_visitante: Optional[int] = None


@router.put("/partidos/{partido_id}/lineups")
async def put_lineups(partido_id: int, req: ActualizarLineupsRequest):
    """Actualiza los quintetos en cancha y/o faltas colectivas."""
    try:
        actualizar_lineups_partido(
            partido_id=partido_id,
            lineup_local=req.lineup_local,
            lineup_visitante=req.lineup_visitante,
            fouls_local=req.fouls_local,
            fouls_visitante=req.fouls_visitante
        )
        return {"message": "Lineups actualizados exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar lineups: {str(e)}"
        )


@router.get("/jugadores")
async def get_jugadores(equipo: Optional[str] = Query(None)):
    """Retorna jugadores registrados, opcionalmente filtrados por equipo."""
    try:
        if equipo:
            return obtener_jugadores_equipo(equipo)
        return _fetchall("SELECT * FROM jugadores ORDER BY equipo, es_titular DESC, nombre ASC LIMIT 100")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar jugadores: {str(e)}"
        )


@router.get("/apuestas/resumen", response_model=ResumenApuestasResponse)
async def get_resumen_apuestas(es_ficticia: Optional[bool] = Query(None)):
    """Retorna resumen global de apuestas (ROI, Win Rate, P&L neto)."""
    try:
        met = calcular_metricas_rendimiento_apuestas(es_ficticia=es_ficticia)
        monto_apostado = float(met.get("monto_total_apostado", 0.0))
        ganancia_neta = float(met.get("ganancia_neta_total", 0.0))
        retorno = monto_apostado + ganancia_neta

        return ResumenApuestasResponse(
            total_apuestas=int(met.get("total_apuestas", 0)),
            ganadas=int(met.get("ganadas", 0)),
            perdidas=int(met.get("perdidas", 0)),
            pushes=int(met.get("pushes", 0)),
            pendientes=int(met.get("pendientes", 0)),
            total_apostado=monto_apostado,
            retorno_total=retorno,
            beneficio_neto=ganancia_neta,
            roi_porcentaje=float(met.get("roi_pct", 0.0)),
            win_rate=float(met.get("win_rate_global", 0.0))
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calcular resumen: {str(e)}"
        )


@router.get("/apuestas/metricas")
async def get_metricas_avanzadas(es_ficticia: Optional[bool] = Query(None)):
    """Retorna métricas avanzadas (Yield, Sharpe, Brier Score, etc.)."""
    try:
        return calcular_metricas_rendimiento_apuestas(es_ficticia=es_ficticia)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calcular métricas avanzadas: {str(e)}"
        )


@router.post("/apuestas/recomendar", response_model=RecomendacionApuestaResponse)
async def post_recomendar_apuesta(req: RecomendacionApuestaRequest):
    """
    Analiza señales del partido y cuotas de mercado para generar una recomendación
    multimercado con Valor Esperado (EV), Point Spread Edge, Grado A+/A/B, Criterio de Kelly y XAI.
    """
    try:
        # Calcular tiempo transcurrido total: cuartos previos + tiempo actual
        total_elapsed_min = (req.quarter - 1) * req.quarter_duration + req.elapsed_minutes
        total_game_min = req.quarter_duration * 4.0

        signals = analyze_plays(
            plays=req.plays or [],
            team_a="LOCAL",
            team_b="VISITANTE",
            total_elapsed_min=total_elapsed_min,
            total_game_min=total_game_min,
        )

        league_pace = 100.0 / 48.0 if req.quarter_duration == 12 else 75.0 / 40.0
        prob_under = 1.0 - req.prob_over

        rec = get_live_betting_recommendation(
            signals=signals,
            prob_over=req.prob_over,
            prob_under=prob_under,
            line=req.linea,
            league_avg_pace_per_min=league_pace,
            house_odds_over=req.cuota_over,
            house_odds_under=req.cuota_under,
            line_source="api",
            spread_line=req.spread_line,
            house_odds_spread_home=req.cuota_spread_home,
            house_odds_spread_away=req.cuota_spread_away,
            house_odds_ml_home=req.cuota_gana_a,
            house_odds_ml_away=req.cuota_gana_b,
        )

        # Preparar señales resumidas para la respuesta
        sig_dict = {
            "pace_observed": signals.pace_observed_per_min,
            "pace_projected": signals.pace_projected_total,
            "pace_signal": rec.pace_signal,
            "momentum_signal": rec.momentum_signal,
            "momentum_score": signals.momentum_score,
            "momentum_label": signals.momentum_label,
            "run_team": signals.run_team,
            "run_pts": signals.run_pts,
            "recent_heat": signals.recent_heat,
            "volatility": signals.volatility,
            "total_plays": signals.total_plays,
        }

        # Determinar el mejor EV y la fracción de Kelly
        best_prob = rec.prob_over if rec.direction == "OVER" else rec.prob_under
        chosen_odds = req.cuota_over if rec.direction == "OVER" else req.cuota_under
        from model.live_betting import kelly_fraction as calc_kelly
        kelly_f = calc_kelly(best_prob, chosen_odds, fraction=0.25)
        chosen_ev = rec.ev_over if rec.direction == "OVER" else rec.ev_under
        stake = req.bankroll * kelly_f

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

        return RecomendacionApuestaResponse(
            recommendation=rec.direction,
            edge=float(rec.point_spread_edge),
            ev=float(chosen_ev),
            stake_amount=round(float(stake), 2),
            reasons=rec.reasons,
            kelly_f=float(kelly_f),
            signals=sig_dict,
            spread_recommendation=spread_rec,
            moneyline_recommendation=ml_rec,
            optimal_stopping_action=rec.optimal_stopping_action,
            overreaction_detected=rec.overreaction_detected,
            xai_factors=rec.xai_factors,
            bet_grade=rec.bet_grade,
            suggested_paper_bet=rec.suggested_paper_bet,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar recomendación: {str(e)}"
        )
