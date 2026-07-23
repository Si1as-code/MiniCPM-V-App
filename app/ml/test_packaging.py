"""
============================================================================
Sprint 5 单元测试 - 模型打包流水线
============================================================================
测试范围:
  - 配置类 (QuantizationConfig, ONNXExportConfig, BenchmarkConfig, ValidationConfig, PublishConfig, PackagingConfig)
  - 结果类 (QuantizationResult, ONNXExportResult, BenchmarkResult, ValidationResult, PublishResult)
  - 工具方法 (目录大小计算、校验和、相似度计算等)
  - 流水线编排 (步骤调度、manifest 生成)

注意:
  - 不涉及实际的模型加载和推理（需要 GPU + 大内存）
  - 使用 unittest.mock 模拟外部依赖
============================================================================
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

# 确保能导入 ml 模块
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.packaging.quantize import (
    ModelQuantizer, QuantizationConfig, QuantizationResult,
)
from ml.packaging.export_onnx import (
    ONNXExporter, ONNXExportConfig, ONNXExportResult,
)
from ml.packaging.benchmark import (
    ModelBenchmark, BenchmarkConfig, BenchmarkResult, BenchmarkMetrics,
)
from ml.packaging.validate import (
    ModelValidator, ValidationConfig, ValidationResult, TestCaseResult,
)
from ml.packaging.publish import (
    ModelPublisher, PublishConfig, PublishResult,
)
from ml.packaging.pipeline import (
    PackagingPipeline, PackagingConfig, PipelineManifest,
)


# =============================================================================
# Test Quantization
# =============================================================================
class TestQuantizationConfig(unittest.TestCase):
    """测试量化配置"""

    def test_default_config(self):
        config = QuantizationConfig()
        self.assertEqual(config.method, "gptq")
        self.assertEqual(config.bits, 4)
        self.assertEqual(config.group_size, 128)
        self.assertTrue(os.path.exists(config.output_dir))

    def test_invalid_bits(self):
        with self.assertRaises(ValueError):
            QuantizationConfig(method="gptq", bits=5)

    def test_int8_force_bits(self):
        config = QuantizationConfig(method="int8", bits=4)
        self.assertEqual(config.bits, 8)  # 强制设置为 8


class TestQuantizationResult(unittest.TestCase):
    """测试量化结果"""

    def test_to_dict(self):
        result = QuantizationResult(
            success=True,
            output_dir="./out",
            method="gptq",
            bits=4,
            original_size_mb=100.0,
            quantized_size_mb=25.0,
            compression_ratio=4.0,
            time_seconds=120.0,
        )
        d = result.to_dict()
        self.assertEqual(d["success"], True)
        self.assertEqual(d["compression_ratio"], 4.0)

    def test_to_json(self):
        result = QuantizationResult(
            success=True,
            output_dir="./out",
            method="gptq",
            bits=4,
            original_size_mb=100.0,
            quantized_size_mb=25.0,
            compression_ratio=4.0,
            time_seconds=120.0,
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            result.to_json(path)
            with open(path, "r") as f:
                data = json.load(f)
            self.assertEqual(data["method"], "gptq")
        finally:
            os.unlink(path)


class TestModelQuantizerUtils(unittest.TestCase):
    """测试量化器工具方法"""

    def test_get_dir_size_mb(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = Path(tmpdir) / "test.bin"
            test_file.write_bytes(b"x" * 1024 * 1024)  # 1MB
            size = ModelQuantizer._get_dir_size_mb(tmpdir)
            self.assertAlmostEqual(size, 1.0, places=1)

    def test_load_calibration_data_default(self):
        config = QuantizationConfig(max_calib_samples=10)
        quantizer = ModelQuantizer(config)
        data = quantizer._load_calibration_data()
        self.assertEqual(len(data), 10)
        self.assertIn("请描述这张图片的内容。", data)


# =============================================================================
# Test ONNX Export
# =============================================================================
class TestONNXExportConfig(unittest.TestCase):
    """测试 ONNX 导出配置"""

    def test_default_config(self):
        config = ONNXExportConfig()
        self.assertEqual(config.opset, 14)
        self.assertTrue(config.optimize)
        self.assertTrue(config.dynamic_axes)

    def test_output_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = os.path.join(tmpdir, "onnx_out")
            config = ONNXExportConfig(output_dir=out_dir)
            self.assertTrue(os.path.exists(out_dir))


class TestONNXExportResult(unittest.TestCase):
    """测试 ONNX 导出结果"""

    def test_result_with_files(self):
        result = ONNXExportResult(
            success=True,
            output_dir="./onnx",
            task="full",
            opset=14,
            original_size_mb=100.0,
            exported_size_mb=80.0,
            files=["model.onnx", "config.json"],
            time_seconds=60.0,
        )
        self.assertEqual(len(result.files), 2)
        self.assertTrue(result.success)


# =============================================================================
# Test Benchmark
# =============================================================================
class TestBenchmarkConfig(unittest.TestCase):
    """测试 Benchmark 配置"""

    def test_default_config(self):
        config = BenchmarkConfig()
        self.assertEqual(config.mode, "single")
        self.assertEqual(config.runs, 50)
        self.assertEqual(config.warmup, 5)

    def test_runs_validation(self):
        config = BenchmarkConfig(runs=0)
        self.assertEqual(config.runs, 1)  # 自动修正


class TestBenchmarkMetrics(unittest.TestCase):
    """测试 Benchmark 指标"""

    def test_metrics_creation(self):
        metric = BenchmarkMetrics(
            latency_ms=100.0,
            ttft_ms=30.0,
            tpot_ms=10.0,
            tokens_generated=20,
            peak_memory_mb=2048.0,
            timestamp=time.time(),
        )
        self.assertEqual(metric.tokens_generated, 20)
        self.assertEqual(metric.latency_ms, 100.0)


class TestModelBenchmarkUtils(unittest.TestCase):
    """测试 Benchmark 工具方法"""

    def test_compute_summary(self):
        metrics = [
            BenchmarkMetrics(
                latency_ms=100.0 + i,
                ttft_ms=30.0,
                tpot_ms=10.0,
                tokens_generated=20,
                peak_memory_mb=2048.0,
                timestamp=time.time(),
            )
            for i in range(10)
        ]
        summary = ModelBenchmark._compute_summary(metrics)
        self.assertIn("latency_ms", summary)
        self.assertIn("p95", summary["latency_ms"])
        self.assertIn("throughput", summary)

    def test_analyze_memory_trend_no_leak(self):
        # 稳定的内存使用
        samples = [1000.0 + np.random.normal(0, 10) for _ in range(100)]
        trend = ModelBenchmark._analyze_memory_trend(samples)
        self.assertFalse(trend["leak_detected"])

    def test_analyze_memory_trend_with_leak(self):
        # 明显的内存泄漏
        samples = [1000.0 + i * 5 for i in range(100)]
        trend = ModelBenchmark._analyze_memory_trend(samples)
        self.assertTrue(trend["leak_detected"])
        self.assertGreater(trend["growth_mb"], 0)


# =============================================================================
# Test Validation
# =============================================================================
class TestValidationConfig(unittest.TestCase):
    """测试回归测试配置"""

    def test_default_config(self):
        config = ValidationConfig(
            original_model="model-a",
            target_model="model-b",
        )
        self.assertEqual(config.mode, "original_vs_quantized")
        self.assertEqual(config.min_text_similarity, 0.85)

    def test_empty_model_paths(self):
        with self.assertRaises(ValueError):
            ValidationConfig(original_model="", target_model="model-b")


class TestModelValidatorUtils(unittest.TestCase):
    """测试回归测试工具方法"""

    def test_text_similarity_identical(self):
        sim = ModelValidator._compute_text_similarity("hello world", "hello world")
        self.assertEqual(sim, 1.0)

    def test_text_similarity_completely_different(self):
        sim = ModelValidator._compute_text_similarity("abc", "xyz")
        self.assertEqual(sim, 0.0)

    def test_text_similarity_partial(self):
        sim = ModelValidator._compute_text_similarity("hello world foo", "hello world bar")
        self.assertGreater(sim, 0.0)
        self.assertLess(sim, 1.0)

    def test_semantic_similarity(self):
        sim = ModelValidator._compute_semantic_similarity("hello world", "hello world")
        self.assertEqual(sim, 1.0)

    def test_summarize_results(self):
        results = [
            TestCaseResult(
                task_name="描述",
                original_output="a",
                target_output="a",
                text_similarity=1.0,
                semantic_similarity=1.0,
                original_latency_ms=100.0,
                target_latency_ms=110.0,
                latency_regression=1.1,
                passed=True,
            ),
            TestCaseResult(
                task_name="OCR",
                original_output="b",
                target_output="c",
                text_similarity=0.5,
                semantic_similarity=0.6,
                original_latency_ms=100.0,
                target_latency_ms=300.0,
                latency_regression=3.0,
                passed=False,
            ),
        ]
        validator = ModelValidator(ValidationConfig(original_model="a", target_model="b"))
        summary = validator._summarize_results(results)
        self.assertEqual(summary.total_cases, 2)
        self.assertEqual(summary.passed_cases, 1)
        self.assertEqual(summary.failed_cases, 1)
        self.assertFalse(summary.success)


# =============================================================================
# Test Publish
# =============================================================================
class TestPublishConfig(unittest.TestCase):
    """测试发布配置"""

    def test_default_config(self):
        config = PublishConfig()
        self.assertEqual(config.target, "local")
        self.assertEqual(config.package_format, "tar.gz")

    def test_env_var_loading(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "test-key"
        config = PublishConfig()
        self.assertEqual(config.access_key, "test-key")
        del os.environ["AWS_ACCESS_KEY_ID"]


class TestModelPublisherUtils(unittest.TestCase):
    """测试发布工具方法"""

    def test_compute_checksums(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            (Path(tmpdir) / "config.json").write_text('{"key": "value"}')
            (Path(tmpdir) / "model.bin").write_bytes(b"\x00\x01\x02\x03")

            publisher = ModelPublisher(PublishConfig())
            checksums = publisher._compute_checksums(tmpdir)

            self.assertIn("config.json", checksums)
            self.assertIn("model.bin", checksums)
            self.assertEqual(len(checksums["config.json"]), 64)  # SHA256 hex length

    def test_save_checksums(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checksums = {"file1.txt": "abc123", "file2.txt": "def456"}
            publisher = ModelPublisher(PublishConfig())
            publisher._save_checksums(tmpdir, checksums)

            checksum_path = Path(tmpdir) / "checksums.sha256"
            self.assertTrue(checksum_path.exists())
            content = checksum_path.read_text()
            self.assertIn("abc123  file1.txt", content)

    def test_package_model_tar_gz(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "model")
            os.makedirs(model_dir)
            (Path(model_dir) / "config.json").write_text('{}')

            config = PublishConfig(output_dir=tmpdir, package_format="tar.gz")
            publisher = ModelPublisher(config)
            package_path = publisher._package_model(model_dir, "v1.0")

            self.assertIsNotNone(package_path)
            self.assertTrue(os.path.exists(package_path))
            self.assertTrue(package_path.endswith(".tar.gz"))

    def test_validate_model_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.json").write_text('{}')
            publisher = ModelPublisher(PublishConfig())
            # 不应抛出异常
            publisher._validate_model_dir(tmpdir)

    def test_validate_model_dir_missing(self):
        publisher = ModelPublisher(PublishConfig())
        with self.assertRaises(FileNotFoundError):
            publisher._validate_model_dir("/nonexistent/path")


# =============================================================================
# Test Pipeline
# =============================================================================
class TestPackagingConfig(unittest.TestCase):
    """测试流水线配置"""

    def test_default_steps(self):
        config = PackagingConfig(model_path="test-model")
        self.assertEqual(len(config.steps), 5)
        self.assertIn("quantize", config.steps)
        self.assertIn("publish", config.steps)

    def test_skip_steps(self):
        config = PackagingConfig(
            model_path="test-model",
            skip_steps=["benchmark", "validate"],
        )
        self.assertNotIn("benchmark", config.steps)
        self.assertNotIn("validate", config.steps)
        self.assertIn("quantize", config.steps)

    def test_output_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = os.path.join(tmpdir, "output")
            config = PackagingConfig(model_path="test", output_base_dir=out_dir)
            self.assertTrue(os.path.exists(out_dir))


class TestPipelineManifest(unittest.TestCase):
    """测试流水线清单"""

    def test_manifest_creation(self):
        manifest = PipelineManifest(version="v1.0", start_time="2024-01-01 00:00:00")
        self.assertEqual(manifest.version, "v1.0")
        self.assertFalse(manifest.success)

    def test_manifest_to_json(self):
        manifest = PipelineManifest(version="v1.0", start_time="2024-01-01 00:00:00")
        manifest.steps = [{"step": "quantize", "success": True, "time_seconds": 10}]
        manifest.success = True

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            manifest.to_json(path)
            with open(path, "r") as f:
                data = json.load(f)
            self.assertEqual(data["version"], "v1.0")
            self.assertTrue(data["success"])
        finally:
            os.unlink(path)


class TestPackagingPipeline(unittest.TestCase):
    """测试打包流水线"""

    def test_pipeline_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PackagingConfig(
                model_path="dummy-model",
                output_base_dir=tmpdir,
                version="test-v1",
                dry_run=True,
            )
            pipeline = PackagingPipeline(config)
            results = pipeline.run()

            # 所有步骤都应成功
            for step in config.steps:
                self.assertIn(step, results)
                self.assertTrue(results[step].success)

            # 检查 manifest
            manifest_path = os.path.join(tmpdir, "manifest-test-v1.json")
            self.assertTrue(os.path.exists(manifest_path))

    def test_pipeline_skip_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PackagingConfig(
                model_path="dummy-model",
                output_base_dir=tmpdir,
                skip_steps=["export_onnx", "benchmark"],
                dry_run=True,
            )
            pipeline = PackagingPipeline(config)
            results = pipeline.run()

            self.assertNotIn("export_onnx", results)
            self.assertNotIn("benchmark", results)
            self.assertIn("quantize", results)

    def test_pipeline_from_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "model_path": "test-model",
                "output_base_dir": tmpdir,
                "version": "v1.0",
                "steps": ["quantize", "publish"],
                "dry_run": True,
            }
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            pipeline = PackagingPipeline.from_config(config_path)
            results = pipeline.run()

            self.assertIn("quantize", results)
            self.assertIn("publish", results)
            self.assertNotIn("benchmark", results)


# =============================================================================
# Integration Test
# =============================================================================
class TestPackagingIntegration(unittest.TestCase):
    """集成测试 - 模拟完整流水线"""

    def test_full_pipeline_simulation(self):
        """模拟完整流水线执行"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟模型目录
            model_dir = os.path.join(tmpdir, "model")
            os.makedirs(model_dir)
            (Path(model_dir) / "config.json").write_text('{"model_type": "test"}')
            (Path(model_dir) / "pytorch_model.bin").write_bytes(b"\x00" * 1000)

            config = PackagingConfig(
                model_path=model_dir,
                output_base_dir=os.path.join(tmpdir, "output"),
                version="integration-v1",
                dry_run=True,
            )
            pipeline = PackagingPipeline(config)
            results = pipeline.run()

            # 验证所有步骤成功
            self.assertTrue(all(r.success for r in results.values() if hasattr(r, "success")))

            # 验证 manifest
            manifest_path = os.path.join(config.output_base_dir, "manifest-integration-v1.json")
            self.assertTrue(os.path.exists(manifest_path))

            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            self.assertTrue(manifest["success"])
            self.assertEqual(len(manifest["steps"]), 5)


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    import time
    unittest.main(verbosity=2)
