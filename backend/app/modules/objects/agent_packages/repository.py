"""Agent 包基础数据库查询。"""

from app.modules.executors.models import Environment
from app.modules.objects.agent_packages.models import AgentPackage
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def get_agent_package(db: Session, package_id: int) -> AgentPackage | None:
    """按编号读取 Agent 包。"""

    return db.get(AgentPackage, package_id)


def get_agent_package_by_platform(db: Session, os_name: str, arch: str) -> AgentPackage | None:
    """按 (os, arch) 返回最新启用的 Agent 包。"""

    return db.scalars(
        select(AgentPackage)
        .where(AgentPackage.os == os_name, AgentPackage.arch == arch, AgentPackage.enabled.is_(True))
        .order_by(AgentPackage.updated_at.desc(), AgentPackage.id.desc())
        .limit(1)
    ).first()


def list_agent_packages(db: Session) -> list[AgentPackage]:
    """按更新时间倒序返回全部 Agent 包。"""

    return db.scalars(select(AgentPackage).order_by(AgentPackage.updated_at.desc(), AgentPackage.id.desc())).all()


def count_environments_by_agent_package(db: Session, package_id: int) -> int:
    """统计引用指定 Agent 包的执行器数量。"""

    return db.scalar(select(func.count(Environment.id)).where(Environment.agent_package_id == package_id)) or 0
