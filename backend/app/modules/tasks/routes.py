from fastapi import APIRouter

from app.modules.tasks import results_router, router, streams_router

api_router = APIRouter()
api_router.include_router(router.router)
api_router.include_router(results_router.router)
api_router.include_router(streams_router.router)
