import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from service.auth.jwt import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stats", tags=["统计"])


class StatsResponse(BaseModel):
    success: bool
    total_records: int = 0
    total_conversations: int = 0
    total_api_calls: int = 0
    total_local_inferences: int = 0
    total_tokens_used: int = 0
    total_cost: float = 0.0
    error: str = ""


class DailyStatsResponse(BaseModel):
    success: bool
    stats: list = []
    error: str = ""


@router.get("", response_model=StatsResponse)
async def get_stats(
    user_id: str = Depends(get_current_user_id),
):
    """获取汇总统计"""
    try:
        from data.dao_recognition import recognition_dao
        from data.dao_conversation import conversation_dao
        from data.dao_usage import usage_dao

        total = usage_dao.get_total_stats()
        records = recognition_dao.count()
        conversations = conversation_dao.count()

        return StatsResponse(
            success=True,
            total_records=records,
            total_conversations=conversations,
            total_api_calls=total.get("api_count", 0),
            total_local_inferences=total.get("local_count", 0),
            total_tokens_used=total.get("tokens_used", 0),
            total_cost=total.get("cost", 0.0),
        )
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return StatsResponse(success=False, error=str(e))


@router.get("/daily", response_model=DailyStatsResponse)
async def get_daily_stats(
    days: int = Query(7, ge=1, le=365, description="最近天数"),
    user_id: str = Depends(get_current_user_id),
):
    """获取每日统计数据"""
    try:
        from data.dao_usage import usage_dao

        stats = usage_dao.get_last_n_days(days)
        return DailyStatsResponse(
            success=True,
            stats=[
                {
                    "date": s.date,
                    "local_count": s.local_count,
                    "api_count": s.api_count,
                    "tokens_used": s.tokens_used,
                    "cost": s.cost,
                }
                for s in stats
            ],
        )
    except Exception as e:
        logger.error(f"获取每日统计失败: {e}")
        return DailyStatsResponse(success=False, error=str(e))