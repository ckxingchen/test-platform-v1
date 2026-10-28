"""平台总路由：只负责聚合业务模块，不承载业务逻辑。"""

from fastapi import APIRouter

from app.modules.agent_gateway import routes as agent_gateway
from app.modules.auth import routes as auth
from app.modules.executors import routes as executors
from app.modules.objects.agent_packages import routes as agent_packages
from app.modules.objects.frameworks import routes as frameworks
from app.modules.objects.projects import routes as projects
from app.modules.tasks import routes as tasks
from app.modules.users import routes as users

api_router = APIRouter()
for module_router in (
    auth.api_router,
    users.api_router,
    projects.api_router,
    frameworks.api_router,
    agent_packages.api_router,
    executors.api_router,
    tasks.api_router,
    agent_gateway.api_router,
):
    api_router.include_router(module_router)
