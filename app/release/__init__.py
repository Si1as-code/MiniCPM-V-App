"""
Sprint 8: 发布管理模块

包含：
- 灰度发布管理（分阶段 rollout）
- A/B 测试框架
- 数据库迁移方案（SQLite → PostgreSQL 双写过渡）
"""

from .gradual_rollout import GradualRolloutManager, RolloutStage, RolloutConfig
from .ab_test import ABTestManager, Experiment, Variant, ExperimentResult
from .migration_plan import DatabaseMigrationPlan, MigrationPhase, MigrationStatus

__all__ = [
    "GradualRolloutManager",
    "RolloutStage",
    "RolloutConfig",
    "ABTestManager",
    "Experiment",
    "Variant",
    "ExperimentResult",
    "DatabaseMigrationPlan",
    "MigrationPhase",
    "MigrationStatus",
]
