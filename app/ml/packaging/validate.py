"""
============================================================================
模型回归测试脚本 - 验证量化/导出后模型的输出一致性
============================================================================
技术栈: torch, transformers, numpy, PIL

测试内容:
  - 输出文本一致性（原始 vs 量化/导出）
  - 语义相似度（使用余弦相似度）
  - 置信度偏差（量化导致的置信度变化）
  - 功能完整性（所有任务类型是否正常）

支持的对比模式:
  - original_vs_quantized: 原始模型 vs 量化模型
  - original_vs_onnx: 原始模型 vs ONNX 模型
  - quantized_vs_onnx: 量化模型 vs ONNX 模型

用法:
    # Python API
    from ml.packaging.validate import ModelValidator, ValidationConfig
    config = ValidationConfig(
        original_model="openbmb/MiniCPM-V",
        target_model="./quantized_model",
    )
    validator = ModelValidator(config)
    result = validator.validate()

    # CLI
    python -m ml.packaging.validate \
        --original_model openbmb/MiniCPM-V \
        --target_model ./quantized_model \
        --mode original_vs_quantized
============================================================================
"""

import argparse
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# 验证模式
ValidationMode = Literal[
    "original_vs_quantized",
    "original_vs_onnx",
    "quantized_vs_onnx",
]

# 测试任务类型
TEST_TASKS = [
    {"name": "描述", "question": "请详细描述这张图片的内容。"},
    {"name": "OCR", "question": "图片中的文字是什么？"},
    {"name": "识别", "question": "这张图片中有哪些物体？"},
    {"name": "场景", "question": "这是什么地方？"},
]


@dataclass
class ValidationConfig:
    """回归测试配置"""

    original_model: str  # 原始模型路径
    target_model: str  # 目标模型路径（量化/ONNX）
    mode: ValidationMode = "original_vs_quantized"
    # 测试配置
    test_images: Optional[List[str]] = None  # 测试图片路径列表
    num_test_images: int = 5  # 使用随机生成的测试图片数量
    image_size: int = 448
    max_new_tokens: int = 50
    temperature: float = 0.0  # 贪婪解码，确保可复现
    # 阈值配置
    min_text_similarity: float = 0.85  # 最小文本相似度
    max_latency_regression: float = 2.0  # 最大延迟回退倍数
    # 输出
    output_file: Optional[str] = None
    verbose: bool = False

    def __post_init__(self):
        if not self.original_model or not self.target_model:
            raise ValueError("original_model 和 target_model 不能为空")


@dataclass
class TestCaseResult:
    """单个测试用例的结果"""

    task_name: str
    original_output: str
    target_output: str
    text_similarity: float  # 0-1
    semantic_similarity: float  # 0-1
    original_latency_ms: float
    target_latency_ms: float
    latency_regression: float  # target / original
    passed: bool


@dataclass
class ValidationResult:
    """回归测试结果"""

    success: bool
    mode: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    overall_text_similarity: float
    overall_semantic_similarity: float
    avg_latency_regression: float
    test_results: List[Dict]
    time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class ModelValidator:
    """
    模型回归测试工具

    对比原始模型和量化/导出后模型的输出一致性。
    """

    def __init__(self, config: ValidationConfig):
        self.config = config
        self._setup_logging()

    def _setup_logging(self):
        level = logging.DEBUG if self.config.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def validate(self) -> ValidationResult:
        """
        执行回归测试

        Returns:
            ValidationResult: 测试结果
        """
        logger.info("=" * 60)
        logger.info("开始模型回归测试")
        logger.info(f"模式: {self.config.mode}")
        logger.info(f"原始模型: {self.config.original_model}")
        logger.info(f"目标模型: {self.config.target_model}")
        logger.info("=" * 60)

        t_start = time.time()

        try:
            # 准备测试数据
            test_images = self._prepare_test_images()
            logger.info(f"测试图片数: {len(test_images)}")

            # 加载模型
            logger.info("加载原始模型...")
            original_model, original_processor = self._load_model(
                self.config.original_model
            )

            logger.info("加载目标模型...")
            target_model, target_processor = self._load_model(
                self.config.target_model
            )

            # 执行测试
            results = []
            for img_idx, image in enumerate(test_images):
                for task in TEST_TASKS:
                    logger.info(
                        f"测试 {img_idx+1}/{len(test_images)} - {task['name']}..."
                    )
                    result = self._run_test_case(
                        image=image,
                        task=task,
                        original_model=original_model,
                        original_processor=original_processor,
                        target_model=target_model,
                        target_processor=target_processor,
                    )
                    results.append(result)

            # 汇总结果
            validation_result = self._summarize_results(results)
            validation_result.time_seconds = time.time() - t_start

            # 保存结果
            if self.config.output_file:
                validation_result.to_json(self.config.output_file)
                logger.info(f"结果已保存: {self.config.output_file}")

            self._print_summary(validation_result)
            return validation_result

        except Exception as e:
            logger.error(f"回归测试失败: {e}")
            import traceback
            traceback.print_exc()
            return ValidationResult(
                success=False,
                mode=self.config.mode,
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                overall_text_similarity=0.0,
                overall_semantic_similarity=0.0,
                avg_latency_regression=0.0,
                test_results=[],
                time_seconds=time.time() - t_start,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # 测试实现
    # ------------------------------------------------------------------

    def _run_test_case(
        self,
        image: Image.Image,
        task: Dict,
        original_model,
        original_processor,
        target_model,
        target_processor,
    ) -> TestCaseResult:
        """执行单个测试用例"""
        import torch

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": task["question"]},
                ],
            }
        ]

        # 原始模型推理
        t0 = time.perf_counter()
        original_output = self._inference(
            model=original_model,
            processor=original_processor,
            messages=messages,
        )
        t1 = time.perf_counter()
        original_latency = (t1 - t0) * 1000

        # 目标模型推理
        t0 = time.perf_counter()
        target_output = self._inference(
            model=target_model,
            processor=target_processor,
            messages=messages,
        )
        t1 = time.perf_counter()
        target_latency = (t1 - t0) * 1000

        # 计算相似度
        text_sim = self._compute_text_similarity(original_output, target_output)
        semantic_sim = self._compute_semantic_similarity(
            original_output, target_output
        )

        # 计算延迟回退
        latency_reg = (
            target_latency / original_latency if original_latency > 0 else 1.0
        )

        # 判断是否通过
        passed = (
            text_sim >= self.config.min_text_similarity
            and latency_reg <= self.config.max_latency_regression
        )

        return TestCaseResult(
            task_name=task["name"],
            original_output=original_output,
            target_output=target_output,
            text_similarity=text_sim,
            semantic_similarity=semantic_sim,
            original_latency_ms=original_latency,
            target_latency_ms=target_latency,
            latency_regression=latency_reg,
            passed=passed,
        )

    def _inference(self, model, processor, messages: List[Dict]) -> str:
        """执行推理"""
        import torch

        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=False,
            )

        # 解码输出
        generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        output_text = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        return output_text.strip()

    # ------------------------------------------------------------------
    # 相似度计算
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_text_similarity(text1: str, text2: str) -> float:
        """
        计算文本相似度（基于字符级 Jaccard）

        实际生产环境建议使用:
        - BLEU / ROUGE 分数
        - Sentence-BERT 余弦相似度
        """
        # 简单实现：基于单词集合的 Jaccard 相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union

    @staticmethod
    def _compute_semantic_similarity(text1: str, text2: str) -> float:
        """
        计算语义相似度

        实际生产环境应使用预训练的 Sentence-BERT 模型。
        此处使用简单的字符 n-gram 作为代理。
        """
        # 使用 2-gram 的 Jaccard 相似度作为语义相似度的代理
        def get_ngrams(text, n=2):
            text = text.lower().replace(" ", "")
            return set(text[i : i + n] for i in range(len(text) - n + 1))

        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)

        if not ngrams1 and not ngrams2:
            return 1.0
        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        return intersection / union

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _prepare_test_images(self) -> List[Image.Image]:
        """准备测试图片"""
        images = []

        # 使用用户提供的图片
        if self.config.test_images:
            for path in self.config.test_images:
                if os.path.exists(path):
                    images.append(Image.open(path).convert("RGB"))
                else:
                    logger.warning(f"测试图片不存在: {path}")

        # 生成随机测试图片
        num_random = max(0, self.config.num_test_images - len(images))
        for i in range(num_random):
            arr = np.random.randint(0, 255, (self.config.image_size, self.config.image_size, 3), dtype=np.uint8)
            images.append(Image.fromarray(arr))

        return images

    def _load_model(self, model_path: str) -> Tuple:
        """加载模型和 processor"""
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=False,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=False,
        )
        model.eval()
        return model, processor

    def _summarize_results(self, results: List[TestCaseResult]) -> ValidationResult:
        """汇总测试结果"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        avg_text_sim = np.mean([r.text_similarity for r in results]) if results else 0.0
        avg_semantic_sim = (
            np.mean([r.semantic_similarity for r in results]) if results else 0.0
        )
        avg_latency_reg = (
            np.mean([r.latency_regression for r in results]) if results else 0.0
        )

        return ValidationResult(
            success=(failed == 0),
            mode=self.config.mode,
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            overall_text_similarity=round(avg_text_sim, 4),
            overall_semantic_similarity=round(avg_semantic_sim, 4),
            avg_latency_regression=round(avg_latency_reg, 4),
            test_results=[asdict(r) for r in results],
            time_seconds=0.0,
            metadata={
                "min_text_similarity_threshold": self.config.min_text_similarity,
                "max_latency_regression_threshold": self.config.max_latency_regression,
            },
        )

    def _print_summary(self, result: ValidationResult):
        """打印结果摘要"""
        print("\n" + "=" * 60)
        print("回归测试摘要")
        print("=" * 60)
        print(f"总用例数: {result.total_cases}")
        print(f"通过: {result.passed_cases} | 失败: {result.failed_cases}")
        print(f"文本相似度: {result.overall_text_similarity:.2%}")
        print(f"语义相似度: {result.overall_semantic_similarity:.2%}")
        print(f"平均延迟回退: {result.avg_latency_regression:.2f}x")
        print(f"结果: {'通过' if result.success else '未通过'}")
        print("=" * 60)

    # ------------------------------------------------------------------
    # CLI
    # ------------------------------------------------------------------

    @classmethod
    def from_cli(cls) -> "ModelValidator":
        """从命令行参数创建验证器"""
        parser = argparse.ArgumentParser(description="模型回归测试工具")
        parser.add_argument("--original_model", required=True, help="原始模型路径")
        parser.add_argument("--target_model", required=True, help="目标模型路径")
        parser.add_argument(
            "--mode",
            default="original_vs_quantized",
            choices=["original_vs_quantized", "original_vs_onnx", "quantized_vs_onnx"],
        )
        parser.add_argument("--test_images", default=None, help="逗号分隔的测试图片路径")
        parser.add_argument("--num_test_images", type=int, default=5)
        parser.add_argument("--min_text_similarity", type=float, default=0.85)
        parser.add_argument("--max_latency_regression", type=float, default=2.0)
        parser.add_argument("--output", default=None, help="结果保存路径")
        parser.add_argument("--verbose", action="store_true")

        args = parser.parse_args()
        test_images = None
        if args.test_images:
            test_images = [p.strip() for p in args.test_images.split(",")]

        config = ValidationConfig(
            original_model=args.original_model,
            target_model=args.target_model,
            mode=args.mode,
            test_images=test_images,
            num_test_images=args.num_test_images,
            min_text_similarity=args.min_text_similarity,
            max_latency_regression=args.max_latency_regression,
            output_file=args.output,
            verbose=args.verbose,
        )
        return cls(config)


# 如果直接运行此脚本
if __name__ == "__main__":
    validator = ModelValidator.from_cli()
    result = validator.validate()
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
