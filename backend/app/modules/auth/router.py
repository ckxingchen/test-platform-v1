"""认证接口，提供登录、当前用户查询和密码修改功能。"""

from app.modules.auth.dependencies import current_user
from app.platform.security.service import create_access_token, hash_password, verify_password
from app.modules.users.repository import get_by_username
from app.platform.db.session import get_db
from app.modules.auth.schemas import LoginIn, PasswordChange, TokenOut
from app.modules.users.models import User
from app.modules.users.schemas import UserOut
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    """验证用户名和密码并签发访问令牌。"""

    user = get_by_username(db, data.username)
    if not user or not user.enabled or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    """返回当前登录用户的公开信息。"""

    return user


@router.post("/change-password")
def change_password(data: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """校验原密码后更新当前用户密码。"""

    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码已修改"}
