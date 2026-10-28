"""执行器测试框架部署和部署日志接口。"""

from app.modules.auth.dependencies import admin, current_user
from app.platform.web.helpers import get_or_404
from app.platform.messaging.redis import get_redis
from app.modules.executors.repository import get_environment, list_deployments as crud_list_deployments
from app.platform.db.session import get_db
from app.modules.executors.models import Deployment
from app.modules.executors.schemas import DeploymentOut, FrameworkDeployIn
from app.modules.users.models import User
from app.shared.errors import ServiceError
from app.modules.executors import deployment_service
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/environments", tags=["环境管理"])


@router.post("/{environment_id}/deploy", response_model=DeploymentOut, status_code=202)
def deploy_framework(environment_id: int, data: FrameworkDeployIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    """下发框架部署请求：Agent 在线时轮询拉取并执行部署。"""

    item = get_or_404(get_environment(db, environment_id), "执行器不存在")
    try:
        return deployment_service.deploy_framework(db, item, data.framework_id, user.id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{environment_id}/deployments", response_model=list[DeploymentOut])
def list_deployments(environment_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """按最新优先返回测试框架部署记录。"""

    get_or_404(get_environment(db, environment_id), "执行器不存在")
    return crud_list_deployments(db, environment_id)


@router.get("/{environment_id}/deployments/{deployment_id}/logs")
def deployment_logs(environment_id: int, deployment_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """从 Redis Stream 返回一次框架部署的实时日志。"""

    deployment = db.get(Deployment, deployment_id)
    if not deployment or deployment.environment_id != environment_id:
        raise HTTPException(status_code=404, detail="部署记录不存在")
    rows = get_redis().xrange(f"deployment:{deployment_id}:logs", count=5000)
    return {"logs": [{"id": row_id, **values} for row_id, values in rows]}
