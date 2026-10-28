"""执行器环境、SSH 测试、Agent 部署请求响应模型。"""

from datetime import datetime
from typing import Any

from app.shared.schemas.base import ORMModel
from app.modules.tasks.schemas import TaskOut
from pydantic import BaseModel, Field, model_validator


class EnvironmentIn(BaseModel):
    """创建或更新执行器参数（SSH 密码只在填写时更新；归属人为创建人，不可指定）。"""

    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(default="", max_length=100)
    ssh_password: str = Field(default="", max_length=200)
    os: str | None = Field(default=None, max_length=30)
    arch: str | None = Field(default=None, max_length=30)
    agent_home: str = Field(default="/opt/kw-agent", min_length=2, max_length=500)
    max_workers: int = Field(default=1, ge=1, le=100)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_environment(self):
        """规范化主机标识并校验 Agent 安装目录。"""

        self.host = self.host.strip()
        if not self.host or self.host in {"0.0.0.0", "::"}:
            raise ValueError("执行器主机标识无效")
        normalized_home = self.agent_home.replace("\\", "/").strip()
        if not normalized_home.startswith("/") and not (len(normalized_home) > 1 and normalized_home[1] == ":"):
            raise ValueError("Agent 安装目录必须是绝对路径（Linux /opt/kw-agent 或 Windows D:\\kw-agent）")
        return self


class EnvironmentOut(ORMModel):
    """执行器响应数据（含四态派生字段，由端点手动组装）。"""

    id: int
    name: str
    host: str
    ssh_port: int
    ssh_username: str | None
    os: str | None
    arch: str | None
    agent_home: str
    agent_package_id: int | None
    agent_status: str
    agent_sha256: str | None
    framework_id: int | None
    framework_status: str
    framework_sha256: str | None
    max_workers: int
    running_tasks: int
    active_task_count: int = 0
    agent_update_available: bool = False
    framework_update_available: bool = False
    ready: bool = False
    last_seen: datetime | None
    enabled: bool
    updated_at: datetime
    owner_id: int | None
    owner_name: str | None
    group_name: str | None
    tags: list[str]
    framework_name: str | None
    framework_os: str | None
    framework_arch: str | None


class DeploymentOut(ORMModel):
    """测试框架部署记录响应数据。"""

    id: int
    environment_id: int
    framework_sha256: str
    status: str
    error_message: str | None
    created_by: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EnvironmentOverviewOut(BaseModel):
    """执行器详情页聚合数据（框架版本/部署历史/任务历史/并发占用）。"""

    environment: EnvironmentOut
    framework: dict[str, Any] | None
    agent_package: dict[str, Any] | None
    deploy_history: list[DeploymentOut]
    task_history: list[TaskOut]
    concurrency: dict[str, int]


class FrameworkDeployIn(BaseModel):
    """管理员下发框架部署请求。"""

    framework_id: int
