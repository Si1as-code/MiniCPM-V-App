"""
============================================================================
多轮对话 DAO - conversations 表的 CRUD 操作
============================================================================
"""

import logging
from typing import List, Optional

from data.database import DAOBase, db_manager
from data.models import Conversation

logger = logging.getLogger(__name__)


class ConversationDAO(DAOBase):
    """多轮对话数据访问对象"""

    TABLE_NAME = "conversations"
    MODEL_CLASS = Conversation
    COLUMNS = ["record_id", "role", "content", "token_count", "created_at"]
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        content TEXT NOT NULL DEFAULT '',
        token_count INTEGER DEFAULT 0,
        created_at REAL,
        FOREIGN KEY (record_id) REFERENCES recognition_records(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_conversation_record ON conversations(record_id);
    """

    def __init__(self, db=None):
        super().__init__(db or db_manager)

    def get_by_record_id(self, record_id: int) -> List[Conversation]:
        """获取某条识别记录的所有对话"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE record_id = ? ORDER BY created_at ASC"
        )
        rows = self.db.fetchall(sql, (record_id,))
        return [self._row_to_model(row) for row in rows]

    def get_recent(self, limit: int = 100) -> List[Conversation]:
        """获取最近的对话（所有记录）"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "ORDER BY created_at DESC LIMIT ?"
        )
        rows = self.db.fetchall(sql, (limit,))
        return [self._row_to_model(row) for row in rows]

    def get_token_sum_by_record(self, record_id: int) -> int:
        """统计某条记录的 token 总数"""
        sql = (
            f"SELECT SUM(token_count) FROM {self.TABLE_NAME} "
            "WHERE record_id = ?"
        )
        return self.db.fetchval(sql, (record_id,)) or 0

    def delete_by_record_id(self, record_id: int) -> int:
        """删除某条记录的所有对话"""
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE record_id = ?"
        cursor = self.db.execute(sql, (record_id,))
        return cursor.rowcount


# 全局单例
conversation_dao = ConversationDAO()
