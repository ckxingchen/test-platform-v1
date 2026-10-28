"""用户基础数据库查询。"""

from app.modules.users.models import User
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_by_username(db: Session, username: str) -> User | None:
    """按用户名返回用户，不存在时返回空。"""

    return db.scalar(select(User).where(User.username == username))


def list_users(db: Session) -> list[User]:
    """按创建顺序返回全部平台用户。"""

    return db.scalars(select(User).order_by(User.id)).all()
