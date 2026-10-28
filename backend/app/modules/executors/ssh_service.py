"""SSH/SFTP 远程操作服务：连接测试、OS 探测、文件上传与进程管理。

本模块不 import fastapi、不抛 HTTPException；连接失败统一抛 SSHError，
由端点层决定如何呈现。
"""

import io
import time

import paramiko

from app.platform.security.crypto import decrypt_secret

SSH_CONNECT_TIMEOUT = 10
COMMAND_TIMEOUT = 120

ARCH_ALIASES = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64", "arm64": "arm64", "x86_64": "x86_64"}


class SSHError(Exception):
    """SSH 连接或远程命令执行失败。"""


class RemoteSession:
    """单次 SSH 会话：命令执行 + SFTP 上传。"""

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self._client: paramiko.SSHClient | None = None

    def __enter__(self) -> "RemoteSession":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def connect(self) -> None:
        """建立 SSH 连接，失败抛 SSHError。"""

        if self._client is not None:
            return
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=SSH_CONNECT_TIMEOUT,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:
            client.close()
            raise SSHError(f"SSH 连接失败 {self.host}:{self.port}（{exc}）") from exc
        self._client = client

    def close(self) -> None:
        """关闭 SSH 连接。"""

        if self._client is not None:
            self._client.close()
            self._client = None

    def run(self, command: str, timeout: int = COMMAND_TIMEOUT) -> tuple[int, str]:
        """执行远程命令，返回 (退出码, 合并输出)。"""

        if self._client is None:
            raise SSHError("SSH 会话未建立")
        try:
            _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = (stdout.read() + stderr.read()).decode("utf-8", "replace").strip()
            return exit_code, output
        except Exception as exc:
            raise SSHError(f"远程命令执行失败：[{type(exc).__name__}] {exc}") from exc

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        """通过 SFTP 把字节内容写入远程文件。"""

        if self._client is None:
            raise SSHError("SSH 会话未建立")
        try:
            sftp = self._client.open_sftp()
            try:
                with sftp.open(remote_path, "wb") as remote_file:
                    remote_file.write(io.BytesIO(data).read())
            finally:
                sftp.close()
        except Exception as exc:
            raise SSHError(f"SFTP 上传失败 {remote_path}（{exc}）") from exc


def normalize_arch(raw: str | None) -> str | None:
    """归一化架构标识（AMD64/x64 → x86_64，aarch64 → arm64）。"""

    if not raw:
        return None
    return ARCH_ALIASES.get(raw.strip().lower())


def probe_remote_os(session: RemoteSession) -> tuple[str, str]:
    """探测远程主机 OS 与架构：Linux 用 uname，Windows 回退 PowerShell。

    返回 (os, arch)，os 为 "linux" / "windows"；失败抛 SSHError。
    """

    code, output = session.run("uname -s && uname -m", timeout=15)
    if code == 0 and output:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) >= 2:
            kernel = lines[0].lower()
            if "linux" in kernel:
                arch = normalize_arch(lines[1])
                if arch:
                    return "linux", arch
    code, output = session.run(
        'powershell -NoProfile -Command "[int][System.Environment]::OSVersion.Platform; $env:PROCESSOR_ARCHITECTURE"',
        timeout=30,
    )
    if code == 0 and output:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines and lines[0] in {"2", "Win32NT"}:
            arch = normalize_arch(lines[1] if len(lines) > 1 else "AMD64")
            return "windows", arch or "x86_64"
    raise SSHError("无法识别远程主机操作系统（既不是 Linux 也不是 Windows）")


def test_ssh_connection(host: str, port: int, username: str, password: str) -> dict:
    """测试 SSH 连接并探测 OS/架构，返回结构化结果（不抛异常）。"""

    try:
        with RemoteSession(host, port, username, password) as session:
            os_name, arch = probe_remote_os(session)
            return {"ok": True, "os": os_name, "arch": arch, "message": f"连接成功：{os_name}/{arch}"}
    except SSHError as exc:
        return {"ok": False, "os": None, "arch": None, "message": str(exc)}


def environment_session(environment) -> RemoteSession:
    """用执行器保存的 SSH 凭据建立会话。"""

    password = decrypt_secret(environment.ssh_password_enc)
    if not environment.ssh_username or not password:
        raise SSHError("执行器未配置完整的 SSH 凭据，请先编辑执行器填写 SSH 用户名和密码")
    return RemoteSession(environment.host, environment.ssh_port or 22, environment.ssh_username, password)
