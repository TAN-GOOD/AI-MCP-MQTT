from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# 连接池优化：
# - pool_size: 持久连接数（默认 5）
# - max_overflow: 突发可额外创建的连接数
# - pool_pre_ping: 借出前 ping 一下，避免拿到死连接
# - pool_recycle: 8 小时回收，避免 MySQL wait_timeout 踢掉连接
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=28800,
    pool_timeout=30,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
