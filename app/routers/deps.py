"""公共依赖与工具函数，消除 routers 间的代码重复。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models import User, Project, Tool
from app.services.mcp_manager import mcp_manager


def get_project_or_404(project_id: int, user: User, db: Session) -> Project:
    """查询当前用户的项目，不存在则 404"""
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def build_tools_config(db: Session, project_id: int) -> List[dict]:
    """从数据库构建 tools_config 列表"""
    tools = db.query(Tool).filter(Tool.project_id == project_id).all()
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "tool_type": t.tool_type,
            "config": t.config or {},
        }
        for t in tools
    ]


def sync_tools_to_running(db: Session, project_id: int):
    """若项目正在运行，将最新工具配置同步到 MCP 连接"""
    if not mcp_manager.is_running(project_id):
        return
    tools_config = build_tools_config(db, project_id)
    conn = mcp_manager.get_connection(project_id)
    if conn:
        conn.update_tools(tools_config)
