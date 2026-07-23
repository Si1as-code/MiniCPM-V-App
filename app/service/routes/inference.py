import base64
import io
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from PIL import Image

from service.auth.jwt import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inference", tags=["推理"])


# ------------------------------------------------------------------
# 请求/响应模型
# ------------------------------------------------------------------

class SyncInferenceRequest(BaseModel):
    image_base64: str
    question: str
    task_type: str = "auto"
    force_local: bool = False
    force_cloud: bool = False
    cloud_provider: Optional[str] = None


class SyncInferenceResponse(BaseModel):
    success: bool
    source: str = ""
    formatted_text: str = ""
    confidence: float = 0.0
    inference_time: float = 0.0
    decision_path: list = []
    cost: float = 0.0
    error: str = ""


class AsyncInferenceRequest(BaseModel):
    image_base64: str
    question: str
    task_type: str = "auto"
    provider: str = "qwen"


class AsyncInferenceResponse(BaseModel):
    success: bool
    task_id: int = 0
    status: str = ""
    error: str = ""


# ------------------------------------------------------------------
# 同步推理端点
# ------------------------------------------------------------------

@router.post("/sync", response_model=SyncInferenceResponse)
async def inference_sync(
    request: SyncInferenceRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    同步推理：请求直接发送到端侧引擎，等待推理完成返回结果
    """
    t_start = time.time()
    try:
        # 1. 解码 base64 图片
        image_data = base64.b64decode(request.image_base64)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        # 2. 调用调度引擎
        from api.router import scheduler_router

        decision = scheduler_router.schedule(
            image=image,
            question=request.question,
            task_type=request.task_type,
            force_local=request.force_local,
            force_cloud=request.force_cloud,
            cloud_provider=request.cloud_provider,
        )

        return SyncInferenceResponse(
            success=True,
            source=decision.source,
            formatted_text=decision.final_result.formatted_text,
            confidence=decision.local_confidence,
            inference_time=time.time() - t_start,
            decision_path=decision.decision_path,
            cost=decision.cost,
        )

    except Exception as e:
        logger.error(f"同步推理失败: {e}", exc_info=True)
        return SyncInferenceResponse(
            success=False,
            error=str(e),
            inference_time=time.time() - t_start,
        )


# ------------------------------------------------------------------
# 异步推理端点
# ------------------------------------------------------------------

@router.post("/async", response_model=AsyncInferenceResponse)
async def inference_async(
    request: AsyncInferenceRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    异步推理：将任务写入队列，后台处理
    """
    try:
        from api.router import scheduler_router

        task_id = scheduler_router.schedule_async(
            image_source=request.image_base64,
            question=request.question,
            task_type=request.task_type,
            provider=request.provider,
        )

        return AsyncInferenceResponse(
            success=True,
            task_id=task_id,
            status="pending",
        )

    except Exception as e:
        logger.error(f"异步推理创建失败: {e}")
        return AsyncInferenceResponse(
            success=False,
            error=str(e),
        )