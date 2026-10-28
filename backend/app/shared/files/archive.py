"""ZIP/TAR 归档的安全读取工具。"""

import io
import tarfile
import zipfile
from pathlib import PurePosixPath


def safe_archive_path(value: str) -> str:
    """规范化归档成员路径并拒绝绝对路径、盘符和目录穿越。"""

    value = value.replace("\\", "/")
    if value.startswith("/"):
        raise ValueError(f"压缩包包含绝对路径：{value}")
    path = PurePosixPath(value)
    if not value or ".." in path.parts or ":" in value:
        raise ValueError(f"压缩包包含不安全路径：{value}")
    return path.as_posix()


def strip_archive_root(paths: list[str]) -> list[str]:
    """剥离压缩包顶层的单一项目根目录。

    若所有成员共享同一个顶层目录（如 ``01gjxt_web/testcase/...``），则剥离该根目录，
    使最终路径符合 ``testcase`` / ``business`` / ``config`` 首层规范。
    """

    if not paths:
        return []
    tops = {path.split("/", 1)[0] for path in paths}
    if len(tops) == 1 and next(iter(tops)) not in {"testcase", "business", "config"}:
        prefix = next(iter(tops)) + "/"
        return [path[len(prefix):] for path in paths]
    return paths


def read_archive(data: bytes, filename: str) -> dict[str, bytes]:
    """读取 ZIP 或 TAR 系列归档中的普通文件。"""

    files: dict[str, bytes] = {}
    stream = io.BytesIO(data)
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as archive:
            for item in archive.infolist():
                if ((item.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError(f"压缩包不允许包含符号链接：{item.filename}")
                if not item.is_dir():
                    files[safe_archive_path(item.filename)] = archive.read(item)
        return files
    stream.seek(0)
    try:
        with tarfile.open(fileobj=stream, mode="r:*") as archive:
            for item in archive.getmembers():
                if item.issym() or item.islnk() or item.isdev():
                    raise ValueError(f"压缩包不允许包含链接或设备文件：{item.name}")
                if item.isfile():
                    source = archive.extractfile(item)
                    if source:
                        files[safe_archive_path(item.name)] = source.read()
    except tarfile.TarError as exc:
        raise ValueError(f"不支持的压缩包格式：{filename}") from exc
    return files
