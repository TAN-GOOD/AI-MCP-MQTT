import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.database import engine, SessionLocal, Base
from app.routers import auth, projects, tools
from app.config import settings
from app.services.log_service import log_service
from app.services.mcp_manager import mcp_manager
from app.services.mqtt_manager import mqtt_manager


# ===== 通用 API 限流中间件（按 IP 滑动窗口）=====
# 解析 "60/minute" -> 60 次 / 60 秒
def _parse_rate(rate_str: str):
    count, _, unit = rate_str.partition("/")
    count = int(count)
    unit_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
    window = unit_map.get(unit, 60)
    return count, window

_RATE_COUNT, _RATE_WINDOW = _parse_rate(settings.API_RATE_LIMIT)
_ip_hits: dict = defaultdict(deque)  # ip -> deque[timestamps]


def _is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    dq = _ip_hits[client_ip]
    # 清理过期时间戳
    while dq and now - dq[0] > _RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_COUNT:
        return True
    dq.append(now)
    return False


# 不限流的路径前缀（静态资源、健康检查、登录/注册/刷新需要更宽松）
_EXEMPT_PREFIXES = ("/static", "/api/health", "/api/auth/login", "/api/auth/register", "/api/auth/refresh", "/api/auth/captcha")

Base.metadata.create_all(bind=engine)

def auto_migrate():
    try:
        inspector = inspect(engine)
        columns = {col['name'] for col in inspector.get_columns('tools')}
        if 'sort_order' not in columns:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE tools ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0'))
                conn.commit()
    except Exception as e:
        # 记录错误而非静默吞掉
        import logging
        logging.getLogger("auto_migrate").error(f"数据库迁移失败: {e}")

auto_migrate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动与关闭时统一回收资源"""
    # 启动
    yield
    # 关闭：优雅停止所有 MCP/MQTT 连接，刷写日志
    import asyncio
    tasks = []
    for project_id in list(mcp_manager.connections.keys()):
        tasks.append(mcp_manager.stop_project(project_id))
    for project_id in list(mqtt_manager.clients.keys()):
        tasks.append(mqtt_manager.remove_client(project_id))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await log_service.shutdown()


app = FastAPI(
    title="小智MCP-MQTT管理系统",
    description="通过MCP协议控制物联网设备的管理系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置：allow_origins=* 与 allow_credentials=True 不能同时使用
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
_allow_credentials = "*" not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """通用 API 限流：按客户端 IP 滑动窗口限流，豁免静态资源与认证端点"""
    path = request.url.path
    if not path.startswith(_EXEMPT_PREFIXES):
        client_ip = request.client.host if request.client else "unknown"
        if _is_rate_limited(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求过于频繁，请稍后再试（限流：{settings.API_RATE_LIMIT}）"},
            )
    return await call_next(request)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tools.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "小智MCP-MQTT管理系统 API v1.0.0"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "小智MCP-MQTT管理系统"}
