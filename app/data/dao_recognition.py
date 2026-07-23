"""
============================================================================
识别记录 DAO - recognition_records 表的 CRUD 操作
============================================================================
"""

import logging
from typing import List, Optional

from data.database import DAOBase, db_manager
from data.models import RecognitionRecord

logger = logging.getLogger(__name__)


class RecognitionDAO(DAOBase):
    """识别记录数据访问对象"""

    TABLE_NAME = "recognition_records"
    MODEL_CLASS = RecognitionRecord
    COLUMNS = [
        "image_hash", "image_path", "question", "answer",
        "confidence", "model_version", "device_id",
        "task_type", "synced", "created_at", "updated_at",
    ]
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS recognition_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_hash TEXT NOT NULL,
        image_path TEXT,
        question TEXT NOT NULL DEFAULT '',
        answer TEXT NOT NULL DEFAULT '',
        confidence REAL DEFAULT 0.0,
        model_version TEXT DEFAULT '',
        device_id TEXT DEFAULT '',
        task_type TEXT DEFAULT 'auto',
        synced INTEGER DEFAULT 0,
        created_at REAL,
        updated_at REAL
    );
    CREATE INDEX IF NOT EXISTS idx_recognition_hash ON recognition_records(image_hash);
    CREATE INDEX IF NOT EXISTS idx_recognition_synced ON recognition_records(synced);
    CREATE INDEX IF NOT EXISTS idx_recognition_created ON recognition_records(created_at);
    """

    def __init__(self, db=None):
        super().__init__(db or db_manager)

    # ------------------------------------------------------------------
    # 扩展查询
    # ------------------------------------------------------------------

    def get_by_hash(self, image_hash: str) -> Optional[RecognitionRecord]:
        """根据图片 hash 查询最新记录"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE image_hash = ? ORDER BY created_at DESC LIMIT 1"
        )
        row = self.db.fetchone(sql, (image_hash,))
        return self._row_to_model(row) if row else None

    def get_by_task_type(
        self, task_type: str, limit: int = 50
    ) -> List[RecognitionRecord]:
        """按任务类型查询"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE task_type = ? ORDER BY created_at DESC LIMIT ?"
        )
        rows = self.db.fetchall(sql, (task_type, limit))
        return [self._row_to_model(row) for row in rows]

    def get_unsynced(self, limit: int = 100) -> List[RecognitionRecord]:
        """获取未同步到云端的记录"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE synced = 0 ORDER BY created_at ASC LIMIT ?"
        )
        rows = self.db.fetchall(sql, (limit,))
        return [self._row_to_model(row) for row in rows]

    def mark_synced(self, id: int) -> int:
        """标记记录为已同步"""
        sql = (
            f"UPDATE {self.TABLE_NAME} SET synced = 1, updated_at = ? "
            "WHERE id = ?"
        )
        import time
        cursor = self.db.execute(sql, (time.time(), id))
        return cursor.rowcount

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self.count()
        unsynced = self.db.fetchval(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} WHERE synced = 0"
        ) or 0
        avg_confidence = self.db.fetchval(
            f"SELECT AVG(confidence) FROM {self.TABLE_NAME}"
        ) or 0.0
        return {
            "total": total,
            "unsynced": unsynced,
            "avg_confidence": round(avg_confidence, 3),
        }


# 全局单例
recognition_dao = RecognitionDAO()
