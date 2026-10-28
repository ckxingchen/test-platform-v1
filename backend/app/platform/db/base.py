"""SQLAlchemy 声明基类和数据库通用时间函数。"""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """返回带 UTC 时区的当前时间。"""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的声明式基类。"""
