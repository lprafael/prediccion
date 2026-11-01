"""
Router para Calibración de Modelos Probabilísticos y ML Auto-adaptativo.
Incluye endpoints para Platt Scaling, auto-entrenamiento estadístico
y reentrenamiento de la red neuronal Deep Learning (DeepMomentumResidualNet).
"""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from model.database import obtener_calibracion_activa
from model.learning import (
    ejecutar_auto_entrenamiento_ml,
    cotejar_hitos_partido,
    calibrar_probabilidad,
)

router = APIRouter()


class CalibrarProbabilidadRequest(BaseModel):
    p_raw: float = Field(..., ge=0.0, le=1.0)
    modelo_nombre: str = "default_mc"


@router.get("/calibracion/activa")
async def get_calibracion_activa(modelo_nombre: str = Query("default_mc")):
    """Retorna los parámetros de calibración Platt Scaling activos en el sistema."""
    try:
        return obtener_calibracion_activa(modelo_nombre=modelo_nombre)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener calibración activa: {str(e)}"
        )


@router.post("/calibracion/entrenar")
async def post_entrenar_calibracion(modelo_nombre: str = Query("default_mc")):
    """
    Ejecuta el auto-entrenamiento ML sobre el histórico de partidos finalizados:
    - Platt Scaling para calibrar probabilidades
    - Optimización de inercia Bayesiana (k)
    - Corrección de sesgo residual de puntos totales
    """
    try:
        resultado = ejecutar_auto_entrenamiento_ml(modelo_nombre=modelo_nombre)
        return resultado
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ejecutar auto-entrenamiento: {str(e)}"
        )


@router.post("/calibracion/calibrar")
async def post_calibrar_probabilidad(req: CalibrarProbabilidadRequest):
    """Aplica la calibración Platt Scaling activa a una probabilidad bruta."""
    try:
        calib = obtener_calibracion_activa(modelo_nombre=req.modelo_nombre)
        a = calib.get("platt_a", 1.0)
        b = calib.get("platt_b", 0.0)
        p_calib = calibrar_probabilidad(req.p_raw, platt_a=a, platt_b=b)
        return {
            "p_raw": req.p_raw,
            "p_calibrada": round(p_calib, 4),
            "platt_a": a,
            "platt_b": b
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calibrar probabilidad: {str(e)}"
        )


@router.get("/partidos/{partido_id}/cotejo")
async def get_cotejo_hitos(partido_id: int):
    """
    Evalúa retrospectivamente la precisión de las predicciones e hitos
    frente al resultado final real del partido.
    """
    try:
        evaluacion = cotejar_hitos_partido(partido_id)
        if not evaluacion.get("ok", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=evaluacion.get("motivo", "No se pudo realizar el cotejo")
            )
        return evaluacion
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cotejar hitos del partido: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints de Deep Learning (DeepMomentumResidualNet)
# ─────────────────────────────────────────────────────────────────────────────

class EntrenarDLRequest(BaseModel):
    epochs: int = Field(35, ge=5, le=200, description="Épocas de entrenamiento")
    batch_size: int = Field(16, ge=4, le=128)
    learning_rate: float = Field(1e-3, gt=0.0, le=0.1)


@router.post("/calibracion/entrenar-dl")
async def post_entrenar_deep_learning(req: EntrenarDLRequest = EntrenarDLRequest()):
    """
    🧠 Reentrenar la red neuronal DeepMomentumResidualNet desde el historial
    de partidos almacenado en la BD. El modelo aprende a predecir:
    - Delta de ritmo (momentum ofensivo)
    - Puntos restantes del partido (con incertidumbre heterocedástica)
    - Probabilidad de victoria local calibrada

    El modelo entrenado se guarda en disco y se utiliza en las siguientes
    simulaciones automáticamente (auto-aprendizaje incremental).
    """
    try:
        from model.deep_learning import entrenar_modelo_deep_learning
        resultado = entrenar_modelo_deep_learning(
            muestras=None,          # extrae de la BD + genera sintéticos
            epochs=req.epochs,
            batch_size=req.batch_size,
            learning_rate=req.learning_rate,
        )
        return resultado
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al entrenar modelo Deep Learning: {str(e)}"
        )


@router.get("/calibracion/estado-dl")
async def get_estado_deep_learning():
    """
    Informa si la red neuronal DeepMomentumResidualNet está cargada,
    su tamaño en disco y cuándo fue entrenada por última vez.
    """
    try:
        from model.deep_learning import (
            TORCH_AVAILABLE,
            DEFAULT_MODEL_PATH,
            _obtener_modelo_en_memoria,
        )
        modelo_en_disco = os.path.exists(DEFAULT_MODEL_PATH)
        modelo_en_memoria = _obtener_modelo_en_memoria() is not None if TORCH_AVAILABLE else False
        size_kb = round(os.path.getsize(DEFAULT_MODEL_PATH) / 1024, 1) if modelo_en_disco else None
        mtime = None
        if modelo_en_disco:
            import datetime
            mtime = datetime.datetime.fromtimestamp(
                os.path.getmtime(DEFAULT_MODEL_PATH)
            ).isoformat()
        return {
            "torch_disponible": TORCH_AVAILABLE,
            "modelo_en_disco": modelo_en_disco,
            "modelo_activo_en_memoria": modelo_en_memoria,
            "ruta": DEFAULT_MODEL_PATH,
            "tamano_kb": size_kb,
            "ultima_modificacion": mtime,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estado del modelo DL: {str(e)}"
        )


class IngestaWNBARequest(BaseModel):
    num_partidos: int = Field(3, ge=1, le=20, description="Número de partidos reales a descargar")
    temporada: str = Field("2024", description="Temporada WNBA (ej: '2024', '2023')")
    poblar_estrellas: bool = Field(True, description="Sembrar jugadoras y estrellas WNBA con métricas analíticas")


@router.post("/calibracion/ingestar-wnba")
async def post_ingestar_wnba(req: IngestaWNBARequest = IngestaWNBARequest()):
    """
    🏀 Ingesta partidos reales de la WNBA vía nba_api (league_id='10') con eventos play-by-play
    y siembra jugadoras estrella en PostgreSQL para calibración y Deep Learning.
    """
    try:
        from model.data_ingestion import WNBADataIngestion, poblar_jugadores_estrella_wnba
        jugadoras_cargadas = 0
        if req.poblar_estrellas:
            jugadoras_cargadas = poblar_jugadores_estrella_wnba()

        ingestor = WNBADataIngestion(season=req.temporada)
        res_partidos = ingestor.ingestar_partidos_completos(n_partidos=req.num_partidos)

        return {
            "exito": res_partidos.get("exito", True),
            "liga": "WNBA",
            "temporada": req.temporada,
            "partidos_ingestados": res_partidos.get("partidos_ingestados", 0),
            "total_jugadas": res_partidos.get("total_jugadas", 0),
            "jugadoras_estrellas_registradas": jugadoras_cargadas,
            "mensaje": f"Ingesta WNBA completada con éxito ({res_partidos.get('partidos_ingestados', 0)} partidos, {jugadoras_cargadas} jugadoras)."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ingestar datos de la WNBA: {str(e)}"
        )


class IngestaNBARequest(BaseModel):
    num_partidos: int = Field(3, ge=1, le=20, description="Número de partidos reales a descargar")
    temporada: str = Field("2023-24", description="Temporada NBA (ej: '2023-24')")
    poblar_estrellas: bool = Field(True, description="Sembrar jugadores estrella NBA")


@router.post("/calibracion/ingestar-nba")
async def post_ingestar_nba(req: IngestaNBARequest = IngestaNBARequest()):
    """
    🏀 Ingesta partidos reales de la NBA con eventos play-by-play y siembra estrellas NBA.
    """
    try:
        from model.data_ingestion import NBADataIngestion, poblar_jugadores_estrella_demo
        jugadores_cargados = 0
        if req.poblar_estrellas:
            jugadores_cargados = poblar_jugadores_estrella_demo()

        ingestor = NBADataIngestion(season=req.temporada)
        res_partidos = ingestor.ingestar_partidos_completos(n_partidos=req.num_partidos)

        return {
            "exito": res_partidos.get("exito", True),
            "liga": "NBA",
            "temporada": req.temporada,
            "partidos_ingestados": res_partidos.get("partidos_ingestados", 0),
            "total_jugadas": res_partidos.get("total_jugadas", 0),
            "jugadores_estrellas_registrados": jugadores_cargados,
            "mensaje": f"Ingesta NBA completada con éxito ({res_partidos.get('partidos_ingestados', 0)} partidos)."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ingestar datos de la NBA: {str(e)}"
        )

