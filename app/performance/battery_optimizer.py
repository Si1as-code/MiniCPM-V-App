"""
电池优化策略

根据电量状态和充电状态，自适应调整推理频率、后台任务调度
和网络请求策略，在保证功能的前提下最小化电池消耗。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PowerMode(Enum):
    """电源模式"""
    PERFORMANCE = "performance"   # 高性能（充电中/高电量）
    BALANCED = "balanced"          # 均衡（正常使用）
    LOW_POWER = "low_power"        # 低电量（<20%）
    ULTRA_LOW = "ultra_low"        # 超低电量（<10%）


@dataclass
class InferenceSchedule:
    """推理调度配置"""
    mode: PowerMode
    auto_recognition_interval_s: int  # 自动识别间隔（秒）
    max_inference_per_session: int     # 单次会话最大推理次数
    prefer_local: bool                 # 优先端侧推理（省电）
    enable_background_recognition: bool
    enable_cloud_fallback: bool
    model_precision: str               # fp16 / int8 / int4
    camera_resolution: str             # high / medium / low
    max_image_dimension: int

    @classmethod
    def from_power_mode(cls, mode: PowerMode) -> "InferenceSchedule":
        """根据电源模式生成调度配置"""
        configs = {
            PowerMode.PERFORMANCE: cls(
                mode=mode,
                auto_recognition_interval_s=5,
                max_inference_per_session=50,
                prefer_local=True,
                enable_background_recognition=True,
                enable_cloud_fallback=True,
                model_precision="fp16",
                camera_resolution="high",
                max_image_dimension=448,
            ),
            PowerMode.BALANCED: cls(
                mode=mode,
                auto_recognition_interval_s=15,
                max_inference_per_session=30,
                prefer_local=True,
                enable_background_recognition=True,
                enable_cloud_fallback=True,
                model_precision="int8",
                camera_resolution="medium",
                max_image_dimension=448,
            ),
            PowerMode.LOW_POWER: cls(
                mode=mode,
                auto_recognition_interval_s=60,
                max_inference_per_session=15,
                prefer_local=True,
                enable_background_recognition=False,
                enable_cloud_fallback=False,
                model_precision="int8",
                camera_resolution="medium",
                max_image_dimension=336,
            ),
            PowerMode.ULTRA_LOW: cls(
                mode=mode,
                auto_recognition_interval_s=300,
                max_inference_per_session=5,
                prefer_local=True,
                enable_background_recognition=False,
                enable_cloud_fallback=False,
                model_precision="int4",
                camera_resolution="low",
                max_image_dimension=224,
            ),
        }
        return configs[mode]


class BatteryOptimizer:
    """电池优化器"""

    def __init__(self):
        self._current_mode = PowerMode.BALANCED
        self._current_schedule = InferenceSchedule.from_power_mode(PowerMode.BALANCED)
        self._mode_history: list[dict] = []

    def update_power_state(
        self,
        battery_level: int,  # 0-100
        is_charging: bool,
        is_power_saver: bool = False,
    ) -> PowerMode:
        """根据电池状态更新电源模式"""
        if is_power_saver or battery_level < 10:
            new_mode = PowerMode.ULTRA_LOW
        elif battery_level < 20:
            new_mode = PowerMode.LOW_POWER
        elif is_charging or battery_level > 50:
            new_mode = PowerMode.PERFORMANCE
        else:
            new_mode = PowerMode.BALANCED

        if new_mode != self._current_mode:
            self._mode_history.append({
                "from": self._current_mode.value,
                "to": new_mode.value,
                "battery_level": battery_level,
                "is_charging": is_charging,
            })
            self._current_mode = new_mode
            self._current_schedule = InferenceSchedule.from_power_mode(new_mode)

        return new_mode

    def get_current_schedule(self) -> InferenceSchedule:
        """获取当前调度配置"""
        return self._current_schedule

    def should_allow_inference(self, current_count: int) -> bool:
        """判断是否允许推理"""
        return current_count < self._current_schedule.max_inference_per_session

    def should_allow_background_task(self) -> bool:
        """判断是否允许后台任务"""
        return self._current_schedule.enable_background_recognition

    def get_work_scheduler_config(self) -> dict:
        """获取 WorkManager / BGTaskScheduler 配置"""
        schedule = self._current_schedule
        return {
            "android": {
                "recognition_worker": {
                    "interval_minutes": max(15, schedule.auto_recognition_interval_s // 60),
                    "constraints": {
                        "requires_battery_not_low": schedule.mode != PowerMode.ULTRA_LOW,
                        "requires_storage_not_low": True,
                        "required_network_type": "UNMETERED" if schedule.enable_cloud_fallback else "NOT_REQUIRED",
                    },
                    "backoff_policy": "EXPONENTIAL",
                    "backoff_delay": "30s",
                },
                "sync_worker": {
                    "interval_minutes": 60 if schedule.mode != PowerMode.ULTRA_LOW else 360,
                    "constraints": {
                        "requires_battery_not_low": True,
                        "required_network_type": "UNMETERED",
                    },
                },
            },
            "ios": {
                "bg_app_refresh": {
                    "minimum_interval": schedule.auto_recognition_interval_s,
                    "enabled": schedule.enable_background_recognition,
                },
                "bg_processing": {
                    "enabled": schedule.mode in [PowerMode.PERFORMANCE, PowerMode.BALANCED],
                    "requires_network": schedule.enable_cloud_fallback,
                    "requires_external_power": schedule.mode == PowerMode.PERFORMANCE,
                },
            },
        }

    def get_battery_report(self) -> dict:
        """获取电池优化报告"""
        return {
            "current_mode": self._current_mode.value,
            "schedule": {
                "auto_recognition_interval_s": self._current_schedule.auto_recognition_interval_s,
                "max_inference_per_session": self._current_schedule.max_inference_per_session,
                "prefer_local": self._current_schedule.prefer_local,
                "background_recognition": self._current_schedule.enable_background_recognition,
                "cloud_fallback": self._current_schedule.enable_cloud_fallback,
                "model_precision": self._current_schedule.model_precision,
                "camera_resolution": self._current_schedule.camera_resolution,
                "max_image_dimension": self._current_schedule.max_image_dimension,
            },
            "mode_history_count": len(self._mode_history),
            "recent_transitions": self._mode_history[-10:],
            "estimated_battery_savings": self._estimate_savings(),
        }

    def _estimate_savings(self) -> dict:
        """估算不同模式的省电效果"""
        baseline = 100  # PERFORMANCE 模式为基准 100%
        savings = {
            PowerMode.PERFORMANCE: {"relative_consumption": 100, "savings_pct": 0},
            PowerMode.BALANCED: {"relative_consumption": 65, "savings_pct": 35},
            PowerMode.LOW_POWER: {"relative_consumption": 35, "savings_pct": 65},
            PowerMode.ULTRA_LOW: {"relative_consumption": 15, "savings_pct": 85},
        }
        return savings.get(self._current_mode, savings[PowerMode.BALANCED])

    @staticmethod
    def get_doze_mode_config() -> dict:
        """获取 Doze 模式配置（Android）"""
        return {
            "description": "Android Doze 模式下应用被限制后台活动",
            "strategy": {
                "use_high_priority_fcm": True,  # 高优先级 FCM 唤醒
                "use_workmanager_expedited": True,  # 加速任务（Doze 白名单）
                "request_battery_optimization_exemption": False,  # 不申请白名单（合规）
                "foreground_service_during_active": True,  # 活跃时使用前台服务
            },
            "maintain_functionality": [
                "用户主动拍照识别不受影响",
                "前台运行时不受 Doze 限制",
                "高优先级推送可唤醒应用执行关键任务",
            ],
        }
