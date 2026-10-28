"""通用 HTTP 响应构造。"""

from urllib.parse import quote

from fastapi.responses import Response


def download_response(data: bytes, filename: str) -> Response:
    encoded = quote(filename)
    return Response(data, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"})
