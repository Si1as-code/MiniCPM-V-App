"""
============================================================================
通义千问 VL API 适配器
============================================================================
使用 DashScope SDK 调用通义千问 VL 系列模型（qwen-vl-plus, qwen-vl-max）。
============================================================================
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from api.config import DEFAULT_PROVIDERS
from api.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class QwenProvider(BaseProvider):
    """
    通义千问 VL Provider

    使用 DashScope 官方的 HTTP API（兼容 OpenAI 格式）。
    需要设置环境变量 QWEN_API_KEY。

    API 文档: https://help.aliyun.com/zh/dashscope/
    """

    def __init__(self):
        config = DEFAULT_PROVIDERS.get("qwen")
        if config is None:
            raise ValueError("Qwen Provider 配置未找到")
        super().__init__(config)

    def _call_api(
        self,
        base64_image: str,
        question: str,
    ) -> ProviderResult:
        """
        调用通义千问 VL API

        Args:
            base64_image: 图片 base64 编码
            question: 用户问题

        Returns:
            ProviderResult: 调用结果
        """
        import httpx

        api_key = self._get_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": question,
                        },
                    ],
                }
            ],
            "max_tokens": 512,
            "temperature": 0.7,
        }

        try:
            t_start = time.time()
            with httpx.Client(timeout=self.config.timeout) as client:
                response = client.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                elapsed = time.time() - t_start

            # 检查响应
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get(
                        "message", response.text
                    )
                except Exception:
                    pass
                return ProviderResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {error_detail}",
                    inference_time=elapsed,
                )

            result = response.json()

            # 提取文本
            text = ""
            tokens_used = 0
            choices = result.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                text = message.get("content", "")

            # 提取 token 用量
            usage = result.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            # 计算成本
            cost = (tokens_used / 1000) * self.config.cost_per_1k_tokens

            return ProviderResult(
                success=True,
                text=text.strip(),
                tokens_used=tokens_used,
                cost=cost,
                inference_time=elapsed,
                raw_response=result,
            )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                error=f"请求超时（{self.config.timeout}s）",
            )
        except httpx.RequestError as e:
            return ProviderResult(
                success=False,
                error=f"网络请求失败: {e}",
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                error=f"未知错误: {e}",
            )