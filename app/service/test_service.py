"""
============================================================================
Sprint 4 测试脚本 - 后台服务层
============================================================================
测试内容:
  1. 服务配置默认值
  2. 环境变量覆盖
  3. JWT 令牌创建和验证
  4. JWT 依赖注入
  5. 密码哈希和验证
  6. 验证码生成和验证
  7. OSS 模拟上传
  8. 同步引擎配置
  9. 内存任务队列
  10. WebSocket 连接管理器
============================================================================
"""

import os
import sys
import time
import unittest

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestServiceConfig(unittest.TestCase):
    """测试服务配置"""

    def test_service_config_defaults(self):
        """验证 ServiceConfig 默认值"""
        from service.config import ServiceConfig

        config = ServiceConfig()
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.api_prefix, "/api")
        self.assertEqual(config.db_host, "localhost")
        self.assertEqual(config.db_port, 5432)
        self.assertEqual(config.db_name, "minicpmv")
        self.assertEqual(config.redis_host, "localhost")
        self.assertEqual(config.redis_port, 6379)
        self.assertEqual(config.jwt_algorithm, "HS256")
        self.assertEqual(config.jwt_access_expire, 86400)  # 24h
        self.assertEqual(config.jwt_refresh_expire, 2592000)  # 30d
        self.assertEqual(config.oss_provider, "aliyun")
        self.assertEqual(config.sync_batch_size, 50)
        self.assertEqual(config.sync_interval, 300)
        self.assertEqual(config.rate_limit_per_minute, 60)

    def test_service_config_env_override(self):
        """验证环境变量覆盖"""
        os.environ["SERVICE_HOST"] = "127.0.0.1"
        os.environ["SERVICE_PORT"] = "9000"
        os.environ["SERVICE_DB_HOST"] = "pg.example.com"
        os.environ["SERVICE_JWT_SECRET"] = "test_secret_key"
        os.environ["SERVICE_RATE_LIMIT"] = "100"

        # 重新导入以使用新环境变量
        import importlib
        import service.config
        importlib.reload(service.config)
        config = service.config.ServiceConfig()

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.db_host, "pg.example.com")
        self.assertEqual(config.jwt_secret, "test_secret_key")
        self.assertEqual(config.rate_limit_per_minute, 100)

        # 清理环境变量
        for key in ["SERVICE_HOST", "SERVICE_PORT", "SERVICE_DB_HOST",
                     "SERVICE_JWT_SECRET", "SERVICE_RATE_LIMIT"]:
            del os.environ[key]

    def test_db_dsn_property(self):
        """验证 db_dsn 属性"""
        from service.config import ServiceConfig
        config = ServiceConfig()
        expected = "postgresql://postgres:postgres@localhost:5432/minicpmv"
        self.assertEqual(config.db_dsn, expected)

    def test_redis_dsn_property(self):
        """验证 redis_dsn 属性"""
        from service.config import ServiceConfig
        config = ServiceConfig()
        expected = "redis://localhost:6379/0"
        self.assertEqual(config.redis_dsn, expected)


class TestJWTAuth(unittest.TestCase):
    """测试 JWT 认证"""

    def setUp(self):
        # 确保有测试密钥
        os.environ["SERVICE_JWT_SECRET"] = "test_jwt_secret_for_unit_test"
        import importlib
        import service.config
        importlib.reload(service.config)

    def tearDown(self):
        del os.environ["SERVICE_JWT_SECRET"]

    def test_jwt_create_and_verify(self):
        """验证 JWT 令牌创建和验证"""
        from service.auth.jwt import create_access_token, create_refresh_token, decode_token

        # 测试 access token
        access_token = create_access_token("user_123")
        self.assertIsInstance(access_token, str)
        self.assertTrue(len(access_token) > 20)

        # 解码验证
        payload = decode_token(access_token)
        self.assertEqual(payload["user_id"], "user_123")
        self.assertEqual(payload["token_type"], "access")

        # 测试 refresh token
        refresh_token = create_refresh_token("user_456")
        payload = decode_token(refresh_token)
        self.assertEqual(payload["user_id"], "user_456")
        self.assertEqual(payload["token_type"], "refresh")

    def test_jwt_invalid_token(self):
        """验证无效 token 抛出异常"""
        from service.auth.jwt import decode_token
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            decode_token("invalid_token_here")
        self.assertEqual(ctx.exception.status_code, 401)


class TestPasswordAuth(unittest.TestCase):
    """测试密码认证"""

    def test_password_hash_and_verify(self):
        """验证密码哈希和验证"""
        from service.auth.password import hash_password, verify_password

        password = "my_secure_password_123!"
        hashed = hash_password(password)

        # 密码不能与哈希相同
        self.assertNotEqual(password, hashed)
        # 哈希以 pbkdf2 格式开头
        self.assertTrue(hashed.startswith("pbkdf2$"))

        # 正确密码验证通过
        self.assertTrue(verify_password(password, hashed))
        # 错误密码验证失败
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_sms_code_generate_and_verify(self):
        """验证验证码生成和验证"""
        from service.auth.password import generate_sms_code, send_sms_code, verify_sms_code, SMS_CODE_STORE

        # 生成验证码
        code = generate_sms_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

        # 发送验证码（内部会生成并存储验证码）
        import asyncio
        result = asyncio.run(send_sms_code("13800138000"))
        self.assertTrue(result)

        # 从存储中取出实际发送的验证码
        stored = SMS_CODE_STORE.get("13800138000")
        self.assertIsNotNone(stored)
        actual_code = stored["code"]

        # 验证验证码
        self.assertTrue(verify_sms_code("13800138000", actual_code))

        # 验证码使用后应被删除
        self.assertNotIn("13800138000", SMS_CODE_STORE)

        # 错误验证码
        asyncio.run(send_sms_code("13800138000"))
        self.assertFalse(verify_sms_code("13800138000", "000000"))

        # 不存在的手机号
        self.assertFalse(verify_sms_code("13900139000", code))


class TestOSSClient(unittest.TestCase):
    """测试 OSS 客户端"""

    def test_oss_client_simulate(self):
        """验证 OSS 模拟上传"""
        from service.oss.client import OSSClient

        client = OSSClient()
        # 确保模拟模式
        client._simulate = True
        client._initialized = True

        # 测试上传
        image_data = b"fake_image_data_1234567890"
        result = client.upload_image(
            image_data=image_data,
            image_hash="abc123def456",
            user_id="test_user",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.image_hash, "abc123def456")
        self.assertIn("/mock/", result.url)


class TestSyncEngine(unittest.TestCase):
    """测试同步引擎"""

    def test_sync_engine_config(self):
        """验证同步引擎配置"""
        from service.db.sync_engine import SyncEngine, SyncEngineConfig

        engine = SyncEngine()
        self.assertEqual(engine.config.batch_size, 50)
        self.assertEqual(engine.config.sync_interval, 300)
        self.assertEqual(engine.config.conflict_strategy, "last_write_wins")

    def test_sync_result_dataclass(self):
        """验证 SyncResult 数据类"""
        from service.db.sync_engine import SyncResult

        result = SyncResult()
        self.assertFalse(result.success)
        self.assertEqual(result.uploaded, 0)
        self.assertEqual(result.downloaded, 0)
        self.assertEqual(result.conflicts, 0)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.duration, 0.0)


class TestTaskQueue(unittest.TestCase):
    """测试任务队列"""

    def test_task_queue_memory(self):
        """验证内存任务队列"""
        import asyncio
        from service.task_queue import TaskQueue

        queue = TaskQueue()
        queue._redis = None  # 强制使用内存队列
        queue._memory_queue = []  # 初始化内存队列

        # 入队
        task_data = {"task_id": 1, "type": "inference", "payload": {"question": "test"}}
        asyncio.run(queue.enqueue(task_data))

        # 出队
        dequeued = asyncio.run(queue.dequeue())
        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued["task_id"], 1)
        self.assertEqual(dequeued["type"], "inference")

        # 空队列
        empty = asyncio.run(queue.dequeue())
        self.assertIsNone(empty)


class TestWebSocketManager(unittest.TestCase):
    """测试 WebSocket 连接管理器"""

    def test_connection_manager(self):
        """验证连接管理器"""
        from service.websocket import ConnectionManager

        manager = ConnectionManager()

        # 初始状态
        self.assertEqual(manager._count_connections(), 0)

        # 模拟连接（不实际建立 WebSocket，只测试内部状态）
        class MockWebSocket:
            async def accept(self):
                pass
            async def send_json(self, data):
                pass

        # 因为 connect 需要实际 websocket 连接，我们测试 disconnect 和 send_personal_message
        # 在没有连接的情况下不应报错
        import asyncio
        asyncio.run(manager.send_personal_message(
            {"type": "test"}, "nonexistent_user"
        ))
        # 不应抛出异常，表示处理正常


if __name__ == "__main__":
    unittest.main(verbosity=2)