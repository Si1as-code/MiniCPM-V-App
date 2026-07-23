import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from service.config import service_config

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        t_start = time.time()

        # 读取请求体
        body = b""
        try:
            body = await request.body()
        except Exception:
            pass

        response = await call_next(request)

        # 计算耗时
        duration = time.time() - t_start
        log_msg = (
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} "
            f"({duration:.3f}s)"
        )
        if duration > 1.0:
            logger.warning(f"[慢请求] {log_msg}")
        else:
            logger.info(log_msg)

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 IP 的请求限流中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._requests: dict = defaultdict(list)  # ip -> [timestamp, ...]
        self._max_requests = service_config.rate_limit_per_minute
        self._window = 60  # 窗口大小（秒）

    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # 清理过期记录
        self._requests[client_ip] = [
            t for t in self._requests[client_ip]
            if now - t < self._window
        ]

        # 检查是否超限
        if len(self._requests[client_ip]) >= self._max_requests:
            logger.warning(f"限流: {client_ip} 请求过多")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """可选认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 跳过不需要认证的路径
        public_paths = {
            "/health",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/sms",
            "/api/auth/oauth",
            "/api/docs",
            "/api/openapi.json",
            "/api/redoc",
        }
        if request.url.path in public_paths or request.url.path.startswith("/api/auth/"):
            return await call_next(request)

        # 尝试从 Authorization header 获取 token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from service.auth.jwt import decode_token
                token = auth_header[7:]
                payload = decode_token(token)
                request.state.user_id = payload.get("user_id", "")
            except Exception:
                request.state.user_id = ""
        else:
            request.state.user_id = ""

        return await call_next(request)