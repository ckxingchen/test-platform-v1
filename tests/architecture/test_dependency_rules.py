"""防止模块化重构在后续开发中退化为横向大目录。"""

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
        elif isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
    return result


def python_imports(root: Path):
    for path in root.rglob("*.py"):
        for module in imported_modules(path):
            yield path, module


def test_platform_does_not_depend_on_shared_or_business_modules():
    violations = [
        (path, module)
        for path, module in python_imports(BACKEND / "platform")
        if module.startswith(("app.shared", "app.modules"))
    ]
    assert violations == []


def test_shared_does_not_depend_on_business_modules():
    violations = [
        (path, module)
        for path, module in python_imports(BACKEND / "shared")
        if module.startswith("app.modules")
    ]
    assert violations == []


def test_business_modules_do_not_use_legacy_horizontal_paths():
    legacy_prefixes = (
        "app.api", "app.core", "app.crud", "app.db", "app.models",
        "app.schemas", "app.services", "app.utils",
    )
    violations = [
        (path, module)
        for path, module in python_imports(BACKEND / "modules")
        if module.startswith(legacy_prefixes)
    ]
    assert violations == []


def test_frontend_modules_do_not_import_removed_flat_directories():
    forbidden = ("../components/", "../constants", "../auth", "../../views/", "@/views/")
    violations = []
    for path in (FRONTEND / "modules").rglob("*"):
        if path.suffix not in {".js", ".vue"}:
            continue
        source = path.read_text(encoding="utf-8")
        if any(value in source for value in forbidden):
            violations.append(path)
    assert violations == []


def test_frontend_and_backend_menu_modules_stay_aligned():
    expected = {"auth", "dashboard", "users", "objects", "executors", "tasks"}
    backend_modules = {path.name for path in (BACKEND / "modules").iterdir() if path.is_dir()}
    frontend_modules = {path.name for path in (FRONTEND / "modules").iterdir() if path.is_dir()}
    assert expected <= backend_modules
    assert expected <= frontend_modules
