"""add tool_calls table

Revision ID: 0002_tool_calls
Revises: 0001_baseline
Create Date: 2026-06-27

新增 ToolCall 表，用于结构化记录每次 MCP 工具调用。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_tool_calls"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("is_error", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_calls_project_id", "tool_calls", ["project_id"])
    op.create_index("ix_tool_calls_created_at", "tool_calls", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_created_at", table_name="tool_calls")
    op.drop_index("ix_tool_calls_project_id", table_name="tool_calls")
    op.drop_table("tool_calls")
