"""
============================================================================
后台服务层模块
============================================================================
Sprint 4: 提供 FastAPI 后台服务、云端数据库、用户认证、数据同步等能力。

目录结构:
    service/
    ├── __init__.py          # 模块导出
    ├── config.py            # 服务配置（数据库、Redis、OSS、JWT 等）
    ├── app.py               # FastAPI 应用骨架
    ├── middleware.py         # 鉴权、限流、日志中间件
    ├── task_queue.py        # Redis 任务队列
    ├── websocket.py         # WebSocket 实时推送
    ├── db/
    │   ├── __init__.py
    │   ├── postgres.py      # PostgreSQL 异步连接池
    │   ├── schema.sql       # 云端数据库 Schema
    │   └── sync_engine.py   # 数据同步引擎
    ├── auth/
    │   ├── __init__.py
    │   ├── jwt.py           # JWT 认证
    │   ├── oauth.py         # 第三方登录（微信/Apple）
    │   └── password.py      # 手机号验证码登录
    ├── oss/
    │   ├── __init__.py
    │   └── client.py        # 对象存储客户端
    └── routes/
        ├── __init__.py
        ├── inference.py     # 推理 API 端点
        ├── tasks.py         # 任务管理端点
        └── stats.py         # 统计端点
============================================================================
"""

from service.config import service_config, ServiceConfig
from service.app import create_app

__all__ = [
    "service_config",
    "ServiceConfig",
    "create_app",
]