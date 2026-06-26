import asyncio
import json
import time
import logging
import os
from pathlib import Path
from typing import Dict, Set, Optional, Callable, List
from datetime import datetime
from fastapi import WebSocket

# 本地文件 fallback：DB 写入失败时落盘，避免日志丢失
_FALLBACK_LOG_DIR = Path("logs_fallback")
_fallback_logger = logging.getLogger("log_service_fallback")
if not _fallback_logger.handlers:
    _FALLBACK_LOG_DIR.mkdir(exist_ok=True)
    _handler = logging.FileHandler(_FALLBACK_LOG_DIR / "db_failed.log", encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _fallback_logger.addHandler(_handler)
    _fallback_logger.setLevel(logging.INFO)


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
        # 日志持久化：批量缓存
        self._pending_logs: List[dict] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._max_cache = 50  # 缓存达到此数量时写入
        self._max_per_project = 1000  # 每个项目最多保留日志条数

    def _ensure_flush_task(self):
        """确保后台刷写任务在运行"""
        if self._flush_task is None or self._flush_task.done():
            try:
                self._flush_task = asyncio.create_task(self._flush_loop())
            except RuntimeError:
                pass  # 没有事件循环（启动早期），跳过

    async def _flush_loop(self):
        """后台定时刷写日志到数据库"""
        while True:
            await asyncio.sleep(3)
            await self._flush_to_db()

    async def _flush_to_db(self):
        """将缓存日志批量写入数据库；失败时落本地文件 fallback"""
        if not self._pending_logs:
            return
        logs_to_write = self._pending_logs
        self._pending_logs = []
        try:
            from app.database import SessionLocal
            from app.models import OperationLog
            db = SessionLocal()
            try:
                db.bulk_save_objects([
                    OperationLog(
                        project_id=log["project_id"],
                        level=log["level"],
                        message=log["message"],
                    ) for log in logs_to_write
                ])
                db.commit()
            finally:
                db.close()
        except Exception as e:
            # DB 写入失败：落本地文件 fallback，避免日志丢失
            for log in logs_to_write:
                _fallback_logger.error(
                    f"project={log['project_id']} level={log['level']} msg={log['message']} err={e}"
                )

    async def _trim_project_logs(self, project_id: int):
        """清理项目过多的历史日志"""
        try:
            from app.database import SessionLocal
            from app.models import OperationLog
            from sqlalchemy import delete, select, func
            db = SessionLocal()
            try:
                count = db.query(func.count(OperationLog.id)).filter(
                    OperationLog.project_id == project_id
                ).scalar()
                if count and count > self._max_per_project:
                    # 删除最旧的超出部分
                    excess = count - self._max_per_project
                    old_ids = db.query(OperationLog.id).filter(
                        OperationLog.project_id == project_id
                    ).order_by(OperationLog.created_at.asc()).limit(excess).all()
                    ids_to_delete = [row[0] for row in old_ids]
                    if ids_to_delete:
                        db.query(OperationLog).filter(
                            OperationLog.id.in_(ids_to_delete)
                        ).delete(synchronize_session=False)
                        db.commit()
            finally:
                db.close()
        except Exception:
            pass

    def connect(self, project_id: int, websocket: WebSocket):
        if project_id not in self.connections:
            self.connections[project_id] = set()
        self.connections[project_id].add(websocket)

    async def connect_async(self, project_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connect(project_id, websocket)

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
        # 推送到 WebSocket
        if project_id in self.connections:
            disconnected = set()
            for ws in self.connections[project_id]:
                try:
                    await ws.send_json(log_data)
                except Exception:
                    disconnected.add(ws)
            for ws in disconnected:
                self.connections[project_id].discard(ws)
        # 缓存到持久化队列
        self._pending_logs.append({
            "project_id": project_id,
            "level": level,
            "message": message,
        })
        # 达到阈值立即刷写
        if len(self._pending_logs) >= self._max_cache:
            await self._flush_to_db()
        else:
            self._ensure_flush_task()

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

    def get_history(self, project_id: int, limit: int = 100) -> list:
        """获取项目历史日志"""
        try:
            from app.database import SessionLocal
            from app.models import OperationLog
            db = SessionLocal()
            try:
                logs = db.query(OperationLog).filter(
                    OperationLog.project_id == project_id
                ).order_by(OperationLog.created_at.desc()).limit(limit).all()
                return [
                    {
                        "type": "log",
                        "project_id": log.project_id,
                        "level": log.level,
                        "message": log.message,
                        "timestamp": log.created_at.isoformat() if log.created_at else None,
                    }
                    for log in reversed(logs)  # 返回时间正序
                ]
            finally:
                db.close()
        except Exception:
            return []

    async def shutdown(self):
        """应用关闭时刷写剩余日志"""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_to_db()


log_service = LogService()
