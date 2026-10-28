"""测试任务日志、结果和产物查询下载接口。"""

import re

from app.modules.auth.dependencies import current_user, ensure_project_access
from app.platform.web.helpers import download_response, get_or_404
from app.platform.config.settings import settings
from app.platform.messaging.redis import get_redis
from app.platform.storage.minio import storage
from app.modules.tasks.repository import get_task, list_task_artifacts as crud_list_task_artifacts, list_task_results as crud_list_task_results
from app.platform.db.session import get_db
from app.modules.tasks.models import Task, TaskArtifact
from app.modules.tasks.schemas import ArtifactOut, TaskResultOut
from app.modules.users.models import User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tasks", tags=["任务管理"])

LOG_STREAM_ID_PATTERN = re.compile(r"^\d+-\d+$")


def _task(db: Session, task_id: int, user: User) -> Task:
    """读取任务并校验当前用户的测试项目权限。"""

    task = get_or_404(get_task(db, task_id), "任务不存在")
    ensure_project_access(db, task.project_id, user)
    return task


@router.get("/{task_id}/logs")
def task_logs(
    task_id: int,
    after_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """从 Redis Stream 返回历史日志，支持按最后一条 ID 增量补拉。"""

    _task(db, task_id, user)
    if after_id and not LOG_STREAM_ID_PATTERN.fullmatch(after_id):
        raise HTTPException(status_code=422, detail="日志游标格式无效")
    start = f"({after_id}" if after_id else "-"
    rows = get_redis().xrange(
        f"task:{task_id}:logs",
        min=start,
        max="+",
        count=5000,
    )
    return {"logs": [{"id": row_id, **values} for row_id, values in rows]}


@router.get("/{task_id}/results", response_model=list[TaskResultOut])
def task_results(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回任务结果摘要列表。"""

    _task(db, task_id, user)
    return crud_list_task_results(db, task_id)


@router.get("/{task_id}/artifacts", response_model=list[ArtifactOut])
def task_artifacts(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回任务日志和报告归档清单。"""

    _task(db, task_id, user)
    return crud_list_task_artifacts(db, task_id)


@router.get("/{task_id}/artifacts/{artifact_id}/download")
def download_artifact(task_id: int, artifact_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """下载属于任务的单个归档对象。"""

    _task(db, task_id, user)
    artifact = db.get(TaskArtifact, artifact_id)
    if not artifact or artifact.task_id != task_id:
        raise HTTPException(status_code=404, detail="产物不存在")
    data = storage.get_bytes(settings.artifact_bucket, artifact.object_key)
    filename = artifact.object_key.rsplit("/", 1)[-1]
    return download_response(data, filename)
