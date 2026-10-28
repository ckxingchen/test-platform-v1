"""Agent 双平台打包脚本：PyInstaller onedir + 打包 bin/ 目录为发布包。

用法（Windows 本机 / Linux 服务器各执行一次）：
    python build.py

产物：
    dist/agent.zip  (Windows)   内含 bin/kw-agent.exe + bin/_internal/
    dist/agent.tar.gz (Linux)   内含 bin/kw-agent + bin/_internal/

发布包顶层固定为 bin/，平台上传后按 bin/ 结构部署到 {agent_home}/bin/。
"""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "kw-agent"


def build_binary() -> Path:
    """调用 PyInstaller 生成 onedir 可执行程序。"""

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name", APP_NAME,
        "--paths", str(ROOT),
        str(ROOT / "main.py"),
    ]
    subprocess.run(command, check=True, cwd=str(ROOT))
    return ROOT / "dist" / APP_NAME


def package(binary_dir: Path) -> Path:
    """把 onedir 产物打包为 bin/ 顶层结构的发布包。"""

    output_dir = ROOT / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        archive = output_dir / "agent.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for file in binary_dir.rglob("*"):
                if file.is_file():
                    bundle.write(file, Path("bin") / file.relative_to(binary_dir))
    else:
        archive = output_dir / "agent.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for file in binary_dir.rglob("*"):
                if file.is_file():
                    bundle.add(file, arcname=str(Path("bin") / file.relative_to(binary_dir)))
    return archive


def main() -> None:
    """执行打包并输出产物信息。"""

    binary_dir = build_binary()
    archive = package(binary_dir)
    size_mb = archive.stat().st_size / 1024 / 1024
    print(f"打包完成：{archive}（{size_mb:.1f} MB）")
    entry = "bin/kw-agent.exe" if sys.platform.startswith("win") else "bin/kw-agent"
    print(f"入口文件：{entry}")
    print("请上传到平台「资源管理 → Agent 管理」，OS/架构按当前平台选择")


if __name__ == "__main__":
    main()
