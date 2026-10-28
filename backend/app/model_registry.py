"""Import every ORM model once so SQLAlchemy metadata is complete."""

from app.modules.executors.command_models import AgentCommand
from app.modules.executors.models import Deployment, Environment
from app.modules.objects.agent_packages.models import AgentPackage
from app.modules.tasks.models import Task, TaskArtifact, TaskFile, TaskResult
from app.modules.users.models import User
from app.shared.resources.models import Resource, ResourceFile, ResourceMember

__all__ = [
    "AgentCommand",
    "AgentPackage",
    "Deployment",
    "Environment",
    "Resource",
    "ResourceFile",
    "ResourceMember",
    "Task",
    "TaskArtifact",
    "TaskFile",
    "TaskResult",
    "User",
]
