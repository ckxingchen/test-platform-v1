"""平台 HTTP 客户端：所有与平台的网络交互统一封装在此。

业务模块不直接使用 httpx，方便统一超时、重试和日志。
"""

import logging
from pathlib import Path

import httpx

logger = logging.getLogger("kw-agent.client")


class PlatformClient:
    """平台 API 同步客户端（线程安全，可被任务工作线程复用）。"""

    def __init__(self, config) -> None:
        self.config = config
        self._client = httpx.Client(timeout=httpx.Timeout(300.0, connect=15.0))

    def close(self) -> None:
        """关闭底层 HTTP 连接池。"""

        self._client.close()

    # ---------------------------------------------------------------- 心跳与指令

    def heartbeat(self, running_tasks: list[int], agent_sha256: str | None = None, framework_sha256: str | None = None) -> dict:
        """上报心跳，返回需要取消的任务编号列表。"""

        response = self._client.post(
            self.config.api(f"/agent/{self.config.executor_id}/heartbeat"),
            json={
                "running_tasks": running_tasks,
                "agent_sha256": agent_sha256,
                "framework_sha256": framework_sha256,
            },
        )
        response.raise_for_status()
        return response.json()

    def pull_actions(self) -> dict:
        """拉取部署指令（框架部署等）。"""

        response = self._client.get(self.config.api(f"/agent/{self.config.executor_id}/actions"))
        response.raise_for_status()
        return response.json()

    def pull_tasks(self, limit: int) -> list[dict]:
        """按空闲槽位领取排队任务。"""

        response = self._client.get(self.config.api(f"/agent/{self.config.executor_id}/tasks"), params={"limit": limit})
        response.raise_for_status()
        return response.json().get("tasks") or []

    # ---------------------------------------------------------------- 下载

    def download_framework(self, target: Path) -> bytes:
        """下载执行器绑定的框架归档并返回原始字节（同时落盘）。"""

        response = self._client.get(self.config.api(f"/agent/{self.config.executor_id}/framework"))
        response.raise_for_status()
        data = response.content
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return data

    def download_project(self, task_id: int, target: Path) -> Path:
        """下载任务项目 ZIP（含本次 INI 配置）到临时文件。"""

        response = self._client.get(self.config.api(f"/agent/tasks/{task_id}/project"))
        response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return target

    # ---------------------------------------------------------------- 状态上报

    def report_framework_status(self, deployment_id: int, status: str, sha256: str | None = None, error_message: str | None = None) -> None:
        """上报框架部署结果。"""

        response = self._client.post(
            self.config.api(f"/agent/{self.config.executor_id}/framework/status"),
            json={"deployment_id": deployment_id, "status": status, "sha256": sha256, "error_message": error_message},
        )
        response.raise_for_status()

    def report_task_status(self, task_id: int, status: str, exit_code: int | None = None, error_message: str | None = None) -> None:
        """上报任务状态。"""

        response = self._client.put(
            self.config.api(f"/agent/tasks/{task_id}/status"),
            json={"status": status, "exit_code": exit_code, "error_message": error_message},
        )
        response.raise_for_status()

    def upload_task_logs(self, task_id: int, lines: list[str], level: str = "INFO") -> None:
        """批量上传任务日志行。"""

        if not lines:
            return
        response = self._client.post(
            self.config.api(f"/agent/tasks/{task_id}/logs"),
            json={"lines": lines, "level": level},
        )
        response.raise_for_status()

    def upload_task_results(self, task_id: int, cases: list[dict]) -> None:
        """上传逐用例结构化结果。"""

        response = self._client.post(
            self.config.api(f"/agent/tasks/{task_id}/results"),
            json={"cases": cases},
        )
        response.raise_for_status()

    def upload_task_artifact(self, task_id: int, artifact_type: str, path: Path) -> None:
        """上传任务产物（日志/报告压缩包）。"""

        with path.open("rb") as stream:
            response = self._client.post(
                self.config.api(f"/agent/tasks/{task_id}/artifacts"),
                params={"artifact_type": artifact_type},
                files={"file": (path.name, stream)},
            )
        response.raise_for_status()
