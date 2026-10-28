"""框架部署服务：下载 → 校验 → 解压 → 原子切换 → 上报。"""

import hashlib
import logging
from pathlib import Path

from agent.client.platform_client import PlatformClient
from agent.service.task_runner import safe_project_name
from agent.utils.runtime import current_os, extract_archive, remove_tree

logger = logging.getLogger("kw-agent.deploy")

# 可执行二进制的 magic bytes（用于识别打包时丢失 +x 的内嵌二进制）
_EXEC_MAGICS = (
    b"\x7fELF",        # Linux / 通用 ELF
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit (little endian, macOS)
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit (big endian)
    b"\xca\xfe\xba\xbe",  # Mach-O universal (fat)
)


def _make_executable(path: Path) -> None:
    """若文件当前不可执行，补上 +x（保留其它位）。"""

    try:
        mode = path.stat().st_mode
        if not (mode & 0o111):
            path.chmod(mode | 0o755)
    except OSError:
        logger.warning("无法为 %s 设置执行权限：%s", path, exc_info=True)


def _fix_tree_executable(root: Path, runner_path: str) -> None:
    """打包/解压过程常丢失内嵌二进制的执行权限（尤其 Playwright 的 node 驱动、
    chromium 等），导致任务执行时 Permission denied。这里扫描 staged 目录，对执行
    入口与所有 ELF/Mach-O 二进制补上 +x，保证 clone 后任务能正常拉起浏览器。"""

    # 1. 执行入口本身
    runner = root.joinpath(*Path(runner_path.replace("\\", "/")).parts)
    if runner.is_file():
        _make_executable(runner)

    # 2. 扫描所有文件，按 magic bytes 识别可执行二进制（仅 Unix 系需要）
    if current_os() == "windows":
        return
    fixed = 0
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        try:
            with entry.open("rb") as fh:
                head = fh.read(4)
        except OSError:
            continue
        if head in _EXEC_MAGICS:
            _make_executable(entry)
            fixed += 1
    if fixed:
        logger.info("已为 %s 下 %d 个内嵌二进制补上执行权限", root, fixed)


class DeploymentService:
    """执行平台下发的框架部署（首次部署与重新部署同一路径）。"""

    def __init__(self, config, client: PlatformClient) -> None:
        self.config = config
        self.client = client

    def deploy(self, action: dict) -> None:
        """按部署指令完成框架下载、校验、原子切换和状态上报。"""

        deployment_id = int(action["deployment_id"])
        framework = action.get("framework") or {}
        framework_name = safe_project_name(framework.get("name") or "test-framework")
        expected_sha = str(framework.get("sha256") or "")
        runner_path = str(framework.get("runner_path") or "").strip()
        archive_root = str(framework.get("archive_root") or "").strip("/")
        try:
            self._deploy_internal(framework_name, expected_sha, runner_path, archive_root)
            self.client.report_framework_status(deployment_id, "deployed", sha256=expected_sha)
            logger.info("框架 %s 部署成功 sha=%s", framework_name, expected_sha[:12])
        except Exception as exc:  # noqa: BLE001
            logger.exception("框架 %s 部署失败", framework_name)
            self.client.report_framework_status(deployment_id, "failed", error_message=f"{type(exc).__name__}: {exc}")

    def _deploy_internal(self, framework_name: str, expected_sha: str, runner_path: str, archive_root: str) -> None:
        if not runner_path:
            raise RuntimeError("框架缺少 runner_path 元数据")

        # 1. 下载并校验 SHA256
        archive = self.config.temp_dir / f"framework-{framework_name}.archive"
        data = self.client.download_framework(archive)
        actual_sha = hashlib.sha256(data).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            archive.unlink(missing_ok=True)
            raise RuntimeError(f"框架 SHA256 校验失败（期望 {expected_sha[:12]}…，实际 {actual_sha[:12]}…）")

        # 2. 解压到临时目录
        staged = self.config.temp_dir / f"framework-{framework_name}.new"
        remove_tree(staged)
        extract_archive(archive, staged)
        archive.unlink(missing_ok=True)

        # 2.1 若归档被 archive_root 包裹，把 archive_root 内文件提升到 staged 顶层
        #     这样部署结果就是 frameworks_dir/<name>/{driver,plugins,...}，与 task_runner
        #     期望（clone_tree 后直接找 <name>/<runner_path>）一致。缺失时忽略（兼容
        #     archive_root 留空或归档结构不严格匹配的场景，仅记录警告）。
        if archive_root:
            inner = staged / archive_root
            if inner.is_dir():
                promote = staged.with_name(staged.name + ".promote")
                remove_tree(promote)
                promote.mkdir()
                for entry in inner.iterdir():
                    entry.rename(promote / entry.name)
                remove_tree(staged)
                promote.rename(staged)
                logger.info("已把 archive_root=%s 提升到 %s 顶层", archive_root, staged)
            else:
                logger.warning("归档内未找到 archive_root=%s，按平铺结构继续部署", archive_root)

        # 2.2 修复打包/解压过程中可能丢失的内嵌二进制执行权限（Playwright node 等）
        _fix_tree_executable(staged, runner_path)

        # 3. 校验执行程序存在（Windows 入口为 .exe，Linux 可执行文件）
        runner = staged.joinpath(*Path(runner_path.replace("\\", "/")).parts)
        if not runner.is_file():
            remove_tree(staged)
            raise RuntimeError(f"框架包缺少执行程序：{runner_path}")
        if current_os() == "linux":
            runner.chmod(0o755)

        # 4. 原子切换：旧目录 → .old，新目录 → 正式名，删除旧目录
        target = self.config.frameworks_dir / framework_name
        backup = self.config.frameworks_dir / f"{framework_name}.old"
        remove_tree(backup)
        if target.exists():
            target.rename(backup)
        staged.rename(target)
        remove_tree(backup)
