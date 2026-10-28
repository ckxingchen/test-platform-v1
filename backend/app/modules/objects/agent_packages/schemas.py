"""Agent 包管理请求响应模型。"""

from datetime import datetime

from app.shared.schemas.base import ORMModel
from pydantic import BaseModel, Field


class AgentPackageOut(ORMModel):
    """Agent 包响应数据。"""

    id: int
    name: str
    os: str
    arch: str
    file_name: str
    sha256: str
    size: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SSHConnectionTestIn(BaseModel):
    """测试 SSH 连接请求参数（不落库）。"""

    host: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=100)
    ssh_password: str = Field(min_length=1, max_length=200)


class SSHConnectionTestOut(BaseModel):
    """SSH 连接测试结果。"""

    ok: bool
    os: str | None
    arch: str | None
    message: str


class AgentDeployResultOut(BaseModel):
    """Agent 远程部署结果（含步骤日志）。"""

    success: bool
    steps: list[str]
    agent_status: str
    agent_sha256: str | None
