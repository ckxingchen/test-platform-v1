"""读取测试项目并校验成员权限。"""

from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.platform.web.helpers import get_or_404
from app.shared.permissions.project_access import ensure_project_access
from app.shared.resources.models import Resource
from app.shared.resources.repository import get_resource


def get_accessible_project(db: Session, project_id: int, user: User, write: bool = False) -> Resource:
    project = get_or_404(get_resource(db, project_id, "project"), "测试项目不存在")
    ensure_project_access(db, project.id, user, write)
    return project
