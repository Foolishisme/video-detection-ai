"""
优化后的 FastAPI 后端服务
主要优化点:
1. 共享 YOLO 检测器 (减少内存占用)
2. 共享网络工作线程池 (避免并发冲突)
3. 视频流缓存 (减少重复编码)
4. 检测任务队列化 (避免 CPU 峰值)
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
from queue import Queue, Empty
from collections import deque

# CPU监控依赖（可选）
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client.core.pipeline import VideoPipeline
from client.core.detector import PersonDetector
from client.utils.api_client import NetworkWorker
from client.utils.gemini_client import GeminiWorker
from shared.notifier import AlertNotifier
from shared.schemas import AlertType

# 配置日志 - 生产环境使用WARNING级别，减少日志输出
logging.basicConfig(
    level=logging.WARNING,  # 改为WARNING，只记录警告和错误
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),  # 输出到文件而不是控制台
        logging.StreamHandler()  # 仍然保留控制台输出，但只输出WARNING以上
    ]
)
logger = logging.getLogger(__name__)

# 如果psutil未安装，记录警告
if not HAS_PSUTIL:
    logger.warning("psutil未安装，CPU监控功能将不可用")

# 创建FastAPI应用
app = FastAPI(title="SmartMonitor API (Optimized)")

# 告警存储
alerts: List[Dict[str, Any]] = []
alert_counter = 0

# 全局监控实例
monitor_instance: Optional['OptimizedMonitorService'] = None


class FrameCache:
    """视频帧缓存,避免重复编码"""
    def __init__(self, maxsize=30):
        self.cache = {}
        self.maxsize = maxsize
        self.lock = threading.Lock()
    
    def get(self, source_id: int) -> Optional[bytes]:
        with self.lock:
            return self.cache.get(source_id)
    
    def set(self, source_id: int, jpeg_data: bytes):
        with self.lock:
            if len(self.cache) >= self.maxsize:
                # 删除最旧的缓存
                oldest = min(self.cache.keys())
                del self.cache[oldest]
            self.cache[source_id] = jpeg_data


class DetectionTaskQueue:
    """
    批量检测任务队列（优化版）
    采用批量推理策略，将多路视频帧合并为batch进行推理，充分利用GPU并行能力
    参考业界NVR系统的批量处理方案
    """
    def __init__(self, detector: PersonDetector, max_queue_size=50, 
                 batch_size=4, max_wait_time=0.05):
        """
        初始化批量检测队列
        
        Args:
            detector: 检测器实例
            max_queue_size: 队列最大容量
            batch_size: 批量大小（建议4-8，根据GPU内存调整）
            max_wait_time: 最大等待时间（秒），用于收集批量任务
        """
        self.detector = detector
        self.task_queue = Queue(maxsize=max_queue_size)
        self.result_dict = {}  # source_id -> (has_person, detections)
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread = None
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
    
    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.warning(f"批量检测任务队列已启动 (批量大小: {self.batch_size}, 最大等待: {self.max_wait_time}s)")
    
    def _worker_loop(self):
        """工作线程:批量处理检测任务"""
        while self.running:
            try:
                # 收集批量任务
                batch = []  # [(source_id, frame), ...]
                batch_frames = []  # [frame, ...]
                start_time = time.time()
                
                # 收集批量任务：最多等待max_wait_time或收集到batch_size个
                while len(batch) < self.batch_size:
                    try:
                        # 计算剩余等待时间
                        elapsed = time.time() - start_time
                        timeout = max(0.01, self.max_wait_time - elapsed)
                        
                        # 如果已经等待足够长时间，即使没收集满也处理
                        if elapsed >= self.max_wait_time and len(batch) > 0:
                            break
                        
                        source_id, frame = self.task_queue.get(timeout=timeout)
                        batch.append(source_id)
                        batch_frames.append(frame)
                        
                    except Empty:
                        # 超时或队列为空
                        if len(batch) > 0:
                            # 有任务就处理，不等待
                            break
                        # 完全空闲时休眠
                        time.sleep(0.05)
                        break
                
                # 批量推理
                if batch_frames:
                    try:
                        # 使用批量检测方法（关键优化点）
                        batch_results = self.detector.detect_batch(batch_frames)
                        
                        # 分发结果
                        with self.lock:
                            for source_id, result in zip(batch, batch_results):
                                self.result_dict[source_id] = result
                    except Exception as e:
                        logger.error(f"批量检测出错: {e}", exc_info=True)
                        # 出错时返回空结果
                        with self.lock:
                            for source_id in batch:
                                self.result_dict[source_id] = (False, [])
                
            except Exception as e:
                logger.error(f"检测任务队列出错: {e}", exc_info=True)
                time.sleep(0.1)
    
    def submit(self, source_id: int, frame: np.ndarray):
        """提交检测任务(非阻塞)"""
        try:
            self.task_queue.put_nowait((source_id, frame))
        except:
            # 队列满时丢弃最旧的任务（FIFO策略）
            try:
                self.task_queue.get_nowait()  # 丢弃最旧的
                self.task_queue.put_nowait((source_id, frame))  # 放入新的
            except:
                pass  # 如果还是失败，直接丢弃
    
    def get_result(self, source_id: int) -> Optional[tuple]:
        """获取检测结果"""
        with self.lock:
            return self.result_dict.get(source_id)
    
    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)


class NetworkWorkerPool:
    """网络工作线程池,避免并发请求LLM"""
    def __init__(self, worker_factory, pool_size=2):
        self.workers = []
        self.current_idx = 0
        self.lock = threading.Lock()
        
        for _ in range(pool_size):
            worker = worker_factory()
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"网络工作线程池已启动 (大小: {pool_size})")
    
    def submit_task(self, frame: np.ndarray, query: str):
        """轮询提交任务到线程池"""
        with self.lock:
            worker = self.workers[self.current_idx]
            self.current_idx = (self.current_idx + 1) % len(self.workers)
        
        worker.submit_task(frame, query)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """从所有worker获取结果"""
        for worker in self.workers:
            result = worker.get_result()
            if result:
                return result
        return None
    
    def stop(self):
        for worker in self.workers:
            worker.stop()


class SourceMonitor:
    """单个视频源的监控实例(优化版)"""
    
    def __init__(self, source_id: int, source: Any, config: Dict[str, Any],
                 detection_queue: DetectionTaskQueue,
                 network_pool: NetworkWorkerPool,
                 alert_notifier: Optional[AlertNotifier],
                 alert_images_dir: Path,
                 frame_cache: FrameCache):
        self.source_id = source_id
        self.source = source
        self.config = config
        self.detection_queue = detection_queue
        self.network_pool = network_pool
        self.alert_notifier = alert_notifier
        self.alert_images_dir = alert_images_dir
        self.frame_cache = frame_cache
        
        self.pipeline: Optional[VideoPipeline] = None
        
        # 状态管理
        self.last_upload_time = 0.0
        self.cooldown_seconds = config.get('cooldown_seconds', 5.0)
        self.current_status = "初始化中..."
        
        # 当前帧
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        
        # 统计信息
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        self.alert_count = 0
        self.analysis_count = 0
        self.person_detection_count = 0
        
        # CPU监控
        self.cpu_percent = 0.0
        self.last_cpu_check = time.time()
        
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
    
    def _get_alert_severity(self, result: Dict[str, Any]) -> Optional[str]:
        is_danger = result.get('is_danger', False)
        if is_danger:
            return "high"
        
        alert_type = result.get('alert_type', '')
        reminder_keywords = ['垃圾', '提醒', '杂物', '积水']
        if alert_type and any(keyword in alert_type for keyword in reminder_keywords):
            return "low"
        
        return None
    
    def _save_alert_image(self, frame: np.ndarray, result: Dict[str, Any]) -> str:
        global alert_counter
        alert_counter += 1
        
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            reasoning_short = result.get('reasoning', '危险')[:20].replace(' ', '_').replace('/', '_')
            filename = f"alert_{timestamp}_{alert_counter}_s{self.source_id}_{reasoning_short}.jpg"
            filepath = self.alert_images_dir / filename
            
            cv2.imwrite(str(filepath), frame)
            return str(filepath.relative_to(project_root))
        except Exception as e:
            logger.error(f"保存告警图片失败: {e}")
            return ""
    
    def _add_alert(self, result: Dict[str, Any], frame: Optional[np.ndarray] = None):
        global alerts, alert_counter
        
        alert_counter += 1
        severity = self._get_alert_severity(result)
        
        alert_data = {
            "id": alert_counter,
            "source_id": self.source_id,
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
        
        alerts.insert(0, alert_data)
        
        if len(alerts) > 100:
            del alerts[100:]
        
        if severity == "high" and self.alert_notifier:
            alert_notification = {
                "rule_name": "危险动作检测",
                "description": alert_data["message"] or alert_data["type"],
                "severity": "高",
                "location": f"监控摄像头 {self.source_id}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.alert_notifier.send_alert(alert_notification)
    
    def _monitor_loop(self):
        """监控主循环"""
        self.running = True
        # 只在启动时打印一次
        logger.warning(f"视频源 {self.source_id} 开始监控...")  # 使用WARNING确保能看到
        self.current_status = "监控中..."
        
        self.frame_count = 0
        self.fps_start_time = time.time()
        last_fps_update = time.time()
        
        # 检测策略:每秒检测1次
        target_detection_interval = 1.0
        last_detection_time = 0.0
        
        # 添加统计日志间隔，避免频繁打印
        last_stats_log = time.time()
        stats_log_interval = 60.0  # 每60秒打印一次统计信息
        
        try:
            while self.running:
                success, frame = self.pipeline.read_frame()
                if not success:
                    time.sleep(0.1)  # 增加失败时的休眠时间，减少空转CPU占用
                    continue
                
                # FPS计算（静默，不打印）
                self.frame_count += 1
                current_time = time.time()
                if current_time - last_fps_update >= 1.0:
                    elapsed = current_time - self.fps_start_time
                    if elapsed > 0:
                        self.current_fps = self.frame_count / elapsed
                    self.frame_count = 0
                    self.fps_start_time = current_time
                    last_fps_update = current_time
                
                # CPU使用率监控（每10秒检查一次）
                if current_time - self.last_cpu_check >= 10.0:
                    if HAS_PSUTIL:
                        try:
                            self.cpu_percent = psutil.Process().cpu_percent(interval=0.1)
                            self.last_cpu_check = current_time
                        except Exception:
                            pass
                    else:
                        self.cpu_percent = 0.0
                        self.last_cpu_check = current_time
                
                # 定期打印统计信息（每60秒一次）
                if current_time - last_stats_log >= stats_log_interval:
                    logger.warning(
                        f"[视频源{self.source_id}] FPS: {self.current_fps:.1f}, "
                        f"告警: {self.alert_count}, 分析: {self.analysis_count}, "
                        f"检测人数: {self.person_detection_count}, "
                        f"CPU: {self.cpu_percent:.1f}%"
                    )
                    last_stats_log = current_time
                
                # 基于时间的检测策略:每秒检测1次
                should_detect = (current_time - last_detection_time) >= target_detection_interval
                
                if should_detect:
                    # 批量处理优化：只在队列未满时才提交，避免浪费复制操作
                    # 注意：必须复制，因为后续可能会修改frame（绘制检测框等）
                    if not self.detection_queue.task_queue.full():
                        self.detection_queue.submit(self.source_id, frame.copy())
                    # 队列满时跳过本次检测，等待下次机会（批量处理会自动处理积压）
                    last_detection_time = current_time
                
                # 获取检测结果（静默处理）
                result = self.detection_queue.get_result(self.source_id)
                if result:
                    has_person, detections = result
                    
                    if has_person:
                        self.person_detection_count += 1
                        # 使用共享检测器绘制检测框，避免重复创建检测器实例
                        # 注意：draw_detections需要检测器实例，但这里可以优化
                        # 暂时保留原有逻辑，但减少不必要的实例创建
                        if not hasattr(self, '_temp_detector'):
                            from client.core.detector import PersonDetector
                            self._temp_detector = PersonDetector()
                        frame = self._temp_detector.draw_detections(frame, detections)
                        
                        time_since_last = current_time - self.last_upload_time
                        if time_since_last >= self.cooldown_seconds:
                            prompt = f"""分析画面中的人物姿态和行为..."""
                            
                            # 仅在需要上传时复制帧
                            self.network_pool.submit_task(frame.copy(), prompt)
                            self.current_status = "正在分析..."
                            self.last_upload_time = current_time
                
                # 检查分析结果
                analysis_result = self.network_pool.get_result()
                if analysis_result:
                    self.analysis_count += 1
                    severity = self._get_alert_severity(analysis_result)
                    
                    if severity == "high":
                        self._add_alert(analysis_result, frame.copy())
                        self.alert_count += 1
                        self.current_status = "危险告警!"
                        # 只在有告警时才打印
                        logger.warning(f"[视频源{self.source_id}] 危险告警: {analysis_result.get('alert_message')}")
                    elif severity == "low":
                        self._add_alert(analysis_result, frame.copy())
                        self.current_status = "提醒"
                        logger.warning(f"[视频源{self.source_id}] 提醒: {analysis_result.get('alert_message')}")
                    else:
                        self.current_status = "安全"
                
                # 更新当前帧（优化：减少锁持有时间，使用高效复制）
                # 只在需要时才更新（避免频繁复制）
                if self.frame_count % 2 == 0:  # 每2帧更新一次，降低更新频率
                    with self.frame_lock:
                        # 如果帧已存在且大小相同，可以复用，否则需要复制
                        if self.current_frame is None or self.current_frame.shape != frame.shape:
                            self.current_frame = frame.copy()
                        else:
                            # 直接复制数据，避免重新分配内存（比copy()更高效）
                            np.copyto(self.current_frame, frame)
                
                # 更新帧缓存 - 降低编码频率
                if self.frame_count % 3 == 0:
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ret:
                        self.frame_cache.set(self.source_id, buffer.tobytes())
                
                # 增加休眠时间，降低CPU占用（从30fps降到10fps）
                time.sleep(0.1)  # 约10fps，大幅降低CPU占用
                
        except Exception as e:
            logger.error(f"视频源 {self.source_id} 监控循环出错: {e}", exc_info=True)
        finally:
            self.running = False
            logger.warning(f"视频源 {self.source_id} 已停止")
    
    def initialize(self) -> bool:
        try:
            video_config = self.config.get('video', {})
            source = self.source
            
            if isinstance(source, list):
                source = source[0] if source else 0
            
            if isinstance(source, str) and not source.startswith('rtsp://'):
                source_path = Path(source)
                if not source_path.is_absolute():
                    source_path = project_root / source
                if not source_path.exists():
                    logger.error(f"视频源 {self.source_id}: 文件不存在: {source_path}")
                    return False
                source = str(source_path)
            
            self.pipeline = VideoPipeline(
                source=source,
                width=640,
                height=480,
                fps=video_config.get('fps', 30),
                loop_video=video_config.get('loop_video', True),
                target_fps=video_config.get('target_fps', 0)
            )
            
            if not self.pipeline.start():
                logger.error(f"视频源 {self.source_id}: 管道启动失败")
                return False
            
            logger.info(f"视频源 {self.source_id} 初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"视频源 {self.source_id} 初始化失败: {e}")
            return False
    
    def start(self) -> bool:
        if not self.initialize():
            return False
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True
    
    def stop(self):
        self.running = False
        if self.pipeline:
            self.pipeline.stop()
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "fps": round(self.current_fps, 1),
            "status": self.current_status,
            "alert_count": self.alert_count,
            "analysis_count": self.analysis_count,
            "person_detection_count": self.person_detection_count,
            "connection_status": "Active" if self.running else "Inactive",
            "cpu_percent": round(self.cpu_percent, 1)
        }


class OptimizedMonitorService:
    """优化后的监控服务"""
    
    def __init__(self, config_path: str = "client/config.yaml"):
        self.config = self._load_config(config_path)
        self.sources: Dict[int, SourceMonitor] = {}
        
        # 共享组件
        self.shared_detector: Optional[PersonDetector] = None
        self.detection_queue: Optional[DetectionTaskQueue] = None
        self.network_pool: Optional[NetworkWorkerPool] = None
        self.alert_notifier: Optional[AlertNotifier] = None
        self.frame_cache = FrameCache(maxsize=30)
        
        self.alert_images_dir = project_root / "alerts"
        self.alert_images_dir.mkdir(exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            config_file = project_root / config_path
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"加载配置失败: {e}")
            return {'video': {'sources': [0]}, 'cooldown_seconds': 5.0}
    
    def _create_network_worker(self) -> Any:
        llm_provider = self.config.get('llm_provider', 'remote')
        
        if llm_provider == 'gemini':
            gemini_config = self.config.get('gemini', {})
            api_key = gemini_config.get('api_key') or os.getenv("GEMINI_API_KEY")
            model_name = gemini_config.get('model_name', 'gemini-2.0-flash-exp')
            return GeminiWorker(api_key=api_key, model_name=model_name)
        else:
            server_config = self.config.get('server', {})
            url = f"http://{server_config.get('host', 'localhost')}:{server_config.get('port', 8000)}{server_config.get('endpoint', '/chat')}"
            return NetworkWorker(server_url=url)
    
    def initialize(self) -> bool:
        try:
            # 1. 初始化共享检测器
            logger.warning("初始化共享YOLO检测器...")  # 只打印关键信息
            self.shared_detector = PersonDetector(model_path="yolov8n.pt")
            
            # 2. 获取视频源数量（用于优化批量处理参数）
            video_config = self.config.get('video', {})
            sources = video_config.get('sources') or [video_config.get('source', 0)]
            if not isinstance(sources, list):
                sources = [sources]
            sources = sources[:9]
            num_sources = len(sources)
            
            # 根据视频源数量动态调整批量大小
            # 批量大小：4路以下用4，4-9路用6，更多路用8
            if num_sources <= 4:
                batch_size = 4
            elif num_sources <= 9:
                batch_size = 6
            else:
                batch_size = 8
            
            # 最大等待时间：批量大小越大，等待时间可以稍长
            max_wait_time = 0.05 if batch_size <= 4 else 0.08
            
            # 3. 初始化批量检测任务队列（优化版）
            self.detection_queue = DetectionTaskQueue(
                self.shared_detector,
                max_queue_size=50,
                batch_size=batch_size,
                max_wait_time=max_wait_time
            )
            self.detection_queue.start()
            
            # 4. 初始化网络工作线程池
            self.network_pool = NetworkWorkerPool(
                self._create_network_worker,
                pool_size=2
            )
            
            # 5. 初始化报警通知器
            self.alert_notifier = AlertNotifier()
            
            # 6. 初始化视频源
            
            logger.warning(f"初始化 {len(sources)} 个视频源")
            
            for idx, source in enumerate(sources):
                source_monitor = SourceMonitor(
                    source_id=idx,
                    source=source,
                    config=self.config,
                    detection_queue=self.detection_queue,
                    network_pool=self.network_pool,
                    alert_notifier=self.alert_notifier,
                    alert_images_dir=self.alert_images_dir,
                    frame_cache=self.frame_cache
                )
                self.sources[idx] = source_monitor
            
            logger.warning("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    def start(self) -> bool:
        if not self.initialize():
            return False
        
        for source_id, source_monitor in self.sources.items():
            if not source_monitor.start():
                logger.error(f"视频源 {source_id} 启动失败")
                return False
        
        logger.warning(f"已启动 {len(self.sources)} 个视频源监控")
        return True
    
    def stop(self):
        for source_monitor in self.sources.values():
            source_monitor.stop()
        
        if self.detection_queue:
            self.detection_queue.stop()
        
        if self.network_pool:
            self.network_pool.stop()
    
    def get_source_count(self) -> int:
        return len(self.sources)
    
    def get_cached_frame_jpeg(self, source_id: int) -> Optional[bytes]:
        """从缓存获取JPEG数据"""
        return self.frame_cache.get(source_id)
    
    def get_source_status(self, source_id: int) -> Optional[Dict[str, Any]]:
        if source_id in self.sources:
            return self.sources[source_id].get_status()
        return None


# === API端点 ===

@app.on_event("startup")
async def startup_event():
    global monitor_instance
    monitor_instance = OptimizedMonitorService()
    if not monitor_instance.start():
        logger.error("监控服务启动失败")


@app.on_event("shutdown")
async def shutdown_event():
    global monitor_instance
    if monitor_instance:
        monitor_instance.stop()


def generate_frames_optimized(source_id: int = 0):
    """优化的视频流生成器:使用缓存减少编码"""
    while True:
        if monitor_instance:
            # 优先从缓存读取
            jpeg_data = monitor_instance.get_cached_frame_jpeg(source_id)
            
            if jpeg_data:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg_data + b'\r\n')
            else:
                # 缓存未命中,生成黑屏
                black = np.zeros((480, 640, 3), dtype=np.uint8)
                ret, buf = cv2.imencode('.jpg', black, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
        
        time.sleep(0.1)  # 降低到10fps，减少CPU占用


@app.get("/api/video_feed/{source_id}")
async def video_feed_by_id(source_id: int):
    return StreamingResponse(
        generate_frames_optimized(source_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/alerts")
async def get_alerts():
    return {"alerts": alerts}


@app.get("/api/status/{source_id}")
async def get_source_status(source_id: int):
    if monitor_instance:
        status = monitor_instance.get_source_status(source_id)
        if status:
            return status
    return {"error": f"视频源 {source_id} 不存在"}


@app.get("/api/sources")
async def get_sources():
    if monitor_instance:
        return {
            "source_count": monitor_instance.get_source_count(),
            "sources": list(range(monitor_instance.get_source_count()))
        }
    return {"error": "服务未启动", "source_count": 0, "sources": []}


@app.get("/api/alerts/{alert_id}/image")
async def get_alert_image(alert_id: int):
    for alert in alerts:
        if alert["id"] == alert_id and alert.get("image_path"):
            image_path = project_root / alert["image_path"]
            if image_path.exists():
                return FileResponse(str(image_path))
    return {"error": "图片不存在"}


static_dir = project_root / "server" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_file = static_dir / "index.html"
    if html_file.exists():
        with open(html_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>SmartMonitor API (Optimized)</h1>"
