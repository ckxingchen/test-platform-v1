"""数据库连接与会话管理，为 API 和后台维护任务提供统一会话工厂。"""

from collections.abc import Generator

from app.platform.config.settings import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """为单次 API 请求创建数据库会话，并在结束后可靠关闭。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
