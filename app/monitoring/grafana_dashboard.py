"""
Grafana 仪表板配置生成器

生成 JSON 格式的 Grafana 仪表板配置，包含推理性能、
端云协同、系统健康等面板。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DashboardPanel:
    """仪表板面板"""
    title: str
    panel_type: str  # graph / stat / table / heatmap / gauge
    datasource: str = "Prometheus"
    grid_pos: dict = field(default_factory=lambda: {"x": 0, "y": 0, "w": 12, "h": 8})
    targets: list = field(default_factory=list)
    thresholds: list = field(default_factory=list)
    unit: str = "s"
    description: str = ""

    def add_target(self, expr: str, legend: str = "", ref_id: str = "A"):
        """添加查询目标"""
        self.targets.append({
            "expr": expr,
            "legendFormat": legend,
            "refId": ref_id,
            "datasource": {"type": "prometheus", "uid": "prometheus"},
        })

    def add_threshold(self, value: float, color: str = "red", state: str = "critical"):
        """添加阈值"""
        self.thresholds.append({
            "value": value,
            "color": color,
            "state": state,
        })

    def to_dict(self) -> dict:
        """转为 Grafana JSON"""
        return {
            "title": self.title,
            "type": self.panel_type,
            "datasource": {"type": "prometheus", "uid": "prometheus"},
            "gridPos": self.grid_pos,
            "targets": self.targets,
            "fieldConfig": {
                "defaults": {
                    "unit": self.unit,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            *[{"color": t["color"], "value": t["value"]} for t in self.thresholds],
                        ],
                    },
                },
            },
            "description": self.description,
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi"},
            },
        }


class GrafanaDashboardBuilder:
    """Grafana 仪表板构建器"""

    def __init__(self, title: str = "MiniCPM-V 端侧视觉助手 - 监控仪表板", uid: str = "minicpmv"):
        self.title = title
        self.uid = uid
        self._panels: list[DashboardPanel] = []
        self._build_panels()

    def _build_panels(self):
        """构建所有面板"""

        # ===== 第 1 行：核心 KPI =====
        panel = DashboardPanel(
            title="推理请求总数", panel_type="stat", unit="short",
            grid_pos={"x": 0, "y": 0, "w": 6, "h": 4},
            description="总推理请求量"
        )
        panel.add_target('sum(increase(inference_requests_total[1h]))', "1h", "A")
        panel.add_target('sum(increase(inference_requests_total[24h]))', "24h", "B")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="推理错误率", panel_type="stat", unit="percent",
            grid_pos={"x": 6, "y": 0, "w": 6, "h": 4},
            description="推理错误占比"
        )
        panel.add_target(
            'sum(rate(inference_errors_total[5m])) / sum(rate(inference_requests_total[5m])) * 100',
            "error_rate", "A"
        )
        panel.add_threshold(1.0, "yellow", "warning")
        panel.add_threshold(5.0, "red", "critical")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="缓存命中率", panel_type="stat", unit="percent",
            grid_pos={"x": 12, "y": 0, "w": 6, "h": 4},
            description="推理缓存命中率"
        )
        panel.add_target(
            'sum(rate(inference_cache_hits_total[5m])) / '
            '(sum(rate(inference_cache_hits_total[5m])) + sum(rate(inference_cache_misses_total[5m]))) * 100',
            "hit_rate", "A"
        )
        panel.add_threshold(50.0, "yellow", "warning")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="活跃 WebSocket 连接", panel_type="stat", unit="short",
            grid_pos={"x": 18, "y": 0, "w": 6, "h": 4},
            description="当前 WebSocket 连接数"
        )
        panel.add_target('websocket_connections_active', "active", "A")
        self._panels.append(panel)

        # ===== 第 2 行：推理性能 =====
        panel = DashboardPanel(
            title="推理延迟 (P50/P95/P99)", panel_type="timeseries", unit="s",
            grid_pos={"x": 0, "y": 4, "w": 12, "h": 8},
            description="推理耗时分布"
        )
        panel.add_target(
            'histogram_quantile(0.50, sum(rate(inference_duration_seconds_bucket[5m])) by (le))',
            "P50", "A"
        )
        panel.add_target(
            'histogram_quantile(0.95, sum(rate(inference_duration_seconds_bucket[5m])) by (le))',
            "P95", "B"
        )
        panel.add_target(
            'histogram_quantile(0.99, sum(rate(inference_duration_seconds_bucket[5m])) by (le))',
            "P99", "C"
        )
        panel.add_threshold(2.0, "yellow", "warning")
        panel.add_threshold(5.0, "red", "critical")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="端侧 vs 云端推理量", panel_type="timeseries", unit="short",
            grid_pos={"x": 12, "y": 4, "w": 12, "h": 8},
            description="按来源分类的推理请求"
        )
        panel.add_target(
            'sum(rate(inference_requests_total{source="local"}[5m]))',
            "端侧", "A"
        )
        panel.add_target(
            'sum(rate(inference_requests_total{source="cloud"}[5m]))',
            "云端", "B"
        )
        self._panels.append(panel)

        # ===== 第 3 行：端云协同 =====
        panel = DashboardPanel(
            title="云端 API 调用延迟", panel_type="timeseries", unit="s",
            grid_pos={"x": 0, "y": 12, "w": 12, "h": 8},
            description="各 Provider 的 API 响应时间"
        )
        panel.add_target(
            'histogram_quantile(0.95, sum(rate(cloud_api_duration_seconds_bucket[5m])) by (le, provider))',
            "{{provider}} P95", "A"
        )
        self._panels.append(panel)

        panel = DashboardPanel(
            title="降级次数 & 预算使用", panel_type="timeseries", unit="short",
            grid_pos={"x": 12, "y": 12, "w": 12, "h": 8},
            description="降级到端侧次数和预算使用比例"
        )
        panel.add_target('sum(rate(fallback_to_local_total[5m]))', "降级次数", "A")
        panel.add_target('avg(budget_usage_ratio) * 100', "预算使用率%", "B")
        panel.add_threshold(80.0, "yellow", "warning")
        panel.add_threshold(100.0, "red", "critical")
        self._panels.append(panel)

        # ===== 第 4 行：系统健康 =====
        panel = DashboardPanel(
            title="数据库连接池", panel_type="timeseries", unit="short",
            grid_pos={"x": 0, "y": 20, "w": 8, "h": 8},
            description="PostgreSQL 连接池状态"
        )
        panel.add_target('db_connections_active', "活跃", "A")
        panel.add_target('db_connections_idle', "空闲", "B")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="任务队列", panel_type="timeseries", unit="short",
            grid_pos={"x": 8, "y": 20, "w": 8, "h": 8},
            description="Redis 任务队列状态"
        )
        panel.add_target('queue_tasks_pending', "待处理", "A")
        panel.add_target('sum(rate(queue_tasks_completed[5m]))', "完成速率", "B")
        panel.add_target('sum(rate(queue_tasks_failed[5m]))', "失败速率", "C")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="同步统计", panel_type="timeseries", unit="short",
            grid_pos={"x": 16, "y": 20, "w": 8, "h": 8},
            description="数据同步记录和冲突"
        )
        panel.add_target('sum(rate(db_sync_records_total[5m]))', "同步记录", "A")
        panel.add_target('sum(rate(db_sync_conflicts_total[5m]))', "同步冲突", "B")
        self._panels.append(panel)

        # ===== 第 5 行：认证 & OSS =====
        panel = DashboardPanel(
            title="登录统计", panel_type="timeseries", unit="short",
            grid_pos={"x": 0, "y": 28, "w": 12, "h": 8},
            description="登录尝试和失败"
        )
        panel.add_target('sum(rate(auth_login_attempts_total[5m]))', "尝试", "A")
        panel.add_target('sum(rate(auth_login_failures_total[5m]))', "失败", "B")
        self._panels.append(panel)

        panel = DashboardPanel(
            title="OSS 上传统计", panel_type="timeseries", unit="short",
            grid_pos={"x": 12, "y": 28, "w": 12, "h": 8},
            description="OSS 上传量和耗时"
        )
        panel.add_target('sum(rate(oss_uploads_total[5m]))', "上传次数", "A")
        panel.add_target(
            'histogram_quantile(0.95, sum(rate(oss_upload_duration_seconds_bucket[5m])) by (le))',
            "P95 延迟", "B"
        )
        self._panels.append(panel)

    def build(self) -> dict:
        """构建完整仪表板 JSON"""
        return {
            "title": self.title,
            "uid": self.uid,
            "schemaVersion": 39,
            "version": 1,
            "refresh": "10s",
            "time": {"from": "now-1h", "to": "now"},
            "tags": ["minicpmv", "production"],
            "templating": {
                "list": [
                    {
                        "name": "datasource",
                        "type": "datasource",
                        "query": "prometheus",
                        "current": {"text": "Prometheus", "value": "prometheus"},
                    },
                ],
            },
            "panels": [p.to_dict() for p in self._panels],
            "annotations": {
                "list": [
                    {
                        "name": "Deployments",
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "expr": "changes(app_info[1h])",
                    },
                ],
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """导出 JSON 字符串"""
        return json.dumps(self.build(), ensure_ascii=False, indent=indent)

    def get_alert_rules(self) -> list:
        """获取告警规则"""
        return [
            {
                "name": "推理错误率过高",
                "expr": "sum(rate(inference_errors_total[5m])) / sum(rate(inference_requests_total[5m])) > 0.05",
                "for": "5m",
                "severity": "critical",
                "message": "推理错误率超过 5%",
            },
            {
                "name": "P95 延迟过高",
                "expr": "histogram_quantile(0.95, sum(rate(inference_duration_seconds_bucket[5m])) by (le)) > 5",
                "for": "5m",
                "severity": "warning",
                "message": "P95 推理延迟超过 5 秒",
            },
            {
                "name": "预算即将用尽",
                "expr": "budget_usage_ratio > 0.9",
                "for": "1m",
                "severity": "warning",
                "message": "日预算使用率超过 90%",
            },
            {
                "name": "数据库连接耗尽",
                "expr": "db_connections_active > 18",
                "for": "2m",
                "severity": "critical",
                "message": "数据库活跃连接超过 18 (上限 20)",
            },
            {
                "name": "Redis 队列积压",
                "expr": "queue_tasks_pending > 100",
                "for": "5m",
                "severity": "warning",
                "message": "待处理任务超过 100",
            },
            {
                "name": "同步冲突激增",
                "expr": "rate(db_sync_conflicts_total[5m]) > 10",
                "for": "5m",
                "severity": "warning",
                "message": "同步冲突速率超过 10/min",
            },
        ]
