# SmartMonitor - 智能监控系统

## 项目概述

SmartMonitor 是一个基于端云协同架构的智能监控系统，通过本地 YOLO 初筛和云端大模型仲裁，实现高精度、低误报的危险动作检测。系统支持**多视频源9宫格监控**（最多9路视频），智能分级告警，能够识别具体场景（如打架、摔倒、垃圾、积水等）并显示相应的告警信息。危险情况显示全屏红色弹窗警告，提醒情况在小窗口显示黄色警告。

## 当前进展状态 ✅

### 已完成功能

1. **客户端（本地桌面应用）**
   - ✅ 视频流采集：支持摄像头实时采集（640x480 @ 30fps）
   - ✅ YOLO 检测：使用 YOLOv8n 进行人体检测，实时显示检测框和置信度
   - ✅ 异步网络通信：独立工作线程处理 HTTP 请求，不阻塞视频显示
   - ✅ 图像压缩：自动将图像压缩至 640x640，JPEG 质量 80，控制传输大小
   - ✅ 冷却机制：检测到 Person 后 5 秒冷却时间，避免频繁请求
   - ✅ 结果展示：在视频画面上显示服务端分析结果
   - ✅ **智能告警系统**：分级告警显示（红色危险/黄色提醒），具体告警信息（如"检测到打架"、"有人摔倒"、"地上有垃圾"等）

2. **Web 后端服务** ⭐ 新功能
   - ✅ FastAPI 后端：提供 RESTful API 和 MJPEG 视频流
   - ✅ **多视频源支持**：支持同时监控多个视频源（最多9个），每个视频源独立线程管理
   - ✅ MJPEG 视频流：实时视频流传输（`/video_feed` 和 `/api/video_feed/{source_id}`）
   - ✅ 告警管理 API：告警列表、详情查询（`/api/alerts`），告警包含 `source_id` 标识来源
   - ✅ 系统状态 API：按视频源查询状态（`/api/status/{source_id}`），包含 FPS、告警次数等
   - ✅ 视频源信息 API：获取所有视频源信息（`/api/sources`）
   - ✅ 告警图片服务：告警截图查看（`/api/alerts/{id}/image`）
   - ✅ 监控服务封装：将客户端核心逻辑封装为后台服务，支持多实例

3. **Web 前端界面** ⭐ 新功能
   - ✅ **9宫格监控布局**：支持最多9路视频源同时监控，全屏显示
   - ✅ 实时视频流显示：每个视频源独立的 MJPEG 流实时播放
   - ✅ **告警次数显示**：每个视频窗口左上角显示该源的告警次数（半透明覆盖）
   - ✅ **全屏危险弹窗**：检测到危险动作时，全屏红色弹窗显示告警信息，5秒后自动关闭
   - ✅ **小窗口警告**：检测到提醒类告警（垃圾、积水等）时，在对应视频窗口内显示黄色警告
   - ✅ 自动刷新：告警次数和告警监听自动轮询更新

4. **LLM 服务端（远端）**
   - ✅ Qwen2-VL 模型加载：支持 8bit 量化和 modelscope
   - ✅ FastAPI 接口：提供 `/chat` 端点接收图像分析请求
   - ✅ 语义级分析：使用大模型进行危险情况判断
   - ✅ JSON 响应：返回 `is_danger`、`alert_type`、`alert_message`、`reasoning`、`confidence` 字段
   - ✅ **智能分类**：自动识别具体场景（打架、摔倒、垃圾等）并生成简短告警语句

5. **系统集成**
   - ✅ 端云通信：客户端成功连接远端服务器
   - ✅ 数据流：YOLO 检测 → 图像压缩 → HTTP 上传 → 大模型分析 → 结果返回
   - ✅ 错误处理：完善的异常处理和日志记录
   - ✅ **多视频源管理**：每个视频源独立监控线程、独立状态管理、独立网络工作线程
   - ✅ **分级告警**：根据告警类型自动区分危险（全屏红色弹窗）和提醒（小窗口黄色警告）级别
   - ✅ **前后端分离**：Web 服务独立运行，支持浏览器访问
   - ✅ **9宫格布局**：全屏显示，支持最多9路视频源，空位显示黑屏

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
├── client/                     # 客户端（本地桌面应用）
│   ├── app.py                  # 桌面应用主程序入口
│   ├── core/
│   │   ├── camera.py           # 摄像头连接模块
│   │   ├── pipeline.py         # 视频流采集线程
│   │   ├── detector.py         # YOLO 检测器
│   │   └── rules.py            # 规则引擎（预留）
│   ├── utils/
│   │   ├── api_client.py       # HTTP 客户端（异步）
│   │   ├── gemini_client.py    # Gemini API 客户端
│   │   └── visualization.py    # 可视化工具
│   ├── config.yaml             # 客户端配置
│   └── README.md               # 客户端使用说明
│
├── server/                     # Web 后端服务
│   ├── app.py                  # FastAPI 后端服务
│   ├── start.py                # Web 服务启动脚本
│   ├── static/
│   │   └── index.html          # Web 前端页面
│   └── README.md               # 服务端使用说明
│
├── shared/                     # 共享模块
│   ├── schemas.py              # Pydantic 数据模型
│   └── notifier.py             # 报警通知模块
│
├── alerts/                     # 告警图片存储目录
├── requirements-client.txt     # 客户端依赖
├── requirements-server.txt     # 服务端依赖（参考）
└── README.md                   # 本文件
```

## 技术栈

### 客户端（桌面应用）
- **Python 3.10+**
- **OpenCV**: 视频采集和显示
- **Ultralytics YOLOv8**: 人体检测
- **Requests**: HTTP 客户端
- **PyYAML**: 配置管理
- **Pydantic**: 数据验证
- **Google Generative AI**: Gemini API 支持（可选）

### Web 后端服务 ⭐ 新增
- **FastAPI**: Web 框架和 API 服务
- **Uvicorn**: ASGI 服务器
- **OpenCV**: 视频流处理
- **Ultralytics YOLOv8**: 人体检测（复用客户端模块）
- **Threading**: 后台监控服务

### Web 前端 ⭐ 新增
- **HTML5**: 页面结构
- **CSS3**: 样式和布局
- **JavaScript**: 前端交互和轮询更新
- **MJPEG**: 视频流传输协议

### LLM 服务端（远端）
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

### 方式一：Web 服务模式（推荐）⭐ 新增

#### 1. 安装依赖

```bash
pip install fastapi uvicorn
pip install -r requirements-client.txt  # 安装客户端依赖（包含 OpenCV、YOLO 等）
```

#### 2. 配置 LLM 提供商

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

#### 3. 启动 Web 服务

```bash
python server/start.py
```

或者从项目根目录运行：

```bash
cd server
python start.py
```

#### 4. 访问 Web 界面

- 服务启动后会自动打开浏览器访问 `http://127.0.0.1:8123`
- 或手动访问：`http://127.0.0.1:8123`
- API 文档：`http://127.0.0.1:8123/docs`

#### 5. Web 界面功能

- **9宫格监控**：全屏显示最多9路视频源，每个视频源独立显示
- **告警次数显示**：每个视频窗口左上角显示该源的告警次数
- **全屏危险弹窗**：检测到危险动作时，全屏红色弹窗显示告警信息（5秒自动关闭）
- **小窗口警告**：检测到提醒类告警时，在对应视频窗口内显示黄色警告
- **实时视频流**：每个视频源独立的 MJPEG 流实时播放

### 方式二：桌面应用模式

#### 1. 安装客户端依赖

```bash
pip install -r requirements-client.txt
```

#### 2. 配置 LLM 提供商

同 Web 服务模式的配置步骤。

#### 3. 运行客户端

```bash
cd client
python app.py
```

#### 4. 操作说明

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

### 5. 多视频源9宫格监控 ⭐ 新功能
- **多路视频支持**：支持同时监控最多9路视频源（摄像头、视频文件、RTSP流）
- **9宫格布局**：全屏显示，每个视频源占据一个格子，空位显示黑屏
- **独立监控**：每个视频源独立线程、独立状态管理、独立告警统计
- **告警次数显示**：每个视频窗口左上角显示该源的告警次数（半透明覆盖）

### 6. 智能分级告警系统 ⭐ 新功能
- **具体告警信息**：LLM 返回具体场景类型（打架、摔倒、垃圾、积水等）和简短告警语句
- **分级显示**：
  - 🔴 **全屏红色弹窗**：危险情况（打架、摔倒、受伤等），全屏显示5秒后自动关闭
  - 🟡 **小窗口黄色警告**：非危险但需注意的情况（垃圾、积水等），在对应视频窗口内显示
- **智能判断**：根据 `alert_type` 和 `is_danger` 自动判断告警级别，无需手动配置
- **用户友好**：告警信息清晰具体，便于快速了解现场情况和告警来源

## API 端点说明

### Web 后端服务 API

#### 视频流
- `GET /video_feed` - MJPEG 视频流（兼容旧接口，默认视频源0）
- `GET /api/video_feed/{source_id}` - 获取指定视频源的 MJPEG 视频流

#### 告警管理
- `GET /api/alerts` - 获取告警列表（返回最近100条告警，包含 `source_id` 字段）
- `GET /api/alerts/{alert_id}` - 获取指定告警的详细信息
- `GET /api/alerts/{alert_id}/image` - 获取告警对应的截图

#### 系统状态
- `GET /api/status` - 获取系统运行状态（兼容旧接口，返回视频源0的状态）
- `GET /api/status/{source_id}` - 获取指定视频源的状态（FPS、告警次数、连接状态等）
- `GET /api/sources` - 获取所有视频源信息（视频源数量和ID列表）

#### 前端页面
- `GET /` - Web 9宫格监控主页面
- `GET /docs` - API 交互式文档（FastAPI 自动生成）

### API 响应示例

**告警列表** (`GET /api/alerts`)
```json
{
  "alerts": [
    {
      "id": 1,
      "source_id": 0,
      "timestamp": "10:05:23",
      "type": "打架",
      "message": "检测到打架",
      "severity": "high",
      "reasoning": "画面中多人发生肢体冲突...",
      "confidence": 0.85,
      "is_danger": true,
      "image_path": "alerts/alert_20251203_100523_1_s0_xxx.jpg"
    }
  ]
}
```

**视频源状态** (`GET /api/status/{source_id}`)
```json
{
  "fps": 28.5,
  "status": "监控中...",
  "alert_count": 5,
  "analysis_count": 12,
  "person_detection_count": 45,
  "connection_status": "Active"
}
```

**视频源信息** (`GET /api/sources`)
```json
{
  "source_count": 2,
  "sources": [0, 1]
}
```

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

# 视频源配置（支持多视频源）
video:
  # sources 支持多个视频源（列表格式，最多9个）
  # 每个视频源可以是：
  # - 数字（如 0, 1）：摄像头索引
  # - 字符串（如 "test_video.mp4"）：视频文件路径（相对于项目根目录或绝对路径）
  # - RTSP URL（如 "rtsp://user:pass@ip:port/stream"）：外置摄像头RTSP流
  sources: [0, 1, "rtsp://normal:jU8azeo34@192.168.2.7:554/stream1", "data/video.mp4"]
  # 兼容旧配置：如果 sources 不存在，可以使用 source（单个视频源）
  # source: 0
  fps: 30
  width: 640
  height: 480
  loop_video: true  # 视频文件循环播放
  target_fps: 20   # 视频文件播放速度控制
```

## 工作流程

### Web 服务模式

```
1. 启动 Web 服务（start.py）
   ↓
2. 后台监控服务启动（MonitorService）
   ├─ 读取配置中的视频源列表（sources）
   ├─ 为每个视频源创建 SourceMonitor 实例
   └─ 每个 SourceMonitor 独立运行：
       ├─ 视频采集（VideoPipeline）
       ├─ YOLO 检测（PersonDetector）
       ├─ 独立的网络工作线程（NetworkWorker）
       └─ 检测到 Person？
           ↓
       3. 检查冷却时间（5秒）
           ↓ 满足条件？
       4. 图像压缩（640x640, JPEG 80）
           ↓
       5. HTTP 请求（NetworkWorker 异步）
           ↓
       6. LLM 服务端大模型分析（Qwen2-VL / Gemini）
           ↓
       7. 解析返回结果（is_danger, alert_type, alert_message）
           ↓
       8. 判断告警级别（危险/提醒/安全）
           ↓
       9. 保存告警到内存列表（包含 source_id）
           ↓
10. 前端9宫格显示
    ├─ 视频流：每个视频源独立的 MJPEG 流（/api/video_feed/{source_id}）
    ├─ 告警次数：每2秒更新各视频源状态（/api/status/{source_id}）
    ├─ 告警监听：每1秒检查新告警（/api/alerts）
    ├─ 危险告警：全屏红色弹窗（5秒自动关闭）
    └─ 提醒告警：小窗口黄色警告（10秒自动消失）
```

### 桌面应用模式

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
6. LLM 服务端大模型分析（Qwen2-VL / Gemini）
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
- [x] ✅ 分级告警系统（已完成：全屏红色弹窗/小窗口黄色警告）
- [x] ✅ Web 管理界面（已完成：前后端分离架构，9宫格监控界面）
- [x] ✅ 支持多路视频流（已完成：最多9路视频源，9宫格布局）
- [ ] 添加历史记录和回放功能
- [ ] 支持更多报警方式（邮件、短信等）
- [ ] 告警信息持久化存储（数据库）
- [ ] 告警统计分析功能
- [ ] WebSocket 实时推送（替代轮询）
- [ ] 视频源动态添加/删除功能
- [ ] 视频源分组和切换功能

## 相关文档

- [客户端使用说明](client/README.md)
- [项目重构指南](项目重构指南.md)
- [核心功能提取说明](CORE_EXTRACTED_README.md)

## 开发团队

本项目基于端云协同架构设计，实现了从传统规则检测到 AI 大模型仲裁的升级。

## 许可证

[待定]

---

**最后更新**: 2025-12-04  
**状态**: MVP 已完成，系统正常运行 ✅  
**最新功能**: 
- ⭐ **多视频源9宫格监控**：支持最多9路视频源同时监控，全屏9宫格布局
- ⭐ **智能分级告警系统**：全屏红色危险弹窗 + 小窗口黄色提醒警告
- ⭐ **独立视频源管理**：每个视频源独立线程、独立状态、独立告警统计
- ⭐ **告警次数显示**：每个视频窗口左上角实时显示告警次数

