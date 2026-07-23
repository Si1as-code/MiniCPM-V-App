"""
============================================================================
MiniCPM-V 端侧推理引擎 - 全局配置
============================================================================
技术栈: Python 3.10+, PyTorch 2.x, Transformers, Hugging Face Hub
运行环境: 本地 GPU / AutoDL GPU / CPU (仅测试用)
============================================================================
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal


@dataclass
class AppConfig:
    """App 全局配置，可通过环境变量或代码修改覆盖"""

    # --- 模型配置 ---
    # 模型名称（Hugging Face Hub 或本地路径）
    # ModelScope 格式: "openbmb/MiniCPM-V-2_6"
    # 本地路径格式: "/root/autodl-tmp/models/MiniCPM-V-2_6"
    model_name: str = field(
        default_factory=lambda: os.getenv(
            "MODEL_NAME", "openbmb/MiniCPM-V-4.6"
        )
    )

    # 模型下载源: "auto" / "huggingface" / "modelscope" / "local"
    # - auto: 先尝试本地路径，再尝试 modelscope，最后尝试 huggingface
    # - modelscope: 使用 ModelScope（国内免登录，推荐 AutoDL 使用）
    # - huggingface: 使用 Hugging Face（需要登录 + 同意协议）
    # - local: 仅使用本地路径（不下载）
    model_source: str = field(
        default_factory=lambda: os.getenv("MODEL_SOURCE", "auto")
    )

    # 模型缓存目录（AutoDL 上建议使用 /root/autodl-tmp/）
    model_cache_dir: str = field(
        default_factory=lambda: os.getenv(
            "HF_HOME", os.path.expanduser("~/.cache/huggingface")
        )
    )

    # Hugging Face 镜像（国内 AutoDL 环境必须设置，否则无法下载模型）
    # 可选值: "https://hf-mirror.com" (推荐) / None (直连 huggingface.co)
    hf_endpoint: Optional[str] = field(
        default_factory=lambda: os.getenv(
            "HF_ENDPOINT", "https://hf-mirror.com"
        )
    )

    # --- 推理配置 ---
    # 设备: "cuda" / "cpu" / "auto"
    device: str = field(
        default_factory=lambda: os.getenv("DEVICE", "auto")
    )

    # 数据类型: "auto" / "float16" / "bfloat16" / "float32"
    torch_dtype: str = "auto"

    # 图像降采样模式: "4x" (精细) 或 "16x" (快速)
    downsample_mode: str = "16x"

    # 最大图像切片数（降低可减少显存占用）
    max_slice_nums: int = 9

    # 最大生成 token 数
    max_new_tokens: int = 512

    # 温度（越低越确定，越高越随机）
    temperature: float = 0.7

    # --- 推理引擎配置 ---
    # 结果缓存开关（相同图片 hash 直接返回缓存结果）
    enable_cache: bool = True

    # 缓存大小上限
    max_cache_size: int = 1000

    # 推理超时（秒）
    inference_timeout: int = 30

    # --- 置信度阈值 ---
    # 低于此阈值可能触发云端升级
    confidence_threshold: float = 0.6

    # --- 日志配置 ---
    log_level: str = "INFO"

    def __post_init__(self):
        """初始化后处理"""
        # 确保缓存目录存在
        os.makedirs(self.model_cache_dir, exist_ok=True)

        # 设置 Hugging Face 镜像（必须在 import torch 之前设置环境变量）
        if self.hf_endpoint:
            os.environ["HF_ENDPOINT"] = self.hf_endpoint

        # 自动检测设备
        if self.device == "auto":
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"


# 全局单例配置
config = AppConfig()