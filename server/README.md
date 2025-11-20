# 服务端部署说明（参考文档）

> **注意**: 服务端代码已部署到远端服务器，本地仅保留此参考文档。

## 服务端架构

服务端运行在远端 Linux 服务器上，负责：
- 加载 Qwen2-VL-7B-Instruct 模型
- 接收客户端发送的图像
- 使用大模型进行语义级危险判定
- 返回 JSON 格式的分析结果

## 服务端配置

### 环境变量

```bash
export QWEN_VL_MODEL_PATH="/opt/wyf/ai-models/qwen/Qwen2-VL-7B-Instruct"
export USE_8BIT="True"
export USE_MODELSCOPE="True"
```

### API 端点

- **POST /chat**: 接收图像分析请求
  - 请求格式: `{"image_base64": "...", "query": "..."}`
  - 响应格式: `{"response": "..."}`

- **GET /health**: 健康检查

## 服务端启动

```bash
cd server
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 依赖要求

- Python 3.10+
- PyTorch (CUDA 11.8+)
- Transformers
- FastAPI
- Qwen2-VL-7B-Instruct 模型
- 至少 8GB GPU 显存（使用 8bit 量化）

详细依赖见 `requirements-server.txt`

## 客户端连接

客户端通过 `client/config.yaml` 配置服务端地址：

```yaml
server:
  host: "服务器IP地址"
  port: 8000
  endpoint: "/chat"
```

## 注意事项

1. 服务端需要 GPU 支持（推荐 T4 或更高）
2. 首次启动需要下载模型（约 14GB）
3. 使用 8bit 量化可节省显存
4. 确保防火墙开放 8000 端口
