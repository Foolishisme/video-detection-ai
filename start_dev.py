#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一开发启动脚本
同时启动前端（React）和后端（FastAPI）服务
"""

import subprocess
import sys
import time
import signal
import os
import socket
from pathlib import Path

# 项目根目录
project_root = Path(__file__).parent

# 存储子进程
processes = []


def get_local_ip():
    """获取本机IP地址"""
    try:
        # 连接到一个远程地址来获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号，优雅关闭所有进程"""
    print("\n\n正在关闭所有服务...")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        except Exception as e:
            print(f"关闭进程时出错: {e}")
    print("所有服务已关闭")
    sys.exit(0)


def start_backend():
    """启动后端服务"""
    print("启动后端服务...")
    is_windows = sys.platform == "win32"
    backend_process = subprocess.Popen(
        [sys.executable, str(project_root / "server" / "start.py")],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=is_windows
    )
    return backend_process


def start_frontend():
    """启动前端开发服务器"""
    print("启动前端开发服务器...")
    frontend_dir = project_root / "frontend"
    
    # Windows 上需要使用 shell=True
    is_windows = sys.platform == "win32"
    
    # 检查 node_modules 是否存在
    if not (frontend_dir / "node_modules").exists():
        print("检测到前端依赖未安装，正在安装...")
        install_process = subprocess.run(
            ["npm", "install"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            shell=is_windows
        )
        if install_process.returncode != 0:
            print(f"前端依赖安装失败: {install_process.stderr}")
            return None
    
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=is_windows
    )
    return frontend_process


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("SmartMonitor 开发环境启动中...")
    print("=" * 60)
    print("正在启动前端和后端服务...")
    print("=" * 60)
    print("\n提示: 按 Ctrl+C 停止所有服务\n")
    
    # 启动后端
    backend_process = start_backend()
    if backend_process:
        processes.append(backend_process)
        print("✓ 后端服务已启动")
    
    # 等待后端启动
    time.sleep(2)
    
    # 启动前端
    frontend_process = start_frontend()
    if frontend_process:
        processes.append(frontend_process)
        print("✓ 前端开发服务器已启动")
    
    # 获取配置信息
    backend_host = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port = int(os.getenv("BACKEND_PORT", "8123"))
    frontend_port = int(os.getenv("FRONTEND_PORT", "5173"))
    
    # 获取本机IP用于显示外部访问地址
    local_ip = get_local_ip()
    
    print("\n" + "=" * 60)
    print("服务启动完成！")
    print("=" * 60)
    print("本地访问:")
    print(f"  后端 API: http://127.0.0.1:{backend_port}")
    print(f"  前端界面: http://localhost:{frontend_port}")
    print(f"  API 文档: http://127.0.0.1:{backend_port}/docs")
    if backend_host == "0.0.0.0":
        print("\n外部访问（通过代理或局域网）:")
        print(f"  后端 API: http://{local_ip}:{backend_port}")
        print(f"  前端界面: http://{local_ip}:{frontend_port}")
        print(f"  API 文档: http://{local_ip}:{backend_port}/docs")
    print("=" * 60)
    print("\n提示: 按 Ctrl+C 停止所有服务")
    print("\n提示: 可通过环境变量配置:")
    print("  BACKEND_HOST=0.0.0.0   (默认，允许外部访问)")
    print("  BACKEND_PORT=8123      (默认端口)")
    print("  FRONTEND_PORT=5173     (默认端口)")
    print("=" * 60)
    print()
    
    # 实时输出进程日志
    try:
        import threading
        
        def read_output(process, process_name):
            """在单独线程中读取进程输出"""
            try:
                if process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            print(f"[{process_name}] {line.rstrip()}")
                        if process.poll() is not None:
                            break
            except Exception as e:
                print(f"读取 {process_name} 输出时出错: {e}")
        
        # 为每个进程启动输出读取线程
        threads = []
        for i, process in enumerate(processes):
            process_name = "后端" if i == 0 else "前端"
            thread = threading.Thread(
                target=read_output,
                args=(process, process_name),
                daemon=True
            )
            thread.start()
            threads.append(thread)
        
        # 主循环：检查进程状态
        while True:
            # 检查进程是否还在运行
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    # 进程已退出
                    process_name = "后端" if i == 0 else "前端"
                    print(f"\n[{process_name}] 进程已退出，退出码: {process.returncode}")
                    # 等待其他进程也退出
                    time.sleep(1)
                    signal_handler(None, None)
                    return
            
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()

