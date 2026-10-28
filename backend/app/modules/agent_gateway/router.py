"""Agent Runtime HTTP 通信接口：心跳、部署指令、任务拉取、状态与产物回传。

Agent 通过 HTTP 轮询（无 WebSocket、无 Token，按 executor_id 标识）：
    POST /agent/{executor_id}/heartbeat          心跳 + 取消任务列表
    GET  /agent/{executor_id}/actions            拉取框架部署指令
    GET  /agent/{executor_id}/tasks?limit=N      按空闲槽位领取排队任务
    GET  /agent/{executor_id}/framework          下载框架归档
    GET  /agent/tasks/{task_id}/project          下载项目 ZIP（含本次 INI）
    POST /agent/{executor_id}/framework/status   上报框架部署结果
    PUT  /agent/tasks/{task_id}/status           上报任务状态
    POST /agent/tasks/{task_id}/logs             上传任务日志
    POST /agent/tasks/{task_id}/results          上传用例结果
    POST /agent/tasks/{task_id}/artifacts        上传日志/报告产物
"""

import io
import zipfile
from datetime import datetime, timezone

from app.platform.config.settings import settings
from app.platform.messaging.redis import get_redis
from app.platform.storage.minio import storage
from app.modules.objects.frameworks.facade import get_enabled_framework_with_file
from app.shared.resources.repository import get_package_file
from app.modules.tasks.facade import list_task_files
from app.platform.db.base import utcnow
from app.platform.db.session import get_db
from app.modules.executors.models import Deployment, Environment
from app.modules.tasks.models import Task, TaskArtifact, TaskFile, TaskResult
from app.shared.resources.models import Resource
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/agent", tags=["Agent 通信"])

# 框架约定的测试集/用例前后置文件名（不含目录），勾选下发时需保留祖先目录链上的这些文件。
_SETUP_TEARDOWN_NAMES = {
    "测试集前置.yaml", "测试集前置.yml",
    "测试集后置.yaml", "测试集后置.yml",
    "测试用例前置.yaml", "测试用例前置.yml",
    "测试用例后置.yaml", "测试用例后置.yml",
}


def _environment(db: Session, executor_id: int) -> Environment:
    """读取启用状态的执行器，供 Agent 通信复用。"""

    item = db.get(Environment, executor_id)
    if not item or not item.enabled:
        raise HTTPException(status_code=404, detail="执行器不存在或已停用")
    return item


def _task(db: Session, task_id: int) -> Task:
    """读取任务并校验存在。"""

    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


class HeartbeatIn(BaseModel):
    """Agent 心跳上报。"""

    running_tasks: list[int] = []
    agent_sha256: str | None = None
    framework_sha256: str | None = None


class FrameworkStatusIn(BaseModel):
    """Agent 上报框架部署结果。"""

    deployment_id: int
    status: str = Field(pattern="^(deployed|failed)$")
    sha256: str | None = None
    error_message: str | None = None


class TaskStatusIn(BaseModel):
    """Agent 上报任务状态。"""

    status: str = Field(pattern="^(running|success|failed|timeout|canceled)$")
    exit_code: int | None = None
    error_message: str | None = None


class TaskLogsIn(BaseModel):
    """Agent 上传任务日志行。"""

    lines: list[str] = []
    level: str = "INFO"


class TaskResultsIn(BaseModel):
    """Agent 上传用例执行结果。"""

    cases: list[dict] = []


def _write_log(stream: str, message: str, level: str = "INFO") -> None:
    """把 Agent 日志追加到 Redis Stream。"""

    redis = get_redis()
    redis.xadd(
        stream,
        {"timestamp": datetime.now(timezone.utc).isoformat(), "level": level, "message": message},
        maxlen=10000,
        approximate=True,
    )
    redis.expire(stream, settings.log_retention_seconds)


def _filter_task_files(items: list[TaskFile], selected_case_paths: list[str] | None) -> list[TaskFile]:
    """按用例勾选范围过滤任务冻结文件，返回需要下发到 Agent 的文件子集。"""

    if not selected_case_paths:
        return list(items)
    selected = {path.rstrip("/") for path in selected_case_paths}
    ancestor_dirs: set[str] = set()
    for path in selected:
        node = path.rsplit("/", 1)[0] if "/" in path else ""
        while node:
            ancestor_dirs.add(node)
            node = node.rsplit("/", 1)[0] if "/" in node else ""
    kept: list[TaskFile] = []
    for item in items:
        rel = item.relative_path.replace("\\", "/").strip("/")
        parts = rel.split("/")
        top = parts[0]
        if top in {"business", "config"}:
            kept.append(item)
            continue
        if top == "testcase" and len(parts) >= 2 and parts[1] == "casedata":
            kept.append(item)
            continue
        if top == "testcase":
            if any(rel == sel or rel.startswith(sel + "/") for sel in selected):
                kept.append(item)
                continue
            if parts[-1] in _SETUP_TEARDOWN_NAMES and "/".join(parts[:-1]) in ancestor_dirs:
                kept.append(item)
    return kept


@router.post("/{executor_id}/heartbeat")
def heartbeat(executor_id: int, data: HeartbeatIn, db: Session = Depends(get_db)):
    """Agent 心跳：刷新在线状态并返回需要取消的任务列表。"""

    item = _environment(db, executor_id)
    item.agent_status = "online"
    item.last_seen = utcnow()
    item.running_tasks = len(data.running_tasks or [])
    if data.agent_sha256:
        item.agent_sha256 = data.agent_sha256
    if data.framework_sha256:
        item.framework_sha256 = data.framework_sha256
    running_ids = set(data.running_tasks or [])
    cancel_tasks = [
        task_id
        for task_id in db.scalars(
            select(Task.id).where(
                Task.environment_id == item.id,
                Task.cancel_requested.is_(True),
                Task.status.in_(("preparing", "running")),
            )
        ).all()
        if task_id in running_ids or not running_ids
    ]
    db.commit()
    return {"server_time": utcnow().isoformat(), "cancel_tasks": cancel_tasks}


@router.get("/{executor_id}/actions")
def pull_actions(executor_id: int, db: Session = Depends(get_db)):
    """Agent 拉取部署指令：框架待部署时返回部署详情并标记 deploying。"""

    item = _environment(db, executor_id)
    item.agent_status = "online"
    item.last_seen = utcnow()
    if item.framework_status != "pending" or not item.framework_id:
        db.commit()
        return {"deploy_framework": False}
    framework, framework_file = get_enabled_framework_with_file(db, item.framework_id)
    if not framework or not framework_file:
        item.framework_status = "failed"
        db.commit()
        return {"deploy_framework": False}
    deployment = Deployment(environment_id=item.id, framework_sha256=framework_file.sha256, created_by=1, status="running", started_at=utcnow())
    db.add(deployment)
    db.flush()
    item.framework_status = "deploying"
    db.commit()
    metadata = dict(framework.metadata_json or {})
    metadata.update({"name": framework.name, "os": framework.os, "arch": framework.arch})
    return {
        "deploy_framework": True,
        "deployment_id": deployment.id,
        "framework": {
            "id": framework.id,
            "name": framework.name,
            "sha256": framework_file.sha256,
            "file_name": framework_file.relative_path,
            "runner_path": metadata.get("runner_path", ""),
            "archive_root": metadata.get("archive_root", ""),
        },
    }


@router.get("/{executor_id}/tasks")
def pull_tasks(executor_id: int, limit: int = Query(default=1, ge=1, le=50), db: Session = Depends(get_db)):
    """Agent 按空闲槽位领取排队任务（领取即标记 preparing）。"""

    item = _environment(db, executor_id)
    item.agent_status = "online"
    item.last_seen = utcnow()
    tasks = db.scalars(
        select(Task)
        .where(Task.environment_id == item.id, Task.status == "queued")
        .order_by(Task.id)
        .limit(limit)
    ).all()
    result = []
    for task in tasks:
        if task.cancel_requested:
            task.status, task.finished_at = "canceled", utcnow()
            continue
        task.status = "preparing"
        framework = db.get(Resource, task.framework_id)
        metadata = dict(framework.metadata_json or {}) if framework else {}
        if framework:
            metadata.update({"name": framework.name, "os": framework.os, "arch": framework.arch})
        project = db.get(Resource, task.project_id)
        result.append(
            {
                "task_id": task.id,
                "project_id": task.project_id,
                "project_name": project.name if project else f"project-{task.project_id}",
                "testcase_path": (task.testcase_scope or {}).get("path"),
                "selected_case_paths": task.selected_case_paths,
                "timeout_seconds": task.timeout_seconds,
                "framework": metadata,
            }
        )
    db.commit()
    return {"tasks": result}


@router.get("/{executor_id}/framework")
def download_framework(executor_id: int, db: Session = Depends(get_db)):
    """Agent 下载执行器绑定的最新框架归档。"""

    item = _environment(db, executor_id)
    if not item.framework_id:
        raise HTTPException(status_code=404, detail="执行器未绑定测试框架")
    file = get_package_file(db, item.framework_id)
    if not file:
        raise HTTPException(status_code=404, detail="框架对象不存在")
    data = storage.get_bytes(settings.framework_bucket, file.object_key)
    return Response(data, media_type="application/octet-stream", headers={"X-Content-SHA256": file.sha256})


@router.get("/tasks/{task_id}/project")
def download_task_project(task_id: int, db: Session = Depends(get_db)):
    """把任务冻结的项目文件和本次 INI 配置打包后返回给 Agent。"""

    task = _task(db, task_id)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        snapshot = list_task_files(db, task.id)
        for item in _filter_task_files(list(snapshot), task.selected_case_paths):
            archive.writestr(item.relative_path, storage.get_bytes(settings.project_bucket, item.object_key, item.object_version_id))
        archive.writestr("config/配置文件.ini", task.config_content)
    return Response(output.getvalue(), media_type="application/zip")


@router.post("/{executor_id}/framework/status")
def report_framework_status(executor_id: int, data: FrameworkStatusIn, db: Session = Depends(get_db)):
    """Agent 上报框架部署结果，更新执行器框架状态与 SHA。"""

    item = _environment(db, executor_id)
    deployment = db.get(Deployment, data.deployment_id)
    if deployment and deployment.environment_id == item.id:
        deployment.finished_at = utcnow()
        deployment.status = "success" if data.status == "deployed" else "failed"
        deployment.error_message = data.error_message
    if data.status == "deployed":
        item.framework_status = "deployed"
        if data.sha256:
            item.framework_sha256 = data.sha256
        _write_log(f"deployment:{data.deployment_id}:logs", "框架部署成功")
    else:
        item.framework_status = "failed"
        _write_log(f"deployment:{data.deployment_id}:logs", f"框架部署失败：{data.error_message or '未知错误'}", "ERROR")
    db.commit()
    return {"message": "已更新"}


@router.put("/tasks/{task_id}/status")
def report_task_status(task_id: int, data: TaskStatusIn, db: Session = Depends(get_db)):
    """Agent 上报任务状态迁移。"""

    task = _task(db, task_id)
    if task.status in {"success", "failed", "timeout", "canceled"} and data.status != task.status:
        raise HTTPException(status_code=409, detail="任务已经结束")
    task.status = data.status
    task.exit_code = data.exit_code if data.exit_code is not None else task.exit_code
    if data.error_message:
        task.error_message = data.error_message[:2000]
    if data.status == "running":
        task.started_at = task.started_at or utcnow()
    if data.status in {"success", "failed", "timeout", "canceled"}:
        task.finished_at = utcnow()
        if task.cancel_requested and data.status != "success":
            task.status = "canceled"
    db.commit()
    return {"message": "已更新"}


@router.post("/tasks/{task_id}/logs")
def upload_task_logs(task_id: int, data: TaskLogsIn, db: Session = Depends(get_db)):
    """Agent 上传任务日志行，写入 Redis Stream 供前端实时查看。"""

    _task(db, task_id)
    if not data.lines:
        return {"message": "无日志"}
    redis = get_redis()
    stream = f"task:{task_id}:logs"
    pipe = redis.pipeline()
    now = datetime.now(timezone.utc).isoformat()
    for line in data.lines[:500]:
        pipe.xadd(stream, {"timestamp": now, "level": data.level, "message": line[:4000]}, maxlen=10000, approximate=True)
    pipe.expire(stream, settings.log_retention_seconds)
    pipe.execute()
    return {"message": f"已写入 {len(data.lines)} 行"}


@router.post("/tasks/{task_id}/results")
def upload_task_results(task_id: int, data: TaskResultsIn, db: Session = Depends(get_db)):
    """Agent 上传逐用例结构化执行结果。"""

    task = _task(db, task_id)
    db.query(TaskResult).filter(TaskResult.task_id == task.id).delete()
    for case in data.cases[:2000]:
        db.add(
            TaskResult(
                task_id=task.id,
                case_path=str(case.get("case_path", ""))[:1000],
                case_name=str(case.get("case_name", ""))[:500],
                status=str(case.get("status", ""))[:20],
                error_message=case.get("error_message"),
            )
        )
    db.commit()
    return {"message": f"已写入 {len(data.cases)} 条结果"}


@router.post("/tasks/{task_id}/artifacts", status_code=201)
async def upload_task_artifact(task_id: int, artifact_type: str, file: UploadFile, db: Session = Depends(get_db)):
    """接收 Agent 上传的日志或报告并存入 MinIO。"""

    task = _task(db, task_id)
    data = await file.read()
    safe_name = (file.filename or "artifact.bin").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    key = f"tasks/{task.id}/{artifact_type}/{safe_name}"
    stored = storage.put_bytes(settings.artifact_bucket, key, data, file.content_type or "application/octet-stream")
    artifact = TaskArtifact(task_id=task.id, artifact_type=artifact_type, object_key=key, size=stored.size)
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return {"id": artifact.id, "size": artifact.size}
