"""
内存管理优化

包括 LRU 缓存淘汰策略、图片内存优化、内存压力响应。
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from collections import OrderedDict


class CacheEvictionPolicy(Enum):
    """缓存淘汰策略"""
    LRU = "lru"          # 最近最少使用
    LFU = "lfu"          # 最少使用频率
    FIFO = "fifo"        # 先进先出
    TTL = "ttl"          # 基于过期时间


class MemoryWarningLevel(Enum):
    """内存警告等级"""
    NORMAL = "normal"          # 内存正常
    WARNING = "warning"        # 内存警告（>70%）
    CRITICAL = "critical"      # 内存严重（>85%）
    EMERGENCY = "emergency"    # 内存紧急（>95%）


@dataclass
class MemoryWarning:
    """内存警告事件"""
    level: MemoryWarningLevel
    used_mb: float
    total_mb: float
    usage_ratio: float
    timestamp: float = field(default_factory=time.time)
    action_taken: str = ""


class MemoryManager:
    """内存管理器"""

    def __init__(
        self,
        max_cache_size: int = 100,
        max_cache_memory_mb: float = 256.0,
        image_cache_max_mb: float = 128.0,
    ):
        self.max_cache_size = max_cache_size
        self.max_cache_memory_mb = max_cache_memory_mb
        self.image_cache_max_mb = image_cache_max_mb

        # 推理结果缓存（LRU）
        self._inference_cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_sizes: dict[str, int] = {}  # 每项预估内存（KB）

        # 图片缓存
        self._image_cache: OrderedDict[str, bytes] = OrderedDict()
        self._image_sizes: dict[str, int] = {}

        # 内存警告历史
        self._warnings: list[MemoryWarning] = []

        # 当前内存状态
        self._current_level = MemoryWarningLevel.NORMAL

    def cache_inference_result(self, key: str, result: dict, size_kb: int = 50):
        """缓存推理结果"""
        # LRU 淘汰
        while (len(self._inference_cache) >= self.max_cache_size or
               self._get_cache_memory_mb() + size_kb / 1024 > self.max_cache_memory_mb):
            if not self._inference_cache:
                break
            evicted_key, _ = self._inference_cache.popitem(last=False)
            self._cache_sizes.pop(evicted_key, None)

        self._inference_cache[key] = result
        self._cache_sizes[key] = size_kb
        self._inference_cache.move_to_end(key)

    def get_cached_inference(self, key: str) -> Optional[dict]:
        """获取缓存的推理结果"""
        if key in self._inference_cache:
            self._inference_cache.move_to_end(key)
            return self._inference_cache[key]
        return None

    def cache_image(self, key: str, data: bytes):
        """缓存图片数据"""
        size_kb = len(data) / 1024

        while self._get_image_cache_mb() + size_kb / 1024 > self.image_cache_max_mb:
            if not self._image_cache:
                break
            evicted_key, _ = self._image_cache.popitem(last=False)
            self._image_sizes.pop(evicted_key, None)

        self._image_cache[key] = data
        self._image_sizes[key] = int(size_kb)
        self._image_cache.move_to_end(key)

    def get_cached_image(self, key: str) -> Optional[bytes]:
        """获取缓存的图片"""
        if key in self._image_cache:
            self._image_cache.move_to_end(key)
            return self._image_cache[key]
        return None

    def handle_memory_warning(self, used_mb: float, total_mb: float) -> MemoryWarning:
        """处理内存警告"""
        ratio = used_mb / total_mb if total_mb > 0 else 0

        if ratio > 0.95:
            level = MemoryWarningLevel.EMERGENCY
            action = self._handle_emergency()
        elif ratio > 0.85:
            level = MemoryWarningLevel.CRITICAL
            action = self._handle_critical()
        elif ratio > 0.70:
            level = MemoryWarningLevel.WARNING
            action = self._handle_warning()
        else:
            level = MemoryWarningLevel.NORMAL
            action = "no action needed"

        warning = MemoryWarning(
            level=level, used_mb=used_mb, total_mb=total_mb,
            usage_ratio=ratio, action_taken=action,
        )
        self._warnings.append(warning)
        self._current_level = level
        return warning

    def _handle_warning(self) -> str:
        """处理警告级别"""
        # 清理一半图片缓存
        count = len(self._image_cache) // 2
        for _ in range(count):
            if self._image_cache:
                k, _ = self._image_cache.popitem(last=False)
                self._image_sizes.pop(k, None)
        return f"cleared {count} image cache entries"

    def _handle_critical(self) -> str:
        """处理严重级别"""
        # 清理所有图片缓存 + 一半推理缓存
        img_count = len(self._image_cache)
        self._image_cache.clear()
        self._image_sizes.clear()

        inf_count = len(self._inference_cache) // 2
        for _ in range(inf_count):
            if self._inference_cache:
                k, _ = self._inference_cache.popitem(last=False)
                self._cache_sizes.pop(k, None)
        return f"cleared {img_count} images, {inf_count} inference cache"

    def _handle_emergency(self) -> str:
        """处理紧急级别"""
        # 清理所有缓存
        img_count = len(self._image_cache)
        inf_count = len(self._inference_cache)
        self._image_cache.clear()
        self._image_sizes.clear()
        self._inference_cache.clear()
        self._cache_sizes.clear()
        return f"emergency: cleared all caches ({img_count} images, {inf_count} inferences)"

    def clear_all(self):
        """清理所有缓存"""
        self._inference_cache.clear()
        self._cache_sizes.clear()
        self._image_cache.clear()
        self._image_sizes.clear()

    def get_memory_stats(self) -> dict:
        """获取内存统计"""
        return {
            "inference_cache": {
                "entries": len(self._inference_cache),
                "max_entries": self.max_cache_size,
                "memory_mb": self._get_cache_memory_mb(),
                "max_memory_mb": self.max_cache_memory_mb,
            },
            "image_cache": {
                "entries": len(self._image_cache),
                "memory_mb": self._get_image_cache_mb(),
                "max_memory_mb": self.image_cache_max_mb,
            },
            "current_level": self._current_level.value,
            "total_warnings": len(self._warnings),
            "last_warning": self._warnings[-1].__dict__ if self._warnings else None,
        }

    def _get_cache_memory_mb(self) -> float:
        return sum(self._cache_sizes.values()) / 1024

    def _get_image_cache_mb(self) -> float:
        return sum(self._image_sizes.values()) / 1024

    @staticmethod
    def get_image_optimization_config() -> dict:
        """获取图片内存优化配置"""
        return {
            "android": {
                "bitmap_config": "ARGB_8888",  # 32-bit
                "in_sample_size": 2,  # 下采样因子
                "target_size_px": 448,  # 推理输入尺寸
                "coil_memory_cache_pct": 0.15,  # Coil 内存缓存占可用内存比例
                "coil_disk_cache_mb": 100,
                "downsample_strategy": "CENTER_CROP",  # 中心裁剪
            },
            "ios": {
                "target_size_px": 448,
                "compression_quality": 0.8,
                "use_downsampling": True,
                "image_cache_total_cost_mb": 100,  # NSCache totalCostLimit
                "image_cache_count_limit": 50,
                "preload_all_images": False,
            },
            "shared": {
                "max_image_dimension": 448,  # 最大边长
                "min_image_dimension": 64,   # 最小边长
                "supported_formats": ["jpg", "png", "webp"],
                "convert_to_rgb": True,      # 推理前转 RGB
            },
        }
