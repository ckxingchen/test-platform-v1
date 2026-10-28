"""执行器增删改查、SSH 测试连接和 Agent 远程部署接口。"""

from app.modules.auth.dependencies import admin, current_user
from app.modules.tasks.guards import ensure_no_tasks
from app.platform.web.helpers import commit_or_conflict, get_or_404
from app.platform.config.settings import settings
from app.platform.security.crypto import encrypt_secret
from app.modules.objects.agent_packages.facade import get_agent_package
from app.modules.executors.repository import (
    count_active_tasks,
    environment_state,
    environment_to_dict,
    get_environment,
    get_environment_with_framework,
    list_recent_deployments,
    list_with_framework,
)
from app.shared.resources.repository import get_package_file
from app.modules.tasks.facade import list_tasks_with_names
from app.platform.db.session import get_db
from app.modules.executors.command_models import AgentCommand
from app.modules.executors.models import Deployment, Environment
from app.modules.executors.schemas import (
    EnvironmentIn,
    EnvironmentOut,
    EnvironmentOverviewOut,
)
from app.modules.objects.agent_packages.schemas import AgentDeployResultOut, SSHConnectionTestIn, SSHConnectionTestOut
from app.modules.users.models import User
from app.shared.errors import ServiceError
from app.modules.executors.agent_service import deploy_agent, start_agent, stop_agent
from app.modules.executors.ssh_service import test_ssh_connection
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

router = APIRouter(prefix="/environments", tags=["环境管理"])


RECENT_LIMIT = 10


def _environment(db: Session, environment_id: int) -> Environment:
    """读取执行器，不存在时返回统一的 404。"""

    return get_or_404(get_environment(db, environment_id), "执行器不存在")


def _row_to_dict(db: Session, row) -> dict:
    """把 (执行器, 框架, 归属人) 行组装为带派生状态的响应字典。"""

    item, framework, owner = row
    return environment_to_dict(item, framework, owner, environment_state(db, item))


@router.get("", response_model=list[EnvironmentOut])
def list_environments(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回全部执行器（含四态派生状态）。"""

    return [_row_to_dict(db, row) for row in list_with_framework(db)]


@router.post("", response_model=EnvironmentOut, status_code=201)
def create_environment(data: EnvironmentIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    """创建执行器：保存 SSH 凭据（密码加密落库），归属人为当前操作人。"""

    item = Environment(
        name=data.name,
        host=data.host,
        ssh_port=data.ssh_port,
        ssh_username=data.ssh_username or None,
        ssh_password_enc=encrypt_secret(data.ssh_password) if data.ssh_password else None,
        os=data.os,
        arch=data.arch,
        agent_home=data.agent_home,
        max_workers=data.max_workers,
        enabled=data.enabled,
        owner_id=user.id,
        agent_status="pending",
        framework_status="not_deployed",
    )
    db.add(item)
    with commit_or_conflict(db, "执行器名称已存在"):
        pass
    db.refresh(item)
    row = get_environment_with_framework(db, item.id)
    return _row_to_dict(db, row)


@router.get("/{environment_id}", response_model=EnvironmentOut)
def read_environment(environment_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回指定执行器。"""

    _environment(db, environment_id)
    row = get_environment_with_framework(db, environment_id)
    return _row_to_dict(db, row)


@router.get("/{environment_id}/overview", response_model=EnvironmentOverviewOut)
def environment_overview(environment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回执行器详情聚合：框架版本、Agent 包、部署历史、任务历史与并发占用。"""

    row = get_environment_with_framework(db, environment_id)
    if not row:
        raise HTTPException(status_code=404, detail="执行器不存在")
    item, framework, owner = row

    framework_info = None
    if framework:
        package = get_package_file(db, framework.id)
        framework_info = {
            "id": framework.id,
            "name": framework.name,
            "os": framework.os,
            "arch": framework.arch,
            "latest_sha256": package.sha256 if package else None,
        }
    agent_package = get_agent_package(db, item.agent_package_id) if item.agent_package_id else None
    agent_package_info = {
        "id": agent_package.id,
        "name": agent_package.name,
        "os": agent_package.os,
        "arch": agent_package.arch,
        "sha256": agent_package.sha256,
        "updated_at": agent_package.updated_at,
    } if agent_package else None

    deploys = list_recent_deployments(db, environment_id, RECENT_LIMIT)
    task_history = list_tasks_with_names(db, user=user, environment_id=environment_id, limit=RECENT_LIMIT)

    return {
        "environment": environment_to_dict(item, framework, owner, environment_state(db, item)),
        "framework": framework_info,
        "agent_package": agent_package_info,
        "deploy_history": deploys,
        "task_history": task_history,
        "concurrency": {"max": item.max_workers or 0, "active": count_active_tasks(db, item.id)},
    }


@router.put("/{environment_id}", response_model=EnvironmentOut)
def update_environment(environment_id: int, data: EnvironmentIn, _: User = Depends(admin), db: Session = Depends(get_db)):
    """更新执行器；SSH 凭据只在填写时更新，Agent 参数变更要求重新部署。"""

    item = _environment(db, environment_id)
    registration_changed = (
        item.host != data.host
        or item.ssh_port != data.ssh_port
        or item.agent_home != data.agent_home
        or item.max_workers != data.max_workers
    )
    if registration_changed and count_active_tasks(db, item.id):
        raise HTTPException(status_code=409, detail="执行器仍有运行中任务，暂不能修改 Agent 参数")
    item.name = data.name
    item.host = data.host
    item.ssh_port = data.ssh_port
    item.ssh_username = data.ssh_username or None
    if data.ssh_password:
        item.ssh_password_enc = encrypt_secret(data.ssh_password)
    if data.os:
        item.os = data.os
    if data.arch:
        item.arch = data.arch
    item.agent_home = data.agent_home
    item.max_workers = data.max_workers
    item.enabled = data.enabled
    db.commit()
    row = get_environment_with_framework(db, environment_id)
    return _row_to_dict(db, row)


@router.delete("/{environment_id}")
def delete_environment(environment_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """删除没有任务记录的执行器。"""

    item = _environment(db, environment_id)
    ensure_no_tasks(db, environment_id=item.id, detail="执行器已有任务记录，请停用执行器")
    db.execute(delete(AgentCommand).where(AgentCommand.environment_id == item.id))
    db.execute(delete(Deployment).where(Deployment.environment_id == item.id))
    db.delete(item)
    db.commit()
    return {"message": "已删除"}


@router.post("/test-connection", response_model=SSHConnectionTestOut)
def test_connection(data: SSHConnectionTestIn, _: User = Depends(admin)):
    """测试 SSH 连接并自动探测远程 OS/架构（不落库）。"""

    result = test_ssh_connection(data.host, data.ssh_port, data.ssh_username, data.ssh_password)
    return result


@router.post("/{environment_id}/deploy-agent", response_model=AgentDeployResultOut)
def deploy_environment_agent(environment_id: int, user: User = Depends(admin), db: Session = Depends(get_db)):
    """通过 SSH/SFTP 远程部署（或重新部署）Agent，等待心跳上线。"""

    item = _environment(db, environment_id)
    try:
        return deploy_agent(db, item, user.id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{environment_id}/start-agent")
def start_environment_agent(environment_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """启动已部署的远程 Agent 进程。"""

    item = _environment(db, environment_id)
    try:
        return start_agent(db, item)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{environment_id}/stop-agent")
def stop_environment_agent(environment_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """停止远程 Agent 进程。"""

    item = _environment(db, environment_id)
    try:
        return stop_agent(db, item)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
