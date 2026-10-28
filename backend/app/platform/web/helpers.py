"""无业务语义的 FastAPI 读取、事务冲突和下载响应辅助函数。"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.platform.web.responses import download_response

T = TypeVar("T")


def get_or_404(item: T | None, detail: str) -> T:
    if item is None:
        raise HTTPException(status_code=404, detail=detail)
    return item


@contextmanager
def commit_or_conflict(db: Session, detail: str) -> Iterator[None]:
    try:
        yield
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail)


__all__ = ["commit_or_conflict", "download_response", "get_or_404"]
