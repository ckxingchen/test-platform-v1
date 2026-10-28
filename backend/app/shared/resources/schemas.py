"""对象资源、文件和成员请求响应模型。"""

from datetime import datetime
from typing import Any

from app.shared.schemas.base import ORMModel
from pydantic import BaseModel, Field, field_validator


class ResourceCreate(BaseModel):
    """创建测试项目对象时提交的数据。"""

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        """清理项目名称并拒绝路径分隔符和控制字符。"""

        if not isinstance(value, str):
            return value
        name = value.strip()
        if "/" in name or "\\" in name or any(ord(character) < 32 for character in name):
            raise ValueError("项目名称不能包含路径分隔符或控制字符")
        return name


class ResourceOut(ORMModel):
    """测试项目或测试框架的统一响应数据。"""

    id: int
    resource_type: str
    name: str
    os: str | None
    arch: str | None
    metadata_json: dict[str, Any]
    enabled: bool
    created_by: int
    created_at: datetime
    updated_at: datetime


class FrameworkOut(ResourceOut):
    """测试框架响应数据，附带被多少个执行器使用的反向索引计数。"""

    used_by_count: int = 0


class ResourceFileOut(ORMModel):
    """资源文件及其当前 MinIO 对象信息。"""

    id: int
    resource_id: int
    relative_path: str
    object_key: str
    object_version_id: str | None
    sha256: str
    size: int
    updated_by: int
    updated_at: datetime


class MemberItem(ORMModel):
    """项目资源成员及其项目内角色。"""

    user_id: int
    role: str
