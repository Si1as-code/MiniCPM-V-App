"""
============================================================================
API 调度引擎 - 配置
============================================================================
定义调度策略的阈值、成本、Provider 列表等配置参数。
============================================================================
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProviderConfig:
    """单个云端 Provider 的配置"""
    name: str                    # 唯一标识: "qwen" / "doubao" / "openai"
    display_name: str            # 显示名称
    api_key_env: str             # 环境变量名，如 "QWEN_API_KEY"
    api_base: str                # API 地址
    model_name: str              # 使用的模型名
    cost_per_1k_tokens: float    # 每千 token 成本（元）
    enabled: bool = True         # 是否启用
    max_retries: int = 3         # 最大重试次数
    timeout: int = 30            # 超时秒数
    supports_image: bool = True  # 是否支持图片输入
    supports_stream: bool = False  # 是否支持流式输出


@dataclass
class SchedulerConfig:
    """调度引擎全局配置"""

    # --- 置信度阈值 ---
    # 端侧推理置信度低于此值时，尝试云端 API 升级
    cloud_confidence_threshold: float = field(
        default_factory=lambda: float(
            os.getenv("CLOUD_CONFIDENCE_THRESHOLD", "0.6")
        )
    )

    # 强制端侧推理（禁用云端 API 升级）
    force_local: bool = field(
        default_factory=lambda: os.getenv("FORCE_LOCAL", "false").lower() == "true"
    )

    # --- 任务类型路由 ---
    # 哪些任务类型优先尝试云端（列表非空则跳过端侧，直接走云端）
    cloud_preferred_task_types: List[str] = field(
        default_factory=lambda: ["qa_complex", "ocr_high_accuracy"]
    )

    # 哪些任务类型强制端侧（不尝试云端）
    local_forced_task_types: List[str] = field(
        default_factory=lambda: ["classify", "describe"]
    )

    # --- 预算控制 ---
    # 每日预算上限（元），0 表示不限制
    daily_budget: float = field(
        default_factory=lambda: float(os.getenv("DAILY_BUDGET", "0.0"))
    )

    # 单次 API 调用最大成本（元）
    max_cost_per_call: float = 0.05

    # 预算用尽时自动降级到端侧
    auto_downgrade_on_budget_exhausted: bool = True

    # --- Provider 优先级 ---
    # 按优先级排序的 Provider 名称列表
    provider_priority: List[str] = field(
        default_factory=lambda: ["qwen", "doubao"]
    )

    # --- 降级策略 ---
    # 云端失败后是否重试端侧
    fallback_to_local_on_cloud_failure: bool = True

    # 端侧重试时使用更详细的 prompt
    fallback_retry_prompt: str = (
        "请非常仔细地观察这张图片，描述你看到的所有内容，"
        "包括物体、颜色、位置、文字、人物动作等。不要遗漏任何细节。"
    )

    # --- 统计与日志 ---
    # 是否记录路由决策日志
    log_route_decisions: bool = True


# 预定义的 Provider 配置
DEFAULT_PROVIDERS: Dict[str, ProviderConfig] = {
    "qwen": ProviderConfig(
        name="qwen",
        display_name="通义千问 VL",
        api_key_env="QWEN_API_KEY",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-vl-plus",
        cost_per_1k_tokens=0.003,  # Qwen-VL-Plus: 0.003元/千token
        enabled=False,
        max_retries=3,
        timeout=30,
        supports_image=True,
        supports_stream=False,
    ),
    "doubao": ProviderConfig(
        name="doubao",
        display_name="豆包视觉",
        api_key_env="DOUBAO_API_KEY",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        model_name="doubao-vision-pro-32k",
        cost_per_1k_tokens=0.002,  # 豆包视觉: 0.002元/千token
        enabled=False,
        max_retries=2,
        timeout=45,
        supports_image=True,
        supports_stream=True,
    ),
}


# 全局调度配置
scheduler_config = SchedulerConfig()