"""测试项目成员权限接口。"""

from app.modules.auth.dependencies import admin, current_user, ensure_project_access
from app.platform.web.helpers import get_or_404
from app.modules.objects.projects.repository import list_project_members as crud_list_project_members
from app.shared.resources.repository import get_resource
from app.platform.db.session import get_db
from app.modules.users.models import User
from app.shared.resources.models import ResourceMember
from app.shared.resources.schemas import MemberItem
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

router = APIRouter(prefix="/objects/projects/{project_id}/members", tags=["对象管理"])


@router.get("", response_model=list[MemberItem])
def list_project_members(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回测试项目成员列表。"""

    get_or_404(get_resource(db, project_id, "project"), "测试项目不存在")
    ensure_project_access(db, project_id, user)
    return crud_list_project_members(db, project_id)


@router.put("", response_model=list[MemberItem])
def replace_project_members(project_id: int, members: list[MemberItem], _: User = Depends(admin), db: Session = Depends(get_db)):
    """校验并整体替换测试项目成员。"""

    get_or_404(get_resource(db, project_id, "project"), "测试项目不存在")
    for member in members:
        target = db.get(User, member.user_id)
        if not target or member.role not in {"developer", "viewer"}:
            raise HTTPException(status_code=422, detail="成员或项目角色无效")
    db.execute(delete(ResourceMember).where(ResourceMember.resource_id == project_id))
    db.add_all([ResourceMember(resource_id=project_id, **item.model_dump()) for item in members])
    db.commit()
    return members
