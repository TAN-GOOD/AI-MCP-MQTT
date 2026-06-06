import json
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Project, Tool
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from app.auth import get_current_user
from app.services.mcp_manager import mcp_manager
from app.services.mqtt_manager import mqtt_manager
from app.services.log_service import log_service

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


def get_project_or_404(project_id: int, user: User, db: Session) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    for p in projects:
        p.is_running = mcp_manager.is_running(p.id)
    return projects


@router.post("", response_model=ProjectResponse)
async def create_project(
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


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)
    project.is_running = mcp_manager.is_running(project.id)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
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
    tools_config = []
    for tool in tools:
        tools_config.append({
            "name": tool.name,
            "description": tool.description or "",
            "tool_type": tool.tool_type,
            "config": tool.config or {},
        })

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
    tools_config = []
    for tool in tools:
        tools_config.append({
            "name": tool.name,
            "description": tool.description or "",
            "tool_type": tool.tool_type,
            "config": tool.config or {},
        })

    project_config = {
        "mcp_endpoint": project.mcp_endpoint,
        "mqtt_broker": project.mqtt_broker,
        "mqtt_port": project.mqtt_port,
    }

    await mcp_manager.start_project(project_id, project_config, tools_config)

    project.is_running = True
    db.commit()

    return {"message": "项目已重启", "is_running": True}


@router.websocket("/{project_id}/logs")
async def project_logs_websocket(websocket: WebSocket, project_id: int):
    await log_service.connect(project_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        log_service.disconnect(project_id, websocket)
