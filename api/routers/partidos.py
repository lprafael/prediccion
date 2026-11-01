"""
Router para Partidos — CRUD completo y finalización/liquidación.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from model.database import (
    crear_partido,
    actualizar_partido,
    listar_partidos,
    obtener_partido,
    eliminar_partido,
    finalizar_partido_y_liquidar,
    listar_jugadas,
    guardar_jugadas,
)
from api.schemas.partidos import (
    CrearPartidoRequest,
    ActualizarPartidoRequest,
    FinalizarPartidoRequest,
    PartidoResponse,
)

router = APIRouter()


@router.get("/partidos", response_model=List[PartidoResponse])
async def get_partidos(limit: int = Query(100, ge=1, le=500)):
    """Lista los partidos ordenados cronológicamente por última actualización."""
    try:
        partidos = listar_partidos(limit=limit)
        return partidos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar partidos: {str(e)}"
        )


@router.post("/partidos", response_model=dict, status_code=status.HTTP_201_CREATED)
async def post_partido(req: CrearPartidoRequest):
    """Crea un nuevo partido con sus cuartos iniciales."""
    try:
        partido_id = crear_partido(
            equipo_local=req.equipo_local,
            equipo_visitante=req.equipo_visitante,
            torneo_nombre=req.torneo_nombre,
            cuarto_actual=req.cuarto_actual,
            min_restantes=req.min_restantes,
            seg_restantes=req.seg_restantes,
            quarters_data=req.quarters_data,
            notas=req.notas
        )
        return {"id": partido_id, "message": "Partido creado exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear partido: {str(e)}"
        )


@router.get("/partidos/{partido_id}", response_model=PartidoResponse)
async def get_partido(partido_id: int):
    """Obtiene el detalle completo de un partido por ID, incluyendo marcadores por cuarto."""
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido con ID {partido_id} no encontrado"
        )
    return partido


@router.put("/partidos/{partido_id}")
async def put_partido(partido_id: int, req: ActualizarPartidoRequest):
    """Actualiza los marcadores, minutos y estado de un partido existente."""
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido con ID {partido_id} no encontrado"
        )
    try:
        actualizar_partido(
            partido_id=partido_id,
            cuarto_actual=req.cuarto_actual,
            min_restantes=req.min_restantes,
            seg_restantes=req.seg_restantes,
            quarters_data=req.quarters_data,
            notas=req.notas
        )
        return {"message": "Partido actualizado exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar partido: {str(e)}"
        )


@router.delete("/partidos/{partido_id}", status_code=status.HTTP_200_OK)
async def delete_partido(partido_id: int):
    """Elimina un partido y sus datos dependientes en cascada."""
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido con ID {partido_id} no encontrado"
        )
    try:
        eliminar_partido(partido_id)
        return {"message": f"Partido {partido_id} eliminado exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar partido: {str(e)}"
        )


@router.post("/partidos/{partido_id}/finalizar")
async def post_finalizar_partido(partido_id: int, req: FinalizarPartidoRequest):
    """
    Marca el partido como finalizado, registra el tanteador definitivo
    y liquida automáticamente las apuestas pendientes.
    """
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido con ID {partido_id} no encontrado"
        )
    try:
        resumen = finalizar_partido_y_liquidar(
            partido_id=partido_id,
            pts_local_final=req.pts_local_final,
            pts_visitante_final=req.pts_visitante_final,
            quarters_data=req.quarters_data,
            notas=req.notas
        )
        return resumen
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al finalizar partido: {str(e)}"
        )


@router.get("/partidos/{partido_id}/jugadas")
async def get_partido_jugadas(partido_id: int):
    """Obtiene la lista completa de jugadas play-by-play registradas para un partido."""
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido con ID {partido_id} no encontrado"
        )
    return listar_jugadas(partido_id)


@router.post("/partidos/{partido_id}/jugadas")
async def post_partido_jugadas(partido_id: int, plays: List[dict]):
    """Registra o actualiza jugadas play-by-play para un partido."""
    partido = obtener_partido(partido_id)
    if not partido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partido con ID {partido_id} no encontrado"
        )
    guardar_jugadas(partido_id, plays)
    return {"message": f"{len(plays)} jugadas guardadas", "partido_id": partido_id}
