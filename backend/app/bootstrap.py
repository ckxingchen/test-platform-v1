"""应用启动编排：注册模型、初始化基础设施和平台初始数据。"""

import app.model_registry  # noqa: F401 - 集中注册全部 ORM 模型
from app.modules.users.models import User
from app.modules.users.repository import get_by_username
from app.platform.config.settings import settings
from app.platform.db.init_db import initialize_schema
from app.platform.db.migrations import migrate_environment_governance
from app.platform.db.session import SessionLocal
from app.platform.security.service import hash_password
from app.platform.storage.minio import storage


def initialize_database() -> None:
    """保持原启动行为：迁移数据库、创建存储桶并确保默认管理员存在。"""

    # migrate_environment_governance 由 initialize_schema 调用；显式引用用于
    # 让启动编排和迁移注册关系可被静态检查发现。
    _ = migrate_environment_governance
    initialize_schema()
    storage.ensure_buckets()
    with SessionLocal() as db:
        admin = get_by_username(db, settings.superadmin_username)
        if not admin:
            db.add(User(username=settings.superadmin_username, password_hash=hash_password(settings.superadmin_password), role="admin", enabled=True))
            db.commit()
