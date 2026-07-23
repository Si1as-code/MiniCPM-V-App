"""
============================================================================
模型打包流水线 - 整合量化、导出、测试、发布
============================================================================
技术栈: 整合 quantize, export_onnx, benchmark, validate, publish

流水线步骤:
  1. 量化 (Quantize)     → 减小模型体积
  2. 导出 ONNX (Export)  → 跨平台部署
  3. Benchmark           → 性能测试
  4. 回归测试 (Validate) → 输出一致性验证
  5. 发布 (Publish)      → 打包上传

配置驱动:
  通过 JSON/YAML 配置文件定义流水线参数

用法:
    # Python API
    from ml.packaging.pipeline import PackagingPipeline
    pipeline = PackagingPipeline.from_config("packaging_config.json")
    result = pipeline.run()

    # CLI
    python -m ml.packaging.pipeline \
        --config packaging_config.json \
        --skip_steps benchmark,validate
============================================================================
"""

import argparse
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional

from ml.packaging.quantize import ModelQuantizer, QuantizationConfig, QuantizationResult
from ml.packaging.export_onnx import ONNXExporter, ONNXExportConfig, ONNXExportResult
from ml.packaging.benchmark import ModelBenchmark, BenchmarkConfig, BenchmarkResult
from ml.packaging.validate import ModelValidator, ValidationConfig, ValidationResult
from ml.packaging.publish import ModelPublisher, PublishConfig, PublishResult

logger = logging.getLogger(__name__)

# 流水线步骤
PipelineStep = Literal["quantize", "export_onnx", "benchmark", "validate", "publish"]
ALL_STEPS: List[PipelineStep] = ["quantize", "export_onnx", "benchmark", "validate", "publish"]


@dataclass
class PackagingConfig:
    """打包流水线配置"""

    # 输入
    model_path: str  # 原始模型路径
    output_base_dir: str = "./packaging_output"
    version: str = "v1.0"

    # 步骤开关
    steps: List[PipelineStep] = field(default_factory=lambda: list(ALL_STEPS))
    skip_steps: List[str] = field(default_factory=list)

    # 各步骤配置
    quantize: Dict = field(default_factory=dict)
    export_onnx: Dict = field(default_factory=dict)
    benchmark: Dict = field(default_factory=dict)
    validate: Dict = field(default_factory=dict)
    publish: Dict = field(default_factory=dict)

    # 全局配置
    dry_run: bool = False
    verbose: bool = False
    save_manifest: bool = True  # 保存执行清单

    def __post_init__(self):
        os.makedirs(self.output_base_dir, exist_ok=True)
        # 过滤跳过的步骤
        self.steps = [s for s in self.steps if s not in self.skip_steps]


@dataclass
class PipelineManifest:
    """流水线执行清单"""

    version: str
    start_time: str
    end_time: Optional[str] = None
    steps: List[Dict] = field(default_factory=list)
    success: bool = False
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class PackagingPipeline:
    """
    模型打包流水线

    串联多个打包步骤，提供统一的执行接口。
    """

    def __init__(self, config: PackagingConfig):
        self.config = config
        self._setup_logging()
        self._manifest = PipelineManifest(
            version=config.version,
            start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

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

    def run(self) -> Dict:
        """
        执行完整流水线

        Returns:
            Dict: 各步骤结果汇总
        """
        logger.info("=" * 70)
        logger.info("模型打包流水线启动")
        logger.info(f"版本: {self.config.version}")
        logger.info(f"步骤: {', '.join(self.config.steps)}")
        logger.info(f"输出目录: {self.config.output_base_dir}")
        logger.info("=" * 70)

        t_start = time.time()
        results = {}

        # 各步骤的输出路径传递
        quantized_model_path = self.config.model_path
        onnx_model_path = None

        try:
            for step in self.config.steps:
                logger.info(f"\n{'='*70}")
                logger.info(f"步骤: {step}")
                logger.info(f"{'='*70}")

                step_result = None

                if step == "quantize":
                    step_result = self._run_quantize(quantized_model_path)
                    if step_result.success:
                        quantized_model_path = step_result.output_dir

                elif step == "export_onnx":
                    step_result = self._run_export_onnx(quantized_model_path)
                    if step_result.success:
                        onnx_model_path = step_result.output_dir

                elif step == "benchmark":
                    step_result = self._run_benchmark(quantized_model_path)

                elif step == "validate":
                    step_result = self._run_validate(
                        self.config.model_path,
                        quantized_model_path,
                    )

                elif step == "publish":
                    step_result = self._run_publish(quantized_model_path)

                results[step] = step_result
                self._manifest.steps.append({
                    "step": step,
                    "success": step_result.success if step_result else False,
                    "time_seconds": getattr(step_result, "time_seconds", 0),
                })

                # 如果步骤失败且不是发布步骤，中断流水线
                if step_result and not step_result.success and step != "publish":
                    logger.error(f"步骤 {step} 失败，中断流水线")
                    break

            # 完成
            self._manifest.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self._manifest.success = all(
                s["success"] for s in self._manifest.steps
            )
            self._manifest.metadata["total_time_seconds"] = round(time.time() - t_start, 2)

            if self.config.save_manifest:
                manifest_path = os.path.join(
                    self.config.output_base_dir,
                    f"manifest-{self.config.version}.json",
                )
                self._manifest.to_json(manifest_path)
                logger.info(f"\n执行清单已保存: {manifest_path}")

            self._print_summary(results)
            return results

        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # 各步骤实现
    # ------------------------------------------------------------------

    def _run_quantize(self, model_path: str) -> QuantizationResult:
        """执行量化步骤"""
        output_dir = os.path.join(
            self.config.output_base_dir,
            f"quantized-{self.config.version}",
        )

        config = QuantizationConfig(
            output_dir=output_dir,
            **self.config.quantize,
        )
        quantizer = ModelQuantizer(config)

        if self.config.dry_run:
            logger.info("[Dry Run] 模拟量化步骤")
            return QuantizationResult(
                success=True,
                output_dir=output_dir,
                method=config.method,
                bits=config.bits,
                original_size_mb=0.0,
                quantized_size_mb=0.0,
                compression_ratio=1.0,
                time_seconds=0.0,
                metadata={"dry_run": True},
            )

        return quantizer.quantize(model_path)

    def _run_export_onnx(self, model_path: str) -> ONNXExportResult:
        """执行 ONNX 导出步骤"""
        output_dir = os.path.join(
            self.config.output_base_dir,
            f"onnx-{self.config.version}",
        )

        config = ONNXExportConfig(
            output_dir=output_dir,
            **self.config.export_onnx,
        )
        exporter = ONNXExporter(config)

        if self.config.dry_run:
            logger.info("[Dry Run] 模拟 ONNX 导出步骤")
            return ONNXExportResult(
                success=True,
                output_dir=output_dir,
                task=config.task,
                opset=config.opset,
                original_size_mb=0.0,
                exported_size_mb=0.0,
                files=[],
                time_seconds=0.0,
                metadata={"dry_run": True},
            )

        return exporter.export(model_path)

    def _run_benchmark(self, model_path: str) -> BenchmarkResult:
        """执行 Benchmark 步骤"""
        config = BenchmarkConfig(
            output_file=os.path.join(
                self.config.output_base_dir,
                f"benchmark-{self.config.version}.json",
            ),
            **self.config.benchmark,
        )
        benchmark = ModelBenchmark(config)

        if self.config.dry_run:
            logger.info("[Dry Run] 模拟 Benchmark 步骤")
            return BenchmarkResult(
                success=True,
                model_path=model_path,
                mode=config.mode,
                total_runs=0,
                metrics_summary={},
                raw_metrics=[],
                batch_results=[],
                time_seconds=0.0,
                metadata={"dry_run": True},
            )

        return benchmark.run(model_path)

    def _run_validate(self, original_model: str, target_model: str) -> ValidationResult:
        """执行回归测试步骤"""
        config = ValidationConfig(
            original_model=original_model,
            target_model=target_model,
            output_file=os.path.join(
                self.config.output_base_dir,
                f"validation-{self.config.version}.json",
            ),
            **self.config.validate,
        )
        validator = ModelValidator(config)

        if self.config.dry_run:
            logger.info("[Dry Run] 模拟回归测试步骤")
            return ValidationResult(
                success=True,
                mode=config.mode,
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                overall_text_similarity=1.0,
                overall_semantic_similarity=1.0,
                avg_latency_regression=1.0,
                test_results=[],
                time_seconds=0.0,
                metadata={"dry_run": True},
            )

        return validator.validate()

    def _run_publish(self, model_dir: str) -> PublishResult:
        """执行发布步骤"""
        config = PublishConfig(
            output_dir=self.config.output_base_dir,
            **self.config.publish,
        )
        publisher = ModelPublisher(config)

        if self.config.dry_run:
            logger.info("[Dry Run] 模拟发布步骤")
            return PublishResult(
                success=True,
                model_dir=model_dir,
                version=self.config.version,
                target=config.target,
                package_path=None,
                uploaded_files=[],
                checksums={},
                model_card_path=None,
                total_size_mb=0.0,
                time_seconds=0.0,
                metadata={"dry_run": True},
            )

        return publisher.publish(model_dir, self.config.version)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _print_summary(self, results: Dict):
        """打印流水线执行摘要"""
        print("\n" + "=" * 70)
        print("打包流水线执行摘要")
        print("=" * 70)

        for step, result in results.items():
            status = "通过" if result and result.success else "失败"
            step_time = getattr(result, "time_seconds", 0)
            print(f"  {step:15s} | {status:6s} | {step_time:6.1f}s")

        total_time = self._manifest.metadata.get("total_time_seconds", 0)
        overall = "通过" if self._manifest.success else "失败"
        print(f"\n  总计: {overall} | 耗时: {total_time:.1f}s")
        print("=" * 70)

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config_path: str) -> "PackagingPipeline":
        """从 JSON 配置文件创建流水线"""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = PackagingConfig(**data)
        return cls(config)

    @classmethod
    def from_cli(cls) -> "PackagingPipeline":
        """从命令行参数创建流水线"""
        parser = argparse.ArgumentParser(description="模型打包流水线")
        parser.add_argument("--config", required=True, help="配置文件路径 (JSON)")
        parser.add_argument("--skip_steps", default="", help="逗号分隔的要跳过的步骤")
        parser.add_argument("--dry_run", action="store_true", help="仅模拟执行")
        parser.add_argument("--verbose", action="store_true")

        args = parser.parse_args()
        pipeline = cls.from_config(args.config)

        if args.skip_steps:
            pipeline.config.skip_steps = [s.strip() for s in args.skip_steps.split(",")]
            pipeline.config.steps = [
                s for s in pipeline.config.steps if s not in pipeline.config.skip_steps
            ]
        pipeline.config.dry_run = args.dry_run
        pipeline.config.verbose = args.verbose

        return pipeline


# 如果直接运行此脚本
if __name__ == "__main__":
    pipeline = PackagingPipeline.from_cli()
    results = pipeline.run()
    print(json.dumps(
        {k: (v.to_dict() if hasattr(v, "to_dict") else str(v)) for k, v in results.items()},
        indent=2,
        ensure_ascii=False,
    ))
