import json
import logging
from typing import Set, Dict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # {user_id: {websocket, ...}}
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """建立 WebSocket 连接"""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)
        logger.info(f"WebSocket 连接: user={user_id}, total={self._count_connections()}")

    def disconnect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """断开 WebSocket 连接"""
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WebSocket 断开: user={user_id}, total={self._count_connections()}")

    async def send_personal_message(self, message: dict, user_id: str):
        """发送消息给指定用户"""
        if user_id not in self._connections:
            return
        dead_connections = set()
        for ws in self._connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.add(ws)
        # 清理失效连接
        self._connections[user_id] -= dead_connections

    async def broadcast(self, message: dict):
        """广播消息给所有用户"""
        for user_id in list(self._connections.keys()):
            await self.send_personal_message(message, user_id)

    def _count_connections(self) -> int:
        return sum(len(ws_set) for ws_set in self._connections.values())


# 全局单例
connection_manager = ConnectionManager()


# ------------------------------------------------------------------
# 快捷通知函数
# ------------------------------------------------------------------

async def notify_inference_progress(
    user_id: str,
    task_id: int,
    status: str,
    progress: float = 0.0,
    message: str = "",
):
    """发送推理进度通知"""
    await connection_manager.send_personal_message(
        {
            "type": "inference_progress",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
        },
        user_id,
    )


async def notify_task_completed(
    user_id: str,
    task_id: int,
    result: dict,
):
    """发送任务完成通知"""
    await connection_manager.send_personal_message(
        {
            "type": "task_completed",
            "task_id": task_id,
            "result": result,
        },
        user_id,
    )


async def notify_sync_progress(
    user_id: str,
    status: str,
    uploaded: int = 0,
    downloaded: int = 0,
    message: str = "",
):
    """发送同步进度通知"""
    await connection_manager.send_personal_message(
        {
            "type": "sync_progress",
            "status": status,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "message": message,
        },
        user_id,
    )