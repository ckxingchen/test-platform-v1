"""本次「自动化测试平台整体重构」的回归测试。

覆盖 team-lead 要求的重点验证项（独立证明，不依赖工程师已跑过的测试）：
1. 迁移幂等性（静态守卫 + SQLite 非 PG 无副作用运行）
2. 权限收口（require_roles / ensure_project_access 行为 + 端点依赖静态断言）
3. 名称化冗余字段（environment_to_dict / task_to_dict 组装 + 各端点返回）
4. 新增端点功能（overview / framework 反向索引 / 项目任务 / tasks 过滤）
5. 关键响应 dict 通过 Pydantic Schema 校验（等价于 FastAPI response_model 边界）

说明：本地无 PostgreSQL / Docker 可用，无法对真实 PG 执行两次迁移；故迁移
幂等性以「源码守卫静态断言 + 非 PG 引擎无副作用执行」双重验证，并明确标注。
"""
import inspect

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.model_registry  # noqa: F401 注册全部 ORM 模型到 Base.metadata
from app.modules.auth.dependencies import ensure_project_access, require_roles
from app.modules.executors import deployments_router as deployments
from app.modules.executors import router as environments
from app.modules.executors.models import Environment
from app.modules.executors.repository import environment_to_dict
from app.modules.executors.schemas import EnvironmentOut, EnvironmentOverviewOut
from app.modules.objects.frameworks import router as frameworks
from app.modules.objects.projects import router as projects
from app.modules.tasks import router as tasks
from app.modules.tasks.models import Task
from app.modules.tasks.repository import task_to_dict
from app.modules.tasks.schemas import TaskCreate, TaskOut
from app.modules.users.models import User
from app.platform.db.base import Base
from app.platform.db.migrations import migrate_environment_governance
from app.shared.resources.models import Resource, ResourceFile, ResourceMember
from app.shared.resources.schemas import FrameworkOut


@pytest.fixture()
def engine():
    """每个测试独立的 SQLite 内存库（StaticPool 保证单连接跨 Session 共享）。"""
    db_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(db_engine)
    yield db_engine
    Base.metadata.drop_all(db_engine)
    db_engine.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session


def _user(db: Session, username: str, role: str) -> User:
    user = User(username=username, password_hash="x", role=role)
    db.add(user)
    db.flush()
    return user


def _seed_world(db: Session):
    """构造 admin/dev/viewer 用户、项目、框架、执行器、成员、文件与一条任务。"""
    admin = _user(db, "admin", "admin")
    dev = _user(db, "dev", "developer")
    viewer = _user(db, "viewer", "viewer")

    project = Resource(resource_type="project", name="登录自动化", metadata_json={}, created_by=admin.id)
    framework = Resource(
        resource_type="framework", name="kw-fw", os="linux", arch="x86_64",
        metadata_json={"runner_path": "driver/cli"}, created_by=admin.id,
    )
    db.add_all([project, framework])
    db.flush()

    db.add(ResourceFile(resource_id=project.id, relative_path="testcase/登录/a.yaml", object_key="p/k", sha256="p" * 64, size=1, updated_by=admin.id))
    db.add(ResourceFile(resource_id=framework.id, relative_path="framework.zip", object_key="f/k", sha256="f" * 64, size=1, updated_by=admin.id))

    env = Environment(
        name="exec-1", host="192.168.14.100", framework_id=framework.id,
        framework_status="deployed", agent_status="online", framework_sha256="f" * 64,
        owner_id=admin.id, group_name="核心组", tags=["linux", "ci"],
    )
    db.add(env)
    db.flush()

    db.add(ResourceMember(resource_id=project.id, user_id=dev.id, role="developer"))
    db.add(ResourceMember(resource_id=project.id, user_id=viewer.id, role="viewer"))

    task = Task(
        project_id=project.id, environment_id=env.id, framework_id=framework.id,
        framework_sha256="f" * 64, status="success", config_content="[run]\na=1\n",
        created_by=dev.id, selected_case_paths=["testcase/登录/a.yaml"],
    )
    db.add(task)
    db.flush()
    db.commit()
    return {
        "admin": admin, "dev": dev, "viewer": viewer,
        "project": project, "framework": framework, "env": env, "task": task,
    }


# --------------------------------------------------------------------------- #
# 1. 迁移幂等性
# --------------------------------------------------------------------------- #
class TestMigrationGovernance:
    def test_guards_are_idempotent(self):
        """迁移必须对新增列使用 IF NOT EXISTS，对外键先 DROP CONSTRAINT IF EXISTS。"""
        source = inspect.getsource(migrate_environment_governance)
        assert source.count("ADD COLUMN IF NOT EXISTS") >= 3
        assert "DROP CONSTRAINT IF EXISTS" in source
        assert "fk_agent_environments_owner_id" in source
        assert "ON DELETE SET NULL" in source

    def test_noop_on_non_postgresql(self, engine):
        """非 PostgreSQL 引擎直接返回，不抛异常（SQLite 下可无副作用执行）。"""
        migrate_environment_governance(engine)  # 不应抛错

    def test_registered_in_init_db(self):
        """新迁移必须挂载到 init_db 初始化序列中。"""
        import app.bootstrap as init_db
        assert "migrate_environment_governance" in inspect.getsource(init_db.initialize_database)


# --------------------------------------------------------------------------- #
# 2. 权限收口
# --------------------------------------------------------------------------- #
class TestPermissionEnforcement:
    def test_require_roles_admin_gate(self, db):
        world = _seed_world(db)
        checker = require_roles("admin")
        assert checker(user=world["admin"]).role == "admin"
        with pytest.raises(HTTPException) as exc:
            checker(user=world["viewer"])
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            checker(user=world["dev"])
        assert exc.value.status_code == 403

    def test_ensure_project_access_rules(self, db):
        world = _seed_world(db)
        pid = world["project"].id
        # admin 直通
        ensure_project_access(db, pid, world["admin"])
        # 成员读直通
        ensure_project_access(db, pid, world["viewer"])
        # 非成员 403
        outsider = _user(db, "outsider", "viewer")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            ensure_project_access(db, pid, outsider)
        assert exc.value.status_code == 403
        # viewer 成员写 -> 403（角色非 developer）
        with pytest.raises(HTTPException) as exc:
            ensure_project_access(db, pid, world["viewer"], write=True)
        assert exc.value.status_code == 403
        # developer 成员写 -> 直通
        ensure_project_access(db, pid, world["dev"], write=True)

    def test_framework_write_endpoints_require_admin(self):
        """upload / delete / download / 重新部署 全部挂 Depends(admin)。"""
        for fn in (
            frameworks.upload_framework,
            frameworks.delete_framework,
            frameworks.download_framework,
            deployments.deploy_framework,
        ):
            assert "Depends(admin)" in inspect.getsource(fn), fn.__name__

    def test_framework_read_endpoints_allow_current_user(self):
        for fn in (frameworks.list_frameworks, frameworks.get_framework, frameworks.list_framework_environments):
            assert "current_user" in inspect.getsource(fn) and "Depends(admin)" not in inspect.getsource(fn), fn.__name__

    def test_project_tasks_endpoint_gates_access(self, db):
        world = _seed_world(db)
        pid = world["project"].id
        # 非成员 viewer -> 403（挂 ensure_project_access）
        outsider = _user(db, "outsider2", "viewer")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            projects.list_project_tasks(pid, user=outsider, db=db)
        assert exc.value.status_code == 403
        # 成员 viewer -> 200 语义（返回列表）
        result = projects.list_project_tasks(pid, user=world["viewer"], db=db)
        assert isinstance(result, list) and len(result) == 1

    def test_create_task_rejects_viewer(self, db):
        world = _seed_world(db)
        data = TaskCreate(project_id=world["project"].id, environment_id=world["env"].id, config_content="[run]\na=1\n")
        with pytest.raises(HTTPException) as exc:
            tasks.create_task(data, user=world["viewer"], db=db)
        assert exc.value.status_code == 403


# --------------------------------------------------------------------------- #
# 3. 名称化冗余字段组装
# --------------------------------------------------------------------------- #
class TestNameAssembly:
    def test_environment_to_dict_with_framework_and_owner(self, db):
        world = _seed_world(db)
        item = world["env"]
        result = environment_to_dict(item, world["framework"], world["admin"])
        assert result["framework_name"] == "kw-fw"
        assert result["framework_os"] == "linux"
        assert result["framework_arch"] == "x86_64"
        assert result["owner_name"] == "admin"
        assert result["group_name"] == "核心组"
        assert result["tags"] == ["linux", "ci"]
        EnvironmentOut.model_validate(result)  # 通过 Schema 边界校验

    def test_environment_to_dict_without_join(self, db):
        world = _seed_world(db)
        result = environment_to_dict(world["env"], None, None)
        assert result["framework_name"] is None
        assert result["owner_name"] is None
        EnvironmentOut.model_validate(result)

    def test_task_to_dict_names(self, db):
        world = _seed_world(db)
        result = task_to_dict(world["task"], world["project"], world["env"], world["framework"])
        assert result["project_name"] == "登录自动化"
        assert result["environment_name"] == "exec-1"
        assert result["framework_name"] == "kw-fw"
        TaskOut.model_validate(result)


# --------------------------------------------------------------------------- #
# 4. 端点返回结构与新增端点功能
# --------------------------------------------------------------------------- #
class TestEndpointFields:
    def test_list_tasks_returns_names_and_filters(self, db):
        world = _seed_world(db)
        # 追加一条不同状态/项目的任务
        db.add(Task(project_id=world["project"].id, environment_id=world["env"].id,
                    framework_id=world["framework"].id, framework_sha256="f" * 64,
                    status="failed", config_content="[run]\na=1\n", created_by=world["dev"].id))
        db.commit()

        all_rows = tasks.list_tasks(user=world["admin"], db=db)
        assert len(all_rows) == 2
        for row in all_rows:
            TaskOut.model_validate(row)
            assert row["project_name"] == "登录自动化"
            assert row["environment_name"] == "exec-1"
            assert row["framework_name"] == "kw-fw"

        # 过滤：status
        assert len(tasks.list_tasks(status="failed", user=world["admin"], db=db)) == 1
        # 过滤：project_id
        assert len(tasks.list_tasks(project_id=world["project"].id, user=world["admin"], db=db)) == 2
        # 过滤：environment_id
        assert len(tasks.list_tasks(environment_id=world["env"].id, user=world["admin"], db=db)) == 2
        # 过滤：不存在的 project_id -> 空列表（不报错）
        assert tasks.list_tasks(project_id=99999, user=world["admin"], db=db) == []

    def test_non_admin_list_tasks_scoped_to_membership(self, db):
        world = _seed_world(db)
        rows = tasks.list_tasks(user=world["dev"], db=db)
        assert len(rows) == 1 and rows[0]["project_id"] == world["project"].id

    def test_get_task_returns_names(self, db):
        world = _seed_world(db)
        row = tasks.get_task(world["task"].id, user=world["dev"], db=db)
        TaskOut.model_validate(row)
        assert row["project_name"] == "登录自动化"

    def test_create_task_returns_names(self, db):
        world = _seed_world(db)
        data = TaskCreate(project_id=world["project"].id, environment_id=world["env"].id,
                          selected_case_paths=["testcase/登录/a.yaml"], config_content="[run]\na=1\n")
        row = tasks.create_task(data, user=world["dev"], db=db)
        TaskOut.model_validate(row)
        assert row["project_name"] == "登录自动化"
        assert row["environment_name"] == "exec-1"
        assert row["framework_name"] == "kw-fw"

    def test_rerun_task_returns_names(self, db):
        world = _seed_world(db)
        row = tasks.rerun_task(world["task"].id, user=world["dev"], db=db)
        TaskOut.model_validate(row)
        assert row["project_name"] == "登录自动化"
        assert row["environment_name"] == "exec-1"
        assert row["framework_name"] == "kw-fw"

    def test_list_environments_returns_framework_and_owner(self, db):
        world = _seed_world(db)
        rows = environments.list_environments(_=world["admin"], db=db)
        assert len(rows) == 1
        EnvironmentOut.model_validate(rows[0])
        assert rows[0]["framework_name"] == "kw-fw"
        assert rows[0]["framework_os"] == "linux"
        assert rows[0]["framework_arch"] == "x86_64"
        assert rows[0]["owner_name"] == "admin"

    def test_read_environment_returns_names(self, db):
        world = _seed_world(db)
        row = environments.read_environment(world["env"].id, _=world["admin"], db=db)
        EnvironmentOut.model_validate(row)
        assert row["framework_name"] == "kw-fw"
        assert row["owner_name"] == "admin"

    def test_environment_overview_aggregate(self, db):
        world = _seed_world(db)
        result = environments.environment_overview(world["env"].id, user=world["admin"], db=db)
        EnvironmentOverviewOut.model_validate(result)
        assert result["framework"]["name"] == "kw-fw"
        assert result["concurrency"] == {"max": world["env"].max_workers, "active": 0}
        assert len(result["task_history"]) == 1
        assert result["task_history"][0]["project_name"] == "登录自动化"

    def test_list_frameworks_used_by_count(self, db):
        world = _seed_world(db)
        rows = frameworks.list_frameworks(_=world["admin"], db=db)
        assert len(rows) == 1
        FrameworkOut.model_validate(rows[0])
        assert rows[0]["used_by_count"] == 1

    def test_list_framework_environments(self, db):
        world = _seed_world(db)
        rows = frameworks.list_framework_environments(world["framework"].id, _=world["admin"], db=db)
        assert len(rows) == 1
        EnvironmentOut.model_validate(rows[0])
        assert rows[0]["name"] == "exec-1"
        assert rows[0]["framework_name"] == "kw-fw"

    def test_project_tasks_returns_names(self, db):
        world = _seed_world(db)
        rows = projects.list_project_tasks(world["project"].id, user=world["admin"], db=db)
        assert len(rows) == 1
        TaskOut.model_validate(rows[0])
        assert rows[0]["project_name"] == "登录自动化"
        assert rows[0]["environment_name"] == "exec-1"
