"""业务服务可复用、且不依赖 FastAPI 的领域异常。"""

from app.platform.web.errors import PlatformError


class ServiceError(PlatformError):
    """保留现有 status_code + detail 调用方式的业务异常。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail, status_code=status_code)
