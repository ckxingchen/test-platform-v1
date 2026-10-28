"""任务日志 WebSocket 接口，负责向浏览器实时推送 Redis Stream 日志。"""

import asyncio
import re

from app.platform.messaging.redis import get_async_redis
from app.platform.security.service import decode_access_token
from app.platform.db.session import SessionLocal
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.shared.resources.models import ResourceMember
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
LOG_STREAM_ID_PATTERN = re.compile(r"^\d+-\d+$")


def _websocket_token(websocket: WebSocket) -> tuple[str, str | None]:
    """优先从 WebSocket 子协议读取令牌，兼容旧版 query token。"""

    protocols = [
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    ]
    if len(protocols) >= 2 and protocols[0].lower() == "bearer":
        return protocols[1], "bearer"
    return websocket.query_params.get("token", ""), None


def _task_access_code(token: str, task_id: int) -> int | None:
    """返回 WebSocket 拒绝码；None 表示当前用户可以读取任务日志。"""

    try:
        user_id = int(decode_access_token(token)["sub"])
    except Exception:
        return 4401

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user or not user.enabled:
            return 4401
        task = db.get(Task, task_id)
        if not task:
            return 4404
        if user.role != "admin" and not db.get(
            ResourceMember,
            (task.project_id, user.id),
        ):
            return 4403
    return None


@router.websocket("/ws/tasks/{task_id}")
async def task_stream(websocket: WebSocket, task_id: int) -> None:
    """校验用户的任务访问权限，并持续推送增量日志。"""

    token, subprotocol = _websocket_token(websocket)
    reject_code = _task_access_code(token, task_id)
    if reject_code is not None:
        await websocket.close(code=reject_code)
        return
    await websocket.accept(subprotocol=subprotocol)
    redis = get_async_redis()
    last_id = websocket.query_params.get("last_id", "0-0")
    if not LOG_STREAM_ID_PATTERN.fullmatch(last_id):
        last_id = "0-0"
    try:
        while True:
            rows = await redis.xread(
                {f"task:{task_id}:logs": last_id}, block=10000, count=500
            )
            if not rows:
                await websocket.send_json({"type": "ping"})
                continue
            batch = []
            for _, messages in rows:
                for message_id, values in messages:
                    last_id = message_id
                    batch.append({"id": message_id, **values})
            if batch:
                # 一帧推送一批日志，避免高输出任务触发数千次浏览器更新。
                await websocket.send_json({"type": "logs", "logs": batch})
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        await redis.aclose()
