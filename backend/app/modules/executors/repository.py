"""执行器基础数据库查询与名称化组装（含四态派生）。"""

from app.modules.objects.agent_packages.repository import get_agent_package
from app.shared.resources.common import model_to_dict
from app.shared.resources.repository import get_package_file
from app.modules.executors.models import Deployment, Environment
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.shared.resources.models import Resource
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ACTIVE_TASK_STATUSES = {"queued", "preparing", "running"}


def get_environment(db: Session, environment_id: int) -> Environment | None:
    """按编号读取执行器。"""

    return db.get(Environment, environment_id)


def count_active_tasks(db: Session, environment_id: int) -> int:
    """统计执行器中尚未结束的任务数量。"""

    return db.scalar(select(func.count(Task.id)).where(Task.environment_id == environment_id, Task.status.in_(ACTIVE_TASK_STATUSES))) or 0


def list_with_framework(db: Session) -> list[tuple[Environment, Resource | None, User | None]]:
    """按编号升序返回执行器，并左连接其测试框架与归属人。"""

    rows = db.execute(
        select(Environment, Resource, User)
        .outerjoin(Resource, Resource.id == Environment.framework_id)
        .outerjoin(User, User.id == Environment.owner_id)
        .order_by(Environment.id)
    ).all()
    return [(item, framework, owner) for item, framework, owner in rows]


def get_environment_with_framework(db: Session, environment_id: int) -> tuple[Environment, Resource | None, User | None] | None:
    """读取执行器并左连接其测试框架与归属人。"""

    return db.execute(
        select(Environment, Resource, User)
        .outerjoin(Resource, Resource.id == Environment.framework_id)
        .outerjoin(User, User.id == Environment.owner_id)
        .where(Environment.id == environment_id)
    ).first()


def list_environments_by_framework_with_owner(db: Session, framework_id: int) -> list[tuple[Environment, User | None]]:
    """返回使用指定测试框架的执行器及其归属人。"""

    rows = db.execute(
        select(Environment, User)
        .outerjoin(User, User.id == Environment.owner_id)
        .where(Environment.framework_id == framework_id)
        .order_by(Environment.id)
    ).all()
    return [(item, owner) for item, owner in rows]


def list_deployments(db: Session, environment_id: int) -> list[Deployment]:
    """按最新优先返回测试框架部署记录（全部）。"""

    return db.scalars(
        select(Deployment).where(Deployment.environment_id == environment_id).order_by(Deployment.id.desc())
    ).all()


def list_recent_deployments(db: Session, environment_id: int, limit: int) -> list[Deployment]:
    """按最新优先返回最近 N 条测试框架部署记录。"""

    return db.scalars(
        select(Deployment).where(Deployment.environment_id == environment_id).order_by(Deployment.id.desc()).limit(limit)
    ).all()


def environment_state(db: Session, item: Environment, active_count: int | None = None) -> dict:
    """计算执行器四态派生字段：Agent/框架更新可用性与 READY 判定。"""

    if active_count is None:
        active_count = count_active_tasks(db, item.id)
    framework_file = get_package_file(db, item.framework_id) if item.framework_id else None
    platform_framework_sha = framework_file.sha256 if framework_file else None
    agent_package = get_agent_package(db, item.agent_package_id) if item.agent_package_id else None
    platform_agent_sha = agent_package.sha256 if agent_package else None
    framework_update = bool(
        item.framework_status == "deployed" and platform_framework_sha and item.framework_sha256 != platform_framework_sha
    )
    agent_update = bool(item.agent_status in {"online", "offline"} and platform_agent_sha and item.agent_sha256 != platform_agent_sha)
    ready = bool(
        item.enabled
        and item.agent_status == "online"
        and item.framework_status == "deployed"
        and not framework_update
        and platform_framework_sha is not None
    )
    return {
        "active_task_count": active_count,
        "agent_update_available": agent_update,
        "framework_update_available": framework_update,
        "ready": ready,
    }


def environment_to_dict(
    item: Environment,
    framework: Resource | None = None,
    owner: User | None = None,
    state: dict | None = None,
) -> dict:
    """把执行器及其名称化冗余对象组装为响应字典（含派生状态）。"""

    merged = dict(state or {})
    merged.update(
        {
            "owner_name": owner.username if owner else None,
            "framework_name": framework.name if framework else None,
            "framework_os": framework.os if framework else None,
            "framework_arch": framework.arch if framework else None,
        }
    )
    return model_to_dict(
        item,
        exclude={"ssh_password_enc"},
        defaults={"tags": []},
        extra=merged,
    )
