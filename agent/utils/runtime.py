"""通用工具：OS/架构探测、归档解压、Hard Link 克隆与进程管理。"""

import os
import platform
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

ARCH_ALIASES = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64", "arm64": "arm64", "x86_64": "x86_64"}


def current_os() -> str:
    """返回规范化 OS 标识（linux / windows）。"""

    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    return "linux" if system.startswith("linux") else system


def current_arch() -> str:
    """返回规范化 CPU 架构。"""

    machine = platform.machine().lower()
    return ARCH_ALIASES.get(machine, machine)


def hostname() -> str:
    """返回主机名。"""

    return platform.node() or "unknown"


def extract_archive(archive: Path, target: Path) -> None:
    """安全解压 ZIP / TAR 归档到目标目录（拒绝路径穿越与链接成员）。"""

    target.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                name = item.filename.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts or ":" in name:
                    raise ValueError(f"压缩包包含不安全路径：{item.filename}")
                if item.is_dir():
                    continue
                destination = target.joinpath(*Path(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.read(item))
        return
    with tarfile.open(archive, mode="r:*") as bundle:
        for item in bundle.getmembers():
            if item.issym() or item.islnk() or item.isdev():
                continue
            if not item.isfile():
                continue
            name = item.name.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts or ":" in name:
                raise ValueError(f"压缩包包含不安全路径：{item.name}")
            destination = target.joinpath(*Path(name).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(item) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)


def clone_tree(source: Path, target: Path, skip_names: set[str] | None = None) -> int:
    """目录克隆：优先 Hard Link（共享文件数据），失败回退复制。

    skip_names 指定源目录下需要跳过的顶层子目录（如 testsuits，任务运行时必须独立）。
    返回克隆的文件数。
    """

    skip_names = skip_names or set()
    count = 0
    for item in source.iterdir():
        if item.name in skip_names:
            continue
        destination = target / item.name
        if item.is_dir():
            count += clone_tree(item, destination)
        elif item.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                destination.hardlink_to(item)
            except OSError:
                shutil.copy2(item, destination)
            count += 1
    return count


def remove_tree(target: Path) -> None:
    """递归删除目录（容错）。"""

    shutil.rmtree(target, ignore_errors=True)


class ProcessRunner:
    """跨平台子进程执行：流式读取输出、超时与取消。"""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        """进程是否仍在运行。"""

        return self._process is not None and self._process.poll() is None

    def start(self, command: list[str], cwd: Path) -> None:
        """启动子进程。"""

        environment = os.environ.copy()
        # stdout 接入管道后 Python 默认会块缓冲，强制无缓冲以便实时采集。
        environment.setdefault("PYTHONUNBUFFERED", "1")
        self._process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=environment,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if current_os() == "windows" else 0,
        )

    def stream(self, on_line) -> int:
        """逐行读取输出直到进程结束，返回退出码。"""

        assert self._process is not None
        for line in self._process.stdout:
            on_line(line.rstrip())
        return self._process.wait()

    def iter_lines(self):
        """逐行产出进程输出（生成器），调用方负责消费完毕后调用 wait。"""

        assert self._process is not None
        for line in self._process.stdout:
            yield line

    def wait(self, timeout: float) -> int:
        """等待进程结束（超时抛 TimeoutError）。"""

        assert self._process is not None
        try:
            return self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("任务执行超时") from exc

    def kill(self) -> None:
        """强制终止进程树。"""

        if self._process is None:
            return
        if current_os() == "windows":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                capture_output=True,
            )
        else:
            try:
                self._process.terminate()
            except OSError:
                pass
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
