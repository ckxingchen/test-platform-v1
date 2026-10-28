from fastapi import APIRouter

from app.modules.executors import deployments_router, router

api_router = APIRouter()
api_router.include_router(router.router)
api_router.include_router(deployments_router.router)
