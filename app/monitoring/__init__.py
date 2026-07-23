"""
Sprint 8: 监控模块

包含：
- Firebase Crashlytics 崩溃监控配置（Android + iOS）
- Sentry 性能监控配置
- Prometheus 后端指标采集
- Grafana 仪表板配置生成
"""

from .crashlytics_config import CrashlyticsConfig, CrashReport, CrashSeverity
from .sentry_config import SentryConfig, SentryEventProcessor
from .metrics import MetricsCollector, MetricType, MetricRecord
from .grafana_dashboard import GrafanaDashboardBuilder, DashboardPanel

__all__ = [
    "CrashlyticsConfig",
    "CrashReport",
    "CrashSeverity",
    "SentryConfig",
    "SentryEventProcessor",
    "MetricsCollector",
    "MetricType",
    "MetricRecord",
    "GrafanaDashboardBuilder",
    "DashboardPanel",
]
