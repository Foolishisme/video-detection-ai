#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动脚本
启动FastAPI后端服务
"""

import uvicorn
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """主函数"""
    # 服务器配置 - 支持环境变量配置，默认允许外部访问
    host = os.getenv("BACKEND_HOST", "0.0.0.0")  # 默认 0.0.0.0 允许外部访问
    port = int(os.getenv("BACKEND_PORT", "8123"))
    
    # 显示URL时使用实际可访问的地址
    display_host = host if host != "0.0.0.0" else "127.0.0.1"
    url = f"http://{display_host}:{port}"
    
    print("=" * 60)
    print("SmartMonitor 后端服务启动中...")
    print("=" * 60)
    print(f"后端 API 地址: {url}")
    if host == "0.0.0.0":
        print(f"外部访问地址: http://<your-ip>:{port}")
    print(f"API 文档: {url}/docs")
    print("=" * 60)
    print("\n前端开发服务器:")
    print("  如果使用统一启动脚本 (start_dev.py)，前端将自动启动")
    print("  前端地址: http://localhost:5173")
    print("  外部访问: http://<your-ip>:5173")
    print("\n或者手动启动前端:")
    print("  cd frontend")
    print("  npm run dev")
    print("=" * 60)
    print("\n提示: 按 Ctrl+C 停止服务\n")
    print("提示: 可通过环境变量配置:")
    print("  BACKEND_HOST=0.0.0.0  (默认，允许外部访问)")
    print("  BACKEND_PORT=8123     (默认端口)")
    print("=" * 60)
    print("\n注意: 前端界面需要通过 start_dev.py 启动或手动访问 http://localhost:5173")
    print("=" * 60)
    
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

