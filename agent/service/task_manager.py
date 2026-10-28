"""多任务并发管理：ThreadPoolExecutor + 运行任务注册表。"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from agent.client.platform_client import PlatformClient
from agent.service.task_runner import TaskRunner

logger = logging.getLogger("kw-agent.manager")


class TaskManager:
    """维护运行中的 TaskRunner，提供并发上限与取消能力。"""

    def __init__(self, config, client: PlatformClient) -> None:
        self.config = config
        self.client = client
        self._pool = ThreadPoolExecutor(max_workers=config.max_workers, thread_name_prefix="kw-task")
        self._running: dict[int, TaskRunner] = {}
        self._lock = threading.Lock()

    @property
    def running_ids(self) -> list[int]:
        """当前运行中的任务编号列表。"""

        with self._lock:
            return list(self._running)

    @property
    def free_workers(self) -> int:
        """空闲槽位数。"""

        return max(0, self.config.max_workers - len(self.running_ids))

    def submit(self, payload: dict) -> None:
        """提交任务到线程池执行。"""

        task_id = int(payload["task_id"])
        runner = TaskRunner(self.config, self.client, payload)

        def _wrapped() -> None:
            try:
                runner.run()
            finally:
                with self._lock:
                    self._running.pop(task_id, None)

        with self._lock:
            self._running[task_id] = runner
        self._pool.submit(_wrapped)
        logger.info("任务 %s 已提交（运行中 %s）", task_id, len(self.running_ids))

    def cancel(self, task_id: int) -> None:
        """取消运行中的任务。"""

        with self._lock:
            runner = self._running.get(task_id)
        if runner:
            logger.info("取消任务 %s", task_id)
            runner.cancel()

    def shutdown(self) -> None:
        """等待全部任务结束后关闭线程池。"""

        self._pool.shutdown(wait=True)
