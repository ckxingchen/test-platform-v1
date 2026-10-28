"""框架部署编排：校验 + 建部署记录 + 标记待部署（Agent 轮询拉取）。"""

from app.platform.config.settings import settings
from app.platform.messaging.redis import get_redis
from app.modules.executors.repository import count_active_tasks
from app.modules.objects.frameworks.facade import get_enabled_framework_with_file
from app.modules.executors.models import Deployment, Environment
from app.shared.errors import ServiceError
from sqlalchemy.orm import Session


def deploy_framework(db: Session, item: Environment, framework_id: int, user_id: int) -> Deployment:
    """下发框架部署请求：平台记录 pending 状态，由 Agent 轮询 actions 拉取执行。"""

    if not item.enabled:
        raise ServiceError(422, "执行器已停用")
    if item.agent_status != "online":
        raise ServiceError(422, "Agent 不在线，请先部署并启动 Agent")
    if count_active_tasks(db, item.id):
        raise ServiceError(409, "执行器仍有运行中任务，暂不能部署框架")
    if item.framework_status == "deploying":
        raise ServiceError(409, "测试框架正在部署，请等待完成")
    framework, framework_file = get_enabled_framework_with_file(db, framework_id)
    if not framework or not framework_file:
        raise ServiceError(422, "选择的测试框架不存在、已禁用或没有归档文件")
    if item.os and framework.os and framework.os != item.os:
        raise ServiceError(422, f"框架平台 {framework.os} 与执行器平台 {item.os} 不匹配")
    if item.arch and framework.arch and framework.arch != item.arch:
        raise ServiceError(422, f"框架架构 {framework.arch} 与执行器架构 {item.arch} 不匹配")

    deployment = Deployment(environment_id=item.id, framework_sha256=framework_file.sha256, created_by=user_id)
    db.add(deployment)
    item.framework_id = framework.id
    item.framework_status = "pending"
    db.commit()
    db.refresh(deployment)
    redis = get_redis()
    redis.xadd(
        f"deployment:{deployment.id}:logs",
        {"level": "INFO", "message": "框架部署请求已下发，等待 Agent 拉取"},
        maxlen=10000,
        approximate=True,
    )
    redis.expire(f"deployment:{deployment.id}:logs", settings.log_retention_seconds)
    return deployment
