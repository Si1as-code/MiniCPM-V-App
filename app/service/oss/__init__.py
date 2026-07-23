"""
对象存储模块
提供图片上传到阿里云 OSS / 腾讯云 COS 的能力。
"""

from service.oss.client import OSSClient, get_oss_client, OSSUploadResult

__all__ = [
    "OSSClient",
    "get_oss_client",
    "OSSUploadResult",
]