"""SQLAlchemy 模型到响应字典的通用序列化。"""

from typing import Any

from sqlalchemy import inspect as sa_inspect


def model_to_dict(model: object, extra: dict[str, Any] | None = None, exclude: set[str] | None = None, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    columns = {attr.key: getattr(model, attr.key) for attr in sa_inspect(model).mapper.column_attrs}
    for key, fallback in (defaults or {}).items():
        if columns.get(key) is None:
            columns[key] = fallback
    for key in exclude or set():
        columns.pop(key, None)
    columns.update(extra or {})
    return columns
