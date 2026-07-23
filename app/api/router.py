"""
============================================================================
API 路由引擎 - 核心调度逻辑
============================================================================
这是 Sprint 3 的核心模块，负责端云协同的智能路由决策。

路由决策流程:
  1. 检查任务类型 → 是否需要强制端侧或强制云端
  2. 检查预算 → 是否可用云端 API
  3. 先尝试端侧推理 → 获取置信度
  4. 如果置信度达标 → 返回端侧结果
  5. 如果置信度不足 → 尝试云端 API（按优先级排序）
  6. 如果云端失败 → 降级策略（重新端侧 or 返回已有结果）
============================================================================
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING, Union

from PIL import Image

from api.config import scheduler_config
from api.budget import budget_controller
from api.providers.base import BaseProvider, ProviderResult
from api.providers.qwen import QwenProvider
from api.providers.doubao import DoubaoProvider
from api.fallback import fallback_handler, FallbackResult
from data.dao_api_tasks import api_task_dao
from data.models import APITask

if TYPE_CHECKING:
    from engine.result_parser import InferenceResult
else:
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
class RouteDecision:
    """
    路由决策结果

    记录了完整的路由链路，包括：
      - 最终结果
      - 决策链路（端侧→云端→降级）
      - 每次尝试的详细信息
      - 决策原因
    """
    final_result: InferenceResult
    source: str = "local"  # local / cloud / fallback
    local_confidence: float = 0.0
    decision_path: List[str] = field(default_factory=list)
    attempts: List[dict] = field(default_factory=list)
    total_time: float = 0.0
    cloud_results: List[ProviderResult] = field(default_factory=list)
    cost: float = 0.0


class SchedulerRouter:
    """
    API 调度器 - 单例模式

    核心职责:
      1. 智能路由: 根据置信度、任务类型、预算决定端侧还是云端
      2. 云端 Provider 管理: 按优先级调度多个 Provider
      3. 成本控制: 与 budget_controller 联动
      4. 任务队列: 云端异步任务写入 api_tasks 表
    """

    _instance: Optional["SchedulerRouter"] = None

    def __new__(cls) -> "SchedulerRouter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._providers_initialized = False

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def schedule(
        self,
        image: Image.Image,
        question: str,
        task_type: str = "auto",
        force_local: bool = False,
        force_cloud: bool = False,
        cloud_provider: Optional[str] = None,
    ) -> RouteDecision:
        """
        执行一次完整的调度决策

        Args:
            image: PIL Image 对象
            question: 用户问题
            task_type: 任务类型
            force_local: 强制端侧推理
            force_cloud: 强制云端推理
            cloud_provider: 指定云端 Provider

        Returns:
            RouteDecision: 路由决策结果
        """
        t_start = time.time()
        decision_path = []
        attempts = []

        # 1) 任务类型路由
        routed = self._route_by_task_type(task_type, force_local, force_cloud)
        if routed == "local":
            return self._run_local_only(image, question, task_type, t_start)

        # 2) 检查预算
        if not budget_controller.can_use_cloud_api():
            logger.info("路由: 预算不足，使用端侧推理")
            decision_path.append("budget_exhausted_use_local")
            return self._run_local_only(image, question, task_type, t_start)

        # 3) 尝试端侧推理
        result = RouteDecision(
            final_result=InferenceResult(),
            source="local",
            decision_path=decision_path,
            attempts=attempts,
        )

        if not routed == "cloud":
            logger.info("路由: 先尝试端侧推理")
            local_result = self._try_local_inference(
                image, question, task_type
            )
            result.local_confidence = local_result.confidence
            attempts.append({
                "type": "local",
                "success": True,
                "confidence": local_result.confidence,
            })
            decision_path.append(
                f"local_first: confidence={local_result.confidence:.2f}"
            )

            # 如果置信度达标，直接返回
            if local_result.confidence >= scheduler_config.cloud_confidence_threshold:
                logger.info(
                    f"路由: 端侧置信度 {local_result.confidence:.2f} "
                    f"达标 >= {scheduler_config.cloud_confidence_threshold}"
                )
                result.final_result = local_result
                result.source = "local"
                result.total_time = time.time() - t_start
                budget_controller.record_local_usage()
                return result

            decision_path.append(
                f"confidence_below_threshold: "
                f"{local_result.confidence:.2f} < "
                f"{scheduler_config.cloud_confidence_threshold}"
            )
            logger.info(
                f"路由: 端侧置信度 {local_result.confidence:.2f} 不足，"
                f"尝试云端 API"
            )

        # 4) 尝试云端 API
        cloud_results = self._try_cloud_providers(
            image, question, cloud_provider
        )
        result.cloud_results = cloud_results

        # 检查是否有成功的云端结果
        successful_cloud = [r for r in cloud_results if r.success]
        cloud_cost = sum(r.cost for r in cloud_results)
        result.cost = cloud_cost

        if successful_cloud:
            best_cloud = successful_cloud[0]  # 取第一个成功的
            cloud_result = self._cloud_to_inference_result(best_cloud)
            result.final_result = cloud_result
            result.source = "cloud"
            decision_path.append(
                f"cloud_success: {best_cloud.provider_name}, "
                f"cost={best_cloud.cost:.4f}元"
            )
            attempts.append({
                "type": "cloud",
                "provider": best_cloud.provider_name,
                "success": True,
                "cost": best_cloud.cost,
            })

            # 记录成本
            budget_controller.record_api_usage(
                best_cloud.provider_name,
                best_cloud.tokens_used,
                best_cloud.cost,
            )

            # 记录云端任务
            self._record_api_task(best_cloud, task_type)

            result.total_time = time.time() - t_start
            return result

        # 5) 云端全部失败 → 降级
        cloud_error = cloud_results[0].error if cloud_results else "所有 Provider 失败"
        decision_path.append(f"cloud_all_failed: {cloud_error}")
        logger.warning(f"路由: 所有云端 Provider 失败，启动降级")

        fallback = fallback_handler.handle(
            image=image,
            question=question,
            local_result=result.final_result if result.final_result.raw_text else None,
            cloud_error=cloud_error,
            task_type=task_type,
        )

        result.final_result = fallback.final_result
        result.source = "fallback"
        result.decision_path = decision_path
        result.attempts = attempts
        result.total_time = time.time() - t_start
        return result

    def schedule_async(
        self,
        image_source: Union[str, Image.Image],
        question: str,
        task_type: str = "auto",
        provider: str = "qwen",
    ) -> int:
        """
        异步调度：将任务写入 api_tasks 队列，后台处理

        Args:
            image_source: 图片来源
            question: 用户问题
            task_type: 任务类型
            provider: 目标 Provider

        Returns:
            int: 任务 ID（api_tasks 表）
        """
        # 创建任务记录
        import time as t
        task = APITask(
            provider=provider,
            status="pending",
            scheduled_at=t.time(),
        )
        task_id = api_task_dao.insert(task)
        logger.info(
            f"异步任务已创建: id={task_id}, provider={provider}"
        )
        return task_id

    def get_decision_history(self) -> List[dict]:
        """获取路由决策统计（TODO: 将来实现持久化）"""
        # 当前只返回空列表，后续 Sprint 可以扩展
        return []

    # ------------------------------------------------------------------
    # 内部路由方法
    # ------------------------------------------------------------------

    def _route_by_task_type(
        self,
        task_type: str,
        force_local: bool,
        force_cloud: bool,
    ) -> str:
        """
        根据任务类型和强制标志决定路由策略

        Returns:
            "local" / "cloud" / "hybrid"
        """
        if force_local:
            logger.info("路由: 强制端侧推理")
            return "local"

        if force_cloud:
            logger.info("路由: 强制云端推理")
            return "cloud"

        if task_type in scheduler_config.local_forced_task_types:
            logger.info(f"路由: 任务类型 {task_type} 强制端侧")
            return "local"

        if task_type in scheduler_config.cloud_preferred_task_types:
            logger.info(f"路由: 任务类型 {task_type} 优先云端")
            return "cloud"

        return "hybrid"  # 先端侧，置信度不足再云端

    # ------------------------------------------------------------------
    # 内部执行方法
    # ------------------------------------------------------------------

    def _run_local_only(
        self,
        image: Image.Image,
        question: str,
        task_type: str,
        t_start: float,
    ) -> RouteDecision:
        """仅执行端侧推理"""
        result = self._try_local_inference(image, question, task_type)
        budget_controller.record_local_usage()

        return RouteDecision(
            final_result=result,
            source="local",
            local_confidence=result.confidence,
            decision_path=["local_only"],
            attempts=[{
                "type": "local",
                "success": True,
                "confidence": result.confidence,
            }],
            total_time=time.time() - t_start,
        )

    def _try_local_inference(
        self,
        image: Image.Image,
        question: str,
        task_type: str,
    ) -> InferenceResult:
        """执行端侧推理"""
        logger.info("执行端侧推理...")
        from engine.inference_engine import inference_engine
        return inference_engine.inference(
            image_source=image,
            question=question,
            task_type=task_type,
        )

    def _try_cloud_providers(
        self,
        image: Image.Image,
        question: str,
        preferred_provider: Optional[str] = None,
    ) -> List[ProviderResult]:
        """
        按优先级依次尝试云端 Provider

        Args:
            image: 图片
            question: 问题
            preferred_provider: 首选 Provider

        Returns:
            List[ProviderResult]: 所有 Provider 的尝试结果
        """
        results = []
        providers = self._get_available_providers(preferred_provider)

        if not providers:
            logger.warning("没有可用的云端 Provider")
            return results

        for provider in providers:
            logger.info(f"尝试云端 Provider: {provider.name}")
            result = provider.inference(image, question)
            results.append(result)

            if result.success:
                logger.info(f"Provider {provider.name} 成功")
                break  # 成功后不再尝试后续 Provider

        return results

    # ------------------------------------------------------------------
    # Provider 管理
    # ------------------------------------------------------------------

    def _init_providers(self):
        """初始化所有 Provider"""
        if self._providers_initialized:
            return

        try:
            self._providers["qwen"] = QwenProvider()
            logger.debug("Qwen Provider 已初始化")
        except Exception as e:
            logger.warning(f"Qwen Provider 初始化失败: {e}")

        try:
            self._providers["doubao"] = DoubaoProvider()
            logger.debug("Doubao Provider 已初始化")
        except Exception as e:
            logger.warning(f"Doubao Provider 初始化失败: {e}")

        self._providers_initialized = True

    def _get_available_providers(
        self,
        preferred: Optional[str] = None,
    ) -> List[BaseProvider]:
        """
        获取可用的 Provider 列表（按优先级排序）

        Args:
            preferred: 首选 Provider 名称

        Returns:
            List[BaseProvider]: 可用 Provider 列表
        """
        self._init_providers()

        # 确定优先级顺序
        priority = scheduler_config.provider_priority.copy()
        if preferred and preferred in priority:
            priority.remove(preferred)
            priority.insert(0, preferred)

        available = []
        for name in priority:
            provider = self._providers.get(name)
            if provider and provider.is_available:
                available.append(provider)

        return available

    def get_provider(self, name: str) -> Optional[BaseProvider]:
        """获取指定名称的 Provider"""
        self._init_providers()
        return self._providers.get(name)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _cloud_to_inference_result(
        self, cloud_result: ProviderResult
    ) -> "InferenceResult":
        """
        将云端 Provider 结果转为标准 InferenceResult

        Args:
            cloud_result: Provider 调用结果

        Returns:
            InferenceResult: 标准推理结果
        """
        from engine.result_parser import result_parser

        return result_parser.parse(
            raw_text=cloud_result.text,
            model_name=cloud_result.model_name,
            model_source="cloud",
            image_hash="",
            image_size=(0, 0),
            task_type="auto",
            user_question="",
        )

    def _record_api_task(self, result: ProviderResult, task_type: str):
        """记录云端 API 调用到任务表"""
        try:
            task = APITask(
                provider=result.provider_name,
                status="completed",
                last_error="",
            )
            api_task_dao.insert(task)
        except Exception as e:
            logger.error(f"记录 API 任务失败: {e}")


# 全局单例
scheduler_router = SchedulerRouter()