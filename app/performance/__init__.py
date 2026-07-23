"""
Sprint 8: 性能打磨模块

包含：
- 冷启动优化（延迟初始化、预加载策略）
- 内存管理（缓存淘汰、图片内存优化）
- 电池策略（自适应推理频率、低电量模式）
"""

from .cold_start import ColdStartOptimizer, StartupPhase, StartupProfile
from .memory_manager import MemoryManager, CacheEvictionPolicy, MemoryWarning
from .battery_optimizer import BatteryOptimizer, PowerMode, InferenceSchedule

__all__ = [
    "ColdStartOptimizer",
    "StartupPhase",
    "StartupProfile",
    "MemoryManager",
    "CacheEvictionPolicy",
    "MemoryWarning",
    "BatteryOptimizer",
    "PowerMode",
    "InferenceSchedule",
]
