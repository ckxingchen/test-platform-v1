from types import SimpleNamespace

from app.modules.executors import deployment_service


class FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True

    def refresh(self, _item):
        return None


class FakeRedis:
    def __init__(self):
        self.messages = []

    def xadd(self, key, fields, **kwargs):
        self.messages.append((key, fields, kwargs))

    def expire(self, *_args):
        return True


def test_same_framework_and_sha_can_be_redeployed(monkeypatch):
    """重新部署是显式操作，不应因执行器已有相同版本而拒绝。"""

    environment = SimpleNamespace(
        id=3,
        enabled=True,
        agent_status="online",
        framework_status="deployed",
        framework_id=7,
        framework_sha256="a" * 64,
        os="linux",
        arch="x86_64",
    )
    framework = SimpleNamespace(id=7, os="linux", arch="x86_64")
    framework_file = SimpleNamespace(sha256="a" * 64)
    redis = FakeRedis()
    db = FakeDb()

    monkeypatch.setattr(deployment_service, "count_active_tasks", lambda *_args: 0)
    monkeypatch.setattr(
        deployment_service,
        "get_enabled_framework_with_file",
        lambda *_args: (framework, framework_file),
    )
    monkeypatch.setattr(deployment_service, "get_redis", lambda: redis)

    deployment = deployment_service.deploy_framework(db, environment, framework.id, user_id=1)

    assert deployment.framework_sha256 == framework_file.sha256
    assert db.added == [deployment]
    assert db.committed is True
    assert environment.framework_status == "pending"
    assert redis.messages[0][1]["message"] == "框架部署请求已下发，等待 Agent 拉取"
