"""测试任务、快照、结果和产物 ORM 模型。"""

from datetime import datetime

from app.platform.db.base import Base, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class Task(Base):
    """测试项目在已部署环境中的一次运行任务。"""

    __tablename__ = "agent_tasks"
    __table_args__ = (Index("ix_agent_tasks_status_created", "status", "created_at"), Index("ix_agent_tasks_environment_status", "environment_id", "status"))
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("object_resources.id"))
    environment_id: Mapped[int] = mapped_column(ForeignKey("agent_environments.id"))
    framework_id: Mapped[int] = mapped_column(ForeignKey("object_resources.id"))
    framework_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    testcase_scope: Mapped[dict | None] = mapped_column(JSON)
    selected_case_paths: Mapped[list | None] = mapped_column(JSON)
    config_content: Mapped[str] = mapped_column(Text)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskFile(Base):
    """任务创建时冻结的测试项目对象版本。"""

    __tablename__ = "agent_task_files"
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"), primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(1000), primary_key=True)
    object_key: Mapped[str] = mapped_column(String(1200))
    object_version_id: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))


class TaskResult(Base):
    """任务执行后的测试结果摘要。"""

    __tablename__ = "agent_task_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"), index=True)
    case_path: Mapped[str] = mapped_column(String(1000))
    case_name: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)


class TaskArtifact(Base):
    """任务日志、报告等 MinIO 归档产物。"""

    __tablename__ = "agent_task_artifacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(30))
    object_key: Mapped[str] = mapped_column(String(1000))
    size: Mapped[int] = mapped_column(Integer)
