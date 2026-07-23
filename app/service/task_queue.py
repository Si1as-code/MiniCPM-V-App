import asyncio
import json
import logging
import time
from typing import Optional, Callable, Any

from service.config import service_config

logger = logging.getLogger(__name__)


class TaskQueue:
    """基于 Redis 的异步任务队列"""

    def __init__(self):
        self._redis = None
        self._running = False
        self._queue_key = "minicpmv:task_queue"

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    service_config.redis_dsn,
                    decode_responses=True,
                )
                await self._redis.ping()
                logger.info("Redis 连接成功")
            except Exception as e:
                logger.warning(f"Redis 连接失败，使用内存队列: {e}")
                self._redis = None
        return self._redis

    async def enqueue(self, task_data: dict) -> bool:
        """
        将任务推入队列

        Args:
            task_data: 任务数据字典
                - task_id: 任务 ID
                - type: 任务类型 (inference / sync / cleanup)
                - payload: 任务负载
        """
        redis = await self._get_redis()
        if redis:
            await redis.lpush(self._queue_key, json.dumps(task_data))
        else:
            # 内存队列回退
            if not hasattr(self, "_memory_queue"):
                self._memory_queue = []
            self._memory_queue.append(task_data)
        logger.info(f"任务已入队: {task_data.get('task_id', 'unknown')}")
        return True

    async def dequeue(self) -> Optional[dict]:
        """从队列取出任务"""
        redis = await self._get_redis()
        if redis:
            data = await redis.rpop(self._queue_key)
            return json.loads(data) if data else None
        else:
            if hasattr(self, "_memory_queue") and self._memory_queue:
                return self._memory_queue.pop(0)
        return None

    async def process_next(self, handler: Callable[[dict], Any]) -> bool:
        """
        处理下一个任务

        Args:
            handler: 任务处理函数，接收任务数据 dict

        Returns:
            bool: 是否有任务被处理
        """
        task = await self.dequeue()
        if task is None:
            return False

        try:
            logger.info(f"处理任务: {task.get('task_id', 'unknown')}")
            await handler(task)
            return True
        except Exception as e:
            logger.error(f"任务处理失败: {task.get('task_id', 'unknown')}: {e}")
            return False

    async def start_worker(self, handler: Callable[[dict], Any]):
        """启动后台工作线程"""
        self._running = True
        logger.info("任务队列工作线程已启动")
        while self._running:
            try:
                processed = await self.process_next(handler)
                if not processed:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"工作线程异常: {e}")
                await asyncio.sleep(5)

    async def stop_worker(self):
        """停止工作线程"""
        self._running = False
        logger.info("任务队列工作线程已停止")

    async def queue_length(self) -> int:
        """获取队列长度"""
        redis = await self._get_redis()
        if redis:
            return await redis.llen(self._queue_key)
        return len(getattr(self, "_memory_queue", []))


# 全局单例
task_queue = TaskQueue()