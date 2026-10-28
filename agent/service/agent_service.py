"""Agent 主循环：心跳 → 拉取部署指令 → 拉取任务 → 调度执行。"""

import logging
import time

from agent.client.platform_client import PlatformClient
from agent.service.deployment_service import DeploymentService
from agent.service.task_manager import TaskManager
from agent.utils.runtime import current_arch, current_os, hostname

logger = logging.getLogger("kw-agent.service")


class AgentService:
    """Agent 业务主循环。"""

    def __init__(self, config) -> None:
        self.config = config
        self.client = PlatformClient(config)
        self.task_manager = TaskManager(config, self.client)
        self.deployment_service = DeploymentService(config, self.client)
        self.framework_sha256: str | None = None
        self.agent_sha256: str | None = None
        self._stop = False

    def stop(self) -> None:
        """请求停止主循环并等待运行中任务结束。"""

        self._stop = True

    def run(self) -> None:
        """阻塞运行主循环，直到异常退出或外部停止。"""

        logger.info(
            "kw-agent 启动 executor_id=%s name=%s os=%s arch=%s host=%s platform=%s",
            self.config.executor_id, self.config.name, current_os(), current_arch(), hostname(), self.config.platform_url,
        )
        if not self.config.executor_id:
            raise RuntimeError("配置缺少 agent.executor_id，请通过平台部署 Agent 生成 config/config.yaml")
        try:
            while not self._stop:
                self._tick()
                time.sleep(self.config.task_poll_interval)
        except KeyboardInterrupt:
            logger.info("收到中断信号，退出主循环")
        finally:
            self.task_manager.shutdown()
            self.client.close()
            logger.info("kw-agent 已退出")

    def _tick(self) -> None:
        """单轮循环：心跳（含取消）→ 部署指令 → 任务领取。"""

        try:
            self._heartbeat()
        except Exception as exc:  # noqa: BLE001 网络抖动不应退出主循环
            logger.warning("心跳失败：%s", exc)
            return
        try:
            self._handle_actions()
        except Exception as exc:  # noqa: BLE001
            logger.warning("处理部署指令失败：%s", exc)
        try:
            self._pull_tasks()
        except Exception as exc:  # noqa: BLE001
            logger.warning("拉取任务失败：%s", exc)

    def _heartbeat(self) -> None:
        """心跳上报并处理平台下发的取消任务。"""

        result = self.client.heartbeat(
            self.task_manager.running_ids,
            agent_sha256=self.agent_sha256,
            framework_sha256=self.framework_sha256,
        )
        for task_id in result.get("cancel_tasks") or []:
            self.task_manager.cancel(int(task_id))

    def _handle_actions(self) -> None:
        """拉取并执行部署指令（部署期间阻塞任务拉取，框架部署要求无运行任务）。"""

        action = self.client.pull_actions()
        if not action.get("deploy_framework"):
            return
        logger.info("收到框架部署指令 deployment_id=%s", action.get("deployment_id"))
        self.deployment_service.deploy(action)

    def _pull_tasks(self) -> None:
        """按空闲槽位领取排队任务。"""

        free = self.task_manager.free_workers
        if free <= 0:
            return
        for payload in self.client.pull_tasks(free):
            if self.task_manager.free_workers <= 0:
                break
            self.task_manager.submit(payload)
