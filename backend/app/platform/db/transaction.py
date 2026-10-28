"""统一数据库事务边界和唯一约束冲突转换。"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.platform.web.errors import ConflictError


@contextmanager
def transaction(db: Session, conflict_detail: str = "数据已存在") -> Iterator[None]:
    try:
        yield
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_detail) from exc
    except Exception:
        db.rollback()
        raise
