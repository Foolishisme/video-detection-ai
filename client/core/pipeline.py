"""
视频流采集线程 (Producer)
负责从摄像头或视频文件读取帧，放入队列供检测器消费
"""

import cv2
import threading
import queue
import logging
import time
import sys
from pathlib import Path
from typing import Optional, Tuple

# 添加项目根目录到路径，以便导入core_extracted
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core_extracted import CameraConnector


class VideoPipeline:
    """
    视频流采集管道（Producer）
    使用独立线程持续读取视频帧，放入队列供消费者使用
    """
    
    def __init__(self, source = 0, width: int = 640, height: int = 480, fps: int = 30, loop_video: bool = True, target_fps: float = 0):
        """
        初始化视频管道
        
        Args:
            source: 视频源（摄像头索引 int 或文件路径 str）
            width: 期望宽度
            height: 期望高度
            fps: 期望帧率
            loop_video: 视频文件循环播放（仅对视频文件有效）
            target_fps: 目标播放帧率（仅对视频文件有效，0表示不控制速度）
        """
        self.source = source
        self.is_video_file = isinstance(source, str)
        self.loop_video = loop_video and self.is_video_file
        self.target_fps = target_fps if self.is_video_file else 0  # 仅对视频文件有效
        self.camera = CameraConnector(source=source, width=width, height=height, fps=fps)
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)  # 小队列减少延迟
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(__name__)
        
        # 视频播放速度控制相关
        self.last_frame_time = 0.0  # 上一帧的时间
    
    def start(self) -> bool:
        """
        启动视频采集线程
        
        Returns:
            bool: 启动成功返回True
        """
        if not self.camera.connect():
            self.logger.error("摄像头连接失败")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        self.logger.info("视频采集线程已启动")
        return True
    
    def _capture_loop(self):
        """采集循环（在独立线程中运行）"""
        while self.running:
            # 视频文件播放速度控制（在读取帧之前控制，避免跳帧）
            if self.is_video_file and self.target_fps > 0:
                current_time = time.time()
                frame_interval = 1.0 / self.target_fps
                if self.last_frame_time > 0:
                    elapsed = current_time - self.last_frame_time
                    if elapsed < frame_interval:
                        time.sleep(frame_interval - elapsed)
                self.last_frame_time = time.time()
            
            success, frame = self.camera.read_frame()
            if not success:
                # 如果是视频文件且支持循环，则重新打开视频
                if self.is_video_file and self.loop_video:
                    self.logger.info("视频播放完毕，重新开始播放...")
                    self.camera.release()
                    if not self.camera.connect():
                        self.logger.error("重新打开视频文件失败，停止采集")
                        break
                    # 重置时间戳，开始新的一轮播放
                    self.last_frame_time = 0.0
                    continue
                else:
                    # 摄像头或视频文件（不循环）读取失败
                    if self.is_video_file:
                        self.logger.warning("视频文件读取完毕或失败")
                        break
                    else:
                        self.logger.warning("读取帧失败，尝试重连...")
                        # 尝试重连
                        if not self.camera.connect():
                            self.logger.error("重连失败，停止采集")
                            break
                continue
            
            # 非阻塞方式放入队列（如果队列满则丢弃旧帧）
            try:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()  # 丢弃最旧的帧
                    except queue.Empty:
                        pass
                self.frame_queue.put_nowait(frame.copy())
            except queue.Full:
                pass  # 队列满时跳过
    
    def read_frame(self) -> Tuple[bool, Optional[cv2.typing.MatLike]]:
        """
        从队列读取一帧（非阻塞）
        
        Returns:
            tuple: (success, frame) - success为True表示成功获取帧
        """
        try:
            frame = self.frame_queue.get_nowait()
            return True, frame
        except queue.Empty:
            return False, None
    
    def stop(self):
        """停止视频采集"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.camera.release()
        self.logger.info("视频采集已停止")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running and self.camera.is_connected()
