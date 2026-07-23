"""
============================================================================
降级策略模块
============================================================================
当云端 API 调用失败时的降级处理策略。
============================================================================
"""

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Union

from PIL import Image

from api.config import scheduler_config

if TYPE_CHECKING:
    from engine.result_parser import InferenceResult
else:
    # 运行时使用简化的 InferenceResult（避免触发 torch 导入）
    class InferenceResult:
        def __init__(self, raw_text="", formatted_text="", confidence=0.0,
                     labels=None, inference_time=0.0, **kwargs):
            self.raw_text = raw_text
            self.formatted_text = formatted_text
            self.confidence = confidence
            self.labels = labels or []
            self.inference_time = inference_time

logger = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    """
    降级处理结果

    记录了降级链路的完整路径，方便后续分析和调试。
    """
    final_result: "InferenceResult"
    fallback_chain: List[str] = field(default_factory=list)
    total_time: float = 0.0
    all_attempts: List[dict] = field(default_factory=list)


class FallbackHandler:
    """
    降级处理器

    当云端 API 调用失败时，执行降级策略：
    1. 重新尝试端侧推理（带更详细的 prompt）
    2. 如果还是失败，返回端侧推理的最佳结果
    """

    def __init__(self):
        self._fallback_order = [
            self._try_local_with_retry_prompt,
        ]

    def handle(
        self,
        image: Image.Image,
        question: str,
        local_result: Optional["InferenceResult"] = None,
        cloud_error: str = "",
        task_type: str = "auto",
    ) -> "FallbackResult":
        """
        执行降级处理

        Args:
            image: 原始图片
            question: 用户问题
            local_result: 之前端侧推理的结果（如果有）
            cloud_error: 云端 API 的错误信息
            task_type: 任务类型

        Returns:
            FallbackResult: 降级后的最佳结果
        """
        t_start = time.time()
        chain = []
        attempts = []

        # 记录云端失败
        if cloud_error:
            chain.append(f"cloud_failed: {cloud_error}")
            attempts.append({
                "type": "cloud",
                "success": False,
                "error": cloud_error,
            })
            logger.warning(f"云端 API 失败，启动降级: {cloud_error}")

        # 如果已有端侧结果，直接使用
        if local_result is not None and local_result.confidence > 0:
            chain.append("used_local_result")
            attempts.append({
                "type": "local_original",
                "success": True,
                "confidence": local_result.confidence,
            })
            logger.info("降级: 使用已有端侧结果")
            return FallbackResult(
                final_result=local_result,
                fallback_chain=chain,
                total_time=time.time() - t_start,
                all_attempts=attempts,
            )

        # 尝试端侧重试（带更详细的 prompt）
        if scheduler_config.fallback_to_local_on_cloud_failure:
            for fallback_fn in self._fallback_order:
                try:
                    result = fallback_fn(image, question, task_type)
                    if result:
                        chain.append(fallback_fn.__name__)
                        attempts.append({
                            "type": fallback_fn.__name__,
                            "success": True,
                            "confidence": result.confidence,
                        })
                        logger.info(f"降级成功: {fallback_fn.__name__}")
                        return FallbackResult(
                            final_result=result,
                            fallback_chain=chain,
                            total_time=time.time() - t_start,
                            all_attempts=attempts,
                        )
                except Exception as e:
                    chain.append(f"{fallback_fn.__name__}_failed: {e}")
                    attempts.append({
                        "type": fallback_fn.__name__,
                        "success": False,
                        "error": str(e),
                    })
                    logger.error(f"降级失败: {fallback_fn.__name__}: {e}")

        # 所有降级策略都失败
        error_msg = "所有降级策略均失败"
        logger.error(error_msg)

        return FallbackResult(
            final_result=InferenceResult(
                raw_text=error_msg,
                formatted_text="推理失败，请稍后重试",
                confidence=0.0,
            ),
            fallback_chain=chain,
            total_time=time.time() - t_start,
            all_attempts=attempts,
        )

    # ------------------------------------------------------------------
    # 降级策略实现
    # ------------------------------------------------------------------

    def _try_local_with_retry_prompt(
        self,
        image: Image.Image,
        question: str,
        task_type: str,
    ) -> Optional["InferenceResult"]:
        """
        使用更详细的 prompt 在端侧重试

        Args:
            image: 图片
            question: 用户原始问题
            task_type: 任务类型

        Returns:
            Optional[InferenceResult]: 推理结果
        """
        retry_prompt = scheduler_config.fallback_retry_prompt

        # 如果用户有具体问题，附加到重试 prompt 后面
        if question and question not in ("", "请详细描述这张图片的内容。"):
            retry_prompt = f"{retry_prompt}\n\n用户的具体问题是: {question}"

        logger.info(f"降级重试: 使用详细 prompt 在端侧推理")

        try:
            from engine.inference_engine import inference_engine
            result = inference_engine.inference(
                image_source=image,
                question=retry_prompt,
                task_type=task_type,
                force_reload=True,
            )
            return result
        except Exception as e:
            logger.error(f"端侧重试失败: {e}")
            return None


# 全局单例
fallback_handler = FallbackHandler()