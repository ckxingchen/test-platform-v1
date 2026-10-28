"""执行器 ORM 模型：SSH 凭据 + Agent 部署状态 + 框架部署状态。"""

from datetime import datetime

from app.platform.db.base import Base, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class Environment(Base):
    """跨平台执行器：平台通过 SSH 部署 Agent，Agent 通过 HTTP 轮询平台。

    agent_status: pending(未部署) / deploying(部署中) / online / offline
    framework_status: not_deployed / pending(已下发部署请求) / deploying / deployed / failed
    """

    __tablename__ = "agent_environments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    host: Mapped[str] = mapped_column(String(255))
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    ssh_username: Mapped[str | None] = mapped_column(String(100))
    ssh_password_enc: Mapped[str | None] = mapped_column(Text)
    os: Mapped[str | None] = mapped_column(String(30))
    arch: Mapped[str | None] = mapped_column(String(30))
    agent_home: Mapped[str] = mapped_column(String(500), default="/opt/kw-agent")
    agent_package_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_packages.id", name="fk_agent_environments_agent_package_id", ondelete="SET NULL")
    )
    agent_status: Mapped[str] = mapped_column(String(20), default="pending")
    agent_sha256: Mapped[str | None] = mapped_column(String(64))
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("object_resources.id"))
    framework_status: Mapped[str] = mapped_column(String(20), default="not_deployed")
    framework_sha256: Mapped[str | None] = mapped_column(String(64))
    max_workers: Mapped[int] = mapped_column(Integer, default=1)
    running_tasks: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", name="fk_agent_environments_owner_id", ondelete="SET NULL"))
    group_name: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Deployment(Base):
    """一次测试框架部署及其执行结果。"""

    __tablename__ = "agent_deployments"
    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("agent_environments.id"), index=True)
    framework_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
