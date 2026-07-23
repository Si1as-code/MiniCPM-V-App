"""
============================================================================
MiniCPM-V 端侧推理引擎
============================================================================
这是一个独立的、可测试的推理引擎模块。

核心类:
  - InferenceEngine: 推理编排（对外接口）
  - ModelLoader:    模型加载与管理
  - ResultParser:   结果解析
  - InferenceResult: 结构化结果数据类

辅助工具:
  - load_image:     统一图片加载
  - compute_image_hash: 图片哈希缓存

使用方式:
    from engine import InferenceEngine, ModelLoader, config

    loader = ModelLoader()
    loader.load()
    engine = InferenceEngine()
    result = engine.inference("image.jpg", "描述这张图片")
    print(result.formatted_text)
============================================================================
"""

from engine.inference_engine import InferenceEngine, inference_engine
from engine.model_loader import ModelLoader, model_loader
from engine.result_parser import (
    ResultParser,
    result_parser,
    InferenceResult,
)
from engine.image_processor import (
    load_image,
    compute_image_hash,
    validate_image,
)
from config import AppConfig, config

__all__ = [
    # 引擎
    "InferenceEngine",
    "inference_engine",
    # 模型
    "ModelLoader",
    "model_loader",
    # 结果
    "ResultParser",
    "result_parser",
    "InferenceResult",
    # 图像
    "load_image",
    "compute_image_hash",
    "validate_image",
    # 配置
    "AppConfig",
    "config",
]

__version__ = "0.1.0"