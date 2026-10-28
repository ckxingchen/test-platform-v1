"""FastAPI 生命周期使用的后台维护循环。"""

import asyncio
import logging

from app.platform.config.settings import settings
from app.jobs.maintenance import run_maintenance_once

logger = logging.getLogger(__name__)


async def maintenance_loop() -> None:
    """按固定间隔在线程中运行同步数据库维护，取消时立即退出。"""

    while True:
        try:
            result = await asyncio.to_thread(run_maintenance_once)
            if any(result.values()):
                logger.info("平台维护完成：%s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("平台后台维护失败")
        await asyncio.sleep(settings.maintenance_interval_seconds)
