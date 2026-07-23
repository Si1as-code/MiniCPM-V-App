import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from service.auth.jwt import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["任务管理"])


class TaskResponse(BaseModel):
    id: int
    record_id: Optional[int] = None
    provider: str = ""
    status: str = ""
    retry_count: int = 0
    last_error: str = ""
    scheduled_at: Optional[float] = None
    completed_at: Optional[float] = None
    created_at: Optional[float] = None


class TaskListResponse(BaseModel):
    success: bool
    total: int = 0
    tasks: list = []


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    """查询任务列表"""
    try:
        from data.dao_api_tasks import api_task_dao

        if status:
            tasks = api_task_dao.get_by_status(status, limit)
        else:
            tasks = api_task_dao.get_all(limit=limit, offset=offset)

        return TaskListResponse(
            success=True,
            total=len(tasks),
            tasks=[
                TaskResponse(
                    id=t.id,
                    record_id=t.record_id,
                    provider=t.provider,
                    status=t.status,
                    retry_count=t.retry_count,
                    last_error=t.last_error,
                    scheduled_at=t.scheduled_at,
                    completed_at=t.completed_at,
                    created_at=t.created_at,
                )
                for t in tasks
            ],
        )
    except Exception as e:
        logger.error(f"查询任务列表失败: {e}")
        return TaskListResponse(success=False, total=0, tasks=[])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
):
    """查询单个任务详情"""
    try:
        from data.dao_api_tasks import api_task_dao

        task = api_task_dao.get_by_id(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")

        return TaskResponse(
            id=task.id,
            record_id=task.record_id,
            provider=task.provider,
            status=task.status,
            retry_count=task.retry_count,
            last_error=task.last_error,
            scheduled_at=task.scheduled_at,
            completed_at=task.completed_at,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def cancel_task(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
):
    """取消任务"""
    try:
        from data.dao_api_tasks import api_task_dao

        task = api_task_dao.get_by_id(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")

        api_task_dao.cancel_task(task_id)
        return {"success": True, "message": f"任务 {task_id} 已取消"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))