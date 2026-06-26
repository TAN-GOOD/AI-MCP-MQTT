import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.database import engine, SessionLocal, Base
from app.routers import auth, projects, tools
from app.config import settings
from app.services.log_service import log_service
from app.services.mcp_manager import mcp_manager
from app.services.mqtt_manager import mqtt_manager

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
