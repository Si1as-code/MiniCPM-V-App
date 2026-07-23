"""
============================================================================
使用统计 DAO - usage_stats 表的 CRUD 操作
============================================================================
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from data.database import DAOBase, db_manager
from data.models import UsageStat

logger = logging.getLogger(__name__)


class UsageDAO(DAOBase):
    """使用统计数据访问对象 - 按天聚合"""

    TABLE_NAME = "usage_stats"
    MODEL_CLASS = UsageStat
    COLUMNS = ["date", "local_count", "api_count", "tokens_used", "cost", "created_at"]
    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS usage_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        local_count INTEGER DEFAULT 0,
        api_count INTEGER DEFAULT 0,
        tokens_used INTEGER DEFAULT 0,
        cost REAL DEFAULT 0.0,
        created_at REAL
    );
    """

    def __init__(self, db=None):
        super().__init__(db or db_manager)

    def _today(self) -> str:
        """返回今天的日期字符串 YYYY-MM-DD"""
        return datetime.now().strftime("%Y-%m-%d")

    def record_local_inference(self, tokens: int = 0) -> int:
        """记录一次端侧推理"""
        today = self._today()
        sql = (
            f"INSERT INTO {self.TABLE_NAME} (date, local_count, api_count, tokens_used, cost, created_at) "
            "VALUES (?, 1, 0, ?, 0.0, strftime('%s', 'now')) "
            "ON CONFLICT(date) DO UPDATE SET "
            "local_count = local_count + 1, "
            "tokens_used = tokens_used + excluded.tokens_used"
        )
        cursor = self.db.execute(sql, (today, tokens))
        return cursor.rowcount

    def record_api_call(self, tokens: int = 0, cost: float = 0.0) -> int:
        """记录一次云端 API 调用"""
        today = self._today()
        sql = (
            f"INSERT INTO {self.TABLE_NAME} (date, local_count, api_count, tokens_used, cost, created_at) "
            "VALUES (?, 0, 1, ?, ?, strftime('%s', 'now')) "
            "ON CONFLICT(date) DO UPDATE SET "
            "api_count = api_count + 1, "
            "tokens_used = tokens_used + excluded.tokens_used, "
            "cost = cost + excluded.cost"
        )
        cursor = self.db.execute(sql, (today, tokens, cost))
        return cursor.rowcount

    def get_by_date(self, date: str) -> Optional[UsageStat]:
        """查询某天的统计"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE date = ?"
        row = self.db.fetchone(sql, (date,))
        return self._row_to_model(row) if row else None

    def get_today(self) -> Optional[UsageStat]:
        """获取今天的统计"""
        return self.get_by_date(self._today())

    def get_range(self, start_date: str, end_date: str) -> List[UsageStat]:
        """查询日期范围内的统计"""
        sql = (
            f"SELECT * FROM {self.TABLE_NAME} "
            "WHERE date >= ? AND date <= ? "
            "ORDER BY date ASC"
        )
        rows = self.db.fetchall(sql, (start_date, end_date))
        return [self._row_to_model(row) for row in rows]

    def get_last_n_days(self, n: int = 7) -> List[UsageStat]:
        """获取最近 n 天的统计"""
        end = self._today()
        start = (datetime.now() - timedelta(days=n - 1)).strftime("%Y-%m-%d")
        return self.get_range(start, end)

    def get_total_stats(self) -> dict:
        """获取累计统计"""
        sql = (
            f"SELECT "
            "SUM(local_count) as total_local, "
            "SUM(api_count) as total_api, "
            "SUM(tokens_used) as total_tokens, "
            "SUM(cost) as total_cost "
            f"FROM {self.TABLE_NAME}"
        )
        row = self.db.fetchone(sql)
        if row:
            return {
                "total_local": row["total_local"] or 0,
                "total_api": row["total_api"] or 0,
                "total_tokens": row["total_tokens"] or 0,
                "total_cost": round(row["total_cost"] or 0.0, 4),
            }
        return {"total_local": 0, "total_api": 0, "total_tokens": 0, "total_cost": 0.0}

    def get_daily_budget_usage(self, budget: float) -> dict:
        """获取今日预算使用情况"""
        today_stat = self.get_today()
        if today_stat is None:
            return {
                "today_cost": 0.0,
                "budget": budget,
                "remaining": budget,
                "usage_percent": 0.0,
            }
        today_cost = today_stat.cost
        remaining = max(0, budget - today_cost)
        percent = (today_cost / budget * 100) if budget > 0 else 0.0
        return {
            "today_cost": round(today_cost, 4),
            "budget": budget,
            "remaining": round(remaining, 4),
            "usage_percent": round(percent, 2),
        }


# 全局单例
usage_dao = UsageDAO()
