"""kw-agent 配置加载：从 config/config.yaml 读取运行参数。

打包后的目录结构：
    {agent_home}/bin/kw-agent(.exe)      <- 本程序
    {agent_home}/config/config.yaml      <- 平台部署时生成
    {agent_home}/data/                   <- 框架与任务运行时数据
    {agent_home}/logs/

开发模式（python main.py）下可用 KW_AGENT_HOME 环境变量指定根目录。
"""

import os
import sys
from pathlib import Path

import yaml


def agent_home() -> Path:
    """定位 Agent 根目录：优先环境变量，其次可执行文件上级目录。"""

    env_home = os.environ.get("KW_AGENT_HOME")
    if env_home:
        return Path(env_home).resolve()
    # PyInstaller 打包后 sys.executable 位于 {agent_home}/bin/；开发模式下退回当前文件
    exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    return exe.parent.parent


class AgentConfig:
    """Agent 运行配置。"""

    def __init__(self, home: Path | None = None) -> None:
        self.home = (home or agent_home()).resolve()
        self.config_path = self.home / "config" / "config.yaml"
        self.data_dir = self.home / "data"
        self.frameworks_dir = self.data_dir / "frameworks"
        self.tasks_dir = self.data_dir / "tasks"
        self.temp_dir = self.data_dir / "temp"
        self.logs_dir = self.home / "logs"

        raw: dict = {}
        if self.config_path.is_file():
            with self.config_path.open("r", encoding="utf-8") as stream:
                raw = yaml.safe_load(stream) or {}
        platform_section = raw.get("platform") or {}
        agent_section = raw.get("agent") or {}
        log_section = raw.get("log") or {}

        self.platform_url = str(platform_section.get("url") or os.environ.get("KW_PLATFORM_URL") or "http://127.0.0.1:8000")
        self.executor_id = int(agent_section.get("executor_id") or os.environ.get("KW_EXECUTOR_ID") or 0)
        self.name = str(agent_section.get("name") or "")
        work_dir = agent_section.get("work_dir")
        if work_dir:
            self.data_dir = Path(str(work_dir)).expanduser().resolve()
            self.frameworks_dir = self.data_dir / "frameworks"
            self.tasks_dir = self.data_dir / "tasks"
            self.temp_dir = self.data_dir / "temp"
        self.max_workers = max(1, int(agent_section.get("max_workers") or 1))
        self.heartbeat_interval = max(3, int(agent_section.get("heartbeat_interval") or 10))
        self.task_poll_interval = max(1, int(agent_section.get("task_poll_interval") or 1))
        self.default_timeout = max(60, int(agent_section.get("default_timeout") or 3600))
        self.log_level = str(log_section.get("level") or "INFO").upper()

    def api(self, path: str) -> str:
        """拼接平台 API 地址。"""

        return f"{self.platform_url.rstrip('/')}/api/v1{path}"

    def ensure_dirs(self) -> None:
        """确保运行所需目录存在。"""

        for directory in (self.frameworks_dir, self.tasks_dir, self.temp_dir, self.logs_dir):
            directory.mkdir(parents=True, exist_ok=True)


def load_config() -> AgentConfig:
    """加载 Agent 配置并初始化目录。"""

    config = AgentConfig()
    config.ensure_dirs()
    return config
