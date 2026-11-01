"""
Endpoint WebSocket en Vivo para Partidos.
Canal: ws://localhost:8000/ws/live/{partido_id}
Transmite actualizaciones de marcador, jugadas del play-by-play, re-simulaciones
Monte Carlo y alertas cuantitativas a todos los navegadores conectados.
"""

from typing import Optional, List, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import numpy as np

from api.websocket.manager import manager
from model.database import (
    obtener_partido,
    actualizar_partido,
)
from model.config import TOURNAMENT_PRESETS
from model.engine import BasketballPredictor, SimulationSummary

router = APIRouter()


def _run_quick_sim(partido: dict, linea_apuesta: Optional[float] = None, n_sims: int = 3000) -> dict:
    """Helper para correr una simulación a partir de los datos actuales del partido en DB."""
    torneo_nombre = partido.get("torneo", "NBA")
    # Buscar el preset correspondiente
    torneo_cfg = None
    for cfg in TOURNAMENT_PRESETS.values():
        if cfg.name.lower() in torneo_nombre.lower() or cfg.key.lower() in torneo_nombre.lower():
            torneo_cfg = cfg
            break
    if not torneo_cfg:
        torneo_cfg = TOURNAMENT_PRESETS["NBA"]

    q_actual = partido.get("cuarto_actual", 1)
    min_rest = partido.get("min_restantes", torneo_cfg.quarter_duration)
    seg_rest = partido.get("seg_restantes", 0)
    elapsed_sec = (torneo_cfg.quarter_duration * 60) - (min_rest * 60 + seg_rest)
    elapsed_sec = max(0.0, min(float(torneo_cfg.quarter_duration * 60), elapsed_sec))

    marcadores = partido.get("marcadores", [])
    quarters_data = [(0.0, 0.0)] * 4
    for m in marcadores:
        q_idx = m["cuarto"] - 1
        if 0 <= q_idx < 4:
            quarters_data[q_idx] = (float(m["pts_local"]), float(m["pts_visitante"]))

    total_local = sum(q[0] for q in quarters_data)
    total_visitante = sum(q[1] for q in quarters_data)

    predictor = BasketballPredictor(torneo_cfg)
    summary: SimulationSummary = predictor.run_live_simulation(
        current_quarter=min(q_actual, 4),
        elapsed_seconds_in_quarter=elapsed_sec,
        quarters_data=quarters_data,
        n_simulations=n_sims,
        random_seed=42,
        actual_total_scores=(total_local, total_visitante),
        use_deep_learning=True
    )

    prob_over = None
    prob_under = None
    if linea_apuesta is not None and len(summary.simulated_totals) > 0:
        prob_over = float(np.mean(summary.simulated_totals > linea_apuesta))
        prob_under = float(np.mean(summary.simulated_totals < linea_apuesta))

    return {
        "total_mean": round(float(summary.total_mean), 1),
        "total_median": round(float(summary.total_median), 1),
        "total_p05": round(float(summary.total_p05), 1),
        "total_p95": round(float(summary.total_p95), 1),
        "total_std": round(float(summary.total_std), 1),
        "team_a_mean": round(float(summary.team_a_mean), 1),
        "team_b_mean": round(float(summary.team_b_mean), 1),
        "win_prob_a": round(float(summary.win_prob_a), 4),
        "win_prob_b": round(float(summary.win_prob_b), 4),
        "overtime_prob": round(float(summary.overtime_prob), 4),
        "prior_pace_per_min": round(float(summary.prior_pace_per_min), 2),
        "observed_pace_per_min": round(float(summary.observed_pace_per_min), 2),
        "dl_momentum_label": summary.dl_momentum_label,
        "dl_active": summary.dl_active,
        "prob_over": round(prob_over, 4) if prob_over is not None else None,
        "prob_under": round(prob_under, 4) if prob_under is not None else None,
        "linea_apuesta": linea_apuesta
    }


@router.websocket("/ws/live/{partido_id}")
async def websocket_live_partido(websocket: WebSocket, partido_id: int):
    """Canal WebSocket bidireccional para seguimiento y control en tiempo real."""
    import os
    expected_key = os.getenv("POLIVERSO_API_KEY", "").strip()
    if expected_key:
        token = (
            websocket.query_params.get("api_key")
            or websocket.query_params.get("key")
            or websocket.headers.get("x-api-key")
            or websocket.cookies.get("poliverso_api_key")
        )
        if not token or token != expected_key:
            await websocket.close(code=1008, reason="Unauthorized: Invalid API Key")
            return

    await manager.connect(websocket, partido_id)

    # 1. Enviar estado inicial al cliente
    partido = obtener_partido(partido_id)
    if partido:
        sim_data = _run_quick_sim(partido)
        await manager.send_personal_message({
            "type": "init",
            "partido_id": partido_id,
            "partido": partido,
            "simulation": sim_data
        }, websocket)
    else:
        await manager.send_personal_message({
            "type": "error",
            "message": f"Partido {partido_id} no encontrado"
        }, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)

            elif action == "resimulate":
                # Recalcular simulación con nueva línea u opciones
                linea = data.get("linea_apuesta")
                partido_actual = obtener_partido(partido_id)
                if partido_actual:
                    sim_result = _run_quick_sim(partido_actual, linea_apuesta=linea)
                    # Broadcast a todos los espectadores del partido
                    await manager.broadcast_to_match(partido_id, {
                        "type": "simulation_update",
                        "partido_id": partido_id,
                        "simulation": sim_result
                    })

            elif action == "update_score":
                # Actualizar marcador en DB y notificar a todos
                cuarto_actual = data.get("cuarto_actual", 1)
                min_restantes = data.get("min_restantes", 10)
                seg_restantes = data.get("seg_restantes", 0)
                quarters_data = data.get("quarters_data", [])
                notas = data.get("notas", "")
                linea = data.get("linea_apuesta")

                actualizar_partido(
                    partido_id=partido_id,
                    cuarto_actual=cuarto_actual,
                    min_restantes=min_restantes,
                    seg_restantes=seg_restantes,
                    quarters_data=quarters_data,
                    notas=notas
                )

                partido_actual = obtener_partido(partido_id)
                sim_result = _run_quick_sim(partido_actual, linea_apuesta=linea)

                await manager.broadcast_to_match(partido_id, {
                    "type": "match_updated",
                    "partido_id": partido_id,
                    "partido": partido_actual,
                    "simulation": sim_result
                })

            elif action == "new_play":
                # Notificar jugada o evento play-by-play
                play = data.get("play", {})
                await manager.broadcast_to_match(partido_id, {
                    "type": "play_event",
                    "partido_id": partido_id,
                    "play": play
                })

            elif action == "alert":
                # Disparar alerta sonora y visual
                alert_info = data.get("alert", {})
                await manager.broadcast_to_match(partido_id, {
                    "type": "bet_alert",
                    "partido_id": partido_id,
                    "alert": alert_info
                })

    except WebSocketDisconnect:
        await manager.disconnect(websocket, partido_id)
    except Exception:
        await manager.disconnect(websocket, partido_id)
