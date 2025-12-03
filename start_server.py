#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动脚本
启动FastAPI后端服务并自动打开浏览器
"""

import uvicorn
import webbrowser
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """主函数"""
    # 服务器配置
    host = "127.0.0.1"
    port = 8123
    url = f"http://{host}:{port}"
    
    print("=" * 60)
    print("SmartMonitor 后端服务启动中...")
    print("=" * 60)
    print(f"服务地址: {url}")
    print(f"API文档: {url}/docs")
    print("=" * 60)
    print("\n提示: 按 Ctrl+C 停止服务\n")
    
    # 延迟打开浏览器（等待服务启动）
    def open_browser():
        time.sleep(2)  # 等待2秒让服务启动
        try:
            webbrowser.open(url)
            print(f"浏览器已自动打开: {url}")
        except Exception as e:
            print(f"无法自动打开浏览器: {e}")
            print(f"请手动访问: {url}")
    
    # 在后台线程中打开浏览器
    import threading
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # 启动FastAPI服务
    try:
        uvicorn.run(
            "server.app:app",
            host=host,
            port=port,
            reload=False,  # 生产环境不启用自动重载
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n服务已停止")
    except Exception as e:
        print(f"\n启动服务时出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

