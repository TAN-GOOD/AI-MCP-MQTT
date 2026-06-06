import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import auth, projects, tools

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="小智MCP-MQTT管理系统",
    description="通过MCP协议控制物联网设备的管理系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
