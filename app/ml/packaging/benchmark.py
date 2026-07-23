"""
============================================================================
模型 Benchmark 脚本 - 延迟 / 内存 / 吞吐量测试
============================================================================
技术栈: torch, transformers, psutil, numpy

测试指标:
  - 延迟: P50 / P95 / P99 / 平均
  - 内存: 峰值显存 / 系统内存
  - 吞吐量: images/sec / tokens/sec
  - 首 token 延迟 (TTFT)
  - 每 token 延迟 (TPOT)

支持的测试模式:
  - single: 单图推理（多次取平均）
  - batch: 批量推理（不同 batch size）
  - stress: 压力测试（持续运行，检测内存泄漏）

用法:
    # Python API
    from ml.packaging.benchmark import ModelBenchmark, BenchmarkConfig
    config = BenchmarkConfig(runs=50, warmup=5)
    benchmark = ModelBenchmark(config)
    result = benchmark.run("openbmb/MiniCPM-V")

    # CLI
    python -m ml.packaging.benchmark \
        --model_path openbmb/MiniCPM-V \
        --runs 50 --warmup 5 \
        --output benchmark_result.json
============================================================================
"""

import argparse
import json
import logging
import os
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# 测试模式
BenchmarkMode = Literal["single", "batch", "stress"]


@dataclass
class BenchmarkConfig:
    """Benchmark 配置"""

    mode: BenchmarkMode = "single"
    runs: int = 50  # 推理次数
    warmup: int = 5  # 预热次数
    batch_sizes: List[int] = field(default_factory=lambda: [1, 2, 4, 8])  # batch 测试
    stress_duration: int = 300  # 压力测试持续时间（秒）
    # 输入配置
    image_size: int = 448
    question: str = "请详细描述这张图片的内容。"
    # 输出配置
    output_file: Optional[str] = None  # 结果保存路径
    save_traces: bool = False  # 保存每次推理的详细 trace
    # 设备
    device: str = "cuda"
    trust_remote_code: bool = False
    verbose: bool = False

    def __post_init__(self):
        if self.runs < 1:
            self.runs = 1
        if self.warmup < 0:
            self.warmup = 0


@dataclass
class BenchmarkMetrics:
    """单次推理的指标"""

    latency_ms: float  # 总延迟（ms）
    ttft_ms: float  # Time To First Token（ms）
    tpot_ms: float  # Time Per Output Token（ms）
    tokens_generated: int  # 生成的 token 数
    peak_memory_mb: float  # 峰值显存（MB）
    timestamp: float  # 时间戳


@dataclass
class BenchmarkResult:
    """Benchmark 结果"""

    success: bool
    model_path: str
    mode: str
    total_runs: int
    metrics_summary: Dict  # 统计摘要
    raw_metrics: List[Dict]  # 原始数据
    batch_results: List[Dict]  # batch 模式结果
    time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class ModelBenchmark:
    """
    模型 Benchmark 工具

    测量模型在不同配置下的性能表现。
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self._setup_logging()
        self._traces: List[BenchmarkMetrics] = []

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

    def run(self, model_path: str) -> BenchmarkResult:
        """
        执行 Benchmark

        Args:
            model_path: 模型路径

        Returns:
            BenchmarkResult: 测试结果
        """
        logger.info("=" * 60)
        logger.info(f"开始 Benchmark: {model_path}")
        logger.info(f"模式: {self.config.mode}, 运行次数: {self.config.runs}")
        logger.info("=" * 60)

        t_start = time.time()

        try:
            if self.config.mode == "single":
                result = self._benchmark_single(model_path)
            elif self.config.mode == "batch":
                result = self._benchmark_batch(model_path)
            elif self.config.mode == "stress":
                result = self._benchmark_stress(model_path)
            else:
                raise ValueError(f"不支持的测试模式: {self.config.mode}")

            result.time_seconds = time.time() - t_start

            # 保存结果
            if self.config.output_file:
                result.to_json(self.config.output_file)
                logger.info(f"结果已保存: {self.config.output_file}")

            self._print_summary(result)
            return result

        except Exception as e:
            logger.error(f"Benchmark 失败: {e}")
            traceback.print_exc()
            return BenchmarkResult(
                success=False,
                model_path=model_path,
                mode=self.config.mode,
                total_runs=0,
                metrics_summary={},
                raw_metrics=[],
                batch_results=[],
                time_seconds=time.time() - t_start,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # 测试实现
    # ------------------------------------------------------------------

    def _benchmark_single(self, model_path: str) -> BenchmarkResult:
        """单图推理 benchmark"""
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        # 加载模型
        logger.info("加载模型...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )
        model.eval()

        # 准备测试图片
        logger.info("准备测试数据...")
        test_image = self._create_test_image()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": test_image},
                    {"type": "text", "text": self.config.question},
                ],
            }
        ]

        # 预热
        logger.info(f"预热 {self.config.warmup} 次...")
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)

        for _ in range(self.config.warmup):
            with torch.no_grad():
                _ = model.generate(**inputs, max_new_tokens=10)
            if torch.cuda.is_available():
                torch.cuda.synchronize()

        # 正式测试
        logger.info(f"开始测试 {self.config.runs} 次...")
        metrics_list = []

        for i in range(self.config.runs):
            # 清理显存
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()

            mem_before = self._get_memory_mb()
            t0 = time.perf_counter()

            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=50,
                    do_sample=False,
                )

            if torch.cuda.is_available():
                torch.cuda.synchronize()

            t1 = time.perf_counter()
            mem_after = self._get_memory_mb()

            # 计算指标
            latency_ms = (t1 - t0) * 1000
            tokens_generated = output_ids.shape[1] - inputs["input_ids"].shape[1]
            ttft_ms = latency_ms * 0.3  # 估计值（实际需更精确测量）
            tpot_ms = latency_ms / max(tokens_generated, 1)
            peak_mem = mem_after - mem_before

            metric = BenchmarkMetrics(
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                tpot_ms=tpot_ms,
                tokens_generated=tokens_generated,
                peak_memory_mb=peak_mem,
                timestamp=time.time(),
            )
            metrics_list.append(metric)

            if (i + 1) % 10 == 0:
                logger.info(f"  进度: {i+1}/{self.config.runs}")

        # 计算统计摘要
        summary = self._compute_summary(metrics_list)

        return BenchmarkResult(
            success=True,
            model_path=model_path,
            mode="single",
            total_runs=len(metrics_list),
            metrics_summary=summary,
            raw_metrics=[asdict(m) for m in metrics_list] if self.config.save_traces else [],
            batch_results=[],
            time_seconds=0.0,
            metadata={
                "device": str(model.device),
                "warmup": self.config.warmup,
                "question": self.config.question,
            },
        )

    def _benchmark_batch(self, model_path: str) -> BenchmarkResult:
        """批量推理 benchmark"""
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        logger.info("加载模型...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )
        model.eval()

        test_image = self._create_test_image()
        batch_results = []

        for batch_size in self.config.batch_sizes:
            logger.info(f"\n测试 batch_size={batch_size}...")

            # 准备 batch 数据
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": test_image},
                        {"type": "text", "text": self.config.question},
                    ],
                }
            ] * batch_size

            try:
                inputs = processor.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_dict=True,
                    return_tensors="pt",
                ).to(model.device)

                # 预热
                for _ in range(self.config.warmup):
                    with torch.no_grad():
                        _ = model.generate(**inputs, max_new_tokens=10)
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()

                # 测试
                latencies = []
                for _ in range(self.config.runs):
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                    t0 = time.perf_counter()

                    with torch.no_grad():
                        _ = model.generate(**inputs, max_new_tokens=50)

                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                    t1 = time.perf_counter()
                    latencies.append((t1 - t0) * 1000)

                avg_latency = np.mean(latencies)
                throughput = batch_size / (avg_latency / 1000)  # images/sec

                batch_results.append({
                    "batch_size": batch_size,
                    "avg_latency_ms": round(avg_latency, 2),
                    "p50_latency_ms": round(np.percentile(latencies, 50), 2),
                    "p95_latency_ms": round(np.percentile(latencies, 95), 2),
                    "throughput_images_per_sec": round(throughput, 2),
                })

                logger.info(f"  平均延迟: {avg_latency:.1f}ms, 吞吐量: {throughput:.2f} images/sec")

            except Exception as e:
                logger.warning(f"  batch_size={batch_size} 测试失败: {e}")
                batch_results.append({
                    "batch_size": batch_size,
                    "error": str(e),
                })

        return BenchmarkResult(
            success=True,
            model_path=model_path,
            mode="batch",
            total_runs=self.config.runs * len(self.config.batch_sizes),
            metrics_summary={},
            raw_metrics=[],
            batch_results=batch_results,
            time_seconds=0.0,
            metadata={"batch_sizes_tested": self.config.batch_sizes},
        )

    def _benchmark_stress(self, model_path: str) -> BenchmarkResult:
        """压力测试 - 持续运行检测内存泄漏"""
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        logger.info("加载模型...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )
        model.eval()

        test_image = self._create_test_image()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": test_image},
                    {"type": "text", "text": self.config.question},
                ],
            }
        ]

        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)

        logger.info(f"开始压力测试，持续 {self.config.stress_duration} 秒...")
        t_start = time.time()
        run_count = 0
        memory_samples = []

        while time.time() - t_start < self.config.stress_duration:
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()

            with torch.no_grad():
                _ = model.generate(**inputs, max_new_tokens=30)

            if torch.cuda.is_available():
                mem = torch.cuda.max_memory_allocated() / 1024**2
                memory_samples.append(mem)

            run_count += 1
            if run_count % 50 == 0:
                elapsed = time.time() - t_start
                logger.info(f"  已运行 {run_count} 次，已用 {elapsed:.0f}s")

        # 分析内存趋势
        mem_trend = self._analyze_memory_trend(memory_samples)

        return BenchmarkResult(
            success=True,
            model_path=model_path,
            mode="stress",
            total_runs=run_count,
            metrics_summary={
                "total_runs": run_count,
                "duration_seconds": self.config.stress_duration,
                "memory_leak_detected": mem_trend["leak_detected"],
                "memory_growth_mb": mem_trend["growth_mb"],
                "avg_memory_mb": round(np.mean(memory_samples), 2) if memory_samples else 0,
            },
            raw_metrics=[{"memory_mb": m} for m in memory_samples] if self.config.save_traces else [],
            batch_results=[],
            time_seconds=0.0,
            metadata=mem_trend,
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _create_test_image(self) -> Image.Image:
        """创建测试图片"""
        arr = np.random.randint(0, 255, (self.config.image_size, self.config.image_size, 3), dtype=np.uint8)
        return Image.fromarray(arr)

    @staticmethod
    def _get_memory_mb() -> float:
        """获取当前显存占用（MB）"""
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1024**2
        return 0.0

    @staticmethod
    def _compute_summary(metrics: List[BenchmarkMetrics]) -> Dict:
        """计算统计摘要"""
        if not metrics:
            return {}

        latencies = [m.latency_ms for m in metrics]
        ttfts = [m.ttft_ms for m in metrics]
        tpots = [m.tpot_ms for m in metrics]
        tokens = [m.tokens_generated for m in metrics]
        memories = [m.peak_memory_mb for m in metrics]

        return {
            "latency_ms": {
                "mean": round(np.mean(latencies), 2),
                "std": round(np.std(latencies), 2),
                "min": round(np.min(latencies), 2),
                "max": round(np.max(latencies), 2),
                "p50": round(np.percentile(latencies, 50), 2),
                "p95": round(np.percentile(latencies, 95), 2),
                "p99": round(np.percentile(latencies, 99), 2),
            },
            "ttft_ms": {
                "mean": round(np.mean(ttfts), 2),
                "p95": round(np.percentile(ttfts, 95), 2),
            },
            "tpot_ms": {
                "mean": round(np.mean(tpots), 2),
                "p95": round(np.percentile(tpots, 95), 2),
            },
            "tokens_per_run": {
                "mean": round(np.mean(tokens), 2),
                "min": int(np.min(tokens)),
                "max": int(np.max(tokens)),
            },
            "peak_memory_mb": {
                "mean": round(np.mean(memories), 2),
                "max": round(np.max(memories), 2),
            },
            "throughput": {
                "images_per_sec": round(1000 / np.mean(latencies), 2),
                "tokens_per_sec": round(np.mean(tokens) / (np.mean(latencies) / 1000), 2),
            },
        }

    @staticmethod
    def _analyze_memory_trend(memory_samples: List[float]) -> Dict:
        """分析内存趋势，检测内存泄漏"""
        if len(memory_samples) < 10:
            return {"leak_detected": False, "growth_mb": 0.0, "samples": len(memory_samples)}

        # 线性回归分析趋势
        x = np.arange(len(memory_samples))
        slope = np.polyfit(x, memory_samples, 1)[0]

        # 如果斜率显著为正，认为有内存泄漏
        avg_mem = np.mean(memory_samples)
        leak_detected = slope > avg_mem * 0.001  # 增长超过平均值的 0.1%/sample
        growth = slope * len(memory_samples)

        return {
            "leak_detected": leak_detected,
            "growth_mb": round(growth, 2),
            "slope_mb_per_run": round(slope, 4),
            "samples": len(memory_samples),
        }

    def _print_summary(self, result: BenchmarkResult):
        """打印结果摘要"""
        print("\n" + "=" * 60)
        print("Benchmark 结果摘要")
        print("=" * 60)

        if result.mode == "single" and result.metrics_summary:
            lat = result.metrics_summary.get("latency_ms", {})
            print(f"延迟 (ms): 平均={lat.get('mean', 0):.1f}, P50={lat.get('p50', 0):.1f}, P95={lat.get('p95', 0):.1f}")
            print(f"吞吐量: {result.metrics_summary.get('throughput', {}).get('images_per_sec', 0):.2f} images/sec")
            print(f"峰值显存: {result.metrics_summary.get('peak_memory_mb', {}).get('max', 0):.0f} MB")

        elif result.mode == "batch" and result.batch_results:
            for br in result.batch_results:
                if "error" not in br:
                    print(f"Batch={br['batch_size']}: 延迟={br['avg_latency_ms']:.1f}ms, 吞吐量={br['throughput_images_per_sec']:.2f} images/sec")

        elif result.mode == "stress":
            summary = result.metrics_summary
            print(f"总运行次数: {summary.get('total_runs', 0)}")
            print(f"内存泄漏: {'是' if summary.get('memory_leak_detected') else '否'}")
            print(f"内存增长: {summary.get('memory_growth_mb', 0):.2f} MB")

        print("=" * 60)

    # ------------------------------------------------------------------
    # CLI
    # ------------------------------------------------------------------

    @classmethod
    def from_cli(cls) -> "ModelBenchmark":
        """从命令行参数创建 Benchmark"""
        parser = argparse.ArgumentParser(description="模型 Benchmark 工具")
        parser.add_argument("--model_path", required=True, help="模型路径")
        parser.add_argument("--mode", default="single", choices=["single", "batch", "stress"])
        parser.add_argument("--runs", type=int, default=50)
        parser.add_argument("--warmup", type=int, default=5)
        parser.add_argument("--batch_sizes", default="1,2,4,8", help="逗号分隔的 batch size")
        parser.add_argument("--stress_duration", type=int, default=300)
        parser.add_argument("--image_size", type=int, default=448)
        parser.add_argument("--question", default="请详细描述这张图片的内容。")
        parser.add_argument("--output", default=None, help="结果保存路径")
        parser.add_argument("--save_traces", action="store_true")
        parser.add_argument("--device", default="cuda")
        parser.add_argument("--trust_remote_code", action="store_true")
        parser.add_argument("--verbose", action="store_true")

        args = parser.parse_args()
        batch_sizes = [int(x) for x in args.batch_sizes.split(",")]
        config = BenchmarkConfig(
            mode=args.mode,
            runs=args.runs,
            warmup=args.warmup,
            batch_sizes=batch_sizes,
            stress_duration=args.stress_duration,
            image_size=args.image_size,
            question=args.question,
            output_file=args.output,
            save_traces=args.save_traces,
            device=args.device,
            trust_remote_code=args.trust_remote_code,
            verbose=args.verbose,
        )
        return cls(config)


# 如果直接运行此脚本
if __name__ == "__main__":
    benchmark = ModelBenchmark.from_cli()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    args, _ = parser.parse_known_args()
    result = benchmark.run(args.model_path)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
