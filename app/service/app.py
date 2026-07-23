import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from service.config import service_config
from service.middleware import LoggingMiddleware, RateLimitMiddleware, AuthMiddleware
from service.routes import inference_router, tasks_router, stats_router
from service.websocket import connection_manager
from service.task_queue import task_queue

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("服务启动中...")

    # 初始化数据库连接池
    try:
        from service.db.postgres import init_db_pool
        await init_db_pool()
        logger.info("数据库连接池初始化完成")
    except Exception as e:
        logger.warning(f"数据库连接池初始化失败（可忽略）: {e}")

    logger.info(f"服务已启动: http://{service_config.host}:{service_config.port}")
    yield

    # 关闭
    try:
        from service.db.postgres import close_db_pool
        await close_db_pool()
        logger.info("数据库连接池已关闭")
    except Exception as e:
        logger.warning(f"关闭数据库连接池失败: {e}")

    logger.info("服务已关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="MiniCPM-V 端侧视觉助手 API",
        description="端侧视觉理解 App 后台服务，提供推理、任务管理、统计等能力",
        version="0.4.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )

    # ------------------------------------------------------------------
    # CORS 配置
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=service_config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # 自定义中间件
    # ------------------------------------------------------------------
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)

    # ------------------------------------------------------------------
    # 注册路由
    # ------------------------------------------------------------------
    app.include_router(inference_router, prefix=service_config.api_prefix)
    app.include_router(tasks_router, prefix=service_config.api_prefix)
    app.include_router(stats_router, prefix=service_config.api_prefix)

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health_check():
        db_status = "unknown"
        try:
            from service.db.postgres import get_db_pool
            pool = await get_db_pool()
            db_status = "ok" if await pool.health_check() else "error"
        except Exception:
            db_status = "unavailable"

        return {
            "status": "ok",
            "version": "0.4.0",
            "database": db_status,
        }

    # ------------------------------------------------------------------
    # WebSocket 端点
    # ------------------------------------------------------------------
    @app.websocket("/api/ws")
    async def websocket_endpoint(websocket: WebSocket):
        user_id = websocket.query_params.get("user_id", "anonymous")
        await connection_manager.connect(websocket, user_id)
        try:
            while True:
                data = await websocket.receive_text()
                # 可以在这里处理客户端发送的消息
                await websocket.send_json({
                    "type": "pong",
                    "data": data,
                })
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket, user_id)
        except Exception as e:
            logger.error(f"WebSocket 异常: {e}")
            connection_manager.disconnect(websocket, user_id)

    # ------------------------------------------------------------------
    # 全局异常处理
    # ------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"未捕获异常: {exc}", exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": f"服务器内部错误: {str(exc)}"},
        )

    return app