import subprocess
import os
import threading
import sys
from pathlib import Path
import shutil



def run_backend():
    """启动后端 FastAPI 服务"""
    project_root = Path(__file__).resolve().parent
    backend_dir = project_root / "back"
    venv_python = backend_dir / "venv" / "Scripts" / "python.exe"

    if not backend_dir.exists():
        print(f"[后端错误] 未找到后端目录：{backend_dir}")
        return

    if not venv_python.exists():
        print("[后端错误] 找不到虚拟环境，请创建 venv 再试。")
        return

    print("[后端] 正在启动 FastAPI...")

    cmd = [
        str(venv_python),
        "-m", "uvicorn",
        "main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
    ]

    subprocess.Popen(cmd, cwd=backend_dir).wait()



def run_frontend():
    """启动前端 Vite 服务"""
    project_root = Path(__file__).resolve().parent
    frontend_dir = project_root / "front"

    if not frontend_dir.exists():
        print(f"[前端错误] 未找到前端目录：{frontend_dir}")
        return

    node_modules = frontend_dir / "node_modules"

    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_cmd is None:
        print("[前端错误] 找不到 npm，请确保 Node.js 已正确安装并加入 PATH")
        return

    if not node_modules.exists():
        print("[前端] 未检测到 node_modules，正在安装依赖...")
        install_process = subprocess.Popen([npm_cmd, "install"], cwd=frontend_dir)
        install_process.wait()

    print("[前端] 正在启动前端服务（Vite）...")
    subprocess.Popen([npm_cmd, "run", "dev"], cwd=frontend_dir).wait()



if __name__ == "__main__":
    print("🚀 项目正在启动...")

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)

    backend_thread.start()
    frontend_thread.start()

    backend_thread.join()
    frontend_thread.join()
