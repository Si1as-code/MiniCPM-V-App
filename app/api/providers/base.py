"""
============================================================================
云端 Provider 基类
============================================================================
定义所有云端 API Provider 的统一接口和返回数据结构。
============================================================================
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from PIL import Image

from api.config import ProviderConfig

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """
    Provider 调用结果 - 统一返回格式

    无论哪个 Provider，最终都返回这个格式，
    方便 router 统一处理。
    """
    success: bool = False
    text: str = ""
    error: str = ""
    provider_name: str = ""
    model_name: str = ""
    tokens_used: int = 0
    cost: float = 0.0
    inference_time: float = 0.0
    raw_response: Any = None


class BaseProvider(ABC):
    """
    云端 Provider 基类

    所有具体的 Provider（Qwen、Doubao、OpenAI）都需要继承这个类。
    """

    def __init__(self, config: ProviderConfig):
        """
        Args:
            config: Provider 配置
        """
        self.config = config
        self._api_key: Optional[str] = None

    # ------------------------------------------------------------------
    # 抽象方法（子类必须实现）
    # ------------------------------------------------------------------

    @abstractmethod
    def _call_api(
        self,
        base64_image: str,
        question: str,
    ) -> ProviderResult:
        """
        调用云端 API 的具体实现

        Args:
            base64_image: 图片的 base64 编码
            question: 用户问题

        Returns:
            ProviderResult: 调用结果
        """
        ...

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def inference(
        self,
        image: Image.Image,
        question: str,
    ) -> ProviderResult:
        """
        对外统一的推理接口

        Args:
            image: PIL Image 对象
            question: 用户问题

        Returns:
            ProviderResult: 推理结果
        """
        t_start = time.time()

        # 1) 检查 API Key
        api_key = self._get_api_key()
        if not api_key:
            return ProviderResult(
                success=False,
                error=f"{self.config.display_name} API Key 未配置。"
                       f"请设置环境变量 {self.config.api_key_env}",
                provider_name=self.config.name,
                model_name=self.config.model_name,
            )

        # 2) 检查 Provider 是否启用
        if not self.config.enabled:
            return ProviderResult(
                success=False,
                error=f"{self.config.display_name} 未启用",
                provider_name=self.config.name,
                model_name=self.config.model_name,
            )

        # 3) 将图片转为 base64
        try:
            base64_image = self._image_to_base64(image)
        except Exception as e:
            return ProviderResult(
                success=False,
                error=f"图片编码失败: {e}",
                provider_name=self.config.name,
                model_name=self.config.model_name,
            )

        # 4) 调用 API
        result = self._call_api(base64_image, question)
        result.provider_name = self.config.name
        result.model_name = self.config.model_name
        result.inference_time = time.time() - t_start

        if result.success:
            logger.info(
                f"{self.config.display_name} 调用成功: "
                f"耗时 {result.inference_time:.1f}s, "
                f"tokens={result.tokens_used}, "
                f"成本={result.cost:.4f}元"
            )
        else:
            logger.warning(
                f"{self.config.display_name} 调用失败: {result.error}"
            )

        return result

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _get_api_key(self) -> Optional[str]:
        """获取 API Key（优先从环境变量读取）"""
        if self._api_key:
            return self._api_key
        self._api_key = os.getenv(self.config.api_key_env)
        return self._api_key

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        将 PIL Image 转为 base64 编码

        Args:
            image: PIL Image 对象

        Returns:
            str: base64 编码的图片字符串
        """
        import base64
        import io

        # 限制图片大小（最大 2048px，保持宽高比）
        max_size = 2048
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        # 转为 JPEG base64
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    @property
    def name(self) -> str:
        """Provider 名称"""
        return self.config.name

    @property
    def is_available(self) -> bool:
        """
        Provider 是否可用
        （检查 API Key 是否存在且已启用）
        """
        return bool(self._get_api_key()) and self.config.enabled