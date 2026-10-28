"""公共封装（helpers / common）单元测试。

覆盖 get_or_404、commit_or_conflict、ensure_no_tasks、model_to_dict 与
remove_resource_files，并断言 model_to_dict 三个适配器不泄露敏感键、字段集合
与手写 dict 一致。
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from urllib.parse import quote

import app.model_registry  # noqa: F401 注册全部 ORM 模型到 Base.metadata
from app.modules.executors.models import Environment
from app.modules.executors.repository import environment_to_dict
from app.modules.objects.frameworks.repository import framework_out
from app.modules.objects.projects.access import get_accessible_project
from app.modules.tasks.guards import ensure_no_tasks
from app.modules.tasks.models import Task
from app.modules.tasks.repository import task_to_dict
from app.modules.users.models import User
from app.platform.db.base import Base
from app.platform.db.serialization import model_to_dict
from app.platform.web.helpers import commit_or_conflict, download_response, get_or_404
from app.shared.resources.common import remove_resource_files
from app.shared.resources.models import Resource, ResourceFile, ResourceMember


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


class TestGetOr404:
    def test_returns_value(self):
        assert get_or_404("ok", "缺失") == "ok"

    def test_raises_404_on_none(self):
        with pytest.raises(HTTPException) as exc:
            get_or_404(None, "资源不存在")
        assert exc.value.status_code == 404
        assert exc.value.detail == "资源不存在"


class TestDownloadResponse:
    def test_content_disposition_and_media_type(self):
        resp = download_response(b"raw-bytes", "报告.html")
        assert resp.body == b"raw-bytes"
        assert resp.media_type == "application/octet-stream"
        assert resp.headers["Content-Disposition"] == f"attachment; filename*=UTF-8''{quote('报告.html')}"

    def test_ascii_filename_is_quoted(self):
        resp = download_response(b"x", "report 1.tar.gz")
        assert resp.headers["Content-Disposition"] == "attachment; filename*=UTF-8''report%201.tar.gz"


class TestGetAccessibleProject:
    def _seed(self, db):
        admin = User(username="admin", password_hash="x", role="admin")
        dev = User(username="dev", password_hash="x", role="developer")
        viewer = User(username="viewer", password_hash="x", role="viewer")
        db.add_all([admin, dev, viewer])
        db.flush()
        project = Resource(resource_type="project", name="登录自动化", metadata_json={}, created_by=admin.id)
        db.add(project)
        db.flush()
        db.add(ResourceMember(resource_id=project.id, user_id=dev.id, role="developer"))
        db.add(ResourceMember(resource_id=project.id, user_id=viewer.id, role="viewer"))
        db.commit()
        return admin, dev, viewer, project

    def test_returns_project_for_admin(self, db):
        admin, _, _, project = self._seed(db)
        assert get_accessible_project(db, project.id, admin).id == project.id

    def test_returns_project_for_member_read(self, db):
        _, _, viewer, project = self._seed(db)
        assert get_accessible_project(db, project.id, viewer).id == project.id

    def test_member_viewer_write_denied(self, db):
        _, _, viewer, project = self._seed(db)
        with pytest.raises(HTTPException) as exc:
            get_accessible_project(db, project.id, viewer, write=True)
        assert exc.value.status_code == 403

    def test_member_developer_write_allowed(self, db):
        _, dev, _, project = self._seed(db)
        assert get_accessible_project(db, project.id, dev, write=True).id == project.id

    def test_outsider_denied(self, db):
        _, _, _, project = self._seed(db)
        outsider = User(username="outsider", password_hash="x", role="viewer")
        db.add(outsider)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            get_accessible_project(db, project.id, outsider)
        assert exc.value.status_code == 403

    def test_missing_project_404(self, db):
        admin, _, _, _ = self._seed(db)
        with pytest.raises(HTTPException) as exc:
            get_accessible_project(db, 99999, admin)
        assert exc.value.status_code == 404
        assert exc.value.detail == "测试项目不存在"

    def test_wrong_resource_type_404(self, db):
        admin, _, _, _ = self._seed(db)
        framework = Resource(resource_type="framework", name="kw-fw", os="linux", arch="x86_64", metadata_json={}, created_by=admin.id)
        db.add(framework)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            get_accessible_project(db, framework.id, admin)
        assert exc.value.status_code == 404


class TestCommitOrConflict:
    def test_commit_success(self, db):
        item = Environment(name="ok-env", host="127.0.0.1", framework_id=1)
        db.add(item)
        with commit_or_conflict(db, "环境名称已存在"):
            pass
        assert db.get(Environment, item.id) is not None

    def test_integrity_error_maps_to_409(self, db):
        db.add(Environment(name="dup-env", host="h1", framework_id=1))
        db.commit()
        db.add(Environment(name="dup-env", host="h2", framework_id=1))
        with pytest.raises(HTTPException) as exc:
            with commit_or_conflict(db, "环境名称已存在"):
                pass
        assert exc.value.status_code == 409
        assert exc.value.detail == "环境名称已存在"


class TestEnsureNoTasks:
    def test_no_task_no_raise(self, db):
        ensure_no_tasks(db, resource_id=1, detail="占用")
        ensure_no_tasks(db, environment_id=1, detail="占用")

    def test_resource_task_raises_409(self, db):
        db.add(Task(project_id=1, environment_id=1, framework_id=1, framework_sha256="s" * 64, status="queued", config_content="[run]", created_by=1))
        db.commit()
        with pytest.raises(HTTPException) as exc:
            ensure_no_tasks(db, resource_id=1, detail="测试项目已有任务记录，不能删除")
        assert exc.value.status_code == 409

    def test_environment_task_raises_409(self, db):
        db.add(Task(project_id=1, environment_id=7, framework_id=1, framework_sha256="s" * 64, status="queued", config_content="[run]", created_by=1))
        db.commit()
        with pytest.raises(HTTPException) as exc:
            ensure_no_tasks(db, environment_id=7, detail="环境已有任务记录，请停用环境")
        assert exc.value.status_code == 409


class TestModelToDict:
    def test_excludes_sensitive_keys(self):
        task = Task(project_id=1, environment_id=1, framework_id=1, framework_sha256="s" * 64, status="queued", config_content="[run]\na=1\n")
        env = Environment(name="exec-1", host="h", framework_id=1, ssh_password_enc="secret-hash", tags=None)
        assert "config_content" not in task_to_dict(task)
        assert "ssh_password_enc" not in environment_to_dict(env)

    def test_task_to_dict_key_set_matches_manual(self):
        task = Task(project_id=1, environment_id=1, framework_id=1, framework_sha256="s" * 64, status="queued", config_content="[run]\na=1\n")
        project = Resource(resource_type="project", name="登录自动化", metadata_json={})
        env = Environment(name="exec-1", host="h", framework_id=1)
        framework = Resource(resource_type="framework", name="kw-fw", os="linux", arch="x86_64", metadata_json={})
        result = task_to_dict(task, project, env, framework)
        expected = {
            "id", "project_id", "environment_id", "framework_id", "framework_sha256",
            "status", "testcase_scope", "selected_case_paths", "timeout_seconds",
            "cancel_requested", "exit_code", "error_message", "created_by",
            "created_at", "started_at", "finished_at",
            "project_name", "environment_name", "framework_name", "created_by_name",
        }
        assert set(result.keys()) == expected
        assert result["project_name"] == "登录自动化"
        assert result["environment_name"] == "exec-1"
        assert result["framework_name"] == "kw-fw"

    def test_environment_to_dict_key_set_matches_manual(self):
        env = Environment(name="exec-1", host="h", framework_id=1, ssh_password_enc="secret", tags=None)
        framework = Resource(resource_type="framework", name="kw-fw", os="linux", arch="x86_64", metadata_json={})
        owner = User(username="admin", password_hash="x", role="admin")
        result = environment_to_dict(env, framework, owner)
        expected = {
            "id", "name", "host", "ssh_port", "ssh_username", "os", "arch", "agent_home",
            "agent_package_id", "agent_status", "agent_sha256",
            "framework_id", "framework_status", "framework_sha256",
            "max_workers", "running_tasks", "last_seen", "enabled", "updated_at",
            "owner_id", "owner_name", "group_name", "tags",
            "framework_name", "framework_os", "framework_arch",
        }
        assert set(result.keys()) == expected
        assert result["owner_name"] == "admin"
        assert result["tags"] == []

    def test_model_to_dict_defaults_and_extra(self):
        env = Environment(name="e", host="h", framework_id=1, tags=None)
        result = model_to_dict(env, extra={"framework_name": "kw-fw"}, defaults={"tags": []})
        assert result["tags"] == []
        assert result["framework_name"] == "kw-fw"

    def test_model_to_dict_extra_overrides_column(self):
        env = Environment(name="old-name", host="h", framework_id=1)
        result = model_to_dict(env, extra={"name": "overridden"})
        assert result["name"] == "overridden"

    def test_framework_out_key_set_and_used_by_count(self, db):
        framework = Resource(resource_type="framework", name="kw-fw", os="linux", arch="x86_64", metadata_json={}, created_by=1)
        db.add(framework)
        db.flush()
        db.add(Environment(name="exec", host="h", framework_id=framework.id))
        db.commit()
        result = framework_out(db, framework)
        expected = {
            "id", "resource_type", "name", "os", "arch", "metadata_json",
            "enabled", "created_by", "created_at", "updated_at", "used_by_count",
        }
        assert set(result.keys()) == expected
        assert result["used_by_count"] == 1


class TestRemoveResourceFiles:
    def test_removes_records_and_calls_storage(self, db, monkeypatch):
        resource = Resource(resource_type="project", name="p", metadata_json={}, created_by=1)
        db.add(resource)
        db.flush()
        db.add(ResourceFile(resource_id=resource.id, relative_path="a.yaml", object_key="p/a.yaml", sha256="a" * 64, size=1, updated_by=1))
        db.commit()

        removed: list[tuple[str, str]] = []

        class FakeStorage:
            def remove(self, bucket: str, key: str) -> None:
                removed.append((bucket, key))

        monkeypatch.setattr("app.shared.resources.common.storage", FakeStorage())
        remove_resource_files(db, "test-projects", resource.id)
        db.commit()

        assert removed == [("test-projects", "p/a.yaml")]
        assert db.scalars(select(ResourceFile).where(ResourceFile.resource_id == resource.id)).all() == []

    def test_does_not_commit(self, monkeypatch):
        """函数只清理对象与删记录，把 commit 留给端点统一提交。"""

        class _Result:
            def all(self):
                return []

        class SpyDB:
            def __init__(self):
                self.committed = False
                self.deleted = False

            def scalars(self, *_args, **_kwargs):
                return _Result()

            def execute(self, *_args, **_kwargs):
                self.deleted = True
                return None

            def commit(self):
                self.committed = True

        class FakeStorage:
            def remove(self, bucket: str, key: str) -> None:
                pass

        monkeypatch.setattr("app.shared.resources.common.storage", FakeStorage())
        spy = SpyDB()
        remove_resource_files(spy, "test-projects", 1)

        assert spy.deleted is True
        assert spy.committed is False
