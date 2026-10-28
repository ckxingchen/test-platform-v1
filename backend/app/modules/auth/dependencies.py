"""FastAPI 数据库、当前用户、角色和项目权限依赖。"""

from collections.abc import Callable

from app.platform.config.settings import settings
from app.platform.db.session import get_db
from app.platform.security.service import decode_access_token
from app.modules.users.models import User
from app.shared.permissions.project_access import ensure_project_access
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """解析访问令牌并返回当前启用用户。"""

    try:
        user_id = int(decode_access_token(token)["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    user = db.get(User, user_id)
    if not user or not user.enabled:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def require_roles(*roles: str) -> Callable:
    """创建一个仅允许指定系统角色访问的 FastAPI 依赖。"""

    def checker(user: User = Depends(current_user)) -> User:
        """检查当前用户是否具备接口要求的系统角色。"""

        if user.role not in roles:
            raise HTTPException(status_code=403, detail="没有操作权限")
        return user

    return checker


# 统一导出管理员角色 gate，各端点不再本地重复定义。
admin = require_roles("admin")
