import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from service.config import service_config

logger = logging.getLogger(__name__)


@dataclass
class SyncEngineConfig:
    batch_size: int = field(default_factory=lambda: service_config.sync_batch_size)
    sync_interval: int = field(default_factory=lambda: service_config.sync_interval)
    conflict_strategy: str = "last_write_wins"  # last_write_wins / manual


@dataclass
class SyncResult:
    success: bool = False
    uploaded: int = 0
    downloaded: int = 0
    conflicts: int = 0
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0


class SyncEngine:
    _instance: Optional["SyncEngine"] = None

    def __new__(cls) -> "SyncEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.config = SyncEngineConfig()

    async def sync_records(
        self,
        user_id: str,
        device_id: str,
        db_pool=None,
        local_dao=None,
    ) -> SyncResult:
        """
        增量同步：将本地未同步的 recognition_records 上传到云端

        Args:
            user_id: 用户 ID
            device_id: 设备 ID
            db_pool: PostgreSQL 连接池
            local_dao: 本地 recognition DAO

        Returns:
            SyncResult
        """
        t_start = time.time()
        result = SyncResult()

        if local_dao is None or db_pool is None:
            result.errors.append("local_dao 和 db_pool 不能为空")
            return result

        try:
            # 1. 获取本地未同步记录
            unsynced = local_dao.get_unsynced(limit=self.config.batch_size)
            if not unsynced:
                logger.info("同步: 无未同步记录")
                result.success = True
                return result

            logger.info(f"同步: 发现 {len(unsynced)} 条未同步记录")

            # 2. 批量上传到云端
            uploaded = 0
            for record in unsynced:
                try:
                    # 检查云端是否已存在（基于 image_hash 去重）
                    existing = await db_pool.fetchrow(
                        "SELECT id, updated_at FROM recognition_records_cloud "
                        "WHERE user_id = $1 AND image_hash = $2",
                        user_id, record.image_hash,
                    )

                    if existing:
                        # 冲突解决: last_write_wins
                        if record.updated_at and existing["updated_at"]:
                            if record.updated_at <= existing["updated_at"].timestamp():
                                # 云端更新，跳过
                                local_dao.mark_synced(record.id)
                                result.conflicts += 1
                                continue

                    # 插入或更新
                    if existing:
                        await db_pool.execute(
                            """UPDATE recognition_records_cloud
                               SET question = $1, answer = $2, confidence = $3,
                                   model_version = $4, updated_at = NOW()
                               WHERE id = $5""",
                            record.question, record.answer, record.confidence,
                            record.model_version, existing["id"],
                        )
                    else:
                        await db_pool.execute(
                            """INSERT INTO recognition_records_cloud
                               (user_id, image_hash, image_url, question, answer,
                                confidence, model_version, device_id, task_type)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                            user_id, record.image_hash, record.image_path,
                            record.question, record.answer, record.confidence,
                            record.model_version, device_id, record.task_type,
                        )

                    # 标记已同步
                    local_dao.mark_synced(record.id)
                    uploaded += 1

                    # 记录同步日志
                    await db_pool.execute(
                        """INSERT INTO sync_log
                           (user_id, device_id, table_name, record_id, operation)
                           VALUES ($1, $2, $3, $4, $5)""",
                        user_id, device_id, "recognition_records",
                        record.id, "insert" if not existing else "update",
                    )

                except Exception as e:
                    error_msg = f"同步记录 {record.id} 失败: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            result.uploaded = uploaded
            result.success = True
            logger.info(f"同步完成: 上传 {uploaded} 条, 冲突 {result.conflicts} 条")

        except Exception as e:
            logger.error(f"同步过程出错: {e}")
            result.errors.append(str(e))

        result.duration = time.time() - t_start
        return result

    async def sync_from_cloud(
        self,
        user_id: str,
        device_id: str,
        db_pool=None,
        local_dao=None,
    ) -> SyncResult:
        """
        从云端拉取其他设备的变更到本地
        """
        t_start = time.time()
        result = SyncResult()

        if local_dao is None or db_pool is None:
            result.errors.append("local_dao 和 db_pool 不能为空")
            return result

        try:
            # 获取非本设备的云端变更
            rows = await db_pool.fetch(
                """SELECT r.* FROM recognition_records_cloud r
                   JOIN sync_log s ON r.id = s.record_id
                   WHERE r.user_id = $1
                     AND s.device_id != $2
                     AND s.table_name = 'recognition_records'
                   ORDER BY s.synced_at DESC
                   LIMIT $3""",
                user_id, device_id, self.config.batch_size,
            )

            logger.info(f"从云端拉取: 发现 {len(rows)} 条变更")
            result.downloaded = len(rows)

        except Exception as e:
            logger.error(f"从云端拉取失败: {e}")
            result.errors.append(str(e))

        result.duration = time.time() - t_start
        return result

    async def full_sync(
        self,
        user_id: str,
        device_id: str,
        db_pool=None,
        local_dao=None,
    ) -> SyncResult:
        """全量同步"""
        upload_result = await self.sync_records(user_id, device_id, db_pool, local_dao)
        download_result = await self.sync_from_cloud(user_id, device_id, db_pool, local_dao)
        return SyncResult(
            success=upload_result.success and download_result.success,
            uploaded=upload_result.uploaded,
            downloaded=download_result.downloaded,
            conflicts=upload_result.conflicts + download_result.conflicts,
            errors=upload_result.errors + download_result.errors,
            duration=upload_result.duration + download_result.duration,
        )


def get_sync_engine() -> SyncEngine:
    return SyncEngine()