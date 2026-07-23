"""
============================================================================
模型加载器 - 负责模型加载、卸载、预热、状态管理
============================================================================
技术栈: PyTorch, Transformers (AutoModelForImageTextToText, AutoProcessor)
关键点:
  - MiniCPM-V 4.6 使用标准 Transformers API，无需 trust_remote_code
  - 支持 device_map="auto" 自动多 GPU 分配
  - 支持模型预热（warm-up）减少首次推理延迟
  - 线程安全的单例模式
============================================================================
"""

import logging
import threading
import time
from typing import Optional, Tuple

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

from config import config

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    模型加载器 - 单例模式

    负责 MiniCPM-V 模型的加载、卸载和状态管理。
    使用单例确保全局只有一个模型实例，避免重复加载浪费显存。
    """

    _instance: Optional["ModelLoader"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ModelLoader":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.model = None
        self.processor = None
        self._is_loaded = False
        self._model_load_time: float = 0.0
        self._inference_count: int = 0

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._is_loaded and self.model is not None

    @property
    def model_info(self) -> dict:
        """返回模型元信息"""
        if not self.is_loaded:
            return {"status": "not_loaded"}
        return {
            "status": "loaded",
            "model_name": config.model_name,
            "device": config.device,
            "load_time_seconds": round(self._model_load_time, 2),
            "inference_count": self._inference_count,
            "gpu_memory_mb": self._get_gpu_memory(),
        }

    def load(self, force_reload: bool = False) -> bool:
        """
        加载模型到内存

        Args:
            force_reload: 是否强制重新加载

        Returns:
            bool: 加载是否成功
        """
        if self.is_loaded and not force_reload:
            logger.info("模型已加载，跳过")
            return True

        logger.info(f"正在加载模型: {config.model_name}")
        logger.info(f"目标设备: {config.device}")
        logger.info(f"缓存目录: {config.model_cache_dir}")
        if config.hf_endpoint:
            logger.info(f"HF 镜像: {config.hf_endpoint}")

        t_start = time.time()

        # 解析实际模型路径（可能通过 ModelScope 或本地路径解析）
        model_path = self._resolve_model_path()
        logger.info(f"实际加载路径: {model_path}")

        try:
            # 1) 加载 Processor
            logger.info("  加载 Processor...")
            self.processor = AutoProcessor.from_pretrained(
                model_path,
                cache_dir=config.model_cache_dir,
            )

            # 2) 加载模型
            logger.info("  加载模型权重...")
            load_kwargs = {
                "cache_dir": config.model_cache_dir,
            }

            # 根据设备配置选择加载策略
            if config.device == "cpu":
                load_kwargs["torch_dtype"] = torch.float32
            elif config.device == "cuda":
                # 4.6 支持 torch_dtype="auto"
                load_kwargs["torch_dtype"] = "auto"
                load_kwargs["device_map"] = "auto"

            self.model = AutoModelForImageTextToText.from_pretrained(
                model_path,
                **load_kwargs,
            )

            self._model_load_time = time.time() - t_start
            self._is_loaded = True

            logger.info(
                f"模型加载完成! 耗时: {self._model_load_time:.1f}s"
            )
            gpu_mem = self._get_gpu_memory()
            if gpu_mem:
                logger.info(f"GPU 显存占用: {gpu_mem:.0f} MB")

            # 3) 预热（可选）
            self._warmup()

            return True

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self._is_loaded = False
            raise

    def unload(self):
        """卸载模型，释放显存"""
        logger.info("正在卸载模型...")
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None
        self._is_loaded = False

        # 清理 GPU 缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info(
                f"GPU 显存已释放，当前占用: {self._get_gpu_memory():.0f} MB"
            )

    def get_model_and_processor(self) -> Tuple:
        """获取模型和 Processor 实例"""
        if not self.is_loaded:
            raise RuntimeError("模型未加载，请先调用 load()")
        return self.model, self.processor

    def record_inference(self):
        """记录一次推理调用"""
        self._inference_count += 1

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _resolve_model_path(self) -> str:
        """
        根据配置解析实际模型路径

        支持三种来源:
          - modelscope: 通过 ModelScope 下载（国内免登录）
          - huggingface: 通过 Hugging Face 下载（需登录+同意协议）
          - local: 直接使用本地路径
          - auto: 智能选择
        """
        import os.path as osp

        model_name = config.model_name
        source = config.model_source

        # 如果 model_name 已经是一个存在的本地路径，直接返回
        if osp.isdir(model_name) or osp.isfile(model_name):
            logger.info(f"检测到本地路径，直接使用: {model_name}")
            return model_name

        if source == "local":
            raise FileNotFoundError(
                f"model_source=local 但 {model_name} 不是有效的本地路径"
            )

        if source in ("modelscope", "auto"):
            # 尝试从 ModelScope 下载（国内免登录，速度快）
            local_path = self._try_modelscope(model_name)
            if local_path:
                return local_path
            if source == "modelscope":
                raise RuntimeError(
                    f"ModelScope 下载失败: {model_name}。"
                    f"请确保已安装: pip install modelscope"
                )

        if source in ("huggingface", "auto"):
            # 尝试 Hugging Face（需要登录 + 同意 gated repo 协议）
            return model_name

        return model_name

    def _try_modelscope(self, model_name: str) -> Optional[str]:
        """
        尝试通过 ModelScope 下载模型到本地

        Returns:
            下载后的本地路径，如果失败返回 None
        """
        try:
            from modelscope import snapshot_download

            logger.info(f"  尝试从 ModelScope 下载: {model_name}")
            logger.info("  (国内源，免登录，首次下载较慢)...")

            local_dir = snapshot_download(
                model_name,
                cache_dir=config.model_cache_dir,
            )
            logger.info(f"  ModelScope 下载完成: {local_dir}")
            return local_dir

        except ImportError:
            logger.warning(
                "  ModelScope 未安装，跳过。安装命令: pip install modelscope"
            )
            return None
        except Exception as e:
            logger.warning(f"  ModelScope 下载失败: {e}")
            return None

    def _warmup(self):
        """
        模型预热 - 用一张空白图片跑一次前向传播
        目的：初始化 CUDA 内核，填充 KV Cache，减少首次推理延迟
        """
        logger.info("  模型预热中...")
        try:
            import numpy as np
            from PIL import Image

            # 创建一张空白图片
            dummy_img = Image.fromarray(
                np.zeros((224, 224, 3), dtype=np.uint8)
            )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": dummy_img},
                        {"type": "text", "text": "warmup"},
                    ],
                }
            ]

            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
                processor_kwargs={
                    "images_kwargs": {
                        "downsample_mode": config.downsample_mode,
                        "max_slice_nums": config.max_slice_nums,
                    }
                },
            ).to(self.model.device)

            with torch.no_grad():
                _ = self.model.generate(
                    **inputs,
                    downsample_mode=config.downsample_mode,
                    max_new_tokens=1,
                    do_sample=False,
                )

            logger.info("  预热完成")
        except Exception as e:
            logger.warning(f"预热失败（非致命）: {e}")

    def _get_gpu_memory(self) -> Optional[float]:
        """获取当前 GPU 显存占用（MB）"""
        if not torch.cuda.is_available():
            return None
        return torch.cuda.memory_allocated() / 1024**2


# 全局单例
model_loader = ModelLoader()
