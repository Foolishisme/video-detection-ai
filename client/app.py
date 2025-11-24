"""
智能监控主程序（边缘端）
基于端云协同架构：本地YOLO初筛 + 云端大模型仲裁

核心特性：
- 异步非阻塞：视频流采集与显示（Main Thread）与网络请求（Worker Thread）完全分离
- 事件驱动：仅当检测到Person且满足冷却时间时，才触发上传
- 数据压缩：上传前将图像Resize至640x640并进行JPEG压缩（Quality=80）
"""

import cv2
import yaml
import logging
import time
import sys
import os
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client.core.pipeline import VideoPipeline
from client.core.detector import PersonDetector
from client.utils.api_client import NetworkWorker
from client.utils.gemini_client import GeminiWorker
from client.utils.visualization import (
    draw_status_overlay,
    draw_alert_overlay,
    draw_analysis_result,
    draw_enhanced_overlay
)
from core_extracted import AlertNotifier
from shared.schemas import AlertType


class SmartMonitor:
    """
    智能监控系统主类
    整合视频采集、YOLO检测、网络请求和报警功能
    """
    
    def __init__(self, config_path: str = "client/config.yaml"):
        """
        初始化监控系统
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 初始化组件
        self.pipeline: Optional[VideoPipeline] = None
        self.detector: Optional[PersonDetector] = None
        # network_worker 可以是 NetworkWorker 或 GeminiWorker
        self.network_worker: Optional[Any] = None
        self.alert_notifier: Optional[AlertNotifier] = None
        
        # 状态管理
        self.last_upload_time = 0.0  # 上次上传时间（用于控制上传频率）
        self.last_alert_time = 0.0  # 上次报警时间（用于控制告警频率）
        self.cooldown_seconds = self.config.get('cooldown_seconds', 5.0)
        self.alert_cooldown_seconds = 2.0  # 告警冷却时间（秒），避免同一危险情况重复告警
        self.current_status = "初始化中..."
        self.last_analysis_result: Optional[Dict[str, Any]] = None
        
        # 统计信息
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        self.last_fps_update = time.time()
        self.alert_count = 0  # 告警次数
        self.analysis_count = 0  # 分析请求次数
        self.person_detection_count = 0  # 检测到人的次数
        
        # 图片保存配置
        self.save_alert_images = True  # 是否保存告警图片
        self.alert_images_dir = Path("alerts")
        if self.save_alert_images:
            self.alert_images_dir.mkdir(exist_ok=True)
        
        # 告警显示时间跟踪
        self.alert_display_start_time: Optional[float] = None  # 告警开始显示的时间
        self.alert_display_duration: float = 5.0  # 告警显示持续时间（秒）
        self.last_alert_result: Optional[Dict[str, Any]] = None  # 最后一次告警结果
        
        # 运行标志
        self.running = False
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 合并配置
            merged_config = {
                'llm_provider': config.get('llm_provider', 'remote'),  # 默认使用远端服务器
                'server': config.get('server', {}),
                'gemini': config.get('gemini', {}),
                'thresholds': config.get('thresholds', {}),
                'video': config.get('video', {}),
                'cooldown_seconds': config.get('cooldown_seconds', 5.0)  # 默认5秒冷却
            }
            
            return merged_config
        except Exception as e:
            self.logger.warning(f"加载配置文件失败: {e}，使用默认配置")
            return {
                'server': {'host': 'localhost', 'port': 8000, 'endpoint': '/chat'},
                'video': {'source': 0, 'fps': 30},
                'cooldown_seconds': 5.0
            }
    
    def initialize(self) -> bool:
        """
        初始化所有组件
        
        Returns:
            bool: 初始化成功返回True
        """
        try:
            # 1. 初始化视频管道
            video_config = self.config.get('video', {})
            source = video_config.get('source', 0)
            
            # 如果 source 是字符串，检查文件是否存在
            if isinstance(source, str):
                source_path = Path(source)
                if not source_path.is_absolute():
                    # 相对路径，从项目根目录查找
                    source_path = project_root / source
                
                if not source_path.exists():
                    self.logger.error(f"视频文件不存在: {source_path}")
                    self.logger.info("提示：请将视频文件放在项目根目录，或在配置中使用绝对路径")
                    return False
                
                source = str(source_path)
                self.logger.info(f"使用视频文件作为输入源: {source}")
            
            # 获取目标帧率（用于视频文件播放速度控制）
            target_fps = video_config.get('target_fps', 0)  # 0表示不控制速度
            
            self.pipeline = VideoPipeline(
                source=source,
                width=640,
                height=480,
                fps=video_config.get('fps', 30),
                loop_video=video_config.get('loop_video', True),
                target_fps=target_fps  # 传递目标帧率到采集线程
            )
            
            if not self.pipeline.start():
                self.logger.error("视频管道启动失败")
                return False
            
            # 2. 初始化YOLO检测器
            model_path = "yolov8n.pt"  # 可以使用yolov8n-pose.pt如果需要姿态检测
            self.detector = PersonDetector(model_path=model_path)
            
            # 3. 初始化 LLM 工作线程（根据配置选择）
            llm_provider = self.config.get('llm_provider', 'remote')
            
            if llm_provider == 'gemini':
                # 使用 Gemini API
                gemini_config = self.config.get('gemini', {})
                api_key = gemini_config.get('api_key')  # 如果配置中有，优先使用
                model_name = gemini_config.get('model_name', 'gemini-2.0-flash-exp')
                
                self.logger.info(f"使用 Gemini API，模型: {model_name}")
                self.network_worker = GeminiWorker(
                    api_key=api_key,
                    model_name=model_name
                )
            else:
                # 使用远端 Linux LLM 服务器（默认）
                server_config = self.config.get('server', {})
                server_url = f"http://{server_config.get('host', 'localhost')}:{server_config.get('port', 8000)}{server_config.get('endpoint', '/chat')}"
                self.logger.info(f"使用远端 LLM 服务器: {server_url}")
                self.network_worker = NetworkWorker(server_url=server_url)
            
            self.network_worker.start(callback=self._on_analysis_result)
            
            # 4. 初始化报警通知器
            self.alert_notifier = AlertNotifier()
            
            self.logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            return False
    
    def _on_analysis_result(self, result: Dict[str, Any]):
        """
        网络工作线程的回调函数，当收到服务端分析结果时调用
        
        Args:
            result: 服务端返回的分析结果字典
        """
        self.last_analysis_result = result
    
    def _trigger_alert(self, result: Dict[str, Any], frame: Optional[np.ndarray] = None):
        """
        触发报警
        
        Args:
            result: 分析结果
            frame: 当前帧（用于保存告警图片）
        """
        current_time = time.time()
        
        # 检查告警冷却时间（避免同一危险情况重复告警）
        if current_time - self.last_alert_time < self.alert_cooldown_seconds:
            self.logger.debug(f"告警冷却中，距离上次告警 {current_time - self.last_alert_time:.1f} 秒")
            # 即使冷却中，也要保存图片（因为这是新的危险情况）
            if self.save_alert_images and frame is not None:
                self._save_alert_image(frame, result, is_cooldown=True)
            return
        
        self.last_alert_time = current_time
        self.alert_count += 1
        
        # 发送报警通知
        reasoning = result.get('reasoning', '检测到危险情况')
        alert_data = {
            "rule_name": "危险动作检测",
            "description": f"检测到危险情况: {reasoning}",
            "severity": "高",
            "location": "监控摄像头",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if self.alert_notifier:
            self.alert_notifier.send_alert(alert_data)
        
        # 保存告警图片
        if self.save_alert_images and frame is not None:
            self._save_alert_image(frame, result)
        
        self.logger.warning(f"触发报警: {reasoning}")
    
    def _save_alert_image(self, frame: np.ndarray, result: Dict[str, Any], is_cooldown: bool = False):
        """
        保存告警图片到本地
        
        Args:
            frame: 图像帧
            result: 分析结果
            is_cooldown: 是否在冷却期间（用于文件名标记）
        """
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            reasoning_short = result.get('reasoning', '危险')[:20].replace(' ', '_').replace('/', '_')
            cooldown_tag = "_cooldown" if is_cooldown else ""
            filename = f"alert_{timestamp}_{self.alert_count}{cooldown_tag}_{reasoning_short}.jpg"
            filepath = self.alert_images_dir / filename
            
            # 保存图片
            cv2.imwrite(str(filepath), frame)
            self.logger.info(f"告警图片已保存: {filepath}")
        except Exception as e:
            self.logger.error(f"保存告警图片失败: {e}")
    
    def run(self):
        """运行主循环"""
        if not self.initialize():
            self.logger.error("初始化失败，无法启动")
            return
        
        self.running = True
        self.logger.info("开始监控...")
        self.current_status = "监控中..."
        
        # 重置 FPS 统计
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.last_fps_update = time.time()
        
        try:
            while self.running:
                # 1. 读取帧
                success, frame = self.pipeline.read_frame()
                if not success:
                    time.sleep(0.01)  # 短暂休眠避免CPU占用过高
                    continue
                
                # 注意：视频播放速度控制已在采集线程中实现，这里不需要再次控制
                
                # FPS 计算
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.last_fps_update >= 1.0:  # 每秒更新一次
                    elapsed = current_time - self.fps_start_time
                    if elapsed > 0:
                        self.current_fps = self.frame_count / elapsed
                    self.frame_count = 0
                    self.fps_start_time = current_time
                    self.last_fps_update = current_time
                
                # 2. YOLO推理 -> 获得检测结果
                has_person, detections = self.detector.detect(frame)
                
                # 统计检测到人的次数
                if has_person:
                    self.person_detection_count += 1
                
                # 3. 绘图（画框）
                if has_person:
                    frame = self.detector.draw_detections(frame, detections)
                
                # 4. 逻辑判断：是否发送到服务端
                current_time = time.time()
                time_since_last_upload = current_time - self.last_upload_time
                
                if has_person and time_since_last_upload >= self.cooldown_seconds:
                    # 深度拷贝帧
                    frame_copy = frame.copy()
                    
                    # 构造 Prompt（与服务端保持一致）
                    prompt = f"""你是一个专业的安防监控系统分析专家。监测系统检测到画面中可能发生 {AlertType.PERSON_DETECTED}。

请仔细分析画面中的人物姿态和行为，判断是否存在真正的危险情况。

判断标准：
- SAFE（安全）的情况：
  * 人物在做瑜伽、拉伸等运动
  * 人物在睡觉或休息
  * 人物主动躺下或坐下
  * 人物正常活动，无明显异常

- DANGER（危险）的情况：
  * 人物表现出失去平衡、突然倒地
  * 人物表现出痛苦、无法动弹
  * 人物处于异常姿态，疑似受伤
  * 人物行为异常，可能存在危险

请以严格的 JSON 格式返回分析结果：
{{
    "is_danger": true/false,
    "reasoning": "详细的分析说明，解释为什么判定为安全或危险",
    "confidence": 0.0-1.0之间的浮点数，表示判断的置信度
}}

只返回 JSON，不要包含其他文字。"""
                    
                    # 放入网络工作线程队列（新格式）
                    self.network_worker.submit_task(
                        frame=frame_copy,
                        query=prompt
                    )
                    
                    self.current_status = "正在分析..."
                    self.last_upload_time = current_time  # 更新上传冷却时间
                    self.logger.info("已提交图像到服务端分析")
                
                # 5. 检查网络工作线程返回的结果
                result = self.network_worker.get_result()
                if result:
                    self.analysis_count += 1
                    self.current_status = "分析完成"
                    is_danger = result.get('is_danger', False)
                    
                    if is_danger:
                        # 危险情况：记录告警开始时间
                        self.alert_display_start_time = current_time
                        self.last_alert_result = result
                        # 保存告警图片（在触发告警前保存，确保即使冷却也会保存）
                        if self.save_alert_images:
                            self._save_alert_image(frame.copy(), result)
                        # 触发告警（会检查冷却时间）
                        self._trigger_alert(result, frame)
                        self.current_status = "危险告警!"
                    else:
                        self.current_status = "安全"
                    
                    frame = draw_analysis_result(frame, {
                        'is_danger': is_danger,
                        'reasoning': result.get('reasoning', ''),
                        'confidence': result.get('confidence', 0.5)
                    })
                
                # 5.5. 检查是否需要持续显示告警（在绘制其他内容之前）
                if self.alert_display_start_time is not None:
                    time_since_alert = current_time - self.alert_display_start_time
                    if time_since_alert < self.alert_display_duration:
                        # 仍在告警显示期内，继续显示告警覆盖层
                        frame = draw_alert_overlay(frame, "危险检测!", "high")
                        # 同时显示分析结果
                        if self.last_alert_result:
                            frame = draw_analysis_result(frame, {
                                'is_danger': True,
                                'reasoning': self.last_alert_result.get('reasoning', ''),
                                'confidence': self.last_alert_result.get('confidence', 0.5)
                            })
                    else:
                        # 告警显示时间已过，清除告警显示
                        self.alert_display_start_time = None
                        self.last_alert_result = None
                
                # 6. 绘制增强的状态信息（支持中文）
                info_lines = [
                    f"帧率: {self.current_fps:.1f} FPS",
                    f"状态: {self.current_status}",
                    f"告警次数: {self.alert_count}",
                    f"分析次数: {self.analysis_count}",
                ]
                if has_person:
                    info_lines.append(f"检测到人数: {len(detections)}")
                    info_lines.append(f"人体检测次数: {self.person_detection_count}")
                
                frame = draw_enhanced_overlay(frame, info_lines, position=(10, 30))
                
                # 7. 显示帧
                cv2.imshow('SmartMonitor - 智能监控系统', frame)
                
                # 8. 检查退出条件
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # 'q' 或 ESC
                    self.logger.info("用户请求退出")
                    break
                
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在退出...")
        except Exception as e:
            self.logger.error(f"主循环出错: {e}", exc_info=True)
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        self.logger.info("正在清理资源...")
        self.running = False
        
        if self.pipeline:
            self.pipeline.stop()
        
        if self.network_worker:
            self.network_worker.stop()
        
        cv2.destroyAllWindows()
        self.logger.info("资源清理完成")


def main():
    """主函数入口"""
    # 检查core_extracted.py是否存在
    if not os.path.exists('core_extracted.py'):
        print("错误: 未找到 core_extracted.py 文件")
        print("请确保 core_extracted.py 文件在项目根目录下")
        return
    
    # 创建监控系统实例
    monitor = SmartMonitor()
    
    # 运行
    monitor.run()


if __name__ == "__main__":
    main()
