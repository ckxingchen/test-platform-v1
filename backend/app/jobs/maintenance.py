"""执行器离线检测、任务超时回收和 Redis 日志保留维护。

新架构 Agent 通过 HTTP 轮询，命令租约机制已废弃；本模块只保留：
1. Agent 心跳超时 → offline。
2. 任务超时（started_at + timeout + 300s 宽限）→ timeout。
3. Redis 日志流 TTL 补充。
"""

from datetime import timedelta

from app.modules.executors.models import Environment
from app.modules.tasks.models import Task
from app.platform.config.settings import settings
from app.platform.db.base import utcnow
from app.platform.db.session import SessionLocal
from app.platform.messaging.redis import get_redis
from sqlalchemy import select, text

ACTIVE_TASK_STATUSES = {"queued", "preparing", "running"}


def _has_maintenance_lock(db) -> bool:
    """在 PostgreSQL 中获取事务级互斥锁，多 API 实例时只运行一次维护。"""

    if db.bind.dialect.name != "postgresql":
        return True
    return bool(db.scalar(text("SELECT pg_try_advisory_xact_lock(84721001)")))


def _timeout_tasks(db, now) -> int:
    """结束超过用户超时值和五分钟回收宽限期的活动任务。"""

    count = 0
    tasks = db.scalars(select(Task).where(Task.status.in_(ACTIVE_TASK_STATUSES))).all()
    for task in tasks:
        started = task.started_at or task.created_at
        if started + timedelta(seconds=task.timeout_seconds + 300) >= now:
            continue
        task.status, task.error_message, task.finished_at = "timeout", "测试任务执行超时", now
        task.cancel_requested = True
        count += 1
    return count


def _retain_log_streams() -> None:
    """为没有 TTL 的历史任务和部署日志补充统一保留时间。"""

    redis = get_redis()
    for pattern in ("task:*:logs", "deployment:*:logs"):
        for key in redis.scan_iter(match=pattern, count=200):
            if redis.ttl(key) < 0:
                redis.expire(key, settings.log_retention_seconds)


def run_maintenance_once() -> dict[str, int]:
    """执行一轮可重入维护，并返回本轮处理数量。"""

    now = utcnow()
    result = {"agents": 0, "tasks": 0}
    with SessionLocal.begin() as db:
        if not _has_maintenance_lock(db):
            return result
        stale_before = now - timedelta(seconds=settings.agent_offline_after_seconds)
        environments = db.scalars(
            select(Environment).where(Environment.agent_status == "online", Environment.last_seen < stale_before)
        ).all()
        for environment in environments:
            environment.agent_status = "offline"
            environment.running_tasks = 0
        result["agents"] = len(environments)
        result["tasks"] = _timeout_tasks(db, now)
    try:
        _retain_log_streams()
    except Exception:
        pass
    return result
