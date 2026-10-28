"""FastAPI 应用唯一入口，负责生命周期、中间件和 v1 路由装配。"""

import asyncio
from contextlib import asynccontextmanager

from app.router import api_router
from app.platform.config.settings import settings
from app.bootstrap import initialize_database
from app.jobs.lifecycle import maintenance_loop
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    """初始化依赖资源，并启动可取消的轻量后台维护循环。"""

    initialize_database()
    maintenance = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        maintenance.cancel()
        try:
            await maintenance
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    """返回服务健康状态，供容器和部署脚本探测。"""

    return {"status": "ok"}
