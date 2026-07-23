import asyncio
import logging
from typing import Optional

import asyncpg

from service.config import service_config

logger = logging.getLogger(__name__)


class DatabasePool:
    _instance: Optional["DatabasePool"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> "DatabasePool":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def init_pool(self):
        if self._initialized:
            return
        self._pool = await asyncpg.create_pool(
            dsn=service_config.db_dsn,
            min_size=service_config.db_min_pool,
            max_size=service_config.db_max_pool,
            command_timeout=30,
        )
        self._initialized = True
        logger.info(
            f"PostgreSQL 连接池已初始化: "
            f"min={service_config.db_min_pool}, max={service_config.db_max_pool}"
        )

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("PostgreSQL 连接池已关闭")

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("数据库连接池未初始化，请先调用 init_pool()")
        return self._pool

    async def health_check(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval("SELECT 1")
                return val == 1
        except Exception:
            return False

    async def execute(self, query: str, *args) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute_many(self, query: str, args_list: list):
        async with self.pool.acquire() as conn:
            return await conn.executemany(query, args_list)


async def init_db_pool():
    pool = await DatabasePool.get_instance()
    await pool.init_pool()


async def close_db_pool():
    pool = await DatabasePool.get_instance()
    await pool.close()


def get_db_pool() -> DatabasePool:
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # 异步上下文
        import asyncio as aio
        return aio.run(DatabasePool.get_instance())
    # 同步上下文
    return DatabasePool._instance or DatabasePool()