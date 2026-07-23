"""
============================================================================
模型发布脚本 - Artifact 打包与上传
============================================================================
技术栈: boto3 (S3), oss2 (阿里云), cos-python-sdk (腾讯云)

支持的目标:
  - local: 本地目录（仅打包）
  - s3: AWS S3 / MinIO
  - oss: 阿里云 OSS
  - cos: 腾讯云 COS
  - hf: Hugging Face Hub

打包内容:
  - 模型权重 (safetensors / bin)
  - 配置文件 (config.json, preprocessor_config.json)
  - 分词器文件 (tokenizer.json, vocab.txt)
  - 量化配置 (quantize_config.json)
  - 模型卡片 (README.md, 自动生成)
  - 校验文件 (SHA256 checksums)

用法:
    # Python API
    from ml.packaging.publish import ModelPublisher, PublishConfig
    config = PublishConfig(target="oss", bucket="my-bucket")
    publisher = ModelPublisher(config)
    result = publisher.publish("./quantized_model", "MiniCPM-V-INT4-v1.0")

    # CLI
    python -m ml.packaging.publish \
        --model_dir ./quantized_model \
        --target oss \
        --bucket my-bucket \
        --version v1.0
============================================================================
"""

import argparse
import hashlib
import json
import logging
import os
import tarfile
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

# 发布目标
PublishTarget = Literal["local", "s3", "oss", "cos", "hf"]

# 打包格式
PackageFormat = Literal["dir", "tar.gz", "zip"]


@dataclass
class PublishConfig:
    """发布配置"""

    target: PublishTarget = "local"
    # 本地配置
    output_dir: str = "./published"
    package_format: PackageFormat = "tar.gz"
    # S3 / OSS / COS 配置
    bucket: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None  # 自定义端点（MinIO）
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    # Hugging Face 配置
    hf_repo_id: Optional[str] = None
    hf_token: Optional[str] = None
    private: bool = True
    # 版本配置
    version_prefix: str = ""  # 版本前缀，如 "v1.0/"
    # 元数据
    model_card_template: Optional[str] = None  # 模型卡片模板路径
    tags: List[str] = field(default_factory=list)
    # 其他
    dry_run: bool = False  # 仅模拟，不上传
    verbose: bool = False

    def __post_init__(self):
        os.makedirs(self.output_dir, exist_ok=True)
        # 从环境变量读取凭证
        if not self.access_key:
            self.access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("OSS_ACCESS_KEY")
        if not self.secret_key:
            self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("OSS_SECRET_KEY")
        if not self.hf_token:
            self.hf_token = os.getenv("HF_TOKEN")


@dataclass
class PublishResult:
    """发布结果"""

    success: bool
    model_dir: str
    version: str
    target: str
    package_path: Optional[str]
    uploaded_files: List[str]
    checksums: Dict[str, str]
    model_card_path: Optional[str]
    total_size_mb: float
    time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class ModelPublisher:
    """
    模型发布工具

    负责模型 artifact 的打包、校验和上传。
    """

    def __init__(self, config: PublishConfig):
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

    def publish(self, model_dir: str, version: str) -> PublishResult:
        """
        发布模型

        Args:
            model_dir: 模型目录路径
            version: 版本号（如 "v1.0"）

        Returns:
            PublishResult: 发布结果
        """
        logger.info("=" * 60)
        logger.info(f"开始发布模型: {model_dir}")
        logger.info(f"版本: {version}, 目标: {self.config.target}")
        logger.info("=" * 60)

        t_start = time.time()

        try:
            # 1. 验证模型目录
            self._validate_model_dir(model_dir)

            # 2. 生成模型卡片
            model_card_path = self._generate_model_card(model_dir, version)

            # 3. 计算校验和
            checksums = self._compute_checksums(model_dir)
            self._save_checksums(model_dir, checksums)

            # 4. 打包
            package_path = self._package_model(model_dir, version)

            # 5. 上传
            uploaded_files = []
            if not self.config.dry_run:
                uploaded_files = self._upload(model_dir, version, package_path)
            else:
                logger.info("[Dry Run] 跳过上传")

            total_size = self._get_dir_size_mb(model_dir)

            return PublishResult(
                success=True,
                model_dir=model_dir,
                version=version,
                target=self.config.target,
                package_path=package_path,
                uploaded_files=uploaded_files,
                checksums=checksums,
                model_card_path=model_card_path,
                total_size_mb=total_size,
                time_seconds=time.time() - t_start,
                metadata={"dry_run": self.config.dry_run},
            )

        except Exception as e:
            logger.error(f"发布失败: {e}")
            import traceback
            traceback.print_exc()
            return PublishResult(
                success=False,
                model_dir=model_dir,
                version=version,
                target=self.config.target,
                package_path=None,
                uploaded_files=[],
                checksums={},
                model_card_path=None,
                total_size_mb=0.0,
                time_seconds=time.time() - t_start,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # 实现
    # ------------------------------------------------------------------

    def _validate_model_dir(self, model_dir: str):
        """验证模型目录结构"""
        path = Path(model_dir)
        if not path.exists():
            raise FileNotFoundError(f"模型目录不存在: {model_dir}")

        # 检查必需文件
        required_files = ["config.json"]
        missing = [f for f in required_files if not (path / f).exists()]
        if missing:
            logger.warning(f"缺少推荐文件: {missing}")

        logger.info(f"模型目录验证通过: {model_dir}")

    def _generate_model_card(self, model_dir: str, version: str) -> Optional[str]:
        """生成模型卡片 README.md"""
        readme_path = Path(model_dir) / "README.md"

        # 如果已存在且提供了模板，则不覆盖
        if readme_path.exists() and not self.config.model_card_template:
            logger.info("模型卡片已存在，跳过生成")
            return str(readme_path)

        # 读取模板或生成默认卡片
        if self.config.model_card_template and os.path.exists(self.config.model_card_template):
            with open(self.config.model_card_template, "r", encoding="utf-8") as f:
                template = f.read()
        else:
            template = self._default_model_card_template()

        # 填充模板
        model_card = template.format(
            version=version,
            model_name=Path(model_dir).name,
            tags=", ".join(self.config.tags),
            date=time.strftime("%Y-%m-%d"),
        )

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(model_card)

        logger.info(f"模型卡片已生成: {readme_path}")
        return str(readme_path)

    def _default_model_card_template(self) -> str:
        """默认模型卡片模板"""
        return """---
language: zh
tags:
  - vision-language-model
  - image-text-to-text
  - quantized
---

# {model_name}

## 版本信息

- **版本**: {version}
- **发布日期**: {date}
- **标签**: {tags}

## 模型描述

这是 MiniCPM-V 端侧视觉助手项目的模型 artifact。

## 使用方式

```python
from transformers import AutoModelForImageTextToText, AutoProcessor

model = AutoModelForImageTextToText.from_pretrained("{model_name}")
processor = AutoProcessor.from_pretrained("{model_name}")
```

## 许可

请遵循原始模型许可协议。
"""

    def _compute_checksums(self, model_dir: str) -> Dict[str, str]:
        """计算文件 SHA256 校验和"""
        logger.info("计算文件校验和...")
        checksums = {}
        path = Path(model_dir)

        for filepath in sorted(path.rglob("*")):
            if filepath.is_file():
                rel_path = filepath.relative_to(path).as_posix()
                sha256 = hashlib.sha256()
                with open(filepath, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
                checksums[rel_path] = sha256.hexdigest()

        logger.info(f"已计算 {len(checksums)} 个文件的校验和")
        return checksums

    def _save_checksums(self, model_dir: str, checksums: Dict[str, str]):
        """保存校验和到文件"""
        checksum_path = Path(model_dir) / "checksums.sha256"
        with open(checksum_path, "w", encoding="utf-8") as f:
            for filename, checksum in sorted(checksums.items()):
                f.write(f"{checksum}  {filename}\n")
        logger.info(f"校验和已保存: {checksum_path}")

    def _package_model(self, model_dir: str, version: str) -> Optional[str]:
        """打包模型"""
        if self.config.package_format == "dir":
            logger.info("打包格式: 目录（不打包）")
            return None

        package_name = f"{Path(model_dir).name}-{version}"
        package_path = Path(self.config.output_dir) / f"{package_name}.{self.config.package_format}"

        logger.info(f"打包模型: {package_path}")

        if self.config.package_format == "tar.gz":
            with tarfile.open(package_path, "w:gz") as tar:
                tar.add(model_dir, arcname=package_name)
        elif self.config.package_format == "zip":
            with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for filepath in Path(model_dir).rglob("*"):
                    if filepath.is_file():
                        arcname = f"{package_name}/{filepath.relative_to(model_dir)}"
                        zf.write(filepath, arcname)

        size_mb = os.path.getsize(package_path) / (1024 * 1024)
        logger.info(f"打包完成: {size_mb:.1f} MB")
        return str(package_path)

    def _upload(self, model_dir: str, version: str, package_path: Optional[str]) -> List[str]:
        """上传模型到目标存储"""
        prefix = f"{self.config.version_prefix}{version}/"

        if self.config.target == "local":
            return self._upload_local(model_dir, version)
        elif self.config.target == "s3":
            return self._upload_s3(model_dir, version, prefix)
        elif self.config.target == "oss":
            return self._upload_oss(model_dir, version, prefix)
        elif self.config.target == "cos":
            return self._upload_cos(model_dir, version, prefix)
        elif self.config.target == "hf":
            return self._upload_hf(model_dir, version)
        else:
            raise ValueError(f"不支持的上传目标: {self.config.target}")

    def _upload_local(self, model_dir: str, version: str) -> List[str]:
        """本地发布（仅复制到输出目录）"""
        import shutil

        dest = Path(self.config.output_dir) / version
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(model_dir, dest)
        logger.info(f"模型已复制到: {dest}")
        return [str(dest)]

    def _upload_s3(self, model_dir: str, version: str, prefix: str) -> List[str]:
        """上传到 S3 / MinIO"""
        try:
            import boto3
        except ImportError:
            raise ImportError("S3 上传需要 boto3: pip install boto3")

        s3 = boto3.client(
            "s3",
            region_name=self.config.region,
            endpoint_url=self.config.endpoint,  # MinIO 需要
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
        )

        uploaded = []
        for filepath in Path(model_dir).rglob("*"):
            if filepath.is_file():
                key = f"{prefix}{filepath.relative_to(model_dir).as_posix()}"
                s3.upload_file(str(filepath), self.config.bucket, key)
                uploaded.append(key)

        logger.info(f"已上传 {len(uploaded)} 个文件到 S3 bucket: {self.config.bucket}")
        return uploaded

    def _upload_oss(self, model_dir: str, version: str, prefix: str) -> List[str]:
        """上传到阿里云 OSS"""
        try:
            import oss2
        except ImportError:
            raise ImportError("OSS 上传需要 oss2: pip install oss2")

        auth = oss2.Auth(self.config.access_key, self.config.secret_key)
        bucket = oss2.Bucket(auth, self.config.endpoint, self.config.bucket)

        uploaded = []
        for filepath in Path(model_dir).rglob("*"):
            if filepath.is_file():
                key = f"{prefix}{filepath.relative_to(model_dir).as_posix()}"
                bucket.put_object_from_file(key, str(filepath))
                uploaded.append(key)

        logger.info(f"已上传 {len(uploaded)} 个文件到 OSS bucket: {self.config.bucket}")
        return uploaded

    def _upload_cos(self, model_dir: str, version: str, prefix: str) -> List[str]:
        """上传到腾讯云 COS"""
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError:
            raise ImportError("COS 上传需要 cos-python-sdk: pip install cos-python-sdk-v5")

        config = CosConfig(
            Region=self.config.region,
            SecretId=self.config.access_key,
            SecretKey=self.config.secret_key,
            Endpoint=self.config.endpoint,
        )
        client = CosS3Client(config)

        uploaded = []
        for filepath in Path(model_dir).rglob("*"):
            if filepath.is_file():
                key = f"{prefix}{filepath.relative_to(model_dir).as_posix()}"
                client.upload_file(
                    Bucket=self.config.bucket,
                    LocalFilePath=str(filepath),
                    Key=key,
                )
                uploaded.append(key)

        logger.info(f"已上传 {len(uploaded)} 个文件到 COS bucket: {self.config.bucket}")
        return uploaded

    def _upload_hf(self, model_dir: str, version: str) -> List[str]:
        """上传到 Hugging Face Hub"""
        try:
            from huggingface_hub import HfApi, create_repo
        except ImportError:
            raise ImportError("HF 上传需要 huggingface_hub: pip install huggingface_hub")

        api = HfApi(token=self.config.hf_token)

        # 创建或获取仓库
        repo_id = self.config.hf_repo_id or f"username/{Path(model_dir).name}"
        try:
            create_repo(repo_id, private=self.config.private, token=self.config.hf_token)
        except Exception:
            logger.info(f"仓库已存在: {repo_id}")

        # 上传文件
        api.upload_folder(
            folder_path=model_dir,
            repo_id=repo_id,
            token=self.config.hf_token,
        )

        logger.info(f"已上传到 Hugging Face: {repo_id}")
        return [repo_id]

    @staticmethod
    def _get_dir_size_mb(path: str) -> float:
        """计算目录大小（MB）"""
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
    def from_cli(cls) -> "ModelPublisher":
        """从命令行参数创建发布器"""
        parser = argparse.ArgumentParser(description="模型发布工具")
        parser.add_argument("--model_dir", required=True, help="模型目录")
        parser.add_argument("--version", required=True, help="版本号")
        parser.add_argument("--target", default="local", choices=["local", "s3", "oss", "cos", "hf"])
        parser.add_argument("--output_dir", default="./published")
        parser.add_argument("--package_format", default="tar.gz", choices=["dir", "tar.gz", "zip"])
        parser.add_argument("--bucket", default=None)
        parser.add_argument("--region", default=None)
        parser.add_argument("--endpoint", default=None)
        parser.add_argument("--access_key", default=None)
        parser.add_argument("--secret_key", default=None)
        parser.add_argument("--hf_repo_id", default=None)
        parser.add_argument("--hf_token", default=None)
        parser.add_argument("--version_prefix", default="")
        parser.add_argument("--tags", default="", help="逗号分隔的标签")
        parser.add_argument("--dry_run", action="store_true")
        parser.add_argument("--verbose", action="store_true")

        args = parser.parse_args()
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        config = PublishConfig(
            target=args.target,
            output_dir=args.output_dir,
            package_format=args.package_format,
            bucket=args.bucket,
            region=args.region,
            endpoint=args.endpoint,
            access_key=args.access_key,
            secret_key=args.secret_key,
            hf_repo_id=args.hf_repo_id,
            hf_token=args.hf_token,
            version_prefix=args.version_prefix,
            tags=tags,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        return cls(config)


# 如果直接运行此脚本
if __name__ == "__main__":
    publisher = ModelPublisher.from_cli()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--version", required=True)
    args, _ = parser.parse_known_args()
    result = publisher.publish(args.model_dir, args.version)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
