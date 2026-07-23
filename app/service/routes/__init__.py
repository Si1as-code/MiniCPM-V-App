"""
API 路由模块
提供推理、任务管理、统计等 HTTP API 端点。
"""

from service.routes.inference import router as inference_router
from service.routes.tasks import router as tasks_router
from service.routes.stats import router as stats_router

__all__ = [
    "inference_router",
    "tasks_router",
    "stats_router",
]