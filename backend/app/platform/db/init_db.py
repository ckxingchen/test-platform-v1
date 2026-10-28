"""数据库建表与兼容迁移，不包含任何业务初始化。"""

from app.platform.db.base import Base
from app.platform.db.migrations import migrate_environment_governance, migrate_executor_refactor, migrate_framework_os_arch, migrate_framework_runner_mode, migrate_legacy_schema
from app.platform.db.session import engine


def initialize_schema() -> None:
    """创建已注册 ORM 表，并执行全部幂等兼容迁移。"""
    Base.metadata.create_all(engine)
    migrate_legacy_schema(engine)
    migrate_framework_runner_mode(engine)
    migrate_framework_os_arch(engine)
    migrate_environment_governance(engine)
    migrate_executor_refactor(engine)
