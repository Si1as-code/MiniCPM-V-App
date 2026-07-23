"""
============================================================================
数据库迁移管理器
============================================================================
负责数据库版本控制和表结构初始化/升级。
============================================================================
"""

import logging
import time
from typing import List

from data.database import DatabaseManager, db_manager

logger = logging.getLogger(__name__)

# 当前数据库版本号
CURRENT_VERSION = 1


class MigrationManager:
    """数据库迁移管理器"""

    def __init__(self, db: DatabaseManager = None):
        self.db = db or db_manager

    def init(self):
        """
        初始化数据库：创建版本控制表 + 运行所有迁移
        """
        self._create_version_table()
        self._run_migrations()
        logger.info("数据库迁移完成")

    def _create_version_table(self):
        """创建版本控制表"""
        sql = """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL,
            description TEXT
        )
        """
        self.db.execute(sql)

    def _get_current_version(self) -> int:
        """获取当前数据库版本"""
        row = self.db.fetchone(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        return row["version"] if row else 0

    def _run_migrations(self):
        """运行所有未执行的迁移"""
        current = self._get_current_version()
        logger.info(f"当前数据库版本: {current}, 目标版本: {CURRENT_VERSION}")

        if current >= CURRENT_VERSION:
            logger.info("数据库已是最新版本")
            return

        migrations = self._get_migrations()
        for version, (description, sql_statements) in enumerate(migrations, start=1):
            if version > current:
                self._apply_migration(version, description, sql_statements)

    def _apply_migration(
        self, version: int, description: str, sql_statements: List[str]
    ):
        """执行单个迁移"""
        logger.info(f"执行迁移 {version}: {description}")

        with self.db.transaction():
            for sql in sql_statements:
                if sql.strip():
                    self.db.connection.execute(sql)

            # 记录迁移历史
            self.db.connection.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (version, time.time(), description),
            )

        logger.info(f"迁移 {version} 完成")

    def _get_migrations(self) -> List[tuple]:
        """
        定义所有迁移脚本

        每个迁移是一个元组: (描述, [SQL语句列表])
        """
        return [
            # 版本 1: 初始表结构
            (
                "创建初始表结构",
                [
                    """
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
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_recognition_hash ON recognition_records(image_hash)",
                    "CREATE INDEX IF NOT EXISTS idx_recognition_synced ON recognition_records(synced)",
                    "CREATE INDEX IF NOT EXISTS idx_recognition_created ON recognition_records(created_at)",

                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        record_id INTEGER NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        content TEXT NOT NULL DEFAULT '',
                        token_count INTEGER DEFAULT 0,
                        created_at REAL,
                        FOREIGN KEY (record_id) REFERENCES recognition_records(id) ON DELETE CASCADE
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_conversation_record ON conversations(record_id)",

                    """
                    CREATE TABLE IF NOT EXISTS image_index (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_hash TEXT NOT NULL UNIQUE,
                        embedding_vector BLOB,
                        embedding_version TEXT DEFAULT '',
                        indexed_at REAL
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_image_hash ON image_index(image_hash)",

                    """
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
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_api_status ON api_tasks(status)",
                    "CREATE INDEX IF NOT EXISTS idx_api_scheduled ON api_tasks(scheduled_at)",

                    """
                    CREATE TABLE IF NOT EXISTS user_settings (
                        key TEXT PRIMARY KEY NOT NULL,
                        value TEXT NOT NULL DEFAULT '',
                        updated_at REAL
                    )
                    """,

                    """
                    CREATE TABLE IF NOT EXISTS usage_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL UNIQUE,
                        local_count INTEGER DEFAULT 0,
                        api_count INTEGER DEFAULT 0,
                        tokens_used INTEGER DEFAULT 0,
                        cost REAL DEFAULT 0.0,
                        created_at REAL
                    )
                    """,
                ],
            ),
        ]


# 便捷函数
def init_database(db: DatabaseManager = None):
    """初始化数据库（运行所有迁移）"""
    mgr = MigrationManager(db)
    mgr.init()


def reset_database(db: DatabaseManager = None):
    """
    重置数据库（删除所有表并重新初始化）
    警告：仅用于开发和测试！
    """
    db = db or db_manager
    tables = [
        "schema_version",
        "recognition_records",
        "conversations",
        "image_index",
        "api_tasks",
        "user_settings",
        "usage_stats",
    ]
    for table in tables:
        db.execute(f"DROP TABLE IF EXISTS {table}")
    init_database(db)
    logger.warning("数据库已重置")
