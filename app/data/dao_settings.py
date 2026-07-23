"""
============================================================================
用户设置 DAO - user_settings 表的 CRUD 操作
============================================================================
"""

import json
import logging
import time
from typing import Any, Optional

from data.database import DAOBase, db_manager
from data.models import UserSetting

logger = logging.getLogger(__name__)


class SettingsDAO(DAOBase):
    """用户设置数据访问对象 - key-value 存储"""

    TABLE_NAME = "user_settings"
    MODEL_CLASS = UserSetting
    COLUMNS = ["key", "value", "updated_at"]
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS user_settings (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT NOT NULL DEFAULT '',
        updated_at REAL
    );
    """

    def __init__(self, db=None):
        super().__init__(db or db_manager)

    def set(self, key: str, value: Any) -> int:
        """
        设置键值对（自动序列化 JSON）

        Args:
            key: 设置键名
            value: 任意可 JSON 序列化的值
        """
        str_value = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        sql = (
            f"INSERT INTO {self.TABLE_NAME} (key, value, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
        )
        cursor = self.db.execute(sql, (key, str_value, time.time()))
        return cursor.rowcount

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取设置值（自动反序列化 JSON）

        Args:
            key: 设置键名
            default: 默认值
        """
        sql = f"SELECT value FROM {self.TABLE_NAME} WHERE key = ?"
        row = self.db.fetchone(sql, (key,))
        if row is None:
            return default

        raw = row["value"]
        # 尝试 JSON 反序列化
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw  # 返回原始字符串

    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔值设置"""
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return bool(val)

    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数值设置"""
        val = self.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """获取浮点值设置"""
        val = self.get(key, default)
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def delete(self, key: str) -> int:
        """删除设置"""
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE key = ?"
        cursor = self.db.execute(sql, (key,))
        return cursor.rowcount

    def get_all(self) -> dict:
        """获取所有设置"""
        sql = f"SELECT key, value FROM {self.TABLE_NAME}"
        rows = self.db.fetchall(sql)
        result = {}
        for row in rows:
            key = row["key"]
            raw = row["value"]
            try:
                result[key] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                result[key] = raw
        return result

    # ------------------------------------------------------------------
    # 预设设置项快捷方法
    # ------------------------------------------------------------------

    def get_auto_recognition(self) -> bool:
        """获取自动识别开关"""
        return self.get_bool("auto_recognition", default=False)

    def set_auto_recognition(self, enabled: bool):
        """设置自动识别开关"""
        self.set("auto_recognition", enabled)

    def get_cloud_api_enabled(self) -> bool:
        """获取云端 API 开关"""
        return self.get_bool("cloud_api_enabled", default=False)

    def set_cloud_api_enabled(self, enabled: bool):
        """设置云端 API 开关"""
        self.set("cloud_api_enabled", enabled)

    def get_daily_budget(self) -> float:
        """获取每日预算（元）"""
        return self.get_float("daily_budget", default=0.0)

    def set_daily_budget(self, budget: float):
        """设置每日预算"""
        self.set("daily_budget", budget)


# 全局单例
settings_dao = SettingsDAO()
