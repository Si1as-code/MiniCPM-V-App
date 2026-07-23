"""
============================================================================
后台服务配置
============================================================================
管理所有后台服务的配置项，通过环境变量覆盖默认值。

环境变量前缀: SERVICE_
  例如: SERVICE_DB_HOST=localhost, SERVICE_JWT_SECRET=xxx
============================================================================
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServiceConfig:
    """后台服务全局配置"""

    # --- FastAPI 服务 ---
    host: str = field(
        default_factory=lambda: os.getenv("SERVICE_HOST", "0.0.0.0")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_PORT", "8000"))
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("SERVICE_DEBUG", "false").lower() == "true"
    )
    allowed_origins: list = field(
        default_factory=lambda: os.getenv(
            "SERVICE_ALLOWED_ORIGINS", "*"
        ).split(",")
    )
    api_prefix: str = field(
        default_factory=lambda: os.getenv("SERVICE_API_PREFIX", "/api")
    )

    # --- PostgreSQL 云端数据库 ---
    db_host: str = field(
        default_factory=lambda: os.getenv("SERVICE_DB_HOST", "localhost")
    )
    db_port: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_DB_PORT", "5432"))
    )
    db_name: str = field(
        default_factory=lambda: os.getenv("SERVICE_DB_NAME", "minicpmv")
    )
    db_user: str = field(
        default_factory=lambda: os.getenv("SERVICE_DB_USER", "postgres")
    )
    db_password: str = field(
        default_factory=lambda: os.getenv("SERVICE_DB_PASSWORD", "postgres")
    )
    db_min_pool: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_DB_MIN_POOL", "2"))
    )
    db_max_pool: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_DB_MAX_POOL", "10"))
    )

    @property
    def db_dsn(self) -> str:
        """PostgreSQL 连接字符串"""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # --- Redis ---
    redis_host: str = field(
        default_factory=lambda: os.getenv("SERVICE_REDIS_HOST", "localhost")
    )
    redis_port: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_REDIS_PORT", "6379"))
    )
    redis_db: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_REDIS_DB", "0"))
    )
    redis_password: Optional[str] = field(
        default_factory=lambda: os.getenv("SERVICE_REDIS_PASSWORD", None)
    )

    @property
    def redis_dsn(self) -> str:
        pwd = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pwd}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # --- JWT 认证 ---
    jwt_secret: str = field(
        default_factory=lambda: os.getenv(
            "SERVICE_JWT_SECRET",
            "change-this-to-a-random-secret-in-production",
        )
    )
    jwt_algorithm: str = field(
        default_factory=lambda: os.getenv("SERVICE_JWT_ALGORITHM", "HS256")
    )
    jwt_access_expire: int = field(
        # 访问令牌过期时间（秒），默认 24 小时
        default_factory=lambda: int(os.getenv("SERVICE_JWT_ACCESS_EXPIRE", "86400"))
    )
    jwt_refresh_expire: int = field(
        # 刷新令牌过期时间（秒），默认 30 天
        default_factory=lambda: int(os.getenv("SERVICE_JWT_REFRESH_EXPIRE", "2592000"))
    )

    # --- OSS 对象存储 ---
    oss_provider: str = field(
        default_factory=lambda: os.getenv("SERVICE_OSS_PROVIDER", "aliyun")
    )
    oss_endpoint: str = field(
        default_factory=lambda: os.getenv("SERVICE_OSS_ENDPOINT", "")
    )
    oss_bucket: str = field(
        default_factory=lambda: os.getenv("SERVICE_OSS_BUCKET", "minicpmv-images")
    )
    oss_access_key: str = field(
        default_factory=lambda: os.getenv("SERVICE_OSS_ACCESS_KEY", "")
    )
    oss_secret_key: str = field(
        default_factory=lambda: os.getenv("SERVICE_OSS_SECRET_KEY", "")
    )
    oss_region: str = field(
        default_factory=lambda: os.getenv("SERVICE_OSS_REGION", "cn-hangzhou")
    )
    # 预签名 URL 有效期（秒）
    oss_presign_expire: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_OSS_PRESIGN_EXPIRE", "3600"))
    )

    # --- 同步引擎 ---
    sync_batch_size: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_SYNC_BATCH_SIZE", "50"))
    )
    sync_interval: int = field(
        # 同步间隔（秒），默认 5 分钟
        default_factory=lambda: int(os.getenv("SERVICE_SYNC_INTERVAL", "300"))
    )

    # --- 验证码 ---
    sms_region: str = field(
        default_factory=lambda: os.getenv("SERVICE_SMS_REGION", "cn-hangzhou")
    )
    sms_access_key: str = field(
        default_factory=lambda: os.getenv("SERVICE_SMS_ACCESS_KEY", "")
    )
    sms_secret_key: str = field(
        default_factory=lambda: os.getenv("SERVICE_SMS_SECRET_KEY", "")
    )
    sms_sign_name: str = field(
        default_factory=lambda: os.getenv("SERVICE_SMS_SIGN_NAME", "MiniCPM-V")
    )
    sms_template_code: str = field(
        default_factory=lambda: os.getenv("SERVICE_SMS_TEMPLATE_CODE", "SMS_000001")
    )
    # 验证码有效期（秒）
    sms_code_expire: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_SMS_CODE_EXPIRE", "300"))
    )

    # --- 限流 ---
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("SERVICE_RATE_LIMIT", "60"))
    )


# 全局单例
service_config = ServiceConfig()