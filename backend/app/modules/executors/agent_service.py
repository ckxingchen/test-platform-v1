"""Agent 远程部署编排：SFTP 上传 + 解压 + 配置生成 + 启动 + 心跳等待。

部署目标目录结构（保留 config/data/logs，只替换 bin/）：
    {agent_home}/bin/kw-agent(.exe)
    {agent_home}/config/config.yaml
    {agent_home}/logs/
    {agent_home}/data/{frameworks,tasks,temp}
"""

import time

from app.platform.config.settings import settings
from app.platform.storage.minio import storage
from app.modules.objects.agent_packages.facade import get_agent_package, get_agent_package_by_platform
from app.platform.db.base import utcnow
from app.shared.errors import ServiceError
from app.modules.executors.ssh_service import RemoteSession, SSHError, environment_session
from sqlalchemy.orm import Session


def _config_yaml(environment, platform_url: str) -> str:
    """生成 Agent 运行配置文件内容。"""

    return (
        f"platform:\n"
        f"  url: {platform_url}\n"
        f"agent:\n"
        f"  executor_id: {environment.id}\n"
        f"  name: {environment.name}\n"
        f"  work_dir: {environment.agent_home}/data\n"
        f"  max_workers: {environment.max_workers or 1}\n"
        f"  heartbeat_interval: 10\n"
        f"  task_poll_interval: 1\n"
        f"  default_timeout: 3600\n"
        f"log:\n"
        f"  level: INFO\n"
        f"  file: {environment.agent_home}/logs/agent.log\n"
    )


def _normalize_windows_path(value: str) -> str:
    """把路径统一为 Windows 反斜杠形式。"""

    return value.replace("/", "\\")


def _remote_dirs(agent_home: str, os_name: str) -> list[str]:
    """生成需要确保存在的子目录（含数据目录）。"""

    home = agent_home if os_name == "linux" else _normalize_windows_path(agent_home)
    sep = "/" if os_name == "linux" else "\\"
    return [f"{home}{sep}bin", f"{home}{sep}config", f"{home}{sep}logs", f"{home}{sep}data{sep}frameworks", f"{home}{sep}data{sep}tasks", f"{home}{sep}data{sep}temp"]


def _stop_agent(session: RemoteSession, agent_home: str, os_name: str) -> None:
    """停止远程 Agent 进程（不存在时忽略）。

    匹配 bin/kw-agent（覆盖绝对路径与相对路径两种启动方式），避免残留导致重复进程。
    """

    if os_name == "linux":
        session.run("pkill -f 'bin/kw-agent' || true", timeout=15)
    else:
        home = _normalize_windows_path(agent_home)
        session.run(
            "powershell -NoProfile -Command \"Get-Process kw-agent -ErrorAction SilentlyContinue | Stop-Process -Force\"",
            timeout=30,
        )


def _start_agent(session: RemoteSession, agent_home: str, os_name: str) -> tuple[int, str]:
    """后台启动远程 Agent 进程。

    用 setsid 把进程彻底脱离 SSH 会话，并将外层 stdout/stderr 重定向到 /dev/null，
    避免 paramiko 因后台进程占用通道而在 recv_exit_status 上超时。
    Agent 自身日志仍写入 logs/agent.log。
    """

    if os_name == "linux":
        command = (
            f"cd '{agent_home}' && ( setsid ./bin/kw-agent >> logs/agent.log 2>&1 < /dev/null & ) ; echo started"
        )
        return session.run(command, timeout=30)
    home = _normalize_windows_path(agent_home)
    command = (
        f"powershell -NoProfile -Command \"Start-Process -FilePath '{home}\\bin\\kw-agent.exe' "
        f"-WorkingDirectory '{home}' -WindowStyle Hidden\""
    )
    return session.run(command, timeout=60)


def deploy_agent(db: Session, environment, user_id: int) -> dict:
    """通过 SSH/SFTP 部署（或重新部署）执行器上的 Agent。

    返回 {"success": bool, "steps": [...], "agent_status": ..., "agent_sha256": ...}。
    """

    steps: list[str] = []

    def log(message: str) -> None:
        steps.append(message)

    if not environment.enabled:
        raise ServiceError(422, "执行器已停用")
    if not environment.os or not environment.arch:
        raise ServiceError(422, "执行器尚未探测 OS/架构，请先测试 SSH 连接并保存探测结果")
    package = None
    if environment.agent_package_id:
        package = get_agent_package(db, environment.agent_package_id)
    if not package:
        package = get_agent_package_by_platform(db, environment.os, environment.arch)
    if not package:
        raise ServiceError(422, f"平台没有 {environment.os}/{environment.arch} 的 Agent 包，请先上传")
    if environment.running_tasks:
        raise ServiceError(409, "执行器存在运行中任务，暂不能重新部署 Agent")

    log(f"定位 Agent 包：{package.name} ({package.os}/{package.arch}) sha256={package.sha256[:12]}…")
    data = storage.get_bytes(settings.agent_bucket, package.object_key)
    log(f"从 MinIO 读取 Agent 包成功（{len(data) / 1024 / 1024:.1f} MB）")

    os_name = environment.os
    agent_home = environment.agent_home
    is_windows = os_name == "windows"
    home = agent_home if not is_windows else _normalize_windows_path(agent_home)
    sep = "\\" if is_windows else "/"
    temp_dir = f"{home}{sep}temp{sep}agent-deploy"
    archive_name = "agent-package" + (".zip" if package.object_key.endswith(".zip") else ".tar.gz")
    remote_archive = f"{temp_dir}{sep}{archive_name}"
    extract_dir = f"{temp_dir}{sep}extracted"

    try:
        with environment_session(environment) as session:
            log(f"SSH 连接成功 {environment.host}:{environment.ssh_port}")
            # 1. 准备目录
            if is_windows:
                dir_list = ";".join(f"'{d}'" for d in _remote_dirs(agent_home, os_name) + [temp_dir, extract_dir])
                code, output = session.run(
                    f"powershell -NoProfile -Command \"foreach ($d in @({dir_list})) {{ New-Item -ItemType Directory -Force -Path $d | Out-Null }}\"",
                    timeout=120,
                )
            else:
                code, output = session.run(f"mkdir -p {' '.join(_remote_dirs(agent_home, os_name))} '{temp_dir}' '{extract_dir}'", timeout=30)
            if code:
                raise ServiceError(422, f"创建远程目录失败：{output}")
            log("远程目录就绪（bin/config/logs/data）")

            # 2. 上传包
            session.upload_bytes(data, remote_archive)
            log(f"Agent 包已上传到 {remote_archive}")

            # 3. 解压到临时目录
            if is_windows:
                code, output = session.run(
                    f"powershell -NoProfile -Command \"Expand-Archive -Path '{remote_archive}' -DestinationPath '{extract_dir}' -Force\"",
                    timeout=600,
                )
            else:
                if archive_name.endswith(".zip"):
                    code, output = session.run(f"cd '{extract_dir}' && unzip -o -q '{remote_archive}'", timeout=600)
                    if code:
                        code, output = session.run(f"cd '{extract_dir}' && python3 -m zipfile -e '{remote_archive}' . || tar -xf '{remote_archive}'", timeout=600)
                else:
                    code, output = session.run(f"cd '{extract_dir}' && tar -xzf '{remote_archive}'", timeout=600)
            if code:
                raise ServiceError(422, f"解压 Agent 包失败：{output}")
            log("Agent 包解压完成")

            # 4. 校验入口文件
            entry = "bin\\kw-agent.exe" if is_windows else "bin/kw-agent"
            if is_windows:
                code, output = session.run(f"powershell -NoProfile -Command \"Test-Path '{extract_dir}\\{entry}'\"", timeout=30)
                entry_ok = code == 0 and output.strip().lower() == "true"
            else:
                code, output = session.run(f"test -f '{extract_dir}/bin/kw-agent' && echo ok", timeout=30)
                entry_ok = code == 0 and "ok" in output
            if not entry_ok:
                raise ServiceError(422, f"解压后未找到入口文件 {entry}，请检查 Agent 包结构")
            log("入口文件校验通过")

            # 5. 停止旧 Agent
            _stop_agent(session, agent_home, os_name)
            log("旧 Agent 进程已停止（如存在）")

            # 6. 替换 bin/（保留 config/data/logs）
            if is_windows:
                code, output = session.run(
                    f"powershell -NoProfile -Command \"if (Test-Path '{home}\\bin') {{ Remove-Item -Recurse -Force '{home}\\bin' }}; Move-Item -Path '{extract_dir}\\bin' -Destination '{home}\\bin'",
                    timeout=300,
                )
            else:
                code, output = session.run(f"rm -rf '{home}/bin' && mv '{extract_dir}/bin' '{home}/bin'", timeout=300)
            if code:
                raise ServiceError(422, f"替换 bin/ 目录失败：{output}")
            log("bin/ 目录已替换（config/data/logs 保留）")

            # 7. 写配置文件
            config_content = _config_yaml(environment, settings.agent_public_url.rstrip("/"))
            config_path = f"{home}{sep}config{sep}config.yaml"
            session.upload_bytes(config_content.encode("utf-8"), config_path)
            log(f"配置文件已生成 {config_path}")

            # 8. 可执行权限（Linux）
            if not is_windows:
                session.run(f"chmod +x '{home}/bin/kw-agent'", timeout=30)

            # 9. 清理临时目录
            if is_windows:
                session.run(f"powershell -NoProfile -Command \"Remove-Item -Recurse -Force '{temp_dir}' -ErrorAction SilentlyContinue\"", timeout=120)
            else:
                session.run(f"rm -rf '{temp_dir}'", timeout=120)

            # 10. 启动 Agent
            environment.agent_status = "deploying"
            db.commit()
            code, output = _start_agent(session, agent_home, os_name)
            if code:
                environment.agent_status = "pending"
                db.commit()
                raise ServiceError(422, f"启动 Agent 失败：{output}")
            log("Agent 启动命令已执行，等待心跳上线…")
    except SSHError as exc:
        environment.agent_status = "pending"
        db.commit()
        raise ServiceError(422, str(exc))

    # 11. 等待心跳
    deadline = time.time() + settings.agent_deploy_wait_seconds
    online = False
    while time.time() < deadline:
        db.rollback()
        db.refresh(environment)
        if environment.agent_status == "online" and environment.last_seen and (utcnow() - environment.last_seen).total_seconds() < settings.agent_offline_after_seconds:
            online = True
            break
        time.sleep(3)
    if online:
        environment.agent_sha256 = package.sha256
        environment.agent_package_id = package.id
        environment.agent_status = "online"
        log(f"Agent 已上线（executor_id={environment.id}）")
    else:
        environment.agent_status = "offline"
        log(f"等待 {settings.agent_deploy_wait_seconds}s 未见心跳，请检查远程日志 {agent_home}/logs/agent.log")
    db.commit()
    return {
        "success": online,
        "steps": steps,
        "agent_status": environment.agent_status,
        "agent_sha256": package.sha256 if online else environment.agent_sha256,
    }


def start_agent(db: Session, environment) -> dict:
    """启动已部署的远程 Agent。"""

    if not environment.agent_package_id and not environment.agent_sha256:
        raise ServiceError(422, "Agent 尚未部署，请先执行部署")
    try:
        with environment_session(environment) as session:
            code, output = _start_agent(session, environment.agent_home, environment.os or "linux")
            if code:
                raise ServiceError(422, f"启动 Agent 失败：{output}")
    except SSHError as exc:
        raise ServiceError(422, str(exc))
    return {"message": "Agent 启动命令已执行"}


def stop_agent(db: Session, environment) -> dict:
    """停止远程 Agent 进程。"""

    if environment.running_tasks:
        raise ServiceError(409, "执行器存在运行中任务，暂不能停止 Agent")
    try:
        with environment_session(environment) as session:
            _stop_agent(session, environment.agent_home, environment.os or "linux")
    except SSHError as exc:
        raise ServiceError(422, str(exc))
    environment.agent_status = "offline"
    db.commit()
    return {"message": "Agent 已停止"}
