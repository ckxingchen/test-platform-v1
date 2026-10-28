"""轻量数据库迁移，维护第一版平台所需的增量字段。"""

import json

from sqlalchemy import Engine, text


def _column_exists(connection, table: str, column: str) -> bool:
    """判断指定表列是否存在（迁移幂等守卫）。"""

    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).first()
    )

LEGACY_COLUMNS = {
    "agent_environments": (
        "port",
        "username",
        "auth_type",
        "secret_encrypted",
        "offline_package_id",
        "agent_token_encrypted",
        "deployed_package_sha256",
    ),
    "agent_deployments": ("deployment_type", "package_sha256"),
}

COMMAND_COLUMNS = (
    'ADD COLUMN IF NOT EXISTS "priority" INTEGER NOT NULL DEFAULT 100',
    'ADD COLUMN IF NOT EXISTS "lease_id" VARCHAR(36)',
    'ADD COLUMN IF NOT EXISTS "lease_expires_at" TIMESTAMP WITH TIME ZONE',
    'ADD COLUMN IF NOT EXISTS "delivery_count" INTEGER NOT NULL DEFAULT 0',
)

TASK_COLUMNS = (
    'ADD COLUMN IF NOT EXISTS "selected_case_paths" JSON',
)


def migrate_legacy_schema(engine: Engine) -> None:
    """在 PostgreSQL 中清理旧列并补齐命令租约字段，重复执行保持幂等。"""

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        for definition in COMMAND_COLUMNS:
            connection.execute(text(f'ALTER TABLE "agent_commands" {definition}'))
        for definition in TASK_COLUMNS:
            connection.execute(text(f'ALTER TABLE "agent_tasks" {definition}'))
        connection.execute(text('DROP INDEX IF EXISTS "ix_agent_commands_delivery"'))
        connection.execute(
            text(
                'CREATE INDEX IF NOT EXISTS "ix_agent_commands_delivery" '
                'ON "agent_commands" ("environment_id", "status", "priority", "id")'
            )
        )
        connection.execute(
            text(
                'CREATE INDEX IF NOT EXISTS "ix_agent_commands_lease_expires_at" '
                'ON "agent_commands" ("lease_expires_at")'
            )
        )
        connection.execute(text("UPDATE agent_commands SET status = 'queued' WHERE status = 'sent'"))
        for table, columns in LEGACY_COLUMNS.items():
            for column in columns:
                connection.execute(text(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{column}" CASCADE'))


def migrate_framework_runner_mode(engine: Engine) -> None:
    """统一打包执行：剥离框架清单的 runner_mode 键，停用 python 模式框架并令引用环境待更新。

    数据迁移策略（幂等，可重复执行）：
    1. 对每个 framework 资源的 metadata_json，移除 runner_mode、requirements、wheelhouse 等
       python 模式专属键（保留 name/os/arch/runner_path/archive_root 等打包执行必需字段）。
    2. 停用 runner_mode == "python" 的历史框架对象（统一打包执行后不再支持源码运行）。
    3. 将引用了这些被停用框架的环境 deploy_status 置为 update_available，提示重新部署。
    """

    if engine.dialect.name != "postgresql":
        return
    python_keys = {"runner_mode", "requirements", "wheelhouse"}
    with engine.begin() as connection:
        frameworks = connection.execute(
            text("SELECT id, metadata_json FROM object_resources WHERE resource_type = 'framework'")
        ).fetchall()
        disabled_ids: list[int] = []
        for framework_id, metadata_raw in frameworks:
            if not metadata_raw:
                continue
            metadata = metadata_raw if isinstance(metadata_raw, dict) else json.loads(metadata_raw)
            runner_mode = metadata.get("runner_mode")
            if not isinstance(metadata, dict) or not runner_mode:
                continue
            cleaned = {key: value for key, value in metadata.items() if key not in python_keys}
            if runner_mode == "python":
                disabled_ids.append(framework_id)
            connection.execute(
                text("UPDATE object_resources SET metadata_json = CAST(:meta AS json) WHERE id = :id"),
                {"meta": json.dumps(cleaned, ensure_ascii=False), "id": framework_id},
            )
        if disabled_ids and _column_exists(connection, "agent_environments", "deploy_status"):
            connection.execute(
                text(
                    "UPDATE agent_environments SET deploy_status = 'update_available' "
                    "WHERE framework_id = ANY(:ids)"
                ),
                {"ids": disabled_ids},
            )


def migrate_framework_os_arch(engine: Engine) -> None:
    """框架多版本：给 object_resources 增加 os/arch 独立列，回填后重建唯一约束。

    1. 新增 os、arch 可空列（framework 专用，project 资源保持 NULL）。
    2. 从 metadata_json 回填历史 framework 的 os/arch（缺省时用 linux/x86_64）。
    3. 将唯一约束从 (resource_type, name) 改为 (resource_type, name, os, arch)。
       PostgreSQL 中 NULL 不参与唯一性比较，因此 project 类型（os/arch 均为 NULL）
       可继续存在多条，而 framework 按 (name, os, arch) 严格唯一。
    """

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE "object_resources" ADD COLUMN IF NOT EXISTS "os" VARCHAR(30)'))
        connection.execute(text('ALTER TABLE "object_resources" ADD COLUMN IF NOT EXISTS "arch" VARCHAR(30)'))
        # 回填 framework 的 os/arch
        frameworks = connection.execute(
            text("SELECT id, metadata_json FROM object_resources WHERE resource_type = 'framework' AND (os IS NULL OR arch IS NULL)")
        ).fetchall()
        for resource_id, metadata_raw in frameworks:
            metadata = metadata_raw if isinstance(metadata_raw, dict) else (json.loads(metadata_raw) if metadata_raw else {})
            os_value = (metadata.get("os") or "linux").lower()
            arch_value = (metadata.get("arch") or "x86_64").lower()
            connection.execute(
                text("UPDATE object_resources SET os = :os, arch = :arch WHERE id = :id"),
                {"os": os_value, "arch": arch_value, "id": resource_id},
            )
        # 重建唯一约束：先删除旧的 (resource_type, name) 唯一约束（兼容 SQLAlchemy
        # 自动命名与 PostgreSQL 默认命名），再新建四列唯一约束。为保证幂等，
        # 新增约束前同样先移除同名约束。
        connection.execute(text('ALTER TABLE "object_resources" DROP CONSTRAINT IF EXISTS "uq_object_resources_resource_type_name"'))
        connection.execute(text('ALTER TABLE "object_resources" DROP CONSTRAINT IF EXISTS "object_resources_resource_type_name_key"'))
        connection.execute(text('ALTER TABLE "object_resources" DROP CONSTRAINT IF EXISTS "uq_object_resources_resource_type_name_os_arch"'))
        connection.execute(
            text(
                'ALTER TABLE "object_resources" ADD CONSTRAINT "uq_object_resources_resource_type_name_os_arch" '
                'UNIQUE (resource_type, name, os, arch)'
            )
        )


def migrate_environment_governance(engine: Engine) -> None:
    """给 agent_environments 增加归属人、分组和自由标签三列（幂等）。

    1. owner_id 外键指向 users.id，删除用户时置空（ON DELETE SET NULL）。
    2. group_name 为自由文本分组（VARCHAR(50)，可空）。
    3. tags 为自由标签 JSON 数组（默认 []）。
    为保证重复执行幂等：ADD COLUMN 使用 IF NOT EXISTS；外键约束先
    DROP CONSTRAINT IF EXISTS 再 ADD。
    """

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE "agent_environments" ADD COLUMN IF NOT EXISTS "owner_id" INTEGER'))
        connection.execute(text('ALTER TABLE "agent_environments" ADD COLUMN IF NOT EXISTS "group_name" VARCHAR(50)'))
        connection.execute(text('ALTER TABLE "agent_environments" ADD COLUMN IF NOT EXISTS "tags" JSON NOT NULL DEFAULT \'[]\''))
        connection.execute(text('ALTER TABLE "agent_environments" DROP CONSTRAINT IF EXISTS "fk_agent_environments_owner_id"'))
        connection.execute(
            text(
                'ALTER TABLE "agent_environments" ADD CONSTRAINT "fk_agent_environments_owner_id" '
                'FOREIGN KEY ("owner_id") REFERENCES "users" ("id") ON DELETE SET NULL'
            )
        )


def migrate_executor_refactor(engine: Engine) -> None:
    """Agent 与执行器重构迁移（幂等）。

    1. agent_environments 新增 SSH 凭据、os/arch、agent_home、Agent/框架 SHA 与状态列。
    2. 旧列数据迁移到新列（work_root→agent_home、max_concurrency→max_workers、
       os_family→os、deployed_framework_sha256→framework_sha256、deploy_status→framework_status）。
    3. framework_id 放开非空限制（框架改为 Agent 上线后部署）。
    4. 新增 agent_package_id 外键（agent_packages 表由 create_all 先行创建）。
    5. 清理废弃旧列；将遗留未完成的 Agent 命令统一标记 canceled。
    """

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        executor_columns = (
            'ADD COLUMN IF NOT EXISTS "ssh_port" INTEGER NOT NULL DEFAULT 22',
            'ADD COLUMN IF NOT EXISTS "ssh_username" VARCHAR(100)',
            'ADD COLUMN IF NOT EXISTS "ssh_password_enc" TEXT',
            'ADD COLUMN IF NOT EXISTS "os" VARCHAR(30)',
            'ADD COLUMN IF NOT EXISTS "arch" VARCHAR(30)',
            'ADD COLUMN IF NOT EXISTS "agent_home" VARCHAR(500)',
            'ADD COLUMN IF NOT EXISTS "agent_package_id" INTEGER',
            'ADD COLUMN IF NOT EXISTS "agent_sha256" VARCHAR(64)',
            'ADD COLUMN IF NOT EXISTS "framework_sha256" VARCHAR(64)',
            'ADD COLUMN IF NOT EXISTS "framework_status" VARCHAR(20) NOT NULL DEFAULT \'not_deployed\'',
            'ADD COLUMN IF NOT EXISTS "max_workers" INTEGER NOT NULL DEFAULT 1',
            'ADD COLUMN IF NOT EXISTS "running_tasks" INTEGER NOT NULL DEFAULT 0',
        )
        for definition in executor_columns:
            connection.execute(text(f'ALTER TABLE "agent_environments" {definition}'))
        # 旧列数据迁移（仅在旧列仍存在时执行）
        if _column_exists(connection, "agent_environments", "work_root"):
            connection.execute(text('UPDATE agent_environments SET agent_home = work_root WHERE agent_home IS NULL OR agent_home = \'/opt/kw-agent\''))
        if _column_exists(connection, "agent_environments", "max_concurrency"):
            connection.execute(text('UPDATE agent_environments SET max_workers = max_concurrency'))
        if _column_exists(connection, "agent_environments", "os_family"):
            connection.execute(text('UPDATE agent_environments SET os = LOWER(os_family) WHERE os IS NULL AND os_family IS NOT NULL'))
        if _column_exists(connection, "agent_environments", "deployed_framework_sha256"):
            connection.execute(text('UPDATE agent_environments SET framework_sha256 = deployed_framework_sha256 WHERE framework_sha256 IS NULL'))
        if _column_exists(connection, "agent_environments", "deploy_status"):
            connection.execute(
                text(
                    "UPDATE agent_environments SET framework_status = CASE "
                    "WHEN deploy_status = 'ready' THEN 'deployed' "
                    "WHEN deploy_status IN ('deploying', 'update_available') THEN 'not_deployed' "
                    "WHEN deploy_status = 'failed' THEN 'failed' "
                    "ELSE 'not_deployed' END "
                    "WHERE framework_status = 'not_deployed'"
                )
            )
        # framework_id 允许为空（框架在 Agent 上线后由管理员部署）
        connection.execute(text('ALTER TABLE "agent_environments" ALTER COLUMN "framework_id" DROP NOT NULL'))
        # agent_package_id 外键（先删后建保证幂等，与模型内联命名对齐）
        connection.execute(text('ALTER TABLE "agent_environments" DROP CONSTRAINT IF EXISTS "fk_agent_environments_agent_package_id"'))
        connection.execute(
            text(
                'ALTER TABLE "agent_environments" ADD CONSTRAINT "fk_agent_environments_agent_package_id" '
                'FOREIGN KEY ("agent_package_id") REFERENCES "agent_packages" ("id") ON DELETE SET NULL'
            )
        )
        # 清理废弃旧列
        for column in (
            "work_root",
            "max_concurrency",
            "agent_token_hash",
            "deploy_status",
            "os_family",
            "os_version",
            "deployed_framework_sha256",
            "deploy_error",
        ):
            connection.execute(text(f'ALTER TABLE "agent_environments" DROP COLUMN IF EXISTS "{column}" CASCADE'))
        # 遗留命令统一取消（新架构 Agent 改为 HTTP 轮询，不再消费命令队列）
        connection.execute(text("UPDATE agent_commands SET status = 'canceled' WHERE status IN ('queued', 'leased', 'running')"))
