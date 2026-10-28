"""供任务、执行器和 Agent Gateway 调用的框架入口。"""

from app.modules.objects.frameworks.repository import get_enabled_framework_with_file

__all__ = ["get_enabled_framework_with_file"]
