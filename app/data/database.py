"""
============================================================================
数据库管理器 - SQLite 连接管理 + CRUD 基类 + 事务管理
============================================================================
技术栈: Python 标准库 sqlite3
设计要点:
  - 单例模式确保全局唯一连接池
  - 线程安全（sqlite3 默认支持多线程）
  - 事务上下文管理器支持原子操作
  - CRUD 基类减少 DAO 重复代码
============================================================================
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ==========================================================================
# 数据库连接管理
# ==========================================================================

class DatabaseManager:
    """
    SQLite 数据库管理器 - 单例模式

    负责数据库连接的创建、管理和关闭。
    支持 WAL 模式（Write-Ahead Logging）提升并发性能。
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None) -> "DatabaseManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return
        self._initialized = True

        # 默认数据库路径
        if db_path is None:
            # 放在项目根目录下的 data/ 文件夹
            base_dir = Path(__file__).parent.parent
            db_dir = base_dir / "data_store"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "minicpmv_app.db")

        self.db_path = db_path
        self._local = threading.local()

        # 初始化数据库（建表 + WAL 模式）
        self._init_db()

    def _init_db(self):
        """初始化数据库：启用 WAL 模式，运行迁移"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")

    @property
    def connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（线程隔离）"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def close(self):
        """关闭当前线程的连接"""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def execute(
        self, sql: str, parameters: Tuple = ()
    ) -> sqlite3.Cursor:
        """执行 SQL 语句（不在事务中时自动 commit）"""
        cursor = self.connection.execute(sql, parameters)
        # 只有在非事务模式下才自动提交
        if self.connection.in_transaction is False:
            self.connection.commit()
        return cursor

    def fetchone(self, sql: str, parameters: Tuple = ()) -> Optional[sqlite3.Row]:
        """查询单条记录"""
        cursor = self.connection.execute(sql, parameters)
        return cursor.fetchone()

    def fetchall(self, sql: str, parameters: Tuple = ()) -> List[sqlite3.Row]:
        """查询多条记录"""
        cursor = self.connection.execute(sql, parameters)
        return cursor.fetchall()

    def fetchval(self, sql: str, parameters: Tuple = ()) -> Any:
        """查询单个值"""
        row = self.fetchone(sql, parameters)
        if row:
            return row[0]
        return None

    # ------------------------------------------------------------------
    # 上下文管理器：事务
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(self):
        """
        事务上下文管理器

        支持嵌套事务（通过 SAVEPOINT 实现）。

        用法:
            with db.transaction():
                db.execute("INSERT ...")
                db.execute("UPDATE ...")
                # 如果发生异常，自动回滚
        """
        conn = self.connection
        if conn.in_transaction:
            # 已在事务中，使用 SAVEPOINT（支持嵌套）
            sp_name = f"sp_{threading.current_thread().ident}"
            conn.execute(f"SAVEPOINT {sp_name}")
            try:
                yield conn
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                logger.debug(f"SAVEPOINT {sp_name} 释放")
            except Exception as e:
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                logger.error(f"SAVEPOINT 回滚: {e}")
                raise
        else:
            conn.execute("BEGIN")
            try:
                yield conn
                conn.commit()
                logger.debug("事务提交成功")
            except Exception as e:
                conn.rollback()
                logger.error(f"事务回滚: {e}")
                raise

    # ------------------------------------------------------------------
    # 表操作
    # ------------------------------------------------------------------

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        sql = (
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=?"
        )
        return self.fetchval(sql, (table_name,)) is not None

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表结构信息"""
        cursor = self.connection.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": row["notnull"],
                "default": row["dflt_value"],
                "pk": row["pk"],
            })
        return columns


# ==========================================================================
# CRUD 基类
# ==========================================================================

class DAOBase:
    """
    DAO 基类 - 提供通用的 CRUD 操作

    子类需要实现:
      - TABLE_NAME: 表名
      - MODEL_CLASS: 对应的 dataclass 类型
      - COLUMNS: 字段列表（不含 id）
      - CREATE_SQL: 建表语句
    """

    TABLE_NAME: str = ""
    MODEL_CLASS: Type = None
    COLUMNS: List[str] = []
    CREATE_SQL: str = ""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def create_table(self):
        """创建表（如果不存在）"""
        if self.CREATE_SQL:
            self.db.execute(self.CREATE_SQL)
            logger.debug(f"表 {self.TABLE_NAME} 创建/已存在")

    def drop_table(self):
        """删除表（危险操作，仅测试用）"""
        self.db.execute(f"DROP TABLE IF EXISTS {self.TABLE_NAME}")
        logger.warning(f"表 {self.TABLE_NAME} 已删除")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def insert(self, obj: T) -> int:
        """插入记录，返回自增 id"""
        columns = ", ".join(self.COLUMNS)
        placeholders = ", ".join(["?"] * len(self.COLUMNS))
        sql = f"INSERT INTO {self.TABLE_NAME} ({columns}) VALUES ({placeholders})"

        values = [getattr(obj, col) for col in self.COLUMNS]
        cursor = self.db.execute(sql, tuple(values))
        return cursor.lastrowid

    def get_by_id(self, id: int) -> Optional[T]:
        """根据 id 查询单条记录"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?"
        row = self.db.fetchone(sql, (id,))
        if row:
            return self._row_to_model(row)
        return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """查询所有记录（分页）"""
        sql = f"SELECT * FROM {self.TABLE_NAME} ORDER BY id DESC LIMIT ? OFFSET ?"
        rows = self.db.fetchall(sql, (limit, offset))
        return [self._row_to_model(row) for row in rows]

    def update(self, obj: T) -> int:
        """更新记录（根据 id），返回影响的行数"""
        if getattr(obj, "id", None) is None:
            raise ValueError("更新需要 id 字段")

        columns = ", ".join([f"{c} = ?" for c in self.COLUMNS])
        sql = f"UPDATE {self.TABLE_NAME} SET {columns} WHERE id = ?"

        values = [getattr(obj, col) for col in self.COLUMNS]
        values.append(obj.id)
        cursor = self.db.execute(sql, tuple(values))
        return cursor.rowcount

    def delete(self, id: int) -> int:
        """根据 id 删除记录，返回影响的行数"""
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE id = ?"
        cursor = self.db.execute(sql, (id,))
        return cursor.rowcount

    def count(self) -> int:
        """统计记录总数"""
        return self.db.fetchval(f"SELECT COUNT(*) FROM {self.TABLE_NAME}") or 0

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _row_to_model(self, row: sqlite3.Row) -> T:
        """将 sqlite3.Row 转为 dataclass"""
        data = dict(row)
        return self.MODEL_CLASS(**data)


# 全局数据库管理器实例
db_manager = DatabaseManager()
