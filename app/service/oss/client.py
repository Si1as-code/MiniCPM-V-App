import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional

from service.config import service_config

logger = logging.getLogger(__name__)


@dataclass
class OSSUploadResult:
    success: bool = False
    url: str = ""
    object_key: str = ""
    error: str = ""
    image_hash: str = ""


class OSSClient:
    _instance: Optional["OSSClient"] = None

    def __new__(cls) -> "OSSClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._client = None
        self._initialized = False
        self._simulate = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        self._initialized = True

        if not service_config.oss_access_key or not service_config.oss_secret_key:
            logger.warning("OSS 未配置 AccessKey，使用本地模拟模式")
            self._simulate = True
            return

        if service_config.oss_provider == "aliyun":
            self._init_aliyun()
        elif service_config.oss_provider == "tencent":
            self._init_tencent()
        else:
            raise ValueError(f"不支持的 OSS 提供商: {service_config.oss_provider}")

    def _init_aliyun(self):
        try:
            import oss2
            auth = oss2.Auth(
                service_config.oss_access_key,
                service_config.oss_secret_key,
            )
            self._client = oss2.Bucket(
                auth,
                f"https://{service_config.oss_endpoint}",
                service_config.oss_bucket,
            )
            logger.info(f"阿里云 OSS 客户端已初始化: bucket={service_config.oss_bucket}")
        except ImportError:
            logger.warning("oss2 未安装，使用本地模拟模式")
            self._simulate = True

    def _init_tencent(self):
        try:
            from qcloud_cos import CosConfig, CosS3Client
            config = CosConfig(
                Region=service_config.oss_region,
                SecretId=service_config.oss_access_key,
                SecretKey=service_config.oss_secret_key,
            )
            self._client = CosS3Client(config)
            logger.info(f"腾讯云 COS 客户端已初始化: bucket={service_config.oss_bucket}")
        except ImportError:
            logger.warning("cos-python-sdk-v5 未安装，使用本地模拟模式")
            self._simulate = True

    def upload_image(
        self,
        image_data: bytes,
        image_hash: str,
        user_id: str = "anonymous",
    ) -> OSSUploadResult:
        """
        上传图片到 OSS

        Args:
            image_data: 图片二进制数据
            image_hash: 图片 MD5/SHA256 哈希
            user_id: 用户 ID（用于目录隔离）

        Returns:
            OSSUploadResult
        """
        self._ensure_initialized()

        # 对象键: {user_id}/{hash_prefix}/{hash}.jpg
        hash_prefix = image_hash[:2]
        object_key = f"{user_id}/{hash_prefix}/{image_hash}.jpg"

        if self._simulate:
            return self._simulate_upload(image_data, image_hash, object_key)

        try:
            # 检查是否已存在（去重）
            try:
                self._client.get_object_meta(object_key)
                logger.info(f"图片已存在，跳过上传: {object_key}")
                url = self._build_url(object_key)
                return OSSUploadResult(success=True, url=url, object_key=object_key, image_hash=image_hash)
            except Exception:
                pass  # 不存在，继续上传

            # 上传
            self._client.put_object(
                key=object_key,
                data=image_data,
                headers={"Content-Type": "image/jpeg"},
            )
            url = self._build_url(object_key)
            logger.info(f"图片上传成功: {object_key}")
            return OSSUploadResult(success=True, url=url, object_key=object_key, image_hash=image_hash)
        except Exception as e:
            logger.error(f"图片上传失败: {e}")
            return OSSUploadResult(success=False, error=str(e), image_hash=image_hash)

    def generate_presigned_url(self, object_key: str, expire_seconds: int = 3600) -> str:
        """生成预签名下载 URL"""
        self._ensure_initialized()
        if self._simulate:
            return f"/mock/{object_key}"
        try:
            return self._client.sign_url(
                "GET",
                object_key,
                expire_seconds,
            )
        except Exception as e:
            logger.error(f"生成预签名 URL 失败: {e}")
            return ""

    def delete_image(self, object_key: str) -> bool:
        """删除图片"""
        self._ensure_initialized()
        if self._simulate:
            logger.info(f"[模拟] 删除图片: {object_key}")
            return True
        try:
            self._client.delete_object(object_key)
            return True
        except Exception as e:
            logger.error(f"删除图片失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_url(self, object_key: str) -> str:
        if service_config.oss_provider == "aliyun":
            return f"https://{service_config.oss_bucket}.{service_config.oss_endpoint}/{object_key}"
        return f"https://{service_config.oss_bucket}.cos.{service_config.oss_region}.myqcloud.com/{object_key}"

    def _simulate_upload(self, image_data: bytes, image_hash: str, object_key: str) -> OSSUploadResult:
        """本地模拟上传"""
        sim_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data_store", "oss_simulate",
        )
        dest = os.path.join(sim_dir, object_key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(image_data)
        logger.info(f"[模拟] 图片已保存到本地: {dest}")
        return OSSUploadResult(
            success=True,
            url=f"/mock/{object_key}",
            object_key=object_key,
            image_hash=image_hash,
        )


def get_oss_client() -> OSSClient:
    return OSSClient()