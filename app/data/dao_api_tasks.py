"""
============================================================================
API 任务队列 DAO - api_tasks 表的 CRUD 操作
============================================================================
"""

import logging
import time
from typing import List, Optional

from data.database import DAOBase, db_manager
from data.models import APITask

logger = logging.getLogger(__name__)


class APITaskDAO(DAOBase):
    """云端 API 任务队列数据访问对象"""

    TABLE_NAME = "api_tasks"
    MODEL_CLASS = APITask
    COLUMNS = [
        "record_id", "provider", "status", "retry_count",
        "last_error", "scheduled_at", "completed_at", "created_at",
    ]
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS api_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER,
        provider TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        last_error TEXT DEFAULT '',
        scheduled_at REAL,
        completed_at REAL,
        created_at REAL
    );
    CREATE INDEX IF NOT EXISTS idx_api_status ON api_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_api_scheduled ON api_tasks(scheduled_at);
    """

    def __init__(self, db=None):
        super().__init__(db or db_manager)

    def get_pending(self, limit: int = 50) -> List[APITask]:
        """获取待执行的任务"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE status = 'pending' "
            "ORDER BY scheduled_at ASC LIMIT ?"
        )
        rows = self.db.fetchall(sql, (limit,))
        return [self._row_to_model(row) for row in rows]

    def get_by_status(self, status: str, limit: int = 100) -> List[APITask]:
        """按状态查询任务"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE status = ? ORDER BY created_at DESC LIMIT ?"
        )
        rows = self.db.fetchall(sql, (status, limit))
        return [self._row_to_model(row) for row in rows]

    def update_status(
        self,
        id: int,
        status: str,
        error: str = "",
        increment_retry: bool = False,
    ) -> int:
        """更新任务状态"""
        if status == "completed":
            sql = (
                f"UPDATE {self.TABLE_NAME} "
                "SET status = ?, completed_at = ?, last_error = ? "
                "WHERE id = ?"
            )
            params = (status, time.time(), error, id)
        elif increment_retry:
            sql = (
                f"UPDATE {self.TABLE_NAME} "
                "SET status = ?, retry_count = retry_count + 1, "
                "last_error = ? WHERE id = ?"
            )
            params = (status, error, id)
        else:
            sql = (
                f"UPDATE {self.TABLE_NAME} "
                "SET status = ?, last_error = ? WHERE id = ?"
            )
            params = (status, error, id)

        cursor = self.db.execute(sql, params)
        return cursor.rowcount

    def get_failed_tasks(self, max_retry: int = 3) -> List[APITask]:
        """获取可重试的失败任务"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE status = 'failed' AND retry_count < ? "
            "ORDER BY scheduled_at ASC"
        )
        rows = self.db.fetchall(sql, (max_retry,))
        return [self._row_to_model(row) for row in rows]

    def cancel_task(self, id: int) -> int:
        """取消任务"""
        return self.update_status(id, "cancelled")


# 全局单例
api_task_dao = APITaskDAO()
