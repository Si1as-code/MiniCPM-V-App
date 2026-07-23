"""
============================================================================
预算控制模块
============================================================================
负责 token 计数、日限额检查、自动降级决策。
与 Sprint 2 的 usage_dao 和 settings_dao 联动。
============================================================================
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from api.config import scheduler_config
from data.dao_usage import usage_dao
from data.dao_settings import settings_dao

logger = logging.getLogger(__name__)


class BudgetController:
    """
    预算控制器 - 单例模式

    核心职责:
      1. 检查每日预算是否超限
      2. 记录每次 API 调用的 token 消耗和成本
      3. 提供预算使用统计
    """

    _instance: Optional["BudgetController"] = None

    def __new__(cls) -> "BudgetController":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------
    # 预算检查
    # ------------------------------------------------------------------

    def can_use_cloud_api(self) -> bool:
        """
        检查是否可以使用云端 API

        返回:
            True: 允许使用云端 API
            False: 预算超限或未开启，应降级到端侧

        决策逻辑:
            1. 如果 force_local 为 True → 直接返回 False
            2. 从 settings_dao 读取每日预算
            3. 如果预算为 0（不限制）→ 返回 True
            4. 查询今日已花费成本
            5. 如果已花费 < 预算 → 返回 True，否则 False
        """
        # 强制端侧模式
        if scheduler_config.force_local:
            logger.debug("预算: force_local 模式，跳过云端 API")
            return False

        # 检查云端 API 开关
        if not settings_dao.get_cloud_api_enabled():
            logger.debug("预算: 云端 API 未开启，跳过")
            return False

        # 获取每日预算
        budget = settings_dao.get_daily_budget()
        if budget > 0:
            # 使用 scheduler_config 中的默认值作为兜底
            pass
        elif scheduler_config.daily_budget > 0:
            budget = scheduler_config.daily_budget
        else:
            # 预算为 0 表示不限制
            logger.debug("预算: 未设置预算限制")
            return True

        # 检查今日已花费
        usage = usage_dao.get_daily_budget_usage(budget)
        if usage["remaining"] <= 0:
            logger.warning(
                f"预算超限! 今日已花费 {usage['today_cost']:.4f} 元, "
                f"预算 {budget} 元"
            )
            return False

        logger.debug(
            f"预算: 今日已花费 {usage['today_cost']:.4f} 元, "
            f"剩余 {usage['remaining']:.4f} 元"
        )
        return True

    def check_call_cost(self, estimated_cost: float) -> bool:
        """
        检查单次调用成本是否在允许范围内

        Args:
            estimated_cost: 预估成本（元）

        Returns:
            True: 允许调用
            False: 成本过高，跳过
        """
        max_cost = scheduler_config.max_cost_per_call
        if estimated_cost > max_cost:
            logger.warning(
                f"单次调用成本 {estimated_cost:.4f} 元 "
                f"超过上限 {max_cost} 元"
            )
            return False
        return True

    # ------------------------------------------------------------------
    # 成本记录
    # ------------------------------------------------------------------

    def record_api_usage(
        self,
        provider: str,
        tokens: int,
        cost: float,
    ) -> bool:
        """
        记录一次 API 调用消耗

        Args:
            provider: Provider 名称
            tokens: 消耗的 token 数
            cost: 消耗的成本（元）

        Returns:
            bool: 记录是否成功
        """
        try:
            usage_dao.record_api_call(tokens=tokens, cost=cost)
            logger.info(
                f"API 使用记录: {provider}, "
                f"tokens={tokens}, cost={cost:.4f} 元"
            )
            return True
        except Exception as e:
            logger.error(f"记录 API 使用失败: {e}")
            return False

    def record_local_usage(self, tokens: int = 0) -> bool:
        """
        记录一次端侧推理消耗

        Args:
            tokens: 消耗的 token 数

        Returns:
            bool: 记录是否成功
        """
        try:
            usage_dao.record_local_inference(tokens=tokens)
            return True
        except Exception as e:
            logger.error(f"记录端侧使用失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 统计查询
    # ------------------------------------------------------------------

    def get_budget_status(self) -> Dict:
        """
        获取预算状态摘要

        Returns:
            dict: 包含以下字段
                - budget: 每日预算（元）
                - today_cost: 今日已花费（元）
                - remaining: 剩余预算（元）
                - usage_percent: 使用百分比
                - can_use_cloud: 是否可使用云端 API
                - total_local: 累计端侧推理次数
                - total_api: 累计 API 调用次数
                - total_cost: 累计总成本（元）
        """
        # 获取预算
        budget = settings_dao.get_daily_budget()
        if budget <= 0:
            budget = scheduler_config.daily_budget

        # 今日花费
        if budget > 0:
            usage = usage_dao.get_daily_budget_usage(budget)
        else:
            usage = {
                "today_cost": 0.0,
                "budget": 0.0,
                "remaining": 0.0,
                "usage_percent": 0.0,
            }

        # 累计统计
        total = usage_dao.get_total_stats()

        return {
            **usage,
            "can_use_cloud": self.can_use_cloud_api(),
            **total,
        }


# 全局单例
budget_controller = BudgetController()