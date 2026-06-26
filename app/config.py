from pydantic_settings import BaseSettings
from typing import Optional
import os


_DEFAULT_SECRET = "your-secret-key-change-this-in-production"


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/xiaozhi_mcp"
    SECRET_KEY: str = _DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"
    # 是否允许 MCP wss:// 跳过证书校验（仅自签证书场景，默认 False）
    MCP_ALLOW_INSECURE: bool = False
    # CORS 允许的来源，逗号分隔；默认 * 表示全部（此时会自动关闭 credentials）
    CORS_ORIGINS: str = "*"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 安全检查：SECRET_KEY 使用默认值时直接报错（fail-fast）
if settings.SECRET_KEY == _DEFAULT_SECRET:
    raise RuntimeError(
        "安全错误：SECRET_KEY 仍为默认值，存在 JWT 被伪造风险。"
        "请在 .env 文件中设置一个随机密钥，例如：SECRET_KEY=$(python -c 'import secrets;print(secrets.token_hex(32))')"
    )
