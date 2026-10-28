"""认证接口请求和响应模型。"""

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    """用户名密码登录参数。"""

    username: str
    password: str


class TokenOut(BaseModel):
    """登录成功后返回的访问令牌。"""

    access_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    """当前用户修改密码的参数。"""

    old_password: str
    new_password: str = Field(min_length=6)
