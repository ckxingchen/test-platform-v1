"""与 FastAPI 解耦的统一应用异常。"""


class PlatformError(Exception):
    status_code = 500

    def __init__(self, detail: str, *, status_code: int | None = None) -> None:
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)


class ValidationError(PlatformError):
    status_code = 422


class AuthenticationError(PlatformError):
    status_code = 401


class PermissionDeniedError(PlatformError):
    status_code = 403


class NotFoundError(PlatformError):
    status_code = 404


class ConflictError(PlatformError):
    status_code = 409
