"""
WebSocket Connection Manager para broadcasting en tiempo real por partido.
"""

from typing import Dict, List, Any
from fastapi import WebSocket
import json
import asyncio


class ConnectionManager:
    """Administra conexiones WebSocket segregadas por partido."""

    def __init__(self):
        # partido_id -> lista de WebSockets activos
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, partido_id: int):
        await websocket.accept()
        async with self._lock:
            if partido_id not in self.active_connections:
                self.active_connections[partido_id] = []
            self.active_connections[partido_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, partido_id: int):
        async with self._lock:
            if partido_id in self.active_connections:
                if websocket in self.active_connections[partido_id]:
                    self.active_connections[partido_id].remove(websocket)
                if not self.active_connections[partido_id]:
                    del self.active_connections[partido_id]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    async def broadcast_to_match(self, partido_id: int, message: dict):
        """Envía un mensaje a todos los clientes suscritos a un partido."""
        async with self._lock:
            connections = list(self.active_connections.get(partido_id, []))

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Si falla el envío, desconectar al cliente en segundo plano
                asyncio.create_task(self.disconnect(connection, partido_id))


# Instancia única compartida
manager = ConnectionManager()
