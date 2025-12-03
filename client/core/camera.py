#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
摄像头连接模块
基于OpenCV的通用连接逻辑，支持摄像头和视频文件
"""

import cv2
import logging
from typing import Optional, Dict, Any, Tuple


class CameraConnector:
    """
    摄像头连接管理器 - 基于OpenCV的通用连接逻辑
    
    功能：
    - 支持摄像头索引（int）或视频文件路径（str）
    - 自动设置分辨率、帧率等参数
    - 提供帧读取接口
    - 错误处理和资源管理
    """
    
    def __init__(self, source=0, width=640, height=480, fps=30):
        """
        初始化摄像头连接器
        
        Args:
            source: 摄像头索引（int，如0表示默认摄像头）或视频文件路径（str）
            width: 期望的帧宽度
            height: 期望的帧高度
            fps: 期望的帧率（仅对摄像头有效）
        """
        self.cap = None
        self.source = source
        self.is_opened = False
        self.frame_count = 0
        
        # 视频属性
        self.width = width
        self.height = height
        self.fps = fps
        
        # 日志配置
        self.logger = logging.getLogger('CameraConnector')
    
    def connect(self) -> bool:
        """
        连接到视频源
        
        Returns:
            bool: 连接成功返回True，否则返回False
        """
        self.logger.info(f"正在连接视频源: {self.source}")
        
        try:
            # 创建VideoCapture对象
            self.cap = cv2.VideoCapture(self.source)
            
            if not self.cap.isOpened():
                self.logger.error(f"无法打开视频源: {self.source}")
                return False
            
            # 设置视频属性
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # 仅对摄像头设置帧率（视频文件不需要）
            if isinstance(self.source, int):
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                # 尝试设置MJPG格式（某些摄像头支持，可提高性能）
                try:
                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                except:
                    pass
                # 设置缓冲区大小为1（减少延迟）
                try:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except:
                    pass
            
            # 获取实际视频属性
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.logger.info(f"视频源连接成功")
            self.logger.info(f"视频属性: {self.width}x{self.height} @ {self.fps:.2f} fps")
            
            # 读取第一帧以确认连接正常
            ret, first_frame = self.cap.read()
            if not ret or first_frame is None:
                self.logger.error("无法读取第一帧，连接可能异常")
                self.cap.release()
                return False
            
            self.is_opened = True
            self.logger.info(f"第一帧读取成功，形状: {first_frame.shape}")
            return True
            
        except Exception as e:
            self.logger.error(f"连接视频源时出错: {str(e)}")
            return False
    
    def read_frame(self) -> Tuple[bool, Optional[Any]]:
        """
        读取一帧图像
        
        Returns:
            tuple: (success, frame) - success为True表示成功，frame为numpy数组或None
        """
        if not self.is_opened or self.cap is None:
            self.logger.error("无法读取帧：视频源未打开")
            return False, None
        
        try:
            ret, frame = self.cap.read()
            
            if not ret or frame is None:
                self.logger.warning("读取帧失败或到达视频末尾")
                return False, None
            
            self.frame_count += 1
            return True, frame
            
        except Exception as e:
            self.logger.error(f"读取帧时出错: {str(e)}")
            return False, None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.is_opened and self.cap is not None and self.cap.isOpened()
    
    def get_properties(self) -> Dict[str, Any]:
        """
        获取视频源属性
        
        Returns:
            dict: 包含width, height, fps等属性
        """
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'frame_count': self.frame_count
        }
    
    def release(self):
        """释放资源"""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False
            self.logger.info("视频源资源已释放")
    
    def __del__(self):
        """析构函数，确保资源释放"""
        self.release()

