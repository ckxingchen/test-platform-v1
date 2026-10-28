"""平台下发给 Agent 的持久化命令 ORM 模型。"""

from datetime import datetime

from app.platform.db.base import Base, utcnow
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class AgentCommand(Base):
    """支持断线后继续投递的类型化 Agent 命令。"""

    __tablename__ = "agent_commands"
    __table_args__ = (Index("ix_agent_commands_delivery", "environment_id", "status", "priority", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("agent_environments.id"), index=True)
    command_type: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    lease_id: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    delivery_count: Mapped[int] = mapped_column(Integer, default=0)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("agent_tasks.id"), index=True)
    deployment_id: Mapped[int | None] = mapped_column(ForeignKey("agent_deployments.id"), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
