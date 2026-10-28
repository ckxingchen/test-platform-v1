"""测试框架归档目录结构解析工具。

框架元信息（name / os / arch / runner_path）不再依赖包内 framework.json 清单，
统一由上传接口的表单字段传入，此处仅负责：

1. 读取归档内普通文件；
2. 以入口文件为锚点探测 archive_root——若入口位于归档某单一顶层目录内则剥离该层；
3. 统计 file_count；
4. 校验 runner_path 指向的入口文件真实存在且位于归档内。
"""

from pathlib import PurePosixPath

from app.shared.files.archive import read_archive, safe_archive_path
from app.shared.files.hashing import sha256_bytes


def detect_archive_root(files: dict[str, bytes], runner: str) -> str:
    """以入口文件为锚点探测是否包裹了一层目录。

    若 ``runner`` 直接存在于归档根目录下（如归档内就是 ``runner``），返回空字符串；
    否则若在**唯一**一个一级目录 ``P`` 下存在 ``P/runner``（且找不到第二个候选），
    则认为用户压缩的是外层文件夹，返回该目录名；歧义或缺失时交由调用方报错。
    """

    if not files:
        raise ValueError("压缩包内没有任何文件")
    if runner in files:
        return ""
    candidates = sorted(p for p in files if p.endswith("/" + runner))
    if len(candidates) == 1:
        wrapper = candidates[0][: -len("/" + runner)]
        if wrapper and "/" not in wrapper:
            return wrapper
    return ""


def inspect_framework_package(data: bytes, filename: str, runner_path: str) -> dict:
    """解析框架归档目录结构，校验入口文件并生成元数据。"""

    if not data:
        raise ValueError("上传文件为空")
    runner_path = (runner_path or "").replace("\\", "/").strip("/")
    try:
        runner = safe_archive_path(runner_path)
    except ValueError as exc:
        raise ValueError(f"执行器入口路径无效：{exc}") from exc
    if not runner:
        raise ValueError("请填写执行器入口路径")

    files = read_archive(data, filename)
    archive_root = detect_archive_root(files, runner)

    # 入口文件必须真实存在：既允许位于 archive_root 之内，也允许位于归档根目录。
    candidates = {runner, f"{archive_root}/{runner}"} if archive_root else {runner}
    if not candidates.intersection(files):
        located = f"{archive_root}/{runner}" if archive_root else runner
        raise ValueError(f"执行器入口文件不存在：{located}")

    return {
        "runner_path": runner,
        "archive_root": archive_root,
        "schema_version": 1,
        "archive_sha256": sha256_bytes(data),
        "file_count": len(files),
    }
