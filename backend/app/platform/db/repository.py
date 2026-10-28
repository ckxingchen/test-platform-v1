"""只包含无业务语义的 SQLAlchemy 基础仓储。"""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT]) -> None:
        self.model = model

    def get(self, db: Session, item_id: int) -> ModelT | None:
        return db.get(self.model, item_id)

    def list(self, db: Session, *, offset: int = 0, limit: int = 100) -> list[ModelT]:
        return list(db.scalars(select(self.model).offset(offset).limit(limit)).all())

    def add(self, db: Session, item: ModelT) -> ModelT:
        db.add(item)
        return item

    def delete(self, db: Session, item: ModelT) -> None:
        db.delete(item)

    def exists(self, db: Session, **filters: object) -> bool:
        return db.scalar(select(self.model).filter_by(**filters).limit(1)) is not None
