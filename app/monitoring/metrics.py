"""
Prometheus 后端指标采集

定义 FastAPI 后端的 Prometheus 指标，包括：
- 请求延迟 / 请求计数
- 推理任务指标
- 数据库连接池指标
- Redis 队列指标
- 系统健康指标
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from collections import defaultdict


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricRecord:
    """指标记录"""
    name: str
    type: MetricType
    value: float
    labels: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    help_text: str = ""


class MetricsCollector:
    """Prometheus 指标采集器"""

    def __init__(self):
        self._metrics: dict[str, list[MetricRecord]] = defaultdict(list)
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._define_metrics()

    def _define_metrics(self):
        """定义所有指标"""
        self._metric_definitions = {
            # HTTP 请求指标
            "http_requests_total": (MetricType.COUNTER, "HTTP 请求总数"),
            "http_request_duration_seconds": (MetricType.HISTOGRAM, "HTTP 请求延迟（秒）"),
            "http_requests_in_progress": (MetricType.GAUGE, "正在处理的 HTTP 请求数"),

            # 推理指标
            "inference_requests_total": (MetricType.COUNTER, "推理请求总数"),
            "inference_duration_seconds": (MetricType.HISTOGRAM, "推理耗时（秒）"),
            "inference_errors_total": (MetricType.COUNTER, "推理错误总数"),
            "inference_cache_hits_total": (MetricType.COUNTER, "推理缓存命中数"),
            "inference_cache_misses_total": (MetricType.COUNTER, "推理缓存未命中数"),
            "inference_confidence": (MetricType.HISTOGRAM, "推理置信度分布"),

            # 端云协同指标
            "cloud_api_calls_total": (MetricType.COUNTER, "云端 API 调用次数"),
            "cloud_api_duration_seconds": (MetricType.HISTOGRAM, "云端 API 响应时间"),
            "cloud_api_errors_total": (MetricType.COUNTER, "云端 API 错误数"),
            "fallback_to_local_total": (MetricType.COUNTER, "降级到端侧次数"),
            "budget_usage_ratio": (MetricType.GAUGE, "预算使用比例"),

            # 数据库指标
            "db_connections_active": (MetricType.GAUGE, "活跃数据库连接数"),
            "db_connections_idle": (MetricType.GAUGE, "空闲数据库连接数"),
            "db_query_duration_seconds": (MetricType.HISTOGRAM, "数据库查询耗时"),
            "db_sync_records_total": (MetricType.COUNTER, "同步记录总数"),
            "db_sync_conflicts_total": (MetricType.COUNTER, "同步冲突数"),

            # Redis 队列指标
            "queue_tasks_pending": (MetricType.GAUGE, "待处理任务数"),
            "queue_tasks_completed": (MetricType.COUNTER, "已完成任务数"),
            "queue_tasks_failed": (MetricType.COUNTER, "失败任务数"),
            "queue_processing_duration_seconds": (MetricType.HISTOGRAM, "任务处理耗时"),

            # WebSocket 指标
            "websocket_connections_active": (MetricType.GAUGE, "活跃 WebSocket 连接数"),
            "websocket_messages_sent_total": (MetricType.COUNTER, "WebSocket 发送消息数"),

            # OSS 指标
            "oss_uploads_total": (MetricType.COUNTER, "OSS 上传次数"),
            "oss_upload_bytes": (MetricType.HISTOGRAM, "OSS 上传文件大小（字节）"),
            "oss_upload_duration_seconds": (MetricType.HISTOGRAM, "OSS 上传耗时"),

            # 认证指标
            "auth_login_attempts_total": (MetricType.COUNTER, "登录尝试次数"),
            "auth_login_failures_total": (MetricType.COUNTER, "登录失败次数"),
            "auth_token_refreshes_total": (MetricType.COUNTER, "Token 刷新次数"),

            # 系统指标
            "app_info": (MetricType.GAUGE, "应用信息"),
            "app_uptime_seconds": (MetricType.GAUGE, "应用运行时间"),
        }

    def increment(self, name: str, value: float = 1.0, labels: dict = None):
        """增加计数器"""
        key = self._label_key(name, labels or {})
        self._counters[key] += value
        self._metrics[name].append(MetricRecord(
            name=name, type=MetricType.COUNTER, value=self._counters[key],
            labels=labels or {}, help_text=self._help(name),
        ))

    def set_gauge(self, name: str, value: float, labels: dict = None):
        """设置 Gauge 值"""
        key = self._label_key(name, labels or {})
        self._gauges[key] = value
        self._metrics[name].append(MetricRecord(
            name=name, type=MetricType.GAUGE, value=value,
            labels=labels or {}, help_text=self._help(name),
        ))

    def observe(self, name: str, value: float, labels: dict = None):
        """记录 Histogram 观测值"""
        key = self._label_key(name, labels or {})
        self._histograms[key].append(value)
        self._metrics[name].append(MetricRecord(
            name=name, type=MetricType.HISTOGRAM, value=value,
            labels=labels or {}, help_text=self._help(name),
        ))

    def observe_inference(self, duration: float, confidence: float,
                          cached: bool, success: bool, source: str = "local"):
        """记录推理指标"""
        self.increment("inference_requests_total", labels={"source": source, "success": str(success).lower()})
        self.observe("inference_duration_seconds", duration, labels={"source": source})

        if not success:
            self.increment("inference_errors_total", labels={"source": source})
        if cached:
            self.increment("inference_cache_hits_total")
        else:
            self.increment("inference_cache_misses_total")

        self.observe("inference_confidence", confidence)

    def observe_cloud_call(self, provider: str, duration: float, success: bool):
        """记录云端 API 调用"""
        self.increment("cloud_api_calls_total", labels={"provider": provider, "success": str(success).lower()})
        self.observe("cloud_api_duration_seconds", duration, labels={"provider": provider})
        if not success:
            self.increment("cloud_api_errors_total", labels={"provider": provider})

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式文本"""
        lines = []

        for name, (mtype, help_text) in self._metric_definitions.items():
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {mtype.value}")

            if mtype == MetricType.COUNTER:
                for key, value in self._counters.items():
                    if key.startswith(name):
                        labels = self._extract_labels(key, name)
                        label_str = self._format_labels(labels)
                        lines.append(f"{name}{label_str} {value}")

            elif mtype == MetricType.GAUGE:
                for key, value in self._gauges.items():
                    if key.startswith(name):
                        labels = self._extract_labels(key, name)
                        label_str = self._format_labels(labels)
                        lines.append(f"{name}{label_str} {value}")

            elif mtype == MetricType.HISTOGRAM:
                for key, values in self._histograms.items():
                    if key.startswith(name):
                        labels = self._extract_labels(key, name)
                        label_str = self._format_labels(labels)
                        count = len(values)
                        total = sum(values)
                        lines.append(f"{name}_count{label_str} {count}")
                        lines.append(f"{name}_sum{label_str} {total}")
                        # 分位数
                        if values:
                            sorted_v = sorted(values)
                            for p in [0.5, 0.95, 0.99]:
                                idx = int(len(sorted_v) * p)
                                idx = min(idx, len(sorted_v) - 1)
                                lines.append(f"{name}{{quantile=\"{p}\"}} {sorted_v[idx]}")

        return "\n".join(lines)

    def get_summary(self) -> dict:
        """获取指标摘要"""
        return {
            "total_counters": len([k for k in self._counters]),
            "total_gauges": len(self._gauges),
            "total_histograms": len(self._histograms),
            "total_metric_types": len(self._metric_definitions),
            "uptime": time.time(),
        }

    @staticmethod
    def _label_key(name: str, labels: dict) -> str:
        """生成带标签的键"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    @staticmethod
    def _format_labels(labels: dict) -> str:
        """格式化 Prometheus 标签"""
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"

    @staticmethod
    def _extract_labels(key: str, name: str) -> dict:
        """从键中提取标签"""
        if "{" not in key:
            return {}
        label_part = key.split("{")[1].rstrip("}")
        labels = {}
        for pair in label_part.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                labels[k] = v
        return labels

    def _help(self, name: str) -> str:
        """获取指标帮助文本"""
        if name in self._metric_definitions:
            return self._metric_definitions[name][1]
        return ""
