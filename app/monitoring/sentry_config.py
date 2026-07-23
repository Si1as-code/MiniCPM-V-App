"""
Sentry 性能监控配置

覆盖前后端 Sentry SDK 集成、性能追踪、错误过滤。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class SentryConfig:
    """Sentry 配置"""

    # DSN
    dsn: str = "https://xxxxxxxx@oXXXXXXXX.ingest.sentry.io/XXXXXXXX"
    environment: str = "production"  # development / staging / production
    release: str = "minicpmv@1.0.0"

    # 采样率
    traces_sample_rate: float = 0.1   # 性能追踪采样 10%
    profiles_sample_rate: float = 0.1 # 性能分析采样
    error_sample_rate: float = 1.0    # 错误采样 100%

    # 隐私
    send_default_pii: bool = False     # GDPR 合规：不发送 PII
    max_breadcrumbs: int = 100
    attach_stacktrace: bool = True

    # 过滤
    ignore_errors: list = field(
        default_factory=lambda: [
            "NetworkError",
            "TimeoutError",
            "AbortError",
            "CancellationException",
        ]
    )

    # 性能监控
    enable_tracing: bool = True
    enable_profiling: bool = True
    slow_transaction_threshold_ms: int = 3000

    # 前端（Mobile）
    enable_native_crash: bool = True   # iOS/Android 原生崩溃
    enable_app_start: bool = True      # 应用启动追踪
    enable_screen_tracking: bool = True # 屏幕切换追踪
    enable_memory_tracking: bool = True # 内存监控

    def generate_python_init(self) -> str:
        """生成 Python 后端初始化代码"""
        return f"""# Sentry Python SDK 初始化 (FastAPI)

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.redis import RedisIntegration

def init_sentry():
    sentry_sdk.init(
        dsn="{self.dsn}",
        environment="{self.environment}",
        release="{self.release}",
        traces_sample_rate={self.traces_sample_rate},
        profiles_sample_rate={self.profiles_sample_rate},
        send_default_pii={self.send_default_pii},
        max_breadcrumbs={self.max_breadcrumbs},
        attach_stacktrace={self.attach_stacktrace},
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            AsyncioIntegration(),
            RedisIntegration(),
        ],
        before_send=filter_sensitive_data,
        ignore_errors={self.ignore_errors},
    )

def filter_sensitive_data(event, hint):
    \"\"\"过滤敏感数据（GDPR 合规）\"\"\"
    if 'request' in event:
        headers = event['request'].get('headers', {{}})
        # 移除 Authorization 头
        headers.pop('Authorization', None)
        headers.pop('Cookie', None)
        # 移除请求体中的密码字段
        if 'data' in event['request']:
            data = event['request']['data']
            if isinstance(data, dict):
                data.pop('password', None)
                data.pop('verification_code', None)
                data.pop('token', None)
    return event

# 在 FastAPI lifespan 中调用
# init_sentry()
"""

    def generate_android_init(self) -> str:
        """生成 Android 初始化代码"""
        return f"""// Sentry Android SDK 初始化

import io.sentry.android.core.SentryAndroid
import io.sentry.android.core.SentryAndroidOptions
import io.sentry.android.fragment.FragmentLifecycleIntegration
import io.sentry.android.timber.SentryTimberIntegration

fun initSentry(context: Context) {{
    SentryAndroid.init(context) {{ options ->
        options.dsn = "{self.dsn}"
        options.environment = "{self.environment}"
        options.release = "{self.release}"
        options.tracesSampleRate = {self.traces_sample_rate}
        options.profilesSampleRate = {self.profiles_sample_rate}
        options.isSendDefaultPii = {self.send_default_pii}
        options.maxBreadcrumbs = {self.max_breadcrumbs}
        options.isAttachStacktrace = {self.attach_stacktrace}

        // 性能追踪
        options.isEnableAutoSessionTracking = true
        options.isEnableAppStartTracking = {self.enable_app_start}
        options.isEnableScreenshots = false  // 隐私：不截图
        options.isEnableUserInteractionTracing = {self.enable_screen_tracking}

        // 集成
        options.addIntegration(FragmentLifecycleIntegration())
        options.addIntegration(SentryTimberIntegration())

        // 过滤
        options.setBeforeSend {{ event, _ ->
            // 过滤敏感信息
            event
        }}
    }}
}}
"""

    def generate_ios_init(self) -> str:
        """生成 iOS 初始化代码"""
        return f"""// Sentry iOS SDK 初始化

import Sentry

func initSentry() {{
    SentrySDK.start {{ options in
        options.dsn = "{self.dsn}"
        options.environment = "{self.environment}"
        options.releaseName = "{self.release}"
        options.tracesSampleRate = {self.traces_sample_rate}
        options.profilesSampleRate = {self.profiles_sample_rate}
        options.sendDefaultPii = {self.send_default_pii}
        options.maxBreadcrumbs = {self.max_breadcrumbs}
        options.attachStacktrace = {self.attach_stacktrace}

        // 性能追踪
        options.enableAppStartTracking = {self.enable_app_start}
        options.enableFramesTracking = {self.enable_screen_tracking}
        options.enableCoreDataTracking = true

        // 隐私
        options.beforeSend = {{ event in
            // 过滤敏感信息
            return event
        }}
    }}
}}
"""

    def get_performance_config(self) -> dict:
        """获取性能监控配置"""
        return {
            "tracing": {
                "sample_rate": self.traces_sample_rate,
                "slow_transaction_threshold_ms": self.slow_transaction_threshold_ms,
                "enabled": self.enable_tracing,
            },
            "profiling": {
                "sample_rate": self.profiles_sample_rate,
                "enabled": self.enable_profiling,
            },
            "mobile_specific": {
                "app_start_tracking": self.enable_app_start,
                "screen_tracking": self.enable_screen_tracking,
                "memory_tracking": self.enable_memory_tracking,
                "native_crash": self.enable_native_crash,
            },
            "alerting": {
                "p95_latency_threshold": f"{self.slow_transaction_threshold_ms}ms",
                "error_rate_threshold": "1%",
                "app_start_threshold": "3000ms",
            },
        }


class SentryEventProcessor:
    """Sentry 事件处理器"""

    # 敏感字段列表
    SENSITIVE_FIELDS = {
        "password", "token", "secret", "key", "authorization",
        "cookie", "session_id", "verification_code", "phone_number",
    }

    @classmethod
    def sanitize_event(cls, event: dict) -> dict:
        """清理事件中的敏感数据"""
        if "request" in event:
            req = event["request"]
            # 清理 headers
            if "headers" in req:
                req["headers"] = {
                    k: "[REDACTED]" if k.lower() in cls.SENSITIVE_FIELDS else v
                    for k, v in req["headers"].items()
                }
            # 清理 data
            if "data" in req and isinstance(req["data"], dict):
                req["data"] = cls._sanitize_dict(req["data"])

        # 清理 extra
        if "extra" in event:
            event["extra"] = cls._sanitize_dict(event["extra"])

        return event

    @classmethod
    def _sanitize_dict(cls, data: dict) -> dict:
        """递归清理字典中的敏感字段"""
        sanitized = {}
        for key, value in data.items():
            if key.lower() in cls.SENSITIVE_FIELDS:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = cls._sanitize_dict(value)
            else:
                sanitized[key] = value
        return sanitized

    @classmethod
    def should_ignore(cls, event: dict, ignore_errors: list) -> bool:
        """判断事件是否应被忽略"""
        exception_values = event.get("exception", {}).get("values", [])
        for exc in exception_values:
            exc_type = exc.get("type", "")
            for ignore in ignore_errors:
                if ignore in exc_type:
                    return True
        return False
