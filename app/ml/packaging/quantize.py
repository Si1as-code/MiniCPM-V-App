"""
============================================================================
模型量化脚本 - 支持 GPTQ / AWQ / INT8 / INT4
============================================================================
技术栈: transformers, optimum, auto-gptq (可选), bitsandbytes (可选)

支持的量化方案:
  - INT8: 使用 LLM.int8() 或 optimum.quanto
  - INT4 (GPTQ): 使用 AutoGPTQ 或 optimum.gptq
  - INT4 (AWQ): 使用 AutoAWQ
  - FP16: 半精度（非量化，仅格式转换）

用法:
    # Python API
    from ml.packaging.quantize import ModelQuantizer, QuantizationConfig
    config = QuantizationConfig(method="gptq", bits=4, group_size=128)
    quantizer = ModelQuantizer(config)
    result = quantizer.quantize("openbmb/MiniCPM-V", "./output")

    # CLI
    python -m ml.packaging.quantize \
        --model_path openbmb/MiniCPM-V \
        --output_dir ./quantized \
        --method gptq --bits 4
============================================================================
"""

import argparse
import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# 量化方法类型
QuantMethod = Literal["gptq", "awq", "int8", "fp16", "none"]


@dataclass
class QuantizationConfig:
    """量化配置"""

    method: QuantMethod = "gptq"
    bits: int = 4  # 4 / 8
    group_size: int = 128  # GPTQ group size
    desc_act: bool = False  # GPTQ desc_act
    damp_percent: float = 0.1  # GPTQ damp
    awq_version: str = "gemm"  # AWQ: gemm / gemv
    device: str = "cuda"  # 量化使用的设备
    trust_remote_code: bool = False
    use_triton: bool = False  # GPTQ Triton kernel
    use_cuda_fp16: bool = True  # GPTQ CUDA FP16
    batch_size: int = 1  # 校准 batch size
    calibration_dataset: Optional[str] = None  # 校准数据集路径
    max_calib_samples: int = 128  # 最大校准样本数
    seqlen: int = 2048  # 校准序列长度
    # 输出配置
    output_dir: str = "./quantized_model"
    safe_serialization: bool = True  # 使用 safetensors
    # 日志
    verbose: bool = False

    def __post_init__(self):
        if self.method in ("gptq", "awq") and self.bits not in (2, 3, 4, 8):
            raise ValueError(f"不支持的 bits: {self.bits}")
        if self.method == "int8" and self.bits != 8:
            self.bits = 8
        os.makedirs(self.output_dir, exist_ok=True)


@dataclass
class QuantizationResult:
    """量化结果"""

    success: bool
    output_dir: str
    method: str
    bits: int
    original_size_mb: float
    quantized_size_mb: float
    compression_ratio: float
    time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class ModelQuantizer:
    """
    模型量化器

    封装多种量化方案，提供统一的量化接口。
    """

    def __init__(self, config: QuantizationConfig):
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

    def quantize(
        self,
        model_path: str,
        output_dir: Optional[str] = None,
    ) -> QuantizationResult:
        """
        执行模型量化

        Args:
            model_path: 原始模型路径 (Hugging Face Hub 或本地)
            output_dir: 输出目录 (覆盖 config.output_dir)

        Returns:
            QuantizationResult: 量化结果
        """
        if output_dir:
            self.config.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

        out_dir = Path(self.config.output_dir)
        logger.info("=" * 60)
        logger.info(f"开始量化模型: {model_path}")
        logger.info(f"量化方法: {self.config.method}, {self.config.bits}bit")
        logger.info(f"输出目录: {out_dir.absolute()}")
        logger.info("=" * 60)

        t_start = time.time()

        try:
            if self.config.method == "none":
                result = self._quantize_none(model_path, out_dir)
            elif self.config.method == "fp16":
                result = self._quantize_fp16(model_path, out_dir)
            elif self.config.method == "int8":
                result = self._quantize_int8(model_path, out_dir)
            elif self.config.method == "gptq":
                result = self._quantize_gptq(model_path, out_dir)
            elif self.config.method == "awq":
                result = self._quantize_awq(model_path, out_dir)
            else:
                raise ValueError(f"不支持的量化方法: {self.config.method}")

            result.time_seconds = time.time() - t_start
            logger.info(f"量化完成! 耗时: {result.time_seconds:.1f}s")
            logger.info(f"压缩比: {result.compression_ratio:.2f}x")
            return result

        except Exception as e:
            logger.error(f"量化失败: {e}")
            return QuantizationResult(
                success=False,
                output_dir=str(out_dir),
                method=self.config.method,
                bits=self.config.bits,
                original_size_mb=0.0,
                quantized_size_mb=0.0,
                compression_ratio=0.0,
                time_seconds=time.time() - t_start,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # 量化实现
    # ------------------------------------------------------------------

    def _quantize_none(self, model_path: str, out_dir: Path) -> QuantizationResult:
        """不量化，仅复制模型（用于测试和对比）"""
        logger.info("模式: 仅复制模型（不量化）")
        original_size = self._get_dir_size_mb(model_path)

        # 复制模型文件
        if os.path.isdir(model_path):
            shutil.copytree(model_path, out_dir, dirs_exist_ok=True)
        else:
            shutil.copy2(model_path, out_dir)

        quantized_size = self._get_dir_size_mb(out_dir)
        return QuantizationResult(
            success=True,
            output_dir=str(out_dir),
            method="none",
            bits=16,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=1.0,
            time_seconds=0.0,
            metadata={"note": "原始模型，未量化"},
        )

    def _quantize_fp16(self, model_path: str, out_dir: Path) -> QuantizationResult:
        """FP16 转换（半精度）"""
        logger.info("模式: FP16 半精度转换")
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        original_size = self._get_dir_size_mb(model_path)

        # 加载模型并转换
        logger.info("  加载模型...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        # 保存
        logger.info("  保存 FP16 模型...")
        model.save_pretrained(
            out_dir,
            safe_serialization=self.config.safe_serialization,
        )
        processor.save_pretrained(out_dir)

        quantized_size = self._get_dir_size_mb(out_dir)
        return QuantizationResult(
            success=True,
            output_dir=str(out_dir),
            method="fp16",
            bits=16,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=original_size / quantized_size if quantized_size > 0 else 1.0,
            time_seconds=0.0,
            metadata={"torch_dtype": "float16"},
        )

    def _quantize_int8(self, model_path: str, out_dir: Path) -> QuantizationResult:
        """INT8 量化 - 使用 bitsandbytes LLM.int8()"""
        logger.info("模式: INT8 量化 (bitsandbytes)")
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig

        original_size = self._get_dir_size_mb(model_path)

        # 配置 INT8
        bnb_config = BitsAndBytesConfig(load_in_8bit=True)

        logger.info("  加载模型 (INT8)...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        logger.info("  保存 INT8 模型...")
        model.save_pretrained(
            out_dir,
            safe_serialization=self.config.safe_serialization,
        )
        processor.save_pretrained(out_dir)

        quantized_size = self._get_dir_size_mb(out_dir)
        return QuantizationResult(
            success=True,
            output_dir=str(out_dir),
            method="int8",
            bits=8,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=original_size / quantized_size if quantized_size > 0 else 1.0,
            time_seconds=0.0,
            metadata={"backend": "bitsandbytes"},
        )

    def _quantize_gptq(self, model_path: str, out_dir: Path) -> QuantizationResult:
        """GPTQ INT4 量化"""
        logger.info(f"模式: GPTQ {self.config.bits}bit 量化")

        try:
            from optimum.gptq import GPTQQuantizer, load_dataset
        except ImportError:
            logger.error("optimum[gptq] 未安装，尝试使用 auto-gptq")
            return self._quantize_gptq_auto(model_path, out_dir)

        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor, AutoTokenizer

        original_size = self._get_dir_size_mb(model_path)

        # 加载校准数据
        logger.info("  准备校准数据集...")
        calibration_dataset = self._load_calibration_data()

        # 加载模型（FP16）
        logger.info("  加载模型 (FP16)...")
        model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        # 配置 GPTQ
        logger.info(f"  配置 GPTQ: bits={self.config.bits}, group_size={self.config.group_size}")
        quantizer = GPTQQuantizer(
            bits=self.config.bits,
            dataset=calibration_dataset,
            group_size=self.config.group_size,
            desc_act=self.config.desc_act,
            damp_percent=self.config.damp_percent,
        )

        # 执行量化
        logger.info("  执行 GPTQ 量化（这可能需要很长时间）...")
        model = quantizer.quantize_model(model, tokenizer)

        # 保存
        logger.info("  保存量化模型...")
        model.save_pretrained(
            out_dir,
            safe_serialization=self.config.safe_serialization,
        )
        processor.save_pretrained(out_dir)
        tokenizer.save_pretrained(out_dir)

        quantized_size = self._get_dir_size_mb(out_dir)
        return QuantizationResult(
            success=True,
            output_dir=str(out_dir),
            method="gptq",
            bits=self.config.bits,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=original_size / quantized_size if quantized_size > 0 else 1.0,
            time_seconds=0.0,
            metadata={
                "group_size": self.config.group_size,
                "desc_act": self.config.desc_act,
                "backend": "optimum.gptq",
            },
        )

    def _quantize_gptq_auto(self, model_path: str, out_dir: Path) -> QuantizationResult:
        """使用 auto-gptq 进行量化（fallback）"""
        try:
            from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig
        except ImportError:
            raise ImportError(
                "GPTQ 量化需要安装 optimum[gptq] 或 auto-gptq:\n"
                "  pip install optimum[gpq]\n"
                "  或\n"
                "  pip install auto-gptq"
            )

        logger.info("  使用 auto-gptq 后端")
        original_size = self._get_dir_size_mb(model_path)

        # 配置
        quantize_config = BaseQuantizeConfig(
            bits=self.config.bits,
            group_size=self.config.group_size,
            desc_act=self.config.desc_act,
            damp_percent=self.config.damp_percent,
        )

        # 加载校准数据
        calibration_dataset = self._load_calibration_data()

        # 加载并量化
        logger.info("  加载并量化模型...")
        model = AutoGPTQForCausalLM.from_pretrained(
            model_path,
            quantize_config,
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )
        model.quantize(calibration_dataset)

        # 保存
        logger.info("  保存量化模型...")
        model.save_quantized(
            out_dir,
            use_safetensors=self.config.safe_serialization,
        )

        quantized_size = self._get_dir_size_mb(out_dir)
        return QuantizationResult(
            success=True,
            output_dir=str(out_dir),
            method="gptq",
            bits=self.config.bits,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=original_size / quantized_size if quantized_size > 0 else 1.0,
            time_seconds=0.0,
            metadata={
                "group_size": self.config.group_size,
                "backend": "auto-gptq",
            },
        )

    def _quantize_awq(self, model_path: str, out_dir: Path) -> QuantizationResult:
        """AWQ INT4 量化"""
        logger.info(f"模式: AWQ {self.config.bits}bit 量化")

        try:
            from awq import AutoAWQForCausalLM
        except ImportError:
            raise ImportError(
                "AWQ 量化需要安装 auto-awq:\n"
                "  pip install auto-awq"
            )

        original_size = self._get_dir_size_mb(model_path)

        # 加载校准数据
        calibration_dataset = self._load_calibration_data()

        # 加载模型
        logger.info("  加载模型...")
        model = AutoAWQForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            trust_remote_code=self.config.trust_remote_code,
        )

        # 执行量化
        logger.info("  执行 AWQ 量化...")
        model.quantize(
            tokenizer=None,  # AWQ 可能不需要 tokenizer
            quant_config={
                "zero_point": True,
                "q_group_size": self.config.group_size,
                "w_bit": self.config.bits,
                "version": self.config.awq_version,
            },
        )

        # 保存
        logger.info("  保存量化模型...")
        model.save_quantized(out_dir)

        quantized_size = self._get_dir_size_mb(out_dir)
        return QuantizationResult(
            success=True,
            output_dir=str(out_dir),
            method="awq",
            bits=self.config.bits,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=original_size / quantized_size if quantized_size > 0 else 1.0,
            time_seconds=0.0,
            metadata={
                "group_size": self.config.group_size,
                "version": self.config.awq_version,
                "backend": "auto-awq",
            },
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _load_calibration_data(self) -> List[str]:
        """加载校准数据集"""
        if self.config.calibration_dataset and os.path.exists(self.config.calibration_dataset):
            logger.info(f"  从文件加载校准数据: {self.config.calibration_dataset}")
            with open(self.config.calibration_dataset, "r", encoding="utf-8") as f:
                data = f.read().strip().split("\n")
            return data[: self.config.max_calib_samples]

        # 默认校准数据（简短文本样本）
        logger.info("  使用默认校准数据")
        default_data = [
            "请描述这张图片的内容。",
            "这张图片中有哪些物体？",
            "图片中的文字是什么？",
            "请识别图片中的场景。",
            "这张图是什么风格的？",
        ]
        # 重复扩展到需要的样本数
        repeated = []
        while len(repeated) < self.config.max_calib_samples:
            repeated.extend(default_data)
        return repeated[: self.config.max_calib_samples]

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
    def from_cli(cls) -> "ModelQuantizer":
        """从命令行参数创建量化器"""
        parser = argparse.ArgumentParser(description="模型量化工具")
        parser.add_argument("--model_path", required=True, help="原始模型路径")
        parser.add_argument("--output_dir", default="./quantized_model", help="输出目录")
        parser.add_argument("--method", default="gptq", choices=["gptq", "awq", "int8", "fp16", "none"])
        parser.add_argument("--bits", type=int, default=4, choices=[2, 3, 4, 8])
        parser.add_argument("--group_size", type=int, default=128)
        parser.add_argument("--desc_act", action="store_true", help="GPTQ desc_act")
        parser.add_argument("--calibration_dataset", default=None, help="校准数据集路径")
        parser.add_argument("--max_calib_samples", type=int, default=128)
        parser.add_argument("--device", default="cuda")
        parser.add_argument("--trust_remote_code", action="store_true")
        parser.add_argument("--verbose", action="store_true")

        args = parser.parse_args()
        config = QuantizationConfig(
            method=args.method,
            bits=args.bits,
            group_size=args.group_size,
            desc_act=args.desc_act,
            calibration_dataset=args.calibration_dataset,
            max_calib_samples=args.max_calib_samples,
            device=args.device,
            trust_remote_code=args.trust_remote_code,
            output_dir=args.output_dir,
            verbose=args.verbose,
        )
        return cls(config)


# 如果直接运行此脚本
if __name__ == "__main__":
    quantizer = ModelQuantizer.from_cli()
    args = argparse.Namespace()
    # 重新解析获取 model_path
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    args, _ = parser.parse_known_args()
    result = quantizer.quantize(args.model_path)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
