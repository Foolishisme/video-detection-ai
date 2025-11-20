# 核心功能提取文件使用指南

## 文件说明

`core_extracted.py` 包含了从原项目中提取的核心功能，包括：

1. **摄像头连接模块** (`CameraConnector`) - OpenCV通用连接逻辑
2. **报警系统模块** (`AlertNotifier`) - 网络请求和发邮件逻辑

## 功能模块详解

### 1. 摄像头连接模块 (CameraConnector)

#### 功能特点
- ✅ 支持摄像头索引（int）和视频文件路径（str）
- ✅ 自动设置分辨率、帧率等参数
- ✅ 提供简单的帧读取接口
- ✅ 完善的错误处理和资源管理
- ✅ 基于OpenCV，通用性强

#### 使用方法

```python
from core_extracted import CameraConnector

# 创建连接器（使用默认摄像头，索引0）
camera = CameraConnector(source=0, width=640, height=480, fps=30)

# 连接摄像头
if camera.connect():
    # 读取帧
    success, frame = camera.read_frame()
    if success:
        # 处理frame（numpy数组）
        print(f"帧形状: {frame.shape}")
    
    # 获取属性
    props = camera.get_properties()
    print(f"分辨率: {props['width']}x{props['height']}")
    
    # 释放资源
    camera.release()
```

#### 参数说明

- `source`: 
  - `int`: 摄像头索引（0表示默认摄像头，1表示第二个摄像头等）
  - `str`: 视频文件路径（如 `"video.mp4"`）
- `width`: 期望的帧宽度（默认640）
- `height`: 期望的帧高度（默认480）
- `fps`: 期望的帧率（默认30，仅对摄像头有效）

### 2. 报警系统模块 (AlertNotifier)

#### 功能特点
- ✅ 支持多种通知方式：控制台、文件、邮件、Webhook
- ✅ 可配置的通知模板
- ✅ 网络请求（Webhook）功能
- ✅ 邮件发送功能（SMTP）
- ✅ 严重性级别过滤

#### 使用方法

##### 基本使用

```python
from core_extracted import AlertNotifier

# 创建通知器（使用默认配置）
notifier = AlertNotifier()

# 发送报警
alert_data = {
    "rule_name": "异常行为检测",
    "description": "检测到可疑活动",
    "severity": "高",  # "低"、"中"、"高"
    "location": "摄像头1"
}

notifier.send_alert(alert_data)
```

##### 使用配置文件

```python
# 使用自定义配置文件
notifier = AlertNotifier(config_path="config/notification.json")
```

#### 报警数据格式

`alert_data` 字典应包含以下字段：

- `rule_name` (必需): 规则名称
- `description` (必需): 描述信息
- `severity` (必需): 严重性级别（"低"、"中"、"高"）
- `location` (可选): 位置信息
- `timestamp` (可选): 时间戳（默认使用当前时间）

#### 配置说明

##### 邮件配置

在配置文件中启用邮件通知：

```json
{
  "methods": {
    "email": {
      "enabled": true,
      "min_severity": "中",
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "username": "your_email@gmail.com",
      "password": "your_password",
      "from_address": "your_email@gmail.com",
      "to_addresses": ["admin@example.com"],
      "use_tls": true
    }
  }
}
```

##### Webhook配置

在配置文件中启用Webhook通知：

```json
{
  "methods": {
    "webhook": {
      "enabled": true,
      "min_severity": "中",
      "url": "https://your-api.com/webhook",
      "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_token"
      },
      "method": "POST"
    }
  }
}
```

## 完整使用示例

### 示例：摄像头监控 + 异常报警

```python
from core_extracted import CameraConnector, AlertNotifier
import cv2

# 初始化
camera = CameraConnector(source=0, width=640, height=480)
notifier = AlertNotifier()

# 连接摄像头
if camera.connect():
    print("开始监控...")
    
    frame_count = 0
    while True:
        # 读取帧
        success, frame = camera.read_frame()
        if not success:
            break
        
        frame_count += 1
        
        # ============================================
        # 在这里添加你的检测逻辑
        # ============================================
        # 例如：使用YOLO检测、运动检测等
        # detection_result = your_detection_function(frame)
        
        # 模拟检测到异常
        if frame_count % 100 == 0:  # 每100帧检查一次
            # 假设检测到异常
            has_anomaly = True  # 这里应该是你的检测结果
            
            if has_anomaly:
                # 发送报警
                alert_data = {
                    "rule_name": "异常行为检测",
                    "description": f"在第 {frame_count} 帧检测到异常行为",
                    "severity": "高",
                    "location": "摄像头1"
                }
                notifier.send_alert(alert_data)
        
        # 显示帧（可选）
        cv2.imshow('监控画面', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 清理资源
    camera.release()
    cv2.destroyAllWindows()
else:
    print("无法连接摄像头")
```

## 注意事项

### 摄像头连接
1. **摄像头索引**: 如果默认摄像头（索引0）无法使用，尝试使用索引1、2等
2. **视频文件**: 支持常见视频格式（mp4, avi等）
3. **资源释放**: 使用完毕后务必调用 `camera.release()` 释放资源

### 报警系统
1. **触发逻辑**: 报警的**触发逻辑需要在新项目中自定义实现**，本模块只负责发送通知
2. **配置优先级**: 如果提供了配置文件，会使用配置文件；否则使用默认配置
3. **网络请求**: Webhook功能需要安装 `requests` 库：`pip install requests`
4. **邮件发送**: 邮件功能需要配置正确的SMTP服务器信息

## 依赖要求

```txt
opencv-python>=4.0.0
requests>=2.25.0
```

安装命令：
```bash
pip install opencv-python requests
```

## 在新项目中使用

1. **复制文件**: 将 `core_extracted.py` 复制到新项目中
2. **安装依赖**: 安装所需的Python包
3. **导入使用**: 在代码中导入并使用相应模块
4. **自定义触发逻辑**: 根据新项目的需求，实现报警触发逻辑

## 与原项目的区别

- ✅ **简化**: 移除了复杂的触发逻辑和规则引擎
- ✅ **通用**: 保留了通用的连接和通知功能
- ✅ **易用**: 提供了清晰的接口和示例
- ✅ **可扩展**: 触发逻辑可以在新项目中自由实现

## 常见问题

**Q: 如何测试摄像头连接？**
A: 运行 `core_extracted.py` 文件，它会执行示例代码测试摄像头连接。

**Q: 邮件发送失败怎么办？**
A: 检查SMTP配置是否正确，确保：
- SMTP服务器地址和端口正确
- 用户名和密码正确
- 如果使用Gmail，需要启用"允许不够安全的应用"

**Q: Webhook请求失败怎么办？**
A: 检查：
- URL是否正确
- 网络连接是否正常
- 请求头（如Authorization）是否正确

**Q: 如何自定义报警触发逻辑？**
A: 在检测循环中，根据你的检测结果调用 `notifier.send_alert(alert_data)` 即可。

