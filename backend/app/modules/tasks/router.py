"""测试任务创建、查询、取消和重跑接口。"""

from app.modules.auth.dependencies import current_user, ensure_project_access
from app.modules.objects.projects.access import get_accessible_project
from app.platform.web.helpers import get_or_404
from app.modules.tasks.repository import get_task as crud_get_task
from app.modules.tasks.repository import get_task_with_names, list_tasks_with_names, task_to_dict
from app.platform.db.session import get_db
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskOut
from app.modules.users.models import User
from app.shared.errors import ServiceError
from app.modules.tasks import service as task_lifecycle
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tasks", tags=["任务管理"])



def _task(db: Session, task_id: int, user: User) -> Task:
    """读取任务并校验当前用户的测试项目权限。"""

    task = get_or_404(crud_get_task(db, task_id), "任务不存在")
    ensure_project_access(db, task.project_id, user)
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    project_id: int | None = None,
    environment_id: int | None = None,
    status: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """管理员查看全部任务，普通用户只查看有权限项目的任务；支持按项目/执行器/状态过滤。"""

    return list_tasks_with_names(db, user=user, project_id=project_id, environment_id=environment_id, status=status)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """冻结项目文件，并在同一事务中创建等待 Agent 领取的运行命令。"""

    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="查看人员不能创建任务")
    project = get_accessible_project(db, data.project_id, user, write=True)
    try:
        return task_lifecycle.create_task(db, data, project, user)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回指定任务详情。"""

    _task(db, task_id, user)
    row = get_task_with_names(db, task_id)
    return task_to_dict(*row)


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """标记任务取消状态并在运行时通知 Agent。"""

    task = _task(db, task_id, user)
    if user.role != "admin" and task.created_by != user.id:
        raise HTTPException(status_code=403, detail="只能取消自己创建的任务")
    try:
        return task_lifecycle.cancel_task(db, task)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{task_id}/rerun", response_model=TaskOut, status_code=201)
def rerun_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """复用原项目快照，在环境当前已部署框架上创建新任务。"""

    old = _task(db, task_id, user)
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="查看人员不能创建任务")
    try:
        return task_lifecycle.rerun_task(db, old, user)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
