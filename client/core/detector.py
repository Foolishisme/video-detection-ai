"""
YOLO-Pose 推理封装 (Consumer)
使用 YOLOv8n-Pose 进行人体检测（简化版：只看有没有人）
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from ultralytics import YOLO
import logging


class PersonDetector:
    """
    人体检测器（简化版）
    使用YOLOv8n进行人体检测，不进行复杂的姿态分析
    """
    
    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.25):
        """
        初始化检测器
        
        Args:
            model_path: YOLO模型路径（可以是yolov8n.pt或yolov8n-pose.pt）
            conf_threshold: 置信度阈值
        """
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"YOLO模型已加载: {model_path}")
    
    def detect(self, frame: np.ndarray) -> Tuple[bool, List[dict]]:
        """
        检测画面中是否有人
        
        Args:
            frame: 输入图像帧
            
        Returns:
            tuple: (has_person, detections)
                - has_person: 是否检测到人
                - detections: 检测结果列表，每个元素包含bbox和置信度
        """
        try:
            # YOLO推理（只检测person类，类别ID=0）
            results = self.model(frame, conf=self.conf_threshold, classes=[0], verbose=False)
            
            detections = []
            has_person = False
            
            if results and len(results) > 0:
                result = results[0]
                boxes = result.boxes
                
                if boxes is not None and len(boxes) > 0:
                    has_person = True
                    
                    # 提取检测框信息
                    for box in boxes:
                        # 获取边界框坐标
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        
                        detections.append({
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'confidence': conf,
                            'class_id': 0  # person类
                        })
            
            return has_person, detections
            
        except Exception as e:
            self.logger.error(f"检测过程出错: {e}")
            return False, []
    
    def draw_detections(self, frame: np.ndarray, detections: List[dict]) -> np.ndarray:
        """
        在帧上绘制检测结果
        
        Args:
            frame: 输入图像帧
            detections: 检测结果列表
            
        Returns:
            绘制后的图像帧
        """
        frame_copy = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            
            # 绘制边界框
            cv2.rectangle(frame_copy, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            
            # 绘制标签
            label = f"Person {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame_copy, (int(x1), int(y1) - label_size[1] - 10),
                         (int(x1) + label_size[0], int(y1)), (0, 255, 0), -1)
            cv2.putText(frame_copy, label, (int(x1), int(y1) - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        return frame_copy
