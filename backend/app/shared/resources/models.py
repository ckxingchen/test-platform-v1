"""对象资源、文件和项目成员 ORM 模型。"""

from datetime import datetime

from app.platform.db.base import Base, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Resource(Base):
    """MinIO 中的测试项目或测试框架。"""

    __tablename__ = "object_resources"
    __table_args__ = (UniqueConstraint("resource_type", "name", "os", "arch"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(100))
    os: Mapped[str | None] = mapped_column(String(30))
    arch: Mapped[str | None] = mapped_column(String(30))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResourceFile(Base):
    """对象资源下的一个 MinIO 文件及其当前对象摘要。"""

    __tablename__ = "object_resource_files"
    __table_args__ = (UniqueConstraint("resource_id", "relative_path"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("object_resources.id"), index=True)
    relative_path: Mapped[str] = mapped_column(String(1000))
    object_key: Mapped[str] = mapped_column(String(1200))
    object_version_id: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResourceMember(Base):
    """用户在测试项目资源中的成员角色。"""

    __tablename__ = "object_resource_members"
    resource_id: Mapped[int] = mapped_column(ForeignKey("object_resources.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
