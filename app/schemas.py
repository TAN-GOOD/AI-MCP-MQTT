from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Any, Dict, List
from datetime import datetime


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    captcha_id: str
    captcha_code: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    mcp_endpoint: str = Field(..., max_length=500)
    mqtt_broker: str = Field(..., max_length=255)
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_topic: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    mcp_endpoint: Optional[str] = Field(None, max_length=500)
    mqtt_broker: Optional[str] = Field(None, max_length=255)
    mqtt_port: Optional[int] = Field(None, ge=1, le=65535)
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_topic: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    mcp_endpoint: str
    mqtt_broker: str
    mqtt_port: int
    mqtt_username: Optional[str]
    mqtt_topic: Optional[str]
    is_running: bool
    created_at: datetime
    updated_at: Optional[datetime]
    tools: List["ToolResponse"] = []

    class Config:
        from_attributes = True


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    tool_type: str = Field(..., pattern="^(mqtt_publish|mqtt_subscribe|http_request)$")
    config: Dict[str, Any] = {}


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    tool_type: Optional[str] = Field(None, pattern="^(mqtt_publish|mqtt_subscribe|http_request)$")
    config: Optional[Dict[str, Any]] = None


class ToolResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str]
    tool_type: str
    config: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class LogResponse(BaseModel):
    id: int
    project_id: int
    level: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
