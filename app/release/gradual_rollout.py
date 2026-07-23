"""
灰度发布管理

支持分阶段逐步扩大发布比例，自动监控关键指标，
异常时自动暂停或回滚。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class RolloutStage(Enum):
    """灰度阶段"""
    INTERNAL_TEST = "internal_test"   # 内部测试 (1%)
    ALPHA = "alpha"                   # Alpha 测试 (5%)
    BETA = "beta"                     # Beta 测试 (20%)
    PRODUCTION_50 = "production_50"   # 生产 50%
    FULL_RELEASE = "full_release"     # 全量发布 (100%)
    PAUSED = "paused"                 # 暂停
    ROLLED_BACK = "rolled_back"       # 已回滚


@dataclass
class RolloutConfig:
    """灰度配置"""
    stage: RolloutStage = RolloutStage.INTERNAL_TEST
    rollout_percentage: float = 1.0  # 1% ~ 100%
    target_version: str = "1.0.0"
    min_observation_hours: int = 24  # 最少观察时间
    auto_rollback_thresholds: dict = field(default_factory=lambda: {
        "crash_rate": 0.5,        # 崩溃率 > 0.5% 自动回滚
        "anr_rate": 0.47,         # ANR 率 > 0.47% 自动回滚
        "error_rate": 5.0,        # API 错误率 > 5% 自动回滚
        "negative_feedback_ratio": 0.15,  # 负面反馈比例 > 15%
    })

    # 平台
    platforms: list = field(default_factory=lambda: ["android", "ios"])

    # 用户分群
    segment_filters: dict = field(default_factory=lambda: {
        "min_app_version": "0.9.0",  # 最低可升级版本
        "exclude_rooted": True,       # 排除 root 设备
        "exclude_emulator": True,     # 排除模拟器
    })


@dataclass
class RolloutMetrics:
    """灰度指标"""
    active_users: int = 0
    crash_rate: float = 0.0
    anr_rate: float = 0.0
    api_error_rate: float = 0.0
    negative_feedback_count: int = 0
    total_feedback_count: int = 0
    avg_inference_latency_ms: float = 0.0
    retention_d1: float = 0.0  # 次日留存


class GradualRolloutManager:
    """灰度发布管理器"""

    # 标准灰度阶段
    STAGE_PERCENTAGES = {
        RolloutStage.INTERNAL_TEST: 1.0,
        RolloutStage.ALPHA: 5.0,
        RolloutStage.BETA: 20.0,
        RolloutStage.PRODUCTION_50: 50.0,
        RolloutStage.FULL_RELEASE: 100.0,
    }

    def __init__(self, config: RolloutConfig):
        self.config = config
        self._current_metrics = RolloutMetrics()
        self._stage_history: list[dict] = []
        self._start_time = datetime.now(timezone.utc)

    def should_user_get_update(self, user_id: str) -> bool:
        """判断用户是否应该收到更新（基于哈希分桶）"""
        if self.config.stage == RolloutStage.FULL_RELEASE:
            return True
        if self.config.stage in [RolloutStage.PAUSED, RolloutStage.ROLLED_BACK]:
            return False

        # 使用用户 ID 的哈希值分桶
        hash_value = int(hashlib.sha256(user_id.encode()).hexdigest(), 16)
        bucket = hash_value % 10000  # 0-9999
        threshold = int(self.config.rollout_percentage * 100)
        return bucket < threshold

    def advance_stage(self) -> RolloutStage:
        """推进到下一阶段"""
        if self.config.stage in [RolloutStage.PAUSED, RolloutStage.ROLLED_BACK]:
            return self.config.stage

        stages = list(self.STAGE_PERCENTAGES.keys())
        current_idx = stages.index(self.config.stage) if self.config.stage in stages else -1

        if current_idx < len(stages) - 1:
            old_stage = self.config.stage
            self.config.stage = stages[current_idx + 1]
            self.config.rollout_percentage = self.STAGE_PERCENTAGES[self.config.stage]
            self._stage_history.append({
                "action": "advance",
                "from": old_stage.value,
                "to": self.config.stage.value,
                "percentage": self.config.rollout_percentage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._start_time = datetime.now(timezone.utc)

        return self.config.stage

    def pause_rollout(self, reason: str) -> RolloutStage:
        """暂停灰度"""
        old_stage = self.config.stage
        self.config.stage = RolloutStage.PAUSED
        self._stage_history.append({
            "action": "pause",
            "from": old_stage.value,
            "to": "paused",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return self.config.stage

    def rollback(self, reason: str) -> RolloutStage:
        """回滚"""
        old_stage = self.config.stage
        self.config.stage = RolloutStage.ROLLED_BACK
        self.config.rollout_percentage = 0.0
        self._stage_history.append({
            "action": "rollback",
            "from": old_stage.value,
            "to": "rolled_back",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return self.config.stage

    def update_metrics(self, metrics: RolloutMetrics) -> dict:
        """更新指标并检查是否需要自动回滚"""
        self._current_metrics = metrics
        check_result = self.check_health()
        return check_result

    def check_health(self) -> dict:
        """健康检查"""
        m = self._current_metrics
        thresholds = self.config.auto_rollback_thresholds
        issues = []

        if m.crash_rate > thresholds["crash_rate"]:
            issues.append(f"崩溃率 {m.crash_rate:.2f}% 超过阈值 {thresholds['crash_rate']}%")

        if m.anr_rate > thresholds["anr_rate"]:
            issues.append(f"ANR 率 {m.anr_rate:.2f}% 超过阈值 {thresholds['anr_rate']}%")

        if m.api_error_rate > thresholds["error_rate"]:
            issues.append(f"API 错误率 {m.api_error_rate:.2f}% 超过阈值 {thresholds['error_rate']}%")

        feedback_ratio = (m.negative_feedback_count / m.total_feedback_count
                         if m.total_feedback_count > 0 else 0)
        if feedback_ratio > thresholds["negative_feedback_ratio"]:
            issues.append(f"负面反馈比例 {feedback_ratio:.1%} 超过阈值 {thresholds['negative_feedback_ratio']:.0%}")

        healthy = len(issues) == 0

        result = {
            "healthy": healthy,
            "issues": issues,
            "action": "none",
            "metrics": {
                "active_users": m.active_users,
                "crash_rate": m.crash_rate,
                "anr_rate": m.anr_rate,
                "api_error_rate": m.api_error_rate,
                "avg_inference_latency_ms": m.avg_inference_latency_ms,
                "retention_d1": m.retention_d1,
            },
        }

        if not healthy and self.config.stage not in [RolloutStage.PAUSED, RolloutStage.ROLLED_BACK]:
            result["action"] = "auto_rollback"
            self.rollback(f"自动回滚: {'; '.join(issues)}")

        return result

    def get_rollout_report(self) -> dict:
        """获取灰度报告"""
        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds() / 3600
        return {
            "current_stage": self.config.stage.value,
            "rollout_percentage": self.config.rollout_percentage,
            "target_version": self.config.target_version,
            "platforms": self.config.platforms,
            "elapsed_hours": round(elapsed, 1),
            "min_observation_hours": self.config.min_observation_hours,
            "ready_to_advance": elapsed >= self.config.min_observation_hours and
                                self.check_health()["healthy"],
            "stage_history": self._stage_history,
            "current_metrics": {
                "active_users": self._current_metrics.active_users,
                "crash_rate": self._current_metrics.crash_rate,
                "anr_rate": self._current_metrics.anr_rate,
                "api_error_rate": self._current_metrics.api_error_rate,
            },
        }

    def get_store_rollout_config(self) -> dict:
        """获取商店灰度发布配置"""
        return {
            "google_play": {
                "staged_rollout_percentage": self.config.rollout_percentage,
                "track": self._get_play_track(),
                "country_set": ["CN", "US", "JP"],  # 初始发布国家
            },
            "app_store": {
                "phased_release_enabled": self.config.rollout_percentage < 100,
                "phased_release_percentage": self.config.rollout_percentage,
                "available_countries": ["CN", "US", "JP"],
            },
        }

    def _get_play_track(self) -> str:
        """获取 Google Play 发布轨道"""
        track_map = {
            RolloutStage.INTERNAL_TEST: "internal",
            RolloutStage.ALPHA: "alpha",
            RolloutStage.BETA: "beta",
            RolloutStage.PRODUCTION_50: "production",
            RolloutStage.FULL_RELEASE: "production",
            RolloutStage.PAUSED: "production",
            RolloutStage.ROLLED_BACK: "production",
        }
        return track_map.get(self.config.stage, "internal")
