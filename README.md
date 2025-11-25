# SmartMonitor - 智能监控系统

## 项目概述

SmartMonitor 是一个基于端云协同架构的智能监控系统，通过本地 YOLO 初筛和云端大模型仲裁，实现高精度、低误报的危险动作检测。系统支持智能分级告警，能够识别具体场景（如打架、摔倒、垃圾等）并显示相应的告警信息，危险情况显示红色警告，提醒情况显示黄色提示。

## 当前进展状态 ✅

### 已完成功能

1. **客户端（本地）**
   - ✅ 视频流采集：支持摄像头实时采集（640x480 @ 30fps）
   - ✅ YOLO 检测：使用 YOLOv8n 进行人体检测，实时显示检测框和置信度
   - ✅ 异步网络通信：独立工作线程处理 HTTP 请求，不阻塞视频显示
   - ✅ 图像压缩：自动将图像压缩至 640x640，JPEG 质量 80，控制传输大小
   - ✅ 冷却机制：检测到 Person 后 5 秒冷却时间，避免频繁请求
   - ✅ 结果展示：在视频画面上显示服务端分析结果
   - ✅ **智能告警系统**：分级告警显示（红色危险/黄色提醒），具体告警信息（如"检测到打架"、"有人摔倒"、"地上有垃圾"等）

2. **服务端（远端）**
   - ✅ Qwen2-VL 模型加载：支持 8bit 量化和 modelscope
   - ✅ FastAPI 接口：提供 `/chat` 端点接收图像分析请求
   - ✅ 语义级分析：使用大模型进行危险情况判断
   - ✅ JSON 响应：返回 `is_danger`、`alert_type`、`alert_message`、`reasoning`、`confidence` 字段
   - ✅ **智能分类**：自动识别具体场景（打架、摔倒、垃圾等）并生成简短告警语句

3. **系统集成**
   - ✅ 端云通信：客户端成功连接远端服务器
   - ✅ 数据流：YOLO 检测 → 图像压缩 → HTTP 上传 → 大模型分析 → 结果返回
   - ✅ 错误处理：完善的异常处理和日志记录
   - ✅ **分级告警**：根据告警类型自动区分危险（红色）和提醒（黄色）级别

### 测试验证结果

根据运行日志，系统已成功验证：

- **YOLO 检测**：成功检测到多人（置信度 0.43-0.90）
- **服务端连接**：成功连接到远端服务器
- **大模型分析**：正常返回分析结果，包含具体告警类型和简短告警语句
  ```json
  {
    "is_danger": false,
    "alert_type": "安全",
    "alert_message": "正常活动",
    "reasoning": "人物处于正常站立姿势，没有表现出失去平衡、痛苦或异常姿态...",
    "confidence": 0.91
  }
  ```
- **告警显示**：危险情况显示红色警告（如"检测到打架"），提醒情况显示黄色提醒（如"地上有垃圾"）
- **响应时间**：从提交到返回约 2-3 秒（符合预期）

## 项目架构

```
SmartMonitor/
├── client/                     # 客户端（本地 Windows）
│   ├── app.py                  # 主程序入口
│   ├── core/
│   │   ├── pipeline.py         # 视频流采集线程
│   │   ├── detector.py          # YOLO 检测器
│   │   └── rules.py            # 规则引擎（预留）
│   ├── utils/
│   │   ├── api_client.py       # HTTP 客户端（异步）
│   │   └── visualization.py    # 可视化工具
│   ├── config.yaml             # 客户端配置
│   └── README.md               # 客户端使用说明
│
├── shared/                     # 共享数据模型
│   └── schemas.py              # Pydantic 数据模型
│
├── core_extracted.py           # 核心功能模块（摄像头、报警）
├── requirements-client.txt     # 客户端依赖
├── requirements-server.txt     # 服务端依赖（参考）
└── README.md                   # 本文件
```

## 技术栈

### 客户端
- **Python 3.10+**
- **OpenCV**: 视频采集和显示
- **Ultralytics YOLOv8**: 人体检测
- **Requests**: HTTP 客户端
- **PyYAML**: 配置管理
- **Pydantic**: 数据验证
- **Google Generative AI**: Gemini API 支持（可选）

### 服务端（远端）
- **FastAPI**: Web 框架
- **Qwen2-VL-7B-Instruct**: 视觉大模型
- **Transformers**: 模型加载
- **PyTorch**: 深度学习框架
- **BitsAndBytes**: 8bit 量化

### LLM 提供商支持
- **远端服务器**：支持自定义部署的 Qwen2-VL 模型服务器
- **Google Gemini API**：支持 Gemini-2.0-flash-exp 和 Gemini-2.5-flash-lite 模型
- 可通过配置文件灵活切换 LLM 提供商

## 快速开始

### 1. 安装客户端依赖

```bash
pip install -r requirements-client.txt
```

### 2. 配置 LLM 提供商

编辑 `client/config.yaml`：

**方式一：使用远端服务器**
```yaml
llm_provider: "remote"
server:
  host: "你的服务器IP地址"  # 例如: "192.168.1.100"
  port: 8000
  endpoint: "/chat"
```

**方式二：使用 Google Gemini API**
```yaml
llm_provider: "gemini"
gemini:
  api_key: "你的Gemini_API_KEY"
  model_name: "gemini-2.5-flash-lite"  # 或 "gemini-2.0-flash-exp"
```

### 3. 运行客户端

```bash
cd client
python app.py
```

### 4. 操作说明

- 程序会自动连接摄像头（默认索引 0）
- 检测到 Person 后，每 5 秒自动发送图像到服务端分析
- 按 `q` 或 `ESC` 键退出

## 核心特性

### 1. 异步非阻塞架构
- 视频采集和显示在主线程
- HTTP 请求在独立工作线程
- 网络卡顿不影响视频流畅度

### 2. 事件驱动
- 仅当 YOLO 检测到 Person 时触发上传
- 5 秒冷却时间避免频繁请求
- 智能节流，节省带宽

### 3. 数据压缩
- 图像自动 Resize 至 640x640
- JPEG 压缩质量 80
- 传输大小控制在 50KB 以内

### 4. 端云协同
- 本地：轻量级 YOLO 初筛（CPU 即可）
- 云端：大模型语义分析（需要 GPU）
- 资源合理分配，成本优化

### 5. 智能分级告警系统 ⭐ 新功能
- **具体告警信息**：LLM 返回具体场景类型（打架、摔倒、垃圾等）和简短告警语句
- **分级显示**：
  - 🔴 **红色警告**：危险情况（打架、摔倒、受伤等）
  - 🟡 **黄色提醒**：非危险但需注意的情况（垃圾、杂物等）
- **智能判断**：根据 `alert_type` 自动判断告警级别，无需手动配置
- **用户友好**：告警信息清晰具体，便于快速了解现场情况

## 配置说明

### 客户端配置 (`client/config.yaml`)

```yaml
# LLM 提供商配置（可选值: "remote" 或 "gemini"）
llm_provider: "gemini"  # 默认使用远端服务器

# 服务端配置（当 llm_provider 为 "remote" 时使用）
server:
  host: "服务器IP地址"
  port: 8000
  endpoint: "/chat"

# Gemini API 配置（当 llm_provider 为 "gemini" 时使用）
gemini:
  api_key: "你的Gemini_API_KEY"  # 或通过环境变量 GEMINI_API_KEY 设置
  model_name: "gemini-2.5-flash-lite"  # 可选: "gemini-2.0-flash-exp"

# 冷却时间（秒）
cooldown_seconds: 5.0

# YOLO 检测阈值
thresholds:
  confidence: 0.25  # 置信度阈值

# 视频源配置
video:
  source: 0  # 摄像头索引或视频文件路径
  fps: 30
  width: 640
  height: 480
  loop_video: true  # 视频文件循环播放
  target_fps: 20   # 视频文件播放速度控制
```

## 工作流程

```
1. 视频采集（VideoPipeline）
   ↓
2. YOLO 检测（PersonDetector）
   ↓ 检测到 Person？
3. 检查冷却时间（5秒）
   ↓ 满足条件？
4. 图像压缩（640x640, JPEG 80）
   ↓
5. HTTP 请求（NetworkWorker 异步）
   ↓
6. 服务端大模型分析（Qwen2-VL）
   ↓
7. 解析返回结果（is_danger, alert_type, alert_message）
   ↓
8. 判断告警级别（危险/提醒/安全）
   ↓
9. 显示告警信息（红色警告/黄色提醒）
```

## 日志示例

### 正常情况
```
2025-11-19 16:52:50 - 发送请求到服务端...
2025-11-19 16:52:52 - 已提交图像到服务端分析
2025-11-19 16:52:59 - 服务端分析完成: {
  'is_danger': False,
  'alert_type': '安全',
  'alert_message': '正常活动',
  'reasoning': '人物处于正常站立姿势...',
  'confidence': 0.91
}
```

### 危险情况
```
2025-11-19 16:53:10 - 触发报警: 检测到打架
2025-11-19 16:53:10 - 服务端分析完成: {
  'is_danger': True,
  'alert_type': '打架',
  'alert_message': '检测到打架',
  'reasoning': '画面中多人发生肢体冲突...',
  'confidence': 0.85
}
```

### 提醒情况
```
2025-11-19 16:53:25 - 服务端分析完成: {
  'is_danger': False,
  'alert_type': '垃圾',
  'alert_message': '地上有垃圾',
  'reasoning': '画面中地面有垃圾杂物...',
  'confidence': 0.78
}
```

## 已知问题与限制

1. **服务端依赖**：需要 GPU 服务器运行 Qwen2-VL 模型
2. **网络要求**：需要稳定的网络连接
3. **响应延迟**：大模型推理需要 2-3 秒（可接受）
4. **检测精度**：YOLO 检测置信度阈值可调整（当前 0.25）

## 未来计划

- [x] ✅ 优化大模型 Prompt 以提高准确率（已完成：支持具体告警类型和简短告警语句）
- [x] ✅ 分级告警系统（已完成：红色危险/黄色提醒）
- [ ] 支持多路视频流
- [ ] 添加历史记录和回放功能
- [ ] 支持更多报警方式（邮件、短信等）
- [ ] 添加 Web 管理界面
- [ ] 告警信息持久化存储
- [ ] 告警统计分析功能

## 相关文档

- [客户端使用说明](client/README.md)
- [项目重构指南](项目重构指南.md)
- [核心功能提取说明](CORE_EXTRACTED_README.md)

## 开发团队

本项目基于端云协同架构设计，实现了从传统规则检测到 AI 大模型仲裁的升级。

## 许可证

[待定]

---

**最后更新**: 2025-01-XX  
**状态**: MVP 已完成，系统正常运行 ✅  
**最新功能**: 智能分级告警系统已上线，支持具体告警信息和颜色区分 ⭐

