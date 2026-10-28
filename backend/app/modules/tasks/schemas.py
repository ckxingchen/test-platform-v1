"""任务、结果和产物请求响应模型。"""

from datetime import datetime
from typing import Any

from app.shared.schemas.base import ORMModel
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """创建测试运行任务的参数。"""

    project_id: int
    environment_id: int
    testcase_path: str | None = None
    selected_case_paths: list[str] | None = None
    config_content: str = Field(min_length=1)
    timeout_seconds: int = Field(default=3600, ge=10, le=86400)


class TaskOut(ORMModel):
    """测试任务状态及运行摘要。"""

    id: int
    project_id: int
    environment_id: int
    framework_id: int
    framework_sha256: str
    status: str
    testcase_scope: dict[str, Any] | None
    selected_case_paths: list[str] | None
    timeout_seconds: int
    cancel_requested: bool
    exit_code: int | None
    error_message: str | None
    created_by: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    project_name: str | None
    environment_name: str | None
    framework_name: str | None
    created_by_name: str | None = None


class TaskResultOut(ORMModel):
    """单个任务的测试结果摘要。"""

    id: int
    task_id: int
    case_path: str
    case_name: str
    status: str
    error_message: str | None


class ArtifactOut(ORMModel):
    """任务日志或报告归档信息。"""

    id: int
    task_id: int
    artifact_type: str
    object_key: str
    size: int
