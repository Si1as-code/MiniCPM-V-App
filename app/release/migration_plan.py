"""
数据库迁移方案

实现 SQLite → PostgreSQL 双写过渡期管理，
确保零数据丢失、可回滚、可验证。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class MigrationPhase(Enum):
    """迁移阶段"""
    PREPARATION = "preparation"       # 准备阶段：建表、校验
    DUAL_WRITE = "dual_write"         # 双写阶段：同时写 SQLite 和 PostgreSQL
    VERIFICATION = "verification"      # 验证阶段：数据一致性校验
    READ_SWITCH = "read_switch"        # 读切换：读从 PostgreSQL
    SQLITE_READONLY = "sqlite_readonly" # SQLite 只读
    CLEANUP = "cleanup"                 # 清理：停用 SQLite
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class MigrationStatus(Enum):
    """迁移状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class MigrationStep:
    """迁移步骤"""
    phase: MigrationPhase
    name: str
    description: str
    status: MigrationStatus = MigrationStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    records_migrated: int = 0
    error: str = ""

    def start(self):
        self.status = MigrationStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc).isoformat()

    def complete(self, records: int = 0):
        self.status = MigrationStatus.SUCCESS
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.records_migrated = records

    def fail(self, error: str):
        self.status = MigrationStatus.FAILED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.error = error


class DatabaseMigrationPlan:
    """数据库迁移方案"""

    def __init__(self):
        self._current_phase = MigrationPhase.PREPARATION
        self._steps: list[MigrationStep] = []
        self._init_steps()
        self._dual_write_enabled = False
        self._read_source = "sqlite"  # sqlite / postgresql
        self._migration_log: list[dict] = []

    def _init_steps(self):
        """初始化迁移步骤"""
        self._steps = [
            MigrationStep(
                phase=MigrationPhase.PREPARATION,
                name="create_pg_schema",
                description="在 PostgreSQL 中创建与 SQLite 对应的表结构",
            ),
            MigrationStep(
                phase=MigrationPhase.PREPARATION,
                name="validate_schema",
                description="验证两端 schema 一致性（字段、类型、约束）",
            ),
            MigrationStep(
                phase=MigrationPhase.PREPARATION,
                name="bulk_import",
                description="将 SQLite 现有数据批量导入 PostgreSQL",
            ),
            MigrationStep(
                phase=MigrationPhase.DUAL_WRITE,
                name="enable_dual_write",
                description="开启双写模式：所有写入同时操作 SQLite 和 PostgreSQL",
            ),
            MigrationStep(
                phase=MigrationPhase.DUAL_WRITE,
                name="monitor_dual_write",
                description="监控双写延迟和错误率",
            ),
            MigrationStep(
                phase=MigrationPhase.VERIFICATION,
                name="data_consistency_check",
                description="逐表对比 SQLite 和 PostgreSQL 数据一致性",
            ),
            MigrationStep(
                phase=MigrationPhase.VERIFICATION,
                name="incremental_sync",
                description="同步双写期间产生的增量数据",
            ),
            MigrationStep(
                phase=MigrationPhase.READ_SWITCH,
                name="switch_read_to_pg",
                description="将读操作切换到 PostgreSQL",
            ),
            MigrationStep(
                phase=MigrationPhase.SQLITE_READONLY,
                name="sqlite_readonly_mode",
                description="将 SQLite 设为只读模式（仅作为备份）",
            ),
            MigrationStep(
                phase=MigrationPhase.CLEANUP,
                name="stop_sqlite_write",
                description="停止 SQLite 写入，完全使用 PostgreSQL",
            ),
            MigrationStep(
                phase=MigrationPhase.CLEANUP,
                name="archive_sqlite",
                description="归档 SQLite 数据库文件",
            ),
        ]

    def execute_step(self, step_name: str, callback: Optional[callable] = None) -> MigrationStep:
        """执行迁移步骤"""
        step = next((s for s in self._steps if s.name == step_name), None)
        if not step:
            raise ValueError(f"未知步骤: {step_name}")

        step.start()
        self._log("step_started", step_name)

        try:
            records = 0
            if callback:
                records = callback() or 0

            step.complete(records)
            self._log("step_completed", step_name, {"records": records})

            # 更新当前阶段
            self._update_phase(step)

        except Exception as e:
            step.fail(str(e))
            self._log("step_failed", step_name, {"error": str(e)})
            self._current_phase = MigrationPhase.ROLLED_BACK

        return step

    def _update_phase(self, completed_step: MigrationStep):
        """根据完成的步骤更新当前阶段"""
        phase_order = [
            MigrationPhase.PREPARATION,
            MigrationPhase.DUAL_WRITE,
            MigrationPhase.VERIFICATION,
            MigrationPhase.READ_SWITCH,
            MigrationPhase.SQLITE_READONLY,
            MigrationPhase.CLEANUP,
            MigrationPhase.COMPLETED,
        ]

        if completed_step.name == "enable_dual_write":
            self._dual_write_enabled = True
        elif completed_step.name == "switch_read_to_pg":
            self._read_source = "postgresql"
        elif completed_step.name == "stop_sqlite_write":
            self._dual_write_enabled = False
        elif completed_step.name == "archive_sqlite":
            self._current_phase = MigrationPhase.COMPLETED
            return

        # 更新当前阶段
        current_idx = phase_order.index(self._current_phase)
        next_phase = phase_order[min(current_idx + 1, len(phase_order) - 1)]

        # 检查当前阶段所有步骤是否完成
        current_phase_steps = [s for s in self._steps if s.phase == self._current_phase]
        if all(s.status == MigrationStatus.SUCCESS for s in current_phase_steps):
            self._current_phase = next_phase

    def rollback(self, reason: str):
        """回滚迁移"""
        self._current_phase = MigrationPhase.ROLLED_BACK
        self._dual_write_enabled = False
        self._read_source = "sqlite"
        self._log("rollback", "all", {"reason": reason})

    def get_dual_write_config(self) -> dict:
        """获取双写配置"""
        return {
            "enabled": self._dual_write_enabled,
            "primary": "sqlite" if self._current_phase.value < MigrationPhase.READ_SWITCH.value else "postgresql",
            "read_source": self._read_source,
            "write_targets": ["sqlite", "postgresql"] if self._dual_write_enabled else [self._read_source],
            "conflict_resolution": "postgresql_wins",  # 冲突时 PostgreSQL 优先
            "error_handling": {
                "sqlite_write_failure": "log_and_continue",  # SQLite 写失败不影响主流程
                "pg_write_failure": "retry_3_times",         # PG 写失败重试 3 次
                "sync_error_threshold": 0.01,                # 同步错误率阈值 1%
            },
        }

    def get_migration_progress(self) -> dict:
        """获取迁移进度"""
        total_steps = len(self._steps)
        completed_steps = sum(1 for s in self._steps if s.status == MigrationStatus.SUCCESS)
        failed_steps = sum(1 for s in self._steps if s.status == MigrationStatus.FAILED)
        pending_steps = sum(1 for s in self._steps if s.status == MigrationStatus.PENDING)

        return {
            "current_phase": self._current_phase.value,
            "dual_write_enabled": self._dual_write_enabled,
            "read_source": self._read_source,
            "progress": f"{completed_steps}/{total_steps}",
            "progress_pct": round(completed_steps / total_steps * 100, 1),
            "completed": completed_steps,
            "failed": failed_steps,
            "pending": pending_steps,
            "steps": [
                {
                    "name": s.name,
                    "phase": s.phase.value,
                    "status": s.status.value,
                    "records_migrated": s.records_migrated,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "error": s.error,
                }
                for s in self._steps
            ],
            "log_entries": len(self._migration_log),
        }

    def generate_runbook(self) -> str:
        """生成迁移操作手册"""
        return """# 数据库迁移操作手册
# SQLite → PostgreSQL 双写过渡

## 概述

本手册描述将 MiniCPM-V App 的本地 SQLite 数据库
迁移到云端 PostgreSQL 的完整流程。

## 迁移阶段

### 阶段 1: 准备 (Preparation)
1. 在 PostgreSQL 中创建对应表结构
2. 验证两端 schema 一致性
3. 批量导入现有数据

```python
# 执行准备步骤
plan.execute_step("create_pg_schema", create_pg_schema_callback)
plan.execute_step("validate_schema", validate_schema_callback)
plan.execute_step("bulk_import", bulk_import_callback)
```

### 阶段 2: 双写 (Dual Write)
4. 开启双写模式
5. 监控双写延迟和错误

```python
# 开启双写
plan.execute_step("enable_dual_write")
# 此时所有写入操作同时写 SQLite 和 PostgreSQL

# DAO 层双写示例
def insert_record(data):
    sqlite_dao.insert(data)     # 本地写入
    pg_dao.insert(data)         # 云端写入
    # SQLite 写失败不影响主流程
    # PG 写失败重试 3 次
```

### 阶段 3: 验证 (Verification)
6. 数据一致性校验
7. 增量数据同步

```python
# 一致性校验
def verify_consistency():
    for table in tables:
        sqlite_count = sqlite_dao.count(table)
        pg_count = pg_dao.count(table)
        assert sqlite_count == pg_count, f"{table}: {sqlite_count} != {pg_count}"
```

### 阶段 4: 读切换 (Read Switch)
8. 将读操作切换到 PostgreSQL

```python
plan.execute_step("switch_read_to_pg")
# 此后所有读操作走 PostgreSQL
# SQLite 继续双写
```

### 阶段 5: SQLite 只读
9. 将 SQLite 设为只读

### 阶段 6: 清理 (Cleanup)
10. 停止 SQLite 写入
11. 归档 SQLite 文件

## 回滚策略

任何阶段失败均可回滚到 SQLite 单写模式：

```python
plan.rollback("数据一致性校验失败")
# 回滚后：
# - dual_write = False
# - read_source = "sqlite"
# - 所有操作回到 SQLite
```

## 监控指标

- 双写延迟 (< 100ms)
- 双写错误率 (< 0.01%)
- 数据一致性差异 (0 条)
- PostgreSQL 查询延迟 (P95 < 50ms)

## 预计时间线

| 阶段 | 预计耗时 | 观察期 |
|------|---------|--------|
| 准备 | 1 小时 | - |
| 双写 | - | 7 天 |
| 验证 | 2 小时 | 1 天 |
| 读切换 | 30 分钟 | 3 天 |
| SQLite 只读 | - | 7 天 |
| 清理 | 1 小时 | - |
| **总计** | | **约 18 天** |
"""

    def _log(self, event: str, step: str, extra: dict = None):
        """记录迁移日志"""
        entry = {
            "event": event,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            entry.update(extra)
        self._migration_log.append(entry)
