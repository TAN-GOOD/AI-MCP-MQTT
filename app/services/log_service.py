import asyncio
import json
import time
from typing import Dict, Set, Optional, Callable
from datetime import datetime
from fastapi import WebSocket


class LogService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.connections: Dict[int, Set[WebSocket]] = {}
        self.log_callbacks: Dict[int, list] = {}

    async def connect(self, project_id: int, websocket: WebSocket):
        await websocket.accept()
        if project_id not in self.connections:
            self.connections[project_id] = set()
        self.connections[project_id].add(websocket)

    def disconnect(self, project_id: int, websocket: WebSocket):
        if project_id in self.connections:
            self.connections[project_id].discard(websocket)
            if not self.connections[project_id]:
                del self.connections[project_id]

    async def broadcast(self, project_id: int, level: str, message: str):
        log_data = {
            "type": "log",
            "project_id": project_id,
            "level": level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if project_id in self.connections:
            disconnected = set()
            for ws in self.connections[project_id]:
                try:
                    await ws.send_json(log_data)
                except Exception:
                    disconnected.add(ws)
            for ws in disconnected:
                self.connections[project_id].discard(ws)

    async def broadcast_status(self, project_id: int, is_running: bool):
        status_data = {
            "type": "status",
            "project_id": project_id,
            "is_running": is_running,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if project_id in self.connections:
            disconnected = set()
            for ws in self.connections[project_id]:
                try:
                    await ws.send_json(status_data)
                except Exception:
                    disconnected.add(ws)
            for ws in disconnected:
                self.connections[project_id].discard(ws)


log_service = LogService()
