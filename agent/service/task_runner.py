"""单任务执行：Runtime 克隆 → 项目注入 → CLI 执行 → 结果上传 → 清理。"""

import json
import logging
import re
import time
import zipfile
from pathlib import Path

from agent.client.platform_client import PlatformClient
from agent.utils.runtime import ProcessRunner, clone_tree, current_os, extract_archive, remove_tree

logger = logging.getLogger("kw-agent.task")

# 框架运行时必须独立的顶层目录（多任务并发时不能共享）
RUNTIME_EXCLUSIVE_DIRS = {"testsuits"}
# 日志上传位于任务执行的关键路径。高输出任务若每 50 行请求一次，会被大量
# HTTP 往返显著拖慢；单次 500 行与平台接口上限保持一致。
LOG_FLUSH_LINES = 500
LOG_FLUSH_SECONDS = 0.25


def normalize_testcase_paths(testcase_path: str | None) -> str:
    """把平台用例路径转成框架期望的「testcase 根内相对路径，分号分隔」。"""

    if not testcase_path:
        return ""
    parts = [part.strip() for part in str(testcase_path).split(";") if part.strip()]
    normalized: list[str] = []
    for part in parts:
        stripped = part.replace("\\", "/").strip("/")
        if stripped.startswith("testcase/"):
            stripped = stripped[len("testcase/"):]
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return ";".join(normalized)


def safe_project_name(name: str) -> str:
    """归一化项目名，避免作为目录名出现非法字符。"""

    cleaned = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff.-]+", "_", str(name or "project"))
    return cleaned or "project"


class TaskRunner:
    """一个 TaskRunner 实例负责一个任务的完整生命周期。"""

    def __init__(self, config, client: PlatformClient, payload: dict) -> None:
        self.config = config
        self.client = client
        self.payload = payload
        self.task_id = int(payload["task_id"])
        self.project_name = safe_project_name(payload.get("project_name") or f"project-{self.task_id}")
        self.timeout = int(payload.get("timeout_seconds") or config.default_timeout)
        self.runner = ProcessRunner()
        self.canceled = False

    def run(self) -> None:
        """执行任务并保证最终状态上报（含异常兜底）。"""

        runtime_root = self.config.tasks_dir / str(self.task_id)
        framework_root = runtime_root / "test-framework"
        try:
            self._run_internal(runtime_root, framework_root)
        except TimeoutError:
            self._finish("timeout", error_message="测试任务执行超时")
        except Exception as exc:  # noqa: BLE001 兜底保证状态不悬挂
            logger.exception("任务 %s 执行异常", self.task_id)
            self._finish("failed", error_message=f"{type(exc).__name__}: {exc}")
        finally:
            remove_tree(runtime_root)

    def _run_internal(self, runtime_root: Path, framework_root: Path) -> None:
        framework = self.payload.get("framework") or {}
        framework_name = safe_project_name(framework.get("name") or "test-framework")
        source_root = self.config.frameworks_dir / framework_name
        if not source_root.is_dir():
            raise RuntimeError(f"框架尚未部署：{source_root} 不存在，请先部署框架")

        # 1. 克隆 Framework（Hard Link + copy 回退），testsuits 独立
        cloned = clone_tree(source_root, framework_root, skip_names=RUNTIME_EXCLUSIVE_DIRS)
        self.client.upload_task_logs(self.task_id, [f"Runtime 就绪：克隆框架文件 {cloned} 个（Hard Link 优先）"])

        # 2. 下载项目并注入 testsuits/<project_name>
        project_zip = self.config.temp_dir / f"task-{self.task_id}.zip"
        self.client.download_project(self.task_id, project_zip)
        project_root = framework_root / "testsuits" / self.project_name
        extract_archive(project_zip, project_root)
        project_zip.unlink(missing_ok=True)
        self.client.report_task_status(self.task_id, "running")
        self.client.upload_task_logs(self.task_id, [f"项目已注入 {project_root.relative_to(runtime_root)}"])

        # 3. 定位执行器并构造 CLI
        runner_path = str(framework.get("runner_path") or "").strip()
        if not runner_path:
            raise RuntimeError("框架缺少 runner_path 元数据")
        runner = framework_root.joinpath(*Path(runner_path.replace("\\", "/")).parts)
        if not runner.is_file():
            raise RuntimeError(f"框架执行程序不存在：{runner_path}")
        if current_os() == "linux":
            runner.chmod(0o755)
        arguments = [str(runner), "-r", self.project_name]
        case_paths = normalize_testcase_paths(self.payload.get("testcase_path"))
        if case_paths:
            arguments.append(case_paths)
        arguments.extend(["--parallel_workers", "1"])

        # 4. 执行并流式回传日志
        buffer: list[str] = []
        last_flush = time.monotonic()

        def flush(force: bool = False) -> None:
            nonlocal buffer, last_flush
            if buffer and (force or len(buffer) >= LOG_FLUSH_LINES or time.monotonic() - last_flush >= LOG_FLUSH_SECONDS):
                self.client.upload_task_logs(self.task_id, buffer)
                buffer, last_flush = [], time.monotonic()

        self.runner.start(arguments, framework_root)
        deadline = time.monotonic() + self.timeout
        for line in self.runner.iter_lines():
            buffer.append(line.rstrip()[:4000])
            flush()
            if self.canceled:
                break
            if time.monotonic() > deadline:
                self.runner.kill()
                raise TimeoutError("测试任务执行超时")
        flush(force=True)
        exit_code = self.runner.wait(timeout=30)

        # 5. 收集结果
        self._collect_results(project_root, exit_code)

    def _collect_results(self, project_root: Path, exit_code: int) -> None:
        """读取 case_results.json、打包 report/log 产物并上报最终状态。"""

        report_dir = project_root / "report"
        if report_dir.is_dir():
            report_zip = self.config.temp_dir / f"report-{self.task_id}.zip"
            with zipfile.ZipFile(report_zip, "w", zipfile.ZIP_DEFLATED) as bundle:
                for file in report_dir.rglob("*"):
                    if file.is_file():
                        bundle.write(file, file.relative_to(report_dir))
            try:
                self.client.upload_task_artifact(self.task_id, "report", report_zip)
            finally:
                report_zip.unlink(missing_ok=True)

        log_file = self.config.temp_dir / f"runner-{self.task_id}.log"
        log_file.write_text(f"exit_code={exit_code}\n", encoding="utf-8")
        try:
            self.client.upload_task_artifact(self.task_id, "log", log_file)
        finally:
            log_file.unlink(missing_ok=True)

        cases: list[dict] | None = None
        result_file = project_root / "report" / "case_results.json"
        if result_file.is_file():
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    cases = data
            except (OSError, ValueError):
                cases = None
        if cases is not None:
            self.client.upload_task_results(self.task_id, cases)

        if self.canceled:
            self._finish("canceled", exit_code=exit_code)
        elif exit_code == 0:
            self._finish("success", exit_code=exit_code)
        else:
            self._finish("failed", exit_code=exit_code, error_message=f"测试进程退出码 {exit_code}")

    def cancel(self) -> None:
        """请求取消：终止进程，由 run 主流程收尾上报。"""

        self.canceled = True
        self.runner.kill()

    def _finish(self, status: str, exit_code: int | None = None, error_message: str | None = None) -> None:
        """上报任务最终状态（容错重试一次）。"""

        for attempt in range(2):
            try:
                self.client.report_task_status(self.task_id, status, exit_code=exit_code, error_message=error_message)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("任务 %s 状态上报失败（第 %s 次）：%s", self.task_id, attempt + 1, exc)
                time.sleep(2)
