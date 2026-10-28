from fastapi import APIRouter

from app.modules.objects.projects import files_router, members_router, router

api_router = APIRouter()
api_router.include_router(router.router)
api_router.include_router(files_router.router)
api_router.include_router(members_router.router)
