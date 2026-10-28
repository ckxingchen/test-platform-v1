#!/usr/bin/env python3
"""部署前端到远端（仅前端，快速）。参数化，密码经环境变量传入避免留痕。"""
import os
import sys
import posixpath
import shlex
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = os.environ.get("DEPLOY_HOST", "192.168.14.100")
USER = os.environ.get("DEPLOY_USER", "root")
PASS = os.environ.get("DEPLOY_PASS", "")
REMOTE_DIR = os.environ.get("DEPLOY_DIR", "/opt/test-platform")
LOCAL_FRONTEND = os.environ.get(
    "LOCAL_FRONTEND",
    os.path.join(os.path.dirname(__file__), "..", "frontend"),
)

EXCLUDE_DIRS = {"node_modules", "dist", ".git"}
EXCLUDE_FILES = {".env", ".env.local"}


def collect_files(root):
    """收集 frontend 下需上传的文件相对路径列表（排除 node_modules/dist）。"""
    rel_list = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn in EXCLUDE_FILES:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            rel_list.append(rel)
    return rel_list


def exec_cmd(ssh, cmd, timeout=600):
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
    remote_frontend = posixpath.join(REMOTE_DIR, "frontend")

    # 确保目录存在
    try:
        sftp.stat(remote_frontend)
    except FileNotFoundError:
        print("远端 frontend 目录不存在，创建之。")
        code, out, err = exec_cmd(ssh, f"mkdir -p {remote_frontend}")
        if code != 0:
            print(f"mkdir 失败：{err}")
            sys.exit(1)

    files = collect_files(LOCAL_FRONTEND)
    print(f"[2/5] 本地 frontend 待上传文件：{len(files)} 个")

    # 上传（逐文件，保证目录结构）
    uploaded = 0
    for rel in files:
        local_path = os.path.join(LOCAL_FRONTEND, rel)
        remote_path = posixpath.join(remote_frontend, rel)
        remote_dir = posixpath.dirname(remote_path)
        # 确保远程目录存在
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            # 逐级创建
            exec_cmd(ssh, f"mkdir -p {remote_dir}")
        sftp.put(local_path, remote_path)
        uploaded += 1
        if uploaded % 100 == 0:
            print(f"  已上传 {uploaded}/{len(files)}")
    print(f"[3/5] 上传完成：{uploaded} 个文件")

    legacy_paths = [
        posixpath.join(remote_frontend, "src", name)
        for name in ("views", "components", "theme", "App.vue", "router.js", "api.js", "auth.js", "constants.js")
    ]
    code, _, err = exec_cmd(ssh, "rm -rf " + " ".join(shlex.quote(path) for path in legacy_paths))
    if code != 0:
        print(f"清理远端旧前端目录失败：{err}")
        sys.exit(1)

    # 远端重建 frontend 镜像 + 重启 frontend 容器
    exec_cmd(
        ssh,
        "docker image inspect testplatform-frontend:v1 >/dev/null 2>&1 && "
        "docker tag testplatform-frontend:v1 testplatform-frontend:rollback || true",
    )
    print("[4/5] 远端重建 frontend 镜像 ...")
    build_cmd = (
        f"cd {REMOTE_DIR} && "
        "docker build --build-arg NPM_REGISTRY=https://registry.npmmirror.com "
        "-f frontend/Dockerfile -t testplatform-frontend:v1 ."
    )
    code, out, err = exec_cmd(ssh, build_cmd, timeout=1800)
    if code != 0:
        print(f"镜像构建失败（exit {code}）：\n{err}\n{out}")
        sys.exit(1)
    print(out[-2000:])

    print("[5/5] 重启 frontend 容器 ...")
    # 探测 compose 命令
    code, out, _ = exec_cmd(ssh, "docker-compose version 2>/dev/null")
    if code == 0:
        compose = "docker-compose"
    else:
        compose = "docker compose"
    # CentOS7 叠加 overlay
    code, _, _ = exec_cmd(ssh, "uname -r")
    restart_cmd = (
        f"cd {REMOTE_DIR} && {compose} -f docker-compose.yml "
    )
    # 检查是否存在 centos7 overlay 文件
    code, out, _ = exec_cmd(ssh, f"test -f {REMOTE_DIR}/docker-compose.centos7.yml && echo yes")
    if "yes" in out:
        restart_cmd += "-f docker-compose.centos7.yml "
    restart_cmd += "up -d --no-build --remove-orphans frontend"
    code, out, err = exec_cmd(ssh, restart_cmd, timeout=300)
    if code != 0:
        print(f"容器重启失败：\n{err}\n{out}")
        sys.exit(1)
    print(out)

    # 验证
    code, out, _ = exec_cmd(ssh, f"{compose} ps frontend", timeout=60)
    print(out)
    print("\n✅ 前端部署完成，等待 nginx 生效后即可验证。")
    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
