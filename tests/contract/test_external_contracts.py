"""重构期间不得变化的外部契约基线。"""

import re
from pathlib import Path

import app.model_registry  # noqa: F401 - 注册所有 ORM 模型
from app.main import app
from app.platform.db.base import Base


EXPECTED_API_OPERATIONS = {
    ("/api/v1/agent/tasks/{task_id}/artifacts", "post"),
    ("/api/v1/agent/tasks/{task_id}/logs", "post"),
    ("/api/v1/agent/tasks/{task_id}/project", "get"),
    ("/api/v1/agent/tasks/{task_id}/results", "post"),
    ("/api/v1/agent/tasks/{task_id}/status", "put"),
    ("/api/v1/agent/{executor_id}/actions", "get"),
    ("/api/v1/agent/{executor_id}/framework", "get"),
    ("/api/v1/agent/{executor_id}/framework/status", "post"),
    ("/api/v1/agent/{executor_id}/heartbeat", "post"),
    ("/api/v1/agent/{executor_id}/tasks", "get"),
    ("/api/v1/auth/change-password", "post"),
    ("/api/v1/auth/login", "post"),
    ("/api/v1/auth/me", "get"),
    ("/api/v1/environments", "get"),
    ("/api/v1/environments", "post"),
    ("/api/v1/environments/test-connection", "post"),
    ("/api/v1/environments/{environment_id}", "delete"),
    ("/api/v1/environments/{environment_id}", "get"),
    ("/api/v1/environments/{environment_id}", "put"),
    ("/api/v1/environments/{environment_id}/deploy", "post"),
    ("/api/v1/environments/{environment_id}/deploy-agent", "post"),
    ("/api/v1/environments/{environment_id}/deployments", "get"),
    ("/api/v1/environments/{environment_id}/deployments/{deployment_id}/logs", "get"),
    ("/api/v1/environments/{environment_id}/overview", "get"),
    ("/api/v1/environments/{environment_id}/start-agent", "post"),
    ("/api/v1/environments/{environment_id}/stop-agent", "post"),
    ("/api/v1/objects/agents", "get"),
    ("/api/v1/objects/agents", "post"),
    ("/api/v1/objects/agents/{package_id}", "delete"),
    ("/api/v1/objects/agents/{package_id}", "get"),
    ("/api/v1/objects/agents/{package_id}/download", "get"),
    ("/api/v1/objects/frameworks", "get"),
    ("/api/v1/objects/frameworks", "post"),
    ("/api/v1/objects/frameworks/{framework_id}", "delete"),
    ("/api/v1/objects/frameworks/{framework_id}", "get"),
    ("/api/v1/objects/frameworks/{framework_id}/download", "get"),
    ("/api/v1/objects/frameworks/{framework_id}/environments", "get"),
    ("/api/v1/objects/projects", "get"),
    ("/api/v1/objects/projects", "post"),
    ("/api/v1/objects/projects/{project_id}", "delete"),
    ("/api/v1/objects/projects/{project_id}", "get"),
    ("/api/v1/objects/projects/{project_id}/files", "get"),
    ("/api/v1/objects/projects/{project_id}/files/archive", "post"),
    ("/api/v1/objects/projects/{project_id}/files/batch", "post"),
    ("/api/v1/objects/projects/{project_id}/files/{file_id}", "delete"),
    ("/api/v1/objects/projects/{project_id}/files/{file_id}", "put"),
    ("/api/v1/objects/projects/{project_id}/files/{file_id}/download", "get"),
    ("/api/v1/objects/projects/{project_id}/members", "get"),
    ("/api/v1/objects/projects/{project_id}/members", "put"),
    ("/api/v1/objects/projects/{project_id}/tasks", "get"),
    ("/api/v1/tasks", "get"),
    ("/api/v1/tasks", "post"),
    ("/api/v1/tasks/{task_id}", "get"),
    ("/api/v1/tasks/{task_id}/artifacts", "get"),
    ("/api/v1/tasks/{task_id}/artifacts/{artifact_id}/download", "get"),
    ("/api/v1/tasks/{task_id}/cancel", "post"),
    ("/api/v1/tasks/{task_id}/logs", "get"),
    ("/api/v1/tasks/{task_id}/rerun", "post"),
    ("/api/v1/tasks/{task_id}/results", "get"),
    ("/api/v1/users", "get"),
    ("/api/v1/users", "post"),
    ("/api/v1/users/{user_id}", "put"),
    ("/health", "get"),
}

EXPECTED_TABLE_COLUMNS = {
    "agent_commands": ["id", "environment_id", "command_type", "payload", "status", "priority", "lease_id", "lease_expires_at", "delivery_count", "task_id", "deployment_id", "error_message", "created_at", "started_at", "finished_at"],
    "agent_deployments": ["id", "environment_id", "framework_sha256", "status", "error_message", "created_by", "created_at", "started_at", "finished_at"],
    "agent_environments": ["id", "name", "host", "ssh_port", "ssh_username", "ssh_password_enc", "os", "arch", "agent_home", "agent_package_id", "agent_status", "agent_sha256", "framework_id", "framework_status", "framework_sha256", "max_workers", "running_tasks", "last_seen", "owner_id", "group_name", "tags", "enabled", "updated_at"],
    "agent_packages": ["id", "name", "os", "arch", "file_name", "object_key", "sha256", "size", "enabled", "created_at", "updated_at"],
    "agent_task_artifacts": ["id", "task_id", "artifact_type", "object_key", "size"],
    "agent_task_files": ["task_id", "relative_path", "object_key", "object_version_id", "sha256"],
    "agent_task_results": ["id", "task_id", "case_path", "case_name", "status", "error_message"],
    "agent_tasks": ["id", "project_id", "environment_id", "framework_id", "framework_sha256", "status", "testcase_scope", "selected_case_paths", "config_content", "timeout_seconds", "cancel_requested", "exit_code", "error_message", "created_by", "created_at", "started_at", "finished_at"],
    "object_resource_files": ["id", "resource_id", "relative_path", "object_key", "object_version_id", "sha256", "size", "updated_by", "updated_at"],
    "object_resource_members": ["resource_id", "user_id", "role"],
    "object_resources": ["id", "resource_type", "name", "os", "arch", "metadata_json", "enabled", "created_by", "created_at", "updated_at"],
    "users": ["id", "username", "password_hash", "role", "enabled", "created_at"],
}

EXPECTED_FRONTEND_PATHS = {
    "/login", "/", "", "users", "objects", "objects/agents",
    "objects/frameworks", "objects/projects", "objects/projects/:id",
    "executors", "executors/:id", "tasks", "tasks/create", "tasks/:id",
    "resources", "resources/agents", "resources/frameworks", "resources/projects",
    "resources/projects/:id", "environments", "environments/executors",
    "environments/executors/:id", "execution", "execution/executors",
    "execution/executors/:id", "execution/tasks", "execution/tasks/create",
    "execution/tasks/:id",
}


def test_openapi_operation_contract_is_unchanged():
    schema = app.openapi()
    operations = {
        (path, method)
        for path, methods in schema["paths"].items()
        for method in methods
        if method != "parameters"
    }
    assert operations == EXPECTED_API_OPERATIONS


def test_database_table_and_column_contract_is_unchanged():
    actual = {
        table.name: [column.name for column in table.columns]
        for table in Base.metadata.tables.values()
    }
    assert actual == EXPECTED_TABLE_COLUMNS


def test_frontend_route_path_contract_is_unchanged():
    source_root = Path(__file__).parents[2] / "frontend" / "src"
    route_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.rglob("*.js")
        if path.name == "router.js" or "routes" in path.stem
    )
    actual = set(re.findall(r"\bpath:\s*['\"]([^'\"]*)['\"]", route_sources))
    assert actual == EXPECTED_FRONTEND_PATHS
