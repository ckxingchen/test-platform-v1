"""Agent 二进制包 ORM 模型：按 (name, os, arch) 唯一维护当前最新包。"""

from datetime import datetime

from app.platform.db.base import Base, utcnow
from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class AgentPackage(Base):
    """跨平台 Agent 安装包，重新上传覆盖 MinIO 当前文件并更新 SHA。"""

    __tablename__ = "agent_packages"
    __table_args__ = (UniqueConstraint("name", "os", "arch", name="uq_agent_packages_name_os_arch"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    os: Mapped[str] = mapped_column(String(30))
    arch: Mapped[str] = mapped_column(String(30))
    file_name: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(1200))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
