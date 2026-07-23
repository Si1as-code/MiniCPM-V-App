"""
A/B 测试框架

支持实验配置、用户分桶、变体分配和结果统计。
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ExperimentStatus(Enum):
    """实验状态"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Variant:
    """实验变体"""
    name: str                  # control / treatment_a / treatment_b
    description: str = ""
    weight: float = 50.0       # 权重（百分比）
    # 实验参数
    config: dict = field(default_factory=dict)
    # 统计
    participants: int = 0
    conversions: int = 0
    metrics_sum: dict = field(default_factory=dict)  # 指标累计值
    metrics_count: dict = field(default_factory=dict)  # 指标计数

    @property
    def conversion_rate(self) -> float:
        return self.conversions / self.participants if self.participants > 0 else 0.0

    def get_metric_avg(self, metric_name: str) -> float:
        total = self.metrics_sum.get(metric_name, 0.0)
        count = self.metrics_count.get(metric_name, 0)
        return total / count if count > 0 else 0.0

    def record_conversion(self, metric_name: str = "", metric_value: float = 0.0):
        """记录转化"""
        self.conversions += 1
        if metric_name:
            self.metrics_sum[metric_name] = self.metrics_sum.get(metric_name, 0.0) + metric_value
            self.metrics_count[metric_name] = self.metrics_count.get(metric_name, 0) + 1


@dataclass
class Experiment:
    """A/B 测试实验"""
    experiment_id: str
    name: str
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: dict[str, Variant] = field(default_factory=dict)

    # 实验配置
    primary_metric: str = "conversion_rate"  # 主要指标
    secondary_metrics: list = field(default_factory=list)
    min_sample_size: int = 1000              # 最小样本量
    significance_level: float = 0.05         # 显著性水平
    min_effect_size: float = 0.05            # 最小效应量 (5%)

    # 时间
    started_at: Optional[str] = None
    ended_at: Optional[str] = None

    def add_variant(self, variant: Variant):
        self.variants[variant.name] = variant

    def assign_variant(self, user_id: str) -> str:
        """为用户分配变体（确定性分配）"""
        hash_value = int(hashlib.sha256(
            f"{self.experiment_id}:{user_id}".encode()
        ).hexdigest(), 16)
        bucket = hash_value % 10000  # 0-9999

        cumulative = 0.0
        for name, variant in self.variants.items():
            cumulative += variant.weight * 100  # weight 是百分比
            if bucket < cumulative:
                variant.participants += 1
                return name

        # fallback
        first_variant = next(iter(self.variants))
        self.variants[first_variant].participants += 1
        return first_variant


@dataclass
class ExperimentResult:
    """实验结果"""
    experiment_id: str
    winner: Optional[str] = None
    is_significant: bool = False
    confidence: float = 0.0
    lift: float = 0.0  # 提升幅度
    variant_results: dict = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "winner": self.winner,
            "is_significant": self.is_significant,
            "confidence": self.confidence,
            "lift": self.lift,
            "variant_results": self.variant_results,
            "recommendation": self.recommendation,
        }


class ABTestManager:
    """A/B 测试管理器"""

    def __init__(self):
        self._experiments: dict[str, Experiment] = {}

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        variants: list[Variant],
        primary_metric: str = "conversion_rate",
        **kwargs,
    ) -> Experiment:
        """创建实验"""
        exp = Experiment(
            experiment_id=experiment_id,
            name=name,
            primary_metric=primary_metric,
            **kwargs,
        )
        for v in variants:
            exp.add_variant(v)
        self._experiments[experiment_id] = exp
        return exp

    def start_experiment(self, experiment_id: str) -> Experiment:
        """启动实验"""
        exp = self._experiments[experiment_id]
        exp.status = ExperimentStatus.RUNNING
        exp.started_at = datetime.now(timezone.utc).isoformat()
        return exp

    def get_variant_for_user(self, experiment_id: str, user_id: str) -> Optional[str]:
        """获取用户在实验中的变体分配"""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return None
        return exp.assign_variant(user_id)

    def record_conversion(
        self,
        experiment_id: str,
        variant_name: str,
        metric_name: str = "",
        metric_value: float = 0.0,
    ):
        """记录转化事件"""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return
        variant = exp.variants.get(variant_name)
        if variant:
            variant.record_conversion(metric_name, metric_value)

    def analyze_experiment(self, experiment_id: str) -> ExperimentResult:
        """分析实验结果"""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return ExperimentResult(experiment_id=experiment_id, recommendation="实验不存在")

        result = ExperimentResult(experiment_id=experiment_id)
        control = exp.variants.get("control")
        if not control:
            result.recommendation = "无对照组"
            return result

        # 收集各变体结果
        best_variant = control
        best_rate = control.conversion_rate

        for name, variant in exp.variants.items():
            rate = variant.conversion_rate
            result.variant_results[name] = {
                "participants": variant.participants,
                "conversions": variant.conversions,
                "conversion_rate": rate,
                "metrics": {
                    m: variant.get_metric_avg(m)
                    for m in set(variant.metrics_sum.keys())
                },
            }

            if name != "control" and rate > best_rate:
                best_variant = variant
                best_rate = rate

        # 计算提升
        if control.conversion_rate > 0:
            result.lift = (best_rate - control.conversion_rate) / control.conversion_rate
        else:
            result.lift = 0.0

        # Z 检验（简化版）
        result.is_significant = self._z_test(
            control.participants, control.conversions,
            best_variant.participants, best_variant.conversions,
            exp.significance_level,
        )

        result.confidence = self._calculate_confidence(
            control.participants, control.conversions,
            best_variant.participants, best_variant.conversions,
        )

        # 样本量检查
        total_participants = sum(v.participants for v in exp.variants.values())
        if total_participants < exp.min_sample_size:
            result.recommendation = f"样本量不足 ({total_participants}/{exp.min_sample_size})，继续实验"
        elif result.is_significant and result.lift >= exp.min_effect_size:
            result.winner = best_variant.name
            result.recommendation = f"变体 '{best_variant.name}' 显著优于对照组，建议全量发布"
        else:
            result.recommendation = "无显著差异，建议结束实验并保持对照组"

        return result

    def end_experiment(self, experiment_id: str) -> Experiment:
        """结束实验"""
        exp = self._experiments[experiment_id]
        exp.status = ExperimentStatus.COMPLETED
        exp.ended_at = datetime.now(timezone.utc).isoformat()
        return exp

    def get_experiment_summary(self) -> list[dict]:
        """获取所有实验摘要"""
        summaries = []
        for exp_id, exp in self._experiments.items():
            summaries.append({
                "id": exp_id,
                "name": exp.name,
                "status": exp.status.value,
                "variants": list(exp.variants.keys()),
                "total_participants": sum(v.participants for v in exp.variants.values()),
                "started_at": exp.started_at,
                "ended_at": exp.ended_at,
            })
        return summaries

    @staticmethod
    def _z_test(n1: int, c1: int, n2: int, c2: int, alpha: float = 0.05) -> bool:
        """Z 检验（双比例检验）"""
        if n1 == 0 or n2 == 0:
            return False

        p1 = c1 / n1
        p2 = c2 / n2
        p_pool = (c1 + c2) / (n1 + n2)

        if p_pool == 0 or p_pool == 1:
            return False

        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        if se == 0:
            return False

        z = abs(p1 - p2) / se
        # 双侧检验，alpha=0.05 对应 z > 1.96
        z_critical = 1.96 if alpha == 0.05 else 2.576 if alpha == 0.01 else 1.645
        return z > z_critical

    @staticmethod
    def _calculate_confidence(n1: int, c1: int, n2: int, c2: int) -> float:
        """计算置信度"""
        if n1 == 0 or n2 == 0:
            return 0.0

        p1 = c1 / n1
        p2 = c2 / n2
        p_pool = (c1 + c2) / (n1 + n2)

        if p_pool == 0 or p_pool == 1:
            return 0.0

        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        if se == 0:
            return 0.0

        z = abs(p1 - p2) / se
        # 近似置信度
        confidence = min(99.9, 50 + 50 * math.erf(z / math.sqrt(2)))
        return round(confidence, 1)
