"""测试任务基础数据库查询与名称化冗余组装。"""

from app.shared.resources.common import model_to_dict
from app.modules.executors.models import Environment
from app.modules.tasks.models import Task, TaskArtifact, TaskFile, TaskResult
from app.modules.users.models import User
from app.shared.resources.models import Resource, ResourceMember
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

# project 与 framework 都存储在 object_resources 表，需要两次 alias 分别连接
ProjectResource = aliased(Resource)
FrameworkResource = aliased(Resource)


def get_task(db: Session, task_id: int) -> Task | None:
    """按编号读取测试任务。"""

    return db.get(Task, task_id)


def task_select_with_names():
    """返回带 project/environment/framework/创建人 左连接的任务查询。"""

    return (
        select(Task, ProjectResource, Environment, FrameworkResource, User)
        .outerjoin(ProjectResource, ProjectResource.id == Task.project_id)
        .outerjoin(Environment, Environment.id == Task.environment_id)
        .outerjoin(FrameworkResource, FrameworkResource.id == Task.framework_id)
        .outerjoin(User, User.id == Task.created_by)
    )


def get_task_with_names(db: Session, task_id: int) -> tuple[Task, Resource | None, Environment | None, Resource | None, User | None] | None:
    """读取任务并左连接名称化冗余对象（含创建人）。"""

    return db.execute(task_select_with_names().where(Task.id == task_id)).first()


def list_tasks_with_names(
    db: Session,
    *,
    user: User | None = None,
    project_id: int | None = None,
    environment_id: int | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """按权限与过滤条件返回任务列表（含名称化冗余字段）。"""

    query = task_select_with_names()
    if user is not None and user.role != "admin":
        query = query.join(ResourceMember, ResourceMember.resource_id == Task.project_id).where(
            ResourceMember.user_id == user.id
        )
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if environment_id is not None:
        query = query.where(Task.environment_id == environment_id)
    if status is not None:
        query = query.where(Task.status == status)
    query = query.order_by(Task.id.desc())
    if limit is not None:
        query = query.limit(limit)
    rows = db.execute(query).all()
    return [task_to_dict(task, project, environment, framework, creator) for task, project, environment, framework, creator in rows]


def list_task_files(db: Session, task_id: int) -> list[TaskFile]:
    """返回任务冻结的全部项目文件快照。"""

    return db.scalars(select(TaskFile).where(TaskFile.task_id == task_id)).all()


def list_task_results(db: Session, task_id: int) -> list[TaskResult]:
    """返回任务结果摘要列表。"""

    return db.scalars(select(TaskResult).where(TaskResult.task_id == task_id).order_by(TaskResult.id)).all()


def list_task_artifacts(db: Session, task_id: int) -> list[TaskArtifact]:
    """返回任务日志和报告归档清单。"""

    return db.scalars(select(TaskArtifact).where(TaskArtifact.task_id == task_id).order_by(TaskArtifact.id)).all()


def task_to_dict(task: Task, project: Resource | None = None, environment: Environment | None = None, framework: Resource | None = None, creator: User | None = None) -> dict:
    """把任务及其名称化冗余对象组装为响应字典（含创建人）。"""

    return model_to_dict(
        task,
        exclude={"config_content"},
        extra={
            "project_name": project.name if project else None,
            "environment_name": environment.name if environment else None,
            "framework_name": framework.name if framework else None,
            "created_by_name": creator.username if creator else None,
        },
    )
