"""用户管理接口，供管理员查询、创建和维护平台用户。"""

from app.modules.auth.dependencies import admin
from app.platform.web.helpers import commit_or_conflict, get_or_404
from app.platform.security.service import hash_password
from app.modules.users.repository import list_users as crud_list_users
from app.platform.db.session import get_db
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserOut, UserUpdate
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("", response_model=list[UserOut])
def list_users(_: User = Depends(admin), db: Session = Depends(get_db)):
    """按创建顺序返回全部平台用户。"""

    return crud_list_users(db)


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, _: User = Depends(admin), db: Session = Depends(get_db)):
    """创建一个具有指定系统角色的平台用户。"""

    if data.role not in {"admin", "developer", "viewer"}:
        raise HTTPException(status_code=422, detail="角色无效")
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    with commit_or_conflict(db, "用户名已存在"):
        pass
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, actor: User = Depends(admin), db: Session = Depends(get_db)):
    """更新用户角色、启用状态或登录密码。"""

    user = get_or_404(db.get(User, user_id), "用户不存在")
    if data.role is not None:
        if data.role not in {"admin", "developer", "viewer"}:
            raise HTTPException(status_code=422, detail="角色无效")
        user.role = data.role
    if data.enabled is not None:
        if user.id == actor.id and not data.enabled:
            raise HTTPException(status_code=400, detail="不能禁用当前用户")
        user.enabled = data.enabled
    if data.password:
        user.password_hash = hash_password(data.password)
    db.commit()
    return user
