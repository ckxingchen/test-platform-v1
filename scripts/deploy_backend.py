#!/usr/bin/env python3
"""部署后端到远端（含数据库迁移）。密码经环境变量传入避免留痕。"""
import os
import sys
import posixpath
import shlex
import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.168.14.100")
USER = os.environ.get("DEPLOY_USER", "root")
PASS = os.environ.get("DEPLOY_PASS", "")
REMOTE_DIR = os.environ.get("DEPLOY_DIR", "/opt/test-platform")
LOCAL_APP = os.path.join(os.path.dirname(__file__), "..", "backend", "app")

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}


def collect_files(root):
    """递归收集 backend/app 下需上传的文件相对路径列表。"""
    rel_list = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            rel_list.append(rel)
    return rel_list


def exec_cmd(ssh, cmd, timeout=1800):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main():
    if not PASS:
        print("缺少 DEPLOY_PASS 环境变量，退出。")
        sys.exit(2)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[1/5] 连接 {USER}@{HOST} ...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = ssh.open_sftp()
    remote_app = posixpath.join(REMOTE_DIR, "backend", "app")
    remote_stage = f"{remote_app}.upload"
    remote_backup = f"{remote_app}.previous"

    files = collect_files(LOCAL_APP)
    print(f"[2/5] 本地 backend/app 待上传文件：{len(files)} 个")

    code, _, err = exec_cmd(
        ssh,
        f"rm -rf {shlex.quote(remote_stage)} && mkdir -p {shlex.quote(remote_stage)}",
    )
    if code != 0:
        print(f"Cannot prepare remote staging directory: {err}")
        sys.exit(1)

    uploaded = 0
    for rel in files:
        local_path = os.path.join(LOCAL_APP, rel)
        remote_path = posixpath.join(remote_stage, rel)
        remote_dir = posixpath.dirname(remote_path)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            exec_cmd(ssh, f"mkdir -p {remote_dir}")
        sftp.put(local_path, remote_path)
        uploaded += 1
    # 上传 requirements.txt 和 Dockerfile（依赖变更时必需）
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
    for extra in ("requirements.txt", "Dockerfile"):
        local_extra = os.path.join(backend_dir, extra)
        if os.path.isfile(local_extra):
            sftp.put(local_extra, posixpath.join(REMOTE_DIR, "backend", extra))
            print(f"  已上传 {extra}")
    print(f"[3/5] 上传完成：{uploaded} 个 .py 文件 + 配置文件")
    swap_cmd = (
        f"rm -rf {shlex.quote(remote_backup)} && "
        f"if [ -d {shlex.quote(remote_app)} ]; then mv {shlex.quote(remote_app)} {shlex.quote(remote_backup)}; fi && "
        f"mv {shlex.quote(remote_stage)} {shlex.quote(remote_app)}"
    )
    code, _, err = exec_cmd(ssh, swap_cmd)
    if code != 0:
        print(f"Cannot replace remote backend source: {err}")
        sys.exit(1)

    exec_cmd(
        ssh,
        "docker image inspect testplatform-backend:v1 >/dev/null 2>&1 && "
        "docker tag testplatform-backend:v1 testplatform-backend:rollback || true",
    )
    print("[4/5] 远端重建 backend 镜像 (--no-cache) ...")
    code, out, err = exec_cmd(
        ssh,
        f"cd {REMOTE_DIR} && docker build --no-cache "
        "-f backend/Dockerfile -t testplatform-backend:v1 .",
        timeout=1800,
    )
    if code != 0:
        exec_cmd(
            ssh,
            f"rm -rf {shlex.quote(remote_app)} && "
            f"if [ -d {shlex.quote(remote_backup)} ]; then mv {shlex.quote(remote_backup)} {shlex.quote(remote_app)}; fi",
        )
        print(f"镜像构建失败（exit {code}）：\n{err}\n{out}")
        sys.exit(1)
    print(out[-1500:])

    print("[5/5] 重启 backend 容器 ...")
    code, _, _ = exec_cmd(ssh, "docker-compose version 2>/dev/null")
    compose = "docker-compose" if code == 0 else "docker compose"
    restart_cmd = f"cd {REMOTE_DIR} && {compose} -f docker-compose.yml "
    code, out, _ = exec_cmd(ssh, f"test -f {REMOTE_DIR}/docker-compose.centos7.yml && echo yes")
    if "yes" in out:
        restart_cmd += "-f docker-compose.centos7.yml "
    restart_cmd += "up -d --no-build --force-recreate --no-deps backend"
    code, out, err = exec_cmd(ssh, restart_cmd, timeout=300)
    if code != 0:
        print(f"容器重启失败：\n{err}\n{out}")
        sys.exit(1)
    print(out)
    exec_cmd(ssh, f"rm -rf {shlex.quote(remote_backup)}")

    sftp.close()
    ssh.close()
    print("\n后端部署完成，等待容器启动后验证 /health。")


if __name__ == "__main__":
    main()
