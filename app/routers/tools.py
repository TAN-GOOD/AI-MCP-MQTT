from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Project, Tool
from app.schemas import ToolCreate, ToolUpdate, ToolResponse
from app.auth import get_current_user
from app.routers.deps import get_project_or_404, build_tools_config, sync_tools_to_running
from app.services.mcp_manager import mcp_manager
from app.services.mqtt_manager import mqtt_manager

router = APIRouter(prefix="/api/projects/{project_id}/tools", tags=["工具管理"])


class ToolReorderRequest(BaseModel):
    tool_ids: List[int]


@router.get("", response_model=List[ToolResponse])
def list_tools(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, current_user, db)
    tools = db.query(Tool).filter(Tool.project_id == project_id).order_by(Tool.sort_order, Tool.id).all()
    return tools


@router.put("/reorder")
def reorder_tools(
    project_id: int,
    body: ToolReorderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, current_user, db)
    for idx, tool_id in enumerate(body.tool_ids):
        tool = db.query(Tool).filter(Tool.id == tool_id, Tool.project_id == project_id).first()
        if tool:
            tool.sort_order = idx
    db.commit()
    return {"message": "排序已保存"}


@router.post("", response_model=ToolResponse)
def create_tool(
    project_id: int,
    tool_data: ToolCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)

    existing = db.query(Tool).filter(
        Tool.project_id == project_id, Tool.name == tool_data.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="工具名称已存在")

    new_tool = Tool(
        project_id=project_id,
        name=tool_data.name,
        description=tool_data.description,
        tool_type=tool_data.tool_type,
        config=tool_data.config,
    )
    db.add(new_tool)
    db.commit()
    db.refresh(new_tool)

    sync_tools_to_running(db, project_id)

    return new_tool

@router.get("/{tool_id}", response_model=ToolResponse)
def get_tool(
    project_id: int,
    tool_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, current_user, db)
    tool = db.query(Tool).filter(Tool.id == tool_id, Tool.project_id == project_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
def update_tool(
    project_id: int,
    tool_id: int,
    tool_data: ToolUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, current_user, db)
    tool = db.query(Tool).filter(Tool.id == tool_id, Tool.project_id == project_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    update_data = tool_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tool, key, value)
    db.commit()
    db.refresh(tool)

    sync_tools_to_running(db, project_id)

    return tool


@router.delete("/{tool_id}")
def delete_tool(
    project_id: int,
    tool_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, current_user, db)
    tool = db.query(Tool).filter(Tool.id == tool_id, Tool.project_id == project_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    db.delete(tool)
    db.commit()

    sync_tools_to_running(db, project_id)

    return {"message": "工具已删除"}


@router.post("/{tool_id}/test")
async def test_tool(
    project_id: int,
    tool_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, current_user, db)
    tool = db.query(Tool).filter(Tool.id == tool_id, Tool.project_id == project_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    conn = mcp_manager.get_connection(project_id)
    if not conn:
        raise HTTPException(status_code=400, detail="项目未在运行")

    if tool.tool_type == "mqtt_subscribe":
        mqtt_client = mqtt_manager.get_client(project_id)
        if not mqtt_client:
            raise HTTPException(status_code=400, detail="MQTT客户端未连接")
        topic = tool.config.get("topic", "")
        message = mqtt_client.get_cached_message(topic)
        return {"result": message or "尚未收到消息", "topic": topic}

    return {"message": "请通过MCP协议调用此工具进行测试"}
