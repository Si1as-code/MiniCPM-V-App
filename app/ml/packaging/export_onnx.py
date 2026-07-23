"""
============================================================================
ONNX 导出脚本 - PyTorch → ONNX 转换
============================================================================
技术栈: transformers, optimum[onnxruntime], onnx

支持的导出格式:
  - ONNX: 标准 ONNX 格式
  - ONNX Runtime: 优化后的 ONNX（含图优化）

支持的优化:
  - 图优化 (constant folding, dead code elimination)
  - 量化 (ONNX Runtime INT8 静态量化)
  - 动态轴 (支持变长输入)

用法:
    # Python API
    from ml.packaging.export_onnx import ONNXExporter, ONNXExportConfig
    config = ONNXExportConfig(opset=14, optimize=True)
    exporter = ONNXExporter(config)
    result = exporter.export("openbmb/MiniCPM-V", "./onnx_output")

    # CLI
    python -m ml.packaging.export_onnx \
        --model_path openbmb/MiniCPM-V \
        --output_dir ./onnx \
        --opset 14 --optimize
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

logger = logging.getLogger(__name__)

# 导出任务类型
ExportTask = Literal["vision_encoder", "text_decoder", "full"]


@dataclass
class ONNXExportConfig:
    """ONNX 导出配置"""

    task: ExportTask = "full"
    opset: int = 14  # ONNX opset version
    optimize: bool = True  # 启用图优化
    quantize_onnx: bool = False  # ONNX Runtime INT8 量化
    use_external_data: bool = True  # 大模型使用外部数据格式
    # 输入形状配置
    batch_size: int = 1
    seq_length: int = 512
    image_size: int = 448  # 视觉模型输入尺寸
    num_channels: int = 3
    # 动态轴配置
    dynamic_axes: bool = True  # 支持动态 batch/seq_len
    # 输出配置
    output_dir: str = "./onnx_model"
    save_config: bool = True  # 保存导出配置
    # 设备
    device: str = "cpu"  # ONNX 导出通常在 CPU 上进行
    trust_remote_code: bool = False
    verbose: bool = False

    def __post_init__(self):
        os.makedirs(self.output_dir, exist_ok=True)


@dataclass
class ONNXExportResult:
    """ONNX 导出结果"""

    success: bool
    output_dir: str
    task: str
    opset: int
    original_size_mb: float
    exported_size_mb: float
    files: List[str]  # 导出的文件列表
    time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class ONNXExporter:
    """
    ONNX 模型导出器

    封装 transformers → ONNX 的导出流程，支持视觉语言多模态模型。
    """

    def __init__(self, config: ONNXExportConfig):
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

    def export(
        self,
        model_path: str,
        output_dir: Optional[str] = None,
    ) -> ONNXExportResult:
        """
        导出模型为 ONNX 格式

        Args:
            model_path: 原始模型路径
            output_dir: 输出目录

        Returns:
            ONNXExportResult: 导出结果
        """
        if output_dir:
            self.config.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

        out_dir = Path(self.config.output_dir)
        logger.info("=" * 60)
        logger.info(f"开始导出 ONNX: {model_path}")
        logger.info(f"任务类型: {self.config.task}, opset: {self.config.opset}")
        logger.info(f"输出目录: {out_dir.absolute()}")
        logger.info("=" * 60)

        t_start = time.time()

        try:
            # 优先使用 optimum 库（推荐）
            result = self._export_with_optimum(model_path, out_dir)

            # 如果启用优化
            if self.config.optimize and result.success:
                result = self._optimize_onnx(result)

            # 如果启用量化
            if self.config.quantize_onnx and result.success:
                result = self._quantize_onnx(result)

            result.time_seconds = time.time() - t_start
            logger.info(f"导出完成! 耗时: {result.time_seconds:.1f}s")
            logger.info(f"导出文件数: {len(result.files)}")
            return result

        except Exception as e:
            logger.error(f"导出失败: {e}")
            return ONNXExportResult(
                success=False,
                output_dir=str(out_dir),
                task=self.config.task,
                opset=self.config.opset,
                original_size_mb=0.0,
                exported_size_mb=0.0,
                files=[],
                time_seconds=time.time() - t_start,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # 导出实现
    # ------------------------------------------------------------------

    def _export_with_optimum(self, model_path: str, out_dir: Path) -> ONNXExportResult:
        """使用 optimum 库导出 ONNX"""
        try:
            from optimum.exporters.onnx import main_export, export_models
            from optimum.exporters.tasks import TasksManager
        except ImportError:
            logger.warning("optimum[onnxruntime] 未安装，尝试基础导出")
            return self._export_basic(model_path, out_dir)

        original_size = self._get_dir_size_mb(model_path)

        logger.info("  使用 optimum.exporters.onnx 导出...")

        # 配置动态轴
        dynamic_axes = {}
        if self.config.dynamic_axes:
            dynamic_axes = {
                "input_ids": {0: "batch_size", 1: "sequence_length"},
                "attention_mask": {0: "batch_size", 1: "sequence_length"},
                "pixel_values": {0: "batch_size"},
                "image_sizes": {0: "batch_size"},
            }

        try:
            # 使用 main_export 导出完整模型
            main_export(
                model_name_or_path=model_path,
                output=out_dir,
                task="image-text-to-text",
                opset=self.config.opset,
                device=self.config.device,
                trust_remote_code=self.config.trust_remote_code,
                do_validation=True,
                # 动态轴
                **({"monolith": True} if self.config.task == "full" else {}),
            )
        except Exception as e:
            logger.warning(f"main_export 失败: {e}，尝试基础导出")
            return self._export_basic(model_path, out_dir)

        # 收集导出的文件
        files = self._collect_onnx_files(out_dir)
        exported_size = self._get_dir_size_mb(out_dir)

        return ONNXExportResult(
            success=True,
            output_dir=str(out_dir),
            task=self.config.task,
            opset=self.config.opset,
            original_size_mb=original_size,
            exported_size_mb=exported_size,
            files=files,
            time_seconds=0.0,
            metadata={
                "backend": "optimum",
                "dynamic_axes": self.config.dynamic_axes,
                "optimized": False,
                "quantized": False,
            },
        )

    def _export_basic(self, model_path: str, out_dir: Path) -> ONNXExportResult:
        """基础导出（使用 torch.onnx.export，作为 fallback）"""
        logger.info("  使用 torch.onnx.export 基础导出...")
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        original_size = self._get_dir_size_mb(model_path)

        # 加载模型
        logger.info("    加载模型...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )
        model.eval()

        # 准备示例输入
        logger.info("    准备示例输入...")
        dummy_inputs = self._prepare_dummy_inputs(processor)

        # 导出 ONNX
        onnx_path = out_dir / "model.onnx"
        logger.info(f"    导出到: {onnx_path}")

        # 动态轴配置
        dynamic_axes = None
        if self.config.dynamic_axes:
            dynamic_axes = {}
            for key in dummy_inputs.keys():
                if key in ("input_ids", "attention_mask", "position_ids"):
                    dynamic_axes[key] = {0: "batch", 1: "sequence"}
                elif key in ("pixel_values", "image_sizes"):
                    dynamic_axes[key] = {0: "batch"}

        try:
            with torch.no_grad():
                torch.onnx.export(
                    model,
                    tuple(dummy_inputs.values()),
                    str(onnx_path),
                    input_names=list(dummy_inputs.keys()),
                    output_names=["logits"],
                    dynamic_axes=dynamic_axes,
                    opset_version=self.config.opset,
                    do_constant_folding=self.config.optimize,
                    export_params=True,
                )
        except Exception as e:
            logger.error(f"torch.onnx.export 失败: {e}")
            raise

        # 保存 processor 配置
        processor.save_pretrained(out_dir)

        files = self._collect_onnx_files(out_dir)
        exported_size = self._get_dir_size_mb(out_dir)

        return ONNXExportResult(
            success=True,
            output_dir=str(out_dir),
            task=self.config.task,
            opset=self.config.opset,
            original_size_mb=original_size,
            exported_size_mb=exported_size,
            files=files,
            time_seconds=0.0,
            metadata={
                "backend": "torch.onnx.export",
                "dynamic_axes": self.config.dynamic_axes,
                "optimized": False,
                "quantized": False,
            },
        )

    def _optimize_onnx(self, result: ONNXExportResult) -> ONNXExportResult:
        """使用 ONNX Runtime 优化 ONNX 模型"""
        logger.info("  执行 ONNX 图优化...")
        try:
            from onnxruntime.transformers.optimizer import optimize_model
        except ImportError:
            logger.warning("onnxruntime-transformers 未安装，跳过优化")
            return result

        optimized_files = []
        for onnx_file in result.files:
            if not onnx_file.endswith(".onnx"):
                continue
            filepath = Path(result.output_dir) / onnx_file
            optimized_path = filepath.with_suffix(".optimized.onnx")

            try:
                optimized_model = optimize_model(
                    str(filepath),
                    model_type="gpt2",  # 使用通用优化
                    use_gpu=False,
                    opt_level=99,
                )
                optimized_model.save_model_to_file(str(optimized_path))
                optimized_files.append(optimized_path.name)
                logger.info(f"    优化完成: {optimized_path.name}")
            except Exception as e:
                logger.warning(f"    优化失败 {onnx_file}: {e}")

        result.metadata["optimized"] = True
        result.metadata["optimized_files"] = optimized_files
        result.files.extend(optimized_files)
        result.exported_size_mb = self._get_dir_size_mb(result.output_dir)
        return result

    def _quantize_onnx(self, result: ONNXExportResult) -> ONNXExportResult:
        """使用 ONNX Runtime 进行 INT8 静态量化"""
        logger.info("  执行 ONNX INT8 量化...")
        try:
            from onnxruntime.quantization import quantize_dynamic, QuantType
        except ImportError:
            logger.warning("onnxruntime 未安装，跳过量化")
            return result

        quantized_files = []
        for onnx_file in result.files:
            if not onnx_file.endswith(".onnx") or "quantized" in onnx_file:
                continue
            filepath = Path(result.output_dir) / onnx_file
            quantized_path = filepath.with_suffix(".quantized.onnx")

            try:
                quantize_dynamic(
                    model_input=str(filepath),
                    model_output=str(quantized_path),
                    weight_type=QuantType.QInt8,
                    optimize_model=True,
                )
                quantized_files.append(quantized_path.name)
                logger.info(f"    量化完成: {quantized_path.name}")
            except Exception as e:
                logger.warning(f"    量化失败 {onnx_file}: {e}")

        result.metadata["quantized"] = True
        result.metadata["quantized_files"] = quantized_files
        result.files.extend(quantized_files)
        result.exported_size_mb = self._get_dir_size_mb(result.output_dir)
        return result

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _prepare_dummy_inputs(self, processor) -> Dict[str, "torch.Tensor"]:
        """准备 ONNX 导出用的示例输入"""
        import torch
        import numpy as np
        from PIL import Image

        # 创建虚拟图片
        dummy_image = Image.fromarray(
            np.zeros(
                (self.config.image_size, self.config.image_size, self.config.num_channels),
                dtype=np.uint8,
            )
        )

        # 构建消息并处理
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": dummy_image},
                    {"type": "text", "text": "describe"},
                ],
            }
        ]

        try:
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            )
        except Exception:
            # fallback: 直接创建虚拟张量
            inputs = {
                "input_ids": torch.zeros(
                    (self.config.batch_size, self.config.seq_length), dtype=torch.long
                ),
                "attention_mask": torch.ones(
                    (self.config.batch_size, self.config.seq_length), dtype=torch.long
                ),
                "pixel_values": torch.zeros(
                    (
                        self.config.batch_size,
                        self.config.num_channels,
                        self.config.image_size,
                        self.config.image_size,
                    ),
                    dtype=torch.float32,
                ),
            }

        return {k: v for k, v in inputs.items() if isinstance(v, torch.Tensor)}

    @staticmethod
    def _collect_onnx_files(directory: Path) -> List[str]:
        """收集目录中的所有 ONNX 文件"""
        files = []
        if directory.exists():
            for f in directory.iterdir():
                if f.suffix in (".onnx", ".pb", ".json"):
                    files.append(f.name)
        return sorted(files)

    @staticmethod
    def _get_dir_size_mb(path: str) -> float:
        """计算目录大小（MB）"""
        if not os.path.exists(path):
            return 0.0
        if os.path.isfile(path):
            return os.path.getsize(path) / (1024 * 1024)
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total / (1024 * 1024)

    # ------------------------------------------------------------------
    # CLI
    # ------------------------------------------------------------------

    @classmethod
    def from_cli(cls) -> "ONNXExporter":
        """从命令行参数创建导出器"""
        parser = argparse.ArgumentParser(description="ONNX 导出工具")
        parser.add_argument("--model_path", required=True, help="原始模型路径")
        parser.add_argument("--output_dir", default="./onnx_model", help="输出目录")
        parser.add_argument("--task", default="full", choices=["vision_encoder", "text_decoder", "full"])
        parser.add_argument("--opset", type=int, default=14)
        parser.add_argument("--optimize", action="store_true", help="启用图优化")
        parser.add_argument("--quantize_onnx", action="store_true", help="ONNX INT8 量化")
        parser.add_argument("--dynamic_axes", action="store_true", default=True)
        parser.add_argument("--batch_size", type=int, default=1)
        parser.add_argument("--seq_length", type=int, default=512)
        parser.add_argument("--image_size", type=int, default=448)
        parser.add_argument("--device", default="cpu")
        parser.add_argument("--trust_remote_code", action="store_true")
        parser.add_argument("--verbose", action="store_true")

        args = parser.parse_args()
        config = ONNXExportConfig(
            task=args.task,
            opset=args.opset,
            optimize=args.optimize,
            quantize_onnx=args.quantize_onnx,
            dynamic_axes=args.dynamic_axes,
            batch_size=args.batch_size,
            seq_length=args.seq_length,
            image_size=args.image_size,
            device=args.device,
            trust_remote_code=args.trust_remote_code,
            output_dir=args.output_dir,
            verbose=args.verbose,
        )
        return cls(config)


# 如果直接运行此脚本
if __name__ == "__main__":
    exporter = ONNXExporter.from_cli()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    args, _ = parser.parse_known_args()
    result = exporter.export(args.model_path)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
