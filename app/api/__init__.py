"""
============================================================================
API 调度引擎模块
============================================================================
提供端云协同的智能路由调度。

用法:
    from api import scheduler_router, budget_controller
    from api import SchedulerRouter, RouteDecision

    # 路由调度
    decision = scheduler_router.schedule(
        image=image,
        question="这是什么？",
        task_type="describe",
    )
    print(decision.final_result.formatted_text)
    print(f"决策来源: {decision.source}")  # local / cloud / fallback
============================================================================
"""

from api.config import SchedulerConfig, scheduler_config, ProviderConfig
from api.budget import BudgetController, budget_controller
from api.router import SchedulerRouter, RouteDecision, scheduler_router
from api.fallback import FallbackHandler, FallbackResult, fallback_handler
from api.providers.base import BaseProvider, ProviderResult
from api.providers.qwen import QwenProvider
from api.providers.doubao import DoubaoProvider

__all__ = [
    # 配置
    "SchedulerConfig",
    "scheduler_config",
    "ProviderConfig",
    # 预算控制
    "BudgetController",
    "budget_controller",
    # 路由引擎
    "SchedulerRouter",
    "RouteDecision",
    "scheduler_router",
    # 降级策略
    "FallbackHandler",
    "FallbackResult",
    "fallback_handler",
    # Provider
    "BaseProvider",
    "ProviderResult",
    "QwenProvider",
    "DoubaoProvider",
]