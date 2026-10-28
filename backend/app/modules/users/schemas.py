"""用户管理请求和响应模型。"""

from datetime import datetime

from app.shared.schemas.base import ORMModel
from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    """管理员创建用户时提交的数据。"""

    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6)
    role: str = "viewer"

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        """去除用户名首尾空白后再执行长度校验。"""

        return value.strip() if isinstance(value, str) else value


class UserUpdate(BaseModel):
    """管理员可修改的用户字段。"""

    role: str | None = None
    enabled: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class UserOut(ORMModel):
    """对外返回的用户信息，不包含密码摘要。"""

    id: int
    username: str
    role: str
    enabled: bool
    created_at: datetime
