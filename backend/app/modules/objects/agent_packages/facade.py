"""供执行器模块调用的 Agent 包稳定入口。"""

from app.modules.objects.agent_packages.repository import get_agent_package, get_agent_package_by_platform

__all__ = ["get_agent_package", "get_agent_package_by_platform"]
