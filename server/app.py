"""
FastAPI 后端服务
提供视频流、告警日志、系统状态等API
"""

import cv2
import yaml
import logging
import time
import sys
import os
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import threading

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client.core.pipeline import VideoPipeline
from client.core.detector import PersonDetector
from client.utils.api_client import NetworkWorker
from client.utils.gemini_client import GeminiWorker
from client.utils.visualization import (
    draw_alert_overlay,
    draw_enhanced_overlay
)
# 修复导入路径 - 根据你的项目结构调整
try:
    from core_extracted import AlertNotifier
except ImportError:
    # 如果 core_extracted 不存在，尝试其他可能的路径
    try:
        from client.core_extracted import AlertNotifier
    except ImportError:
        # 提供一个简单的默认实现
        class AlertNotifier:
            def send_alert(self, alert_data):
                logger.warning(f"AlertNotifier not available. Alert: {alert_data}")

from shared.schemas import AlertType


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="SmartMonitor API")

# 告警存储（内存列表，最多保留100条）
alerts: List[Dict[str, Any]] = []
alert_counter = 0

# 全局监控实例
monitor_instance: Optional['MonitorService'] = None


class MonitorService:
    """监控服务核心类"""
    
    def __init__(self, config_path: str = "client/config.yaml"):
        """初始化监控服务"""
        self.config = self._load_config(config_path)
        self.pipeline: Optional[VideoPipeline] = None
        self.detector: Optional[PersonDetector] = None
        self.network_worker: Optional[Any] = None
        self.alert_notifier: Optional[AlertNotifier] = None
        
        # 状态管理
        self.last_upload_time = 0.0
        self.cooldown_seconds = self.config.get('cooldown_seconds', 5.0)
        self.current_status = "初始化中..."
        self.last_analysis_result: Optional[Dict[str, Any]] = None
        
        # 当前帧（用于视频流）
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        
        # 统计信息
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        self.alert_count = 0
        self.analysis_count = 0
        self.person_detection_count = 0
        
        # 运行标志
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 告警图片目录
        self.alert_images_dir = project_root / "alerts"
        self.alert_images_dir.mkdir(exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            config_file = project_root / config_path
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            return {
                'llm_provider': config.get('llm_provider', 'remote'),
                'server': config.get('server', {}),
                'gemini': config.get('gemini', {}),
                'thresholds': config.get('thresholds', {}),
                'video': config.get('video', {}),
                'cooldown_seconds': config.get('cooldown_seconds', 5.0)
            }
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}，使用默认配置")
            return {
                'server': {'host': 'localhost', 'port': 8000, 'endpoint': '/chat'},
                'video': {'source': 0, 'fps': 30},
                'cooldown_seconds': 5.0
            }
    
    def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            # 1. 初始化视频管道
            video_config = self.config.get('video', {})
            source = video_config.get('source', 0)
            
            if isinstance(source, str):
                # 检查是否是 RTSP URL
                if source.startswith('rtsp://'):
                    # RTSP URL，直接使用
                    logger.info(f"检测到 RTSP 视频源: {source}")
                else:
                    # 假设是文件路径，检查文件是否存在
                    source_path = Path(source)
                    if not source_path.is_absolute():
                        source_path = project_root / source
                    
                    if not source_path.exists():
                        logger.error(f"视频文件不存在: {source_path}")
                        return False
                    
                    source = str(source_path)
            
            target_fps = video_config.get('target_fps', 0)
            
            self.pipeline = VideoPipeline(
                source=source,
                width=640,
                height=480,
                fps=video_config.get('fps', 30),
                loop_video=video_config.get('loop_video', True),
                target_fps=target_fps
            )
            
            if not self.pipeline.start():
                logger.error("视频管道启动失败")
                return False
            
            # 2. 初始化YOLO检测器
            model_path = "yolov8n.pt"
            self.detector = PersonDetector(model_path=model_path)
            
            # 3. 初始化LLM工作线程
            llm_provider = self.config.get('llm_provider', 'remote')
            
            if llm_provider == 'gemini':
                gemini_config = self.config.get('gemini', {})
                api_key = gemini_config.get('api_key')
                
                if not api_key or api_key == "your-api-key" or api_key.strip() == "":
                    api_key = os.getenv("GEMINI_API_KEY")
                
                model_name = gemini_config.get('model_name', 'gemini-2.0-flash-exp')
                self.network_worker = GeminiWorker(api_key=api_key, model_name=model_name)
            else:
                server_config = self.config.get('server', {})
                server_url = f"http://{server_config.get('host', 'localhost')}:{server_config.get('port', 8000)}{server_config.get('endpoint', '/chat')}"
                self.network_worker = NetworkWorker(server_url=server_url)
            
            self.network_worker.start(callback=self._on_analysis_result)
            
            # 4. 初始化报警通知器
            self.alert_notifier = AlertNotifier()
            
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    def _on_analysis_result(self, result: Dict[str, Any]):
        """分析结果回调"""
        self.last_analysis_result = result
    
    def _get_alert_severity(self, result: Dict[str, Any]) -> Optional[str]:
        """判断告警级别"""
        is_danger = result.get('is_danger', False)
        if is_danger:
            return "high"
        
        alert_type = result.get('alert_type', '')
        reminder_keywords = ['垃圾', '提醒', '杂物']
        if alert_type and any(keyword in alert_type for keyword in reminder_keywords):
            return "low"
        
        return None
    
    def _save_alert_image(self, frame: np.ndarray, result: Dict[str, Any]) -> str:
        """保存告警图片，返回文件路径"""
        global alert_counter
        alert_counter += 1
        
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            reasoning_short = result.get('reasoning', '危险')[:20].replace(' ', '_').replace('/', '_')
            filename = f"alert_{timestamp}_{alert_counter}_{reasoning_short}.jpg"
            filepath = self.alert_images_dir / filename
            
            cv2.imwrite(str(filepath), frame)
            logger.info(f"告警图片已保存: {filepath}")
            return str(filepath.relative_to(project_root))
        except Exception as e:
            logger.error(f"保存告警图片失败: {e}")
            return ""
    
    def _add_alert(self, result: Dict[str, Any], frame: Optional[np.ndarray] = None):
        """添加告警到列表"""
        global alerts, alert_counter
        
        alert_counter += 1
        severity = self._get_alert_severity(result)
        
        alert_data = {
            "id": alert_counter,
            "timestamp": time.strftime("%H:%M:%S"),
            "type": result.get('alert_type', ''),
            "message": result.get('alert_message', ''),
            "severity": severity or "safe",
            "reasoning": result.get('reasoning', ''),
            "confidence": result.get('confidence', 0.5),
            "is_danger": result.get('is_danger', False),
            "image_path": ""
        }
        
        if frame is not None:
            image_path = self._save_alert_image(frame, result)
            alert_data["image_path"] = image_path
        
        alerts.insert(0, alert_data)  # 插入到开头
        
        # 只保留最近100条 - 修复：使用切片而不是重新赋值
        if len(alerts) > 100:
            del alerts[100:]  # 删除索引100之后的所有元素
        
        # 触发报警通知
        if severity == "high" and self.alert_notifier:
            alert_notification = {
                "rule_name": "危险动作检测",
                "description": alert_data["message"] or alert_data["type"],
                "severity": "高",
                "location": "监控摄像头",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.alert_notifier.send_alert(alert_notification)
    
    def _monitor_loop(self):
        """监控主循环（在独立线程中运行）"""
        self.running = True
        logger.info("开始监控...")
        self.current_status = "监控中..."
        
        self.frame_count = 0
        self.fps_start_time = time.time()
        last_fps_update = time.time()
        
        try:
            while self.running:
                # 1. 读取帧
                success, frame = self.pipeline.read_frame()
                if not success:
                    time.sleep(0.01)
                    continue
                
                # FPS计算
                self.frame_count += 1
                current_time = time.time()
                if current_time - last_fps_update >= 1.0:
                    elapsed = current_time - self.fps_start_time
                    if elapsed > 0:
                        self.current_fps = self.frame_count / elapsed
                    self.frame_count = 0
                    self.fps_start_time = current_time
                    last_fps_update = current_time
                
                # 2. YOLO检测
                has_person, detections = self.detector.detect(frame)
                
                if has_person:
                    self.person_detection_count += 1
                    frame = self.detector.draw_detections(frame, detections)
                
                # 3. 检查是否需要发送到服务端分析
                time_since_last_upload = current_time - self.last_upload_time
                
                if has_person and time_since_last_upload >= self.cooldown_seconds:
                    frame_copy = frame.copy()
                    
                    prompt = f"""你是一个专业的安防监控系统分析专家。监测系统检测到画面中可能发生 {AlertType.PERSON_DETECTED}。

请仔细分析画面中的人物姿态、行为和场景，判断具体情况并分类。

判断标准：
- SAFE（安全）的情况：
  * 人物在做瑜伽、拉伸等运动
  * 人物在睡觉或休息
  * 人物主动躺下或坐下
  * 人物正常活动，无明显异常

- DANGER（危险）的情况：
  * 人物表现出失去平衡、突然倒地 -> 类型：摔倒
  * 人物之间发生肢体冲突、打斗 -> 类型：打架
  * 人物表现出痛苦、无法动弹 -> 类型：受伤
  * 人物处于异常姿态，疑似受伤 -> 类型：异常姿态
  * 其他危险行为

- REMINDER（提醒）的情况：
  * 地上有垃圾、杂物 -> 类型：垃圾
  * 其他需要提醒但不危险的情况

请以严格的 JSON 格式返回分析结果：
{{
    "is_danger": true/false,
    "alert_type": "具体类型，如：打架、摔倒、垃圾、安全等（简短，2-4个字）",
    "alert_message": "简短的告警语句（10字以内），如：'检测到打架'、'有人摔倒'、'地上有垃圾'等",
    "reasoning": "详细的分析说明，解释为什么判定为安全或危险",
    "confidence": 0.0-1.0之间的浮点数，表示判断的置信度
}}

只返回 JSON，不要包含其他文字。"""
                    
                    self.network_worker.submit_task(frame=frame_copy, query=prompt)
                    self.current_status = "正在分析..."
                    self.last_upload_time = current_time
                
                # 4. 检查分析结果
                result = self.network_worker.get_result()
                if result:
                    self.analysis_count += 1
                    self.current_status = "分析完成"
                    
                    severity = self._get_alert_severity(result)
                    
                    if severity == "high":
                        self._add_alert(result, frame.copy())
                        self.alert_count += 1
                        self.current_status = "危险告警!"
                    elif severity == "low":
                        self._add_alert(result, frame.copy())
                        self.current_status = "提醒"
                    else:
                        self.current_status = "安全"
                    
                    self.last_analysis_result = result
                
                # 5. 绘制信息覆盖层（已移除，避免与状态栏信息重叠）
                # info_lines = [
                #     f"帧率: {self.current_fps:.1f} FPS",
                #     f"状态: {self.current_status}",
                #     f"告警次数: {self.alert_count}",
                #     f"分析次数: {self.analysis_count}",
                # ]
                # if has_person:
                #     info_lines.append(f"检测到人数: {len(detections)}")
                # 
                # frame = draw_enhanced_overlay(frame, info_lines, position=(10, 30))
                
                # 如果有告警，绘制告警覆盖层（已移除，避免与状态栏信息重叠）
                # if self.last_analysis_result:
                #     severity = self._get_alert_severity(self.last_analysis_result)
                #     if severity:
                #         alert_message = self.last_analysis_result.get('alert_message', '')
                #         if alert_message:
                #             frame = draw_alert_overlay(frame, alert_message, severity=severity)
                
                # 6. 更新当前帧（用于视频流）
                with self.frame_lock:
                    self.current_frame = frame.copy()
                
                time.sleep(0.01)  # 避免CPU占用过高
                
        except Exception as e:
            logger.error(f"监控循环出错: {e}", exc_info=True)
        finally:
            self.running = False
    
    def start(self) -> bool:
        """启动监控服务"""
        if not self.initialize():
            return False
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True
    
    def stop(self):
        """停止监控服务"""
        self.running = False
        if self.pipeline:
            self.pipeline.stop()
        if self.network_worker:
            self.network_worker.stop()
        logger.info("监控服务已停止")
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """获取当前帧"""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "fps": round(self.current_fps, 1),
            "status": self.current_status,
            "alert_count": self.alert_count,
            "analysis_count": self.analysis_count,
            "person_detection_count": self.person_detection_count,
            "connection_status": "Active" if self.running else "Inactive"
        }


# API端点

@app.on_event("startup")
async def startup_event():
    """启动时初始化监控服务"""
    global monitor_instance
    monitor_instance = MonitorService()
    if not monitor_instance.start():
        logger.error("监控服务启动失败")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    global monitor_instance
    if monitor_instance:
        monitor_instance.stop()


def generate_frames():
    """生成MJPEG视频流"""
    while True:
        if monitor_instance:
            frame = monitor_instance.get_current_frame()
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)  # 约30fps


@app.get("/video_feed")
async def video_feed():
    """MJPEG视频流端点"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/alerts")
async def get_alerts():
    """获取告警列表"""
    return {"alerts": alerts}


@app.get("/api/alerts/{alert_id}")
async def get_alert_detail(alert_id: int):
    """获取告警详情"""
    for alert in alerts:
        if alert["id"] == alert_id:
            return alert
    return {"error": "告警不存在"}


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    if monitor_instance:
        return monitor_instance.get_status()
    return {"error": "监控服务未启动"}


@app.get("/api/alerts/{alert_id}/image")
async def get_alert_image(alert_id: int):
    """获取告警图片"""
    for alert in alerts:
        if alert["id"] == alert_id and alert.get("image_path"):
            image_path = project_root / alert["image_path"]
            if image_path.exists():
                return FileResponse(str(image_path))
    return {"error": "图片不存在"}


# 静态文件服务
static_dir = project_root / "server" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回前端页面"""
    html_file = static_dir / "index.html"
    if html_file.exists():
        with open(html_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>SmartMonitor API</h1><p>前端页面未找到</p>"