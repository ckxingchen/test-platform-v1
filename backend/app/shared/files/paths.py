"""项目文件相对路径规范化与安全校验工具。"""


def validate_relative_path(value: str) -> str:
    """规范化项目相对路径并阻止目录穿越或非法根目录。"""

    value = value.replace("\\", "/").strip("/")
    if not value or "\x00" in value or ":" in value:
        raise ValueError("文件路径无效")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("文件路径无效")
    if parts[0] not in {"testcase", "business", "config"}:
        raise ValueError("项目文件只能位于 testcase、business 或 config")
    return value


def normalize_selected_case_paths(paths: list[str] | None) -> list[str] | None:
    """校验并归并用户勾选的用例路径。

    返回去重 + 最粗粒度归并后的 testcase/ 前缀完整相对路径数组（升序），
    用于按需下发过滤；None 或空列表统一归为 None（整项目运行）。
    """

    if not paths:
        return None
    normalized: list[str] = []
    for raw in paths:
        path = validate_relative_path(str(raw))  # 抛 ValueError 时由调用方转 422
        if not path.startswith("testcase/"):
            raise ValueError(f"用例路径必须在 testcase/ 目录下：{path}")
        if path not in normalized:
            normalized.append(path)
    # 最粗粒度归并：若已选中某目录，则其下所有后代路径都被该目录覆盖，可剔除
    normalized.sort(key=lambda p: p.count("/"))
    merged: list[str] = []
    for path in normalized:
        if any(path.startswith(ancestor + "/") for ancestor in merged):
            continue
        merged.append(path)
    return sorted(merged)
