import json
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db, SessionLocal
from app.models import User, Project, Tool
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from app.auth import get_current_user, decode_token
from app.routers.deps import get_project_or_404, build_tools_config
from app.services.mcp_manager import mcp_manager
from app.services.mqtt_manager import mqtt_manager
from app.services.log_service import log_service

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


def _verify_ws_project_owner(token: str, project_id: int) -> bool:
    """WebSocket 连接鉴权：校验 token 和项目归属"""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return False
        db = SessionLocal()
        try:
            project = db.query(Project).filter(
                Project.id == project_id, Project.user_id == int(user_id)
            ).first()
            return project is not None
        finally:
            db.close()
    except Exception:
        return False


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    for p in projects:
        p.is_running = mcp_manager.is_running(p.id)
    return projects


@router.post("", response_model=ProjectResponse)
def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_project = Project(
        user_id=current_user.id,
        name=project_data.name,
        description=project_data.description,
        mcp_endpoint=project_data.mcp_endpoint,
        mqtt_broker=project_data.mqtt_broker,
        mqtt_port=project_data.mqtt_port,
        mqtt_username=project_data.mqtt_username,
        mqtt_password=project_data.mqtt_password,
        mqtt_topic=project_data.mqtt_topic,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


# ===== 项目模板 =====
PROJECT_TEMPLATES = [
    {
        "key": "light_control",
        "name": "智能灯光控制",
        "description": "通过语音控制灯光开关，支持开/关两个命令",
        "tools": [
            {
                "name": "control_light",
                "description": "控制灯光开关，command=on 开灯，command=off 关灯",
                "tool_type": "mqtt_publish",
                "config": {"topic": "home/light/cmd", "commands": [
                    {"value": "on", "label": "开灯"},
                    {"value": "off", "label": "关灯"},
                ]},
            },
        ],
    },
    {
        "key": "temp_humidity",
        "name": "温湿度采集",
        "description": "查询当前室内温度和湿度",
        "tools": [
            {
                "name": "get_temperature",
                "description": "获取当前室内温度",
                "tool_type": "mqtt_subscribe",
                "config": {"topic": "home/sensor/temp", "json_path": "$.temperature"},
            },
            {
                "name": "get_humidity",
                "description": "获取当前室内湿度",
                "tool_type": "mqtt_subscribe",
                "config": {"topic": "home/sensor/humidity", "json_path": "$.humidity"},
            },
        ],
    },
    {
        "key": "home_assistant",
        "name": "Home Assistant 接入",
        "description": "通过 HTTP 调用 Home Assistant API 控制设备",
        "tools": [
            {
                "name": "ha_toggle",
                "description": "切换 Home Assistant 设备状态，command=on 开启，command=off 关闭",
                "tool_type": "http_request",
                "config": {
                    "url": "http://homeassistant.local:8123/api/services/switch/toggle",
                    "method": "POST",
                    "commands": [
                        {"value": "on", "label": "开启"},
                        {"value": "off", "label": "关闭"},
                    ],
                },
            },
        ],
    },
]


@router.get("/templates/list")
def list_templates(current_user: User = Depends(get_current_user)):
    """获取可用项目模板列表"""
    return [{"key": t["key"], "name": t["name"], "description": t["description"]} for t in PROJECT_TEMPLATES]


@router.post("/templates/apply/{template_key}")
def apply_template(
    template_key: str,
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于模板创建项目（含预置工具）"""
    template = next((t for t in PROJECT_TEMPLATES if t["key"] == template_key), None)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    new_project = Project(
        user_id=current_user.id,
        name=project_data.name or template["name"],
        description=project_data.description or template["description"],
        mcp_endpoint=project_data.mcp_endpoint,
        mqtt_broker=project_data.mqtt_broker,
        mqtt_port=project_data.mqtt_port,
        mqtt_username=project_data.mqtt_username,
        mqtt_password=project_data.mqtt_password,
        mqtt_topic=project_data.mqtt_topic,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    # 创建模板预置工具
    for idx, tool_template in enumerate(template["tools"]):
        new_tool = Tool(
            project_id=new_project.id,
            name=tool_template["name"],
            description=tool_template["description"],
            tool_type=tool_template["tool_type"],
            config=tool_template["config"],
            sort_order=idx,
        )
        db.add(new_tool)
    db.commit()
    db.refresh(new_project)
    return new_project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)
    project.is_running = mcp_manager.is_running(project.id)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)
    update_data = project_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    project.is_running = mcp_manager.is_running(project.id)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)
    if mcp_manager.is_running(project_id):
        await mcp_manager.stop_project(project_id)
        await mqtt_manager.remove_client(project_id)
    db.delete(project)
    db.commit()
    return {"message": "项目已删除"}


@router.post("/{project_id}/start")
async def start_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)

    if mcp_manager.is_running(project_id):
        raise HTTPException(status_code=400, detail="项目已在运行中")

    mqtt_client = await mqtt_manager.get_or_create_client(
        project_id=project_id,
        broker=project.mqtt_broker,
        port=project.mqtt_port,
        username=project.mqtt_username,
        password=project.mqtt_password,
    )

    tools = db.query(Tool).filter(Tool.project_id == project_id).all()
    tools_config = build_tools_config(db, project_id)
    for tool in tools:
        if tool.tool_type == "mqtt_subscribe" and tool.config.get("topic"):
            mqtt_client.subscribe(tool.config["topic"])
            await log_service.broadcast(
                project_id, "INFO",
                f"已订阅MQTT主题: {tool.config['topic']}"
            )

    project_config = {
        "mcp_endpoint": project.mcp_endpoint,
        "mqtt_broker": project.mqtt_broker,
        "mqtt_port": project.mqtt_port,
    }

    await mcp_manager.start_project(project_id, project_config, tools_config)

    project.is_running = True
    db.commit()

    return {"message": "项目已启动", "is_running": True}


@router.post("/{project_id}/stop")
async def stop_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)

    if not mcp_manager.is_running(project_id):
        raise HTTPException(status_code=400, detail="项目未在运行")

    await mcp_manager.stop_project(project_id)
    await mqtt_manager.remove_client(project_id)

    project.is_running = False
    db.commit()

    return {"message": "项目已停止", "is_running": False}


@router.post("/{project_id}/restart")
async def restart_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)

    if mcp_manager.is_running(project_id):
        await mcp_manager.stop_project(project_id)
        await mqtt_manager.remove_client(project_id)

    mqtt_client = await mqtt_manager.get_or_create_client(
        project_id=project_id,
        broker=project.mqtt_broker,
        port=project.mqtt_port,
        username=project.mqtt_username,
        password=project.mqtt_password,
    )

    tools = db.query(Tool).filter(Tool.project_id == project_id).all()
    tools_config = build_tools_config(db, project_id)
    for tool in tools:
        if tool.tool_type == "mqtt_subscribe" and tool.config.get("topic"):
            mqtt_client.subscribe(tool.config["topic"])
            await log_service.broadcast(
                project_id, "INFO",
                f"已订阅MQTT主题: {tool.config['topic']}"
            )

    project_config = {
        "mcp_endpoint": project.mcp_endpoint,
        "mqtt_broker": project.mqtt_broker,
        "mqtt_port": project.mqtt_port,
    }

    await mcp_manager.restart_project(project_id, project_config, tools_config)

    project.is_running = True
    db.commit()

    return {"message": "项目已重启", "is_running": True}


@router.get("/{project_id}/logs/history")
async def get_log_history(
    project_id: int,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取项目历史日志"""
    get_project_or_404(project_id, current_user, db)
    return log_service.get_history(project_id, limit=limit)


@router.websocket("/{project_id}/logs")
async def project_logs_websocket(websocket: WebSocket, project_id: int, token: str = Query(default="")):
    # 鉴权：校验 token 与项目归属
    if not token or not _verify_ws_project_owner(token, project_id):
        await websocket.close(code=4401)
        return
    await log_service.connect_async(project_id, websocket)
    # 连接后先推送历史日志
    history = log_service.get_history(project_id, limit=50)
    try:
        for log_entry in history:
            await websocket.send_json(log_entry)
    except Exception:
        pass
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        log_service.disconnect(project_id, websocket)
