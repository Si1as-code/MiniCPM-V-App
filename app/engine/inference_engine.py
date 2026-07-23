"""
============================================================================
端侧推理引擎 - 核心推理编排
============================================================================
技术栈: PyTorch, Transformers, PIL
这是整个 App 的核心引擎，对内协调模型加载、图像处理、推理、结果解析，
对外提供简洁的 inference() 统一接口。

使用方式:
    from engine.inference_engine import inference_engine

    result = inference_engine.inference(
        image_source="path/to/image.jpg",
        question="描述这张图片"
    )
    print(result.formatted_text)
============================================================================
"""

import logging
import time
import threading
from collections import OrderedDict
from typing import Optional, Union

import torch
from PIL import Image

from config import config
from engine.model_loader import model_loader
from engine.image_processor import (
    load_image, compute_image_hash, validate_image
)
from engine.result_parser import result_parser, InferenceResult

logger = logging.getLogger(__name__)


class InferenceEngine:
    """
    端侧推理引擎 - 单例模式

    核心职责:
      1. 接收图片 + 问题，返回结构化推理结果
      2. 管理推理缓存（LRU）
      3. 线程安全（推理串行，避免 GPU 竞争）
      4. 错误处理与降级
    """

    _instance: Optional["InferenceEngine"] = None
    _lock = threading.Lock()
    _inference_lock = threading.Lock()  # 推理串行锁

    def __new__(cls) -> "InferenceEngine":
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

        # LRU 缓存: {image_hash: InferenceResult}
        self._cache: OrderedDict[str, InferenceResult] = OrderedDict()
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def inference(
        self,
        image_source: Union[str, Image.Image],
        question: str = "请详细描述这张图片的内容。",
        task_type: str = "auto",
        force_reload: bool = False,
    ) -> InferenceResult:
        """
        对单张图片执行推理

        Args:
            image_source: 图片来源 - 本地路径 / URL / PIL.Image 对象
            question: 用户问题（默认描述图片）
            task_type: 任务类型 - "describe" / "ocr" / "qa" / "classify" / "auto"
            force_reload: 是否跳过缓存

        Returns:
            InferenceResult: 结构化的推理结果

        Raises:
            RuntimeError: 模型未加载
            ValueError: 图片无效
        """
        # 1) 确保模型已加载
        if not model_loader.is_loaded:
            raise RuntimeError(
                "模型未加载，请先调用 model_loader.load()"
            )

        # 2) 加载并验证图片
        image = load_image(image_source)
        valid, error_msg = validate_image(image)
        if not valid:
            raise ValueError(f"图片无效: {error_msg}")

        # 3) 检查缓存
        image_hash = compute_image_hash(image)
        if (
            config.enable_cache
            and not force_reload
            and self._check_cache(image_hash)
        ):
            logger.info(f"命中缓存: {image_hash[:12]}...")
            return self._get_cache(image_hash)

        # 4) 执行推理
        t_start = time.time()

        with self._inference_lock:  # GPU 推理串行
            try:
                result = self._run_inference(
                    image=image,
                    image_hash=image_hash,
                    question=question,
                    task_type=task_type,
                )
            except Exception as e:
                logger.error(f"推理失败: {e}")
                raise

        result.inference_time = time.time() - t_start

        # 5) 更新缓存
        if config.enable_cache:
            self._add_cache(image_hash, result)

        # 6) 记录统计
        model_loader.record_inference()

        logger.info(
            f"推理完成: {result.summary()} "
            f"(耗时: {result.inference_time:.1f}s)"
        )
        return result

    def batch_inference(
        self,
        image_sources: list,
        question: str = "请详细描述这张图片的内容。",
        task_type: str = "auto",
    ) -> list:
        """
        批量推理（顺序执行）

        Args:
            image_sources: 图片源列表
            question: 共用问题
            task_type: 任务类型

        Returns:
            list[InferenceResult]: 结果列表
        """
        results = []
        for i, source in enumerate(image_sources):
            logger.info(f"批量推理: {i+1}/{len(image_sources)}")
            try:
                result = self.inference(
                    image_source=source,
                    question=question,
                    task_type=task_type,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"图片 {i+1} 推理失败: {e}")
                # 失败的图片用空结果占位
                results.append(
                    InferenceResult(
                        raw_text=f"推理失败: {e}",
                        formatted_text="推理失败",
                        confidence=0.0,
                    )
                )
        return results

    def get_stats(self) -> dict:
        """获取引擎统计信息"""
        return {
            **model_loader.model_info,
            "cache_size": len(self._cache),
            "cache_max": config.max_cache_size,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _run_inference(
        self,
        image: Image.Image,
        image_hash: str,
        question: str,
        task_type: str,
    ) -> InferenceResult:
        """执行实际推理流程（MiniCPM-V 4.6 标准 API）"""
        model, processor = model_loader.get_model_and_processor()

        # 构建消息（MiniCPM-V 4.6 格式）
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": question},
                ],
            }
        ]

        # 应用 Chat Template（processor_kwargs.images_kwargs 传视觉参数）
        inputs = processor.apply_chat_template(
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
        ).to(model.device)

        # 推理（downsample_mode 同时传给 generate 供 vision encoder 使用）
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                downsample_mode=config.downsample_mode,
                max_new_tokens=config.max_new_tokens,
                do_sample=(config.temperature > 0),
                temperature=config.temperature if config.temperature > 0 else None,
                top_p=0.95,
            )

        # 解码输出（去掉输入部分）
        generated_ids_trimmed = [
            out_ids[len(in_ids):]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        raw_text = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        # 解析结果
        result = result_parser.parse(
            raw_text=raw_text,
            model_name=config.model_name,
            model_source="on_device",
            image_hash=image_hash,
            image_size=image.size,
            task_type=task_type,
            user_question=question,
        )

        return result

    # ------------------------------------------------------------------
    # 缓存管理
    # ------------------------------------------------------------------

    def _check_cache(self, image_hash: str) -> bool:
        """检查缓存是否命中"""
        with self._cache_lock:
            return image_hash in self._cache

    def _get_cache(self, image_hash: str) -> InferenceResult:
        """从缓存获取结果"""
        with self._cache_lock:
            if image_hash in self._cache:
                # LRU: 移到末尾
                self._cache.move_to_end(image_hash)
                return self._cache[image_hash]
        return None

    def _add_cache(self, image_hash: str, result: InferenceResult):
        """添加结果到缓存"""
        with self._cache_lock:
            # LRU 淘汰
            if len(self._cache) >= config.max_cache_size:
                self._cache.popitem(last=False)
            self._cache[image_hash] = result

    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._cache.clear()
            logger.info("缓存已清空")


# 全局单例
inference_engine = InferenceEngine()
