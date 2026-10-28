"""kw-agent 唯一启动入口：加载配置 → 初始化日志 → 运行主循环。"""

import logging
import sys

from agent.config import load_config
from agent.service.agent_service import AgentService


def setup_logging(config) -> None:
    """配置控制台 + 文件双通道日志。"""

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            config.logs_dir / "agent.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handlers.append(file_handler)
    except OSError:
        pass
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )


def main() -> None:
    """Agent 进程入口。"""

    config = load_config()
    setup_logging(config)
    service = AgentService(config)
    service.run()


if __name__ == "__main__":
    main()
