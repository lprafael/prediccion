"""
Pydantic schemas para Partidos — validación de entrada/salida de la API.
"""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class MarcadorCuartoSchema(BaseModel):
    cuarto: int = Field(..., ge=1, le=4)
    pts_local: int = Field(0, ge=0)
    pts_visitante: int = Field(0, ge=0)


class CrearPartidoRequest(BaseModel):
    equipo_local: str = Field(..., min_length=1, max_length=100)
    equipo_visitante: str = Field(..., min_length=1, max_length=100)
    torneo_nombre: str = Field(..., min_length=1)
    cuarto_actual: int = Field(1, ge=1, le=5)
    min_restantes: int = Field(10, ge=0)
    seg_restantes: int = Field(0, ge=0, le=59)
    quarters_data: List[Tuple[int, int]] = Field(default_factory=lambda: [(0, 0), (0, 0), (0, 0), (0, 0)])
    notas: str = Field("", max_length=500)

    model_config = {"json_schema_extra": {
        "example": {
            "equipo_local": "Lakers",
            "equipo_visitante": "Celtics",
            "torneo_nombre": "NBA (National Basketball Association)",
            "cuarto_actual": 2,
            "min_restantes": 5,
            "seg_restantes": 30,
            "quarters_data": [[28, 25], [10, 8], [0, 0], [0, 0]],
            "notas": "Partido inaugural de temporada"
        }
    }}


class ActualizarPartidoRequest(BaseModel):
    cuarto_actual: int = Field(..., ge=1, le=5)
    min_restantes: int = Field(..., ge=0)
    seg_restantes: int = Field(0, ge=0, le=59)
    quarters_data: List[Tuple[int, int]]
    notas: str = Field("", max_length=500)


class FinalizarPartidoRequest(BaseModel):
    pts_local_final: int = Field(..., ge=0)
    pts_visitante_final: int = Field(..., ge=0)
    quarters_data: Optional[List[Tuple[int, int]]] = None
    notas: Optional[str] = None


class PartidoResponse(BaseModel):
    id: int
    torneo: str
    equipo_local: str
    equipo_visitante: str
    estado: str
    cuarto_actual: int
    min_restantes: int
    seg_restantes: int
    notas: Optional[str]
    creado_en: str
    actualizado_en: str
    total_local: Optional[int] = 0
    total_visitante: Optional[int] = 0
    marcadores: Optional[List[MarcadorCuartoSchema]] = None
    pts_local_final: Optional[int] = None
    pts_visitante_final: Optional[int] = None
    total_final: Optional[int] = None
