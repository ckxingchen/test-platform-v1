"""任务生命周期编排：创建、重跑与取消（HTTP 轮询模式，无命令队列）。"""

from app.modules.executors.facade import get_environment
from app.shared.resources.repository import get_package_file, list_resource_files
from app.modules.tasks.repository import get_task_with_names, list_task_files, task_to_dict
from app.platform.db.base import utcnow
from app.modules.executors.models import Environment
from app.modules.tasks.models import Task, TaskFile
from app.modules.tasks.schemas import TaskCreate
from app.modules.users.models import User
from app.shared.resources.models import Resource
from app.shared.errors import ServiceError
from app.shared.configuration.ini import validate_ini_content
from app.shared.files.paths import normalize_selected_case_paths
from sqlalchemy.orm import Session


def _ready_environment(db: Session, environment_id: int) -> Environment:
    """读取可执行环境并保证其框架已部署到最新且 Agent 在线。"""

    item = get_environment(db, environment_id)
    if not item or not item.enabled:
        raise ServiceError(422, "执行器不存在或已停用")
    if item.agent_status != "online":
        raise ServiceError(422, "执行器 Agent 当前不在线")
    if item.framework_status != "deployed":
        raise ServiceError(422, "执行器测试框架尚未部署完成")
    framework = get_package_file(db, item.framework_id) if item.framework_id else None
    if not framework or item.framework_sha256 != framework.sha256:
        raise ServiceError(422, "执行器框架存在更新，请先重新部署")
    return item


def create_task(db: Session, data: TaskCreate, project: Resource, user: User) -> dict:
    """冻结项目文件并创建排队任务，等待 Agent 按空闲槽位拉取。"""

    environment = _ready_environment(db, data.environment_id)
    try:
        validate_ini_content(data.config_content)
    except ValueError as exc:
        raise ServiceError(422, str(exc))
    # 归并用例勾选：selected_case_paths 为主；旧 testcase_path 字符串（单条或分号分隔）兼容并入
    case_paths = list(data.selected_case_paths or [])
    if data.testcase_path:
        for part in str(data.testcase_path).split(";"):
            part = part.strip()
            if part and part not in case_paths:
                case_paths.append(part)
    try:
        selected_case_paths = normalize_selected_case_paths(case_paths or None)
    except ValueError as exc:
        raise ServiceError(422, str(exc))
    files = list_resource_files(db, project.id)
    if not files:
        raise ServiceError(422, "测试项目没有可执行文件")
    task = Task(
        project_id=project.id,
        environment_id=environment.id,
        framework_id=environment.framework_id,
        framework_sha256=environment.framework_sha256 or "",
        status="queued",
        testcase_scope={"path": data.testcase_path} if data.testcase_path else None,
        selected_case_paths=selected_case_paths,
        config_content=data.config_content,
        timeout_seconds=data.timeout_seconds,
        created_by=user.id,
    )
    db.add(task)
    db.flush()
    db.add_all(
        [
            TaskFile(
                task_id=task.id,
                relative_path=item.relative_path,
                object_key=item.object_key,
                object_version_id=item.object_version_id,
                sha256=item.sha256,
            )
            for item in files
        ]
    )
    db.commit()
    db.refresh(task)
    row = get_task_with_names(db, task.id)
    return task_to_dict(*row)


def rerun_task(db: Session, task: Task, user: User) -> dict:
    """复用原项目快照，在执行器当前已部署框架上创建新任务。"""

    environment = _ready_environment(db, task.environment_id)
    new = Task(
        project_id=task.project_id,
        environment_id=task.environment_id,
        framework_id=environment.framework_id,
        framework_sha256=environment.framework_sha256 or "",
        status="queued",
        testcase_scope=task.testcase_scope,
        selected_case_paths=task.selected_case_paths,
        config_content=task.config_content,
        timeout_seconds=task.timeout_seconds,
        created_by=user.id,
    )
    db.add(new)
    db.flush()
    snapshots = list_task_files(db, task.id)
    db.add_all(
        [
            TaskFile(
                task_id=new.id,
                relative_path=item.relative_path,
                object_key=item.object_key,
                object_version_id=item.object_version_id,
                sha256=item.sha256,
            )
            for item in snapshots
        ]
    )
    db.commit()
    db.refresh(new)
    row = get_task_with_names(db, new.id)
    return task_to_dict(*row)


def cancel_task(db: Session, task: Task) -> dict:
    """标记任务取消状态；运行中任务由 Agent 心跳感知 cancel_tasks 后终止进程。"""

    if task.status in {"success", "failed", "canceled", "timeout"}:
        raise ServiceError(409, "任务已经结束")
    task.cancel_requested = True
    if task.status == "queued":
        task.status, task.finished_at = "canceled", utcnow()
    db.commit()
    return {"message": "取消请求已提交"}
