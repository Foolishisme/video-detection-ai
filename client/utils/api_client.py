"""
与云端通信的 HTTP 客户端
发送疑似危险帧到服务端进行二次确认
包含异步网络工作线程，防止阻塞主循环
适配新的 /chat API（简化版）
"""

import cv2
import base64
import json
import threading
import queue
import time
import logging
from typing import Optional, Callable, Dict, Any
import requests
from PIL import Image
import io
import numpy as np


class NetworkWorker:
    """
    网络工作线程
    负责异步发送图像到服务端，不阻塞主视频循环
    适配新的 /chat API
    """
    
    def __init__(self, server_url: str, timeout: int = 30):
        """
        初始化网络工作线程
        
        Args:
            server_url: 服务端URL（如 "http://localhost:8000/chat"）
            timeout: 请求超时时间（秒），大模型推理需要更长时间
        """
        self.server_url = server_url
        self.timeout = timeout
        self.task_queue: queue.Queue = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(__name__)
        self.callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def start(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        启动网络工作线程
        
        Args:
            callback: 结果回调函数，当收到服务端响应时调用
        """
        self.callback = callback
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        self.logger.info("网络工作线程已启动")
    
    def submit_task(self, frame: np.ndarray, query: str):
        """
        提交任务到队列（非阻塞）
        
        Args:
            frame: 图像帧
            query: 查询文本（Prompt）
        """
        try:
            self.task_queue.put_nowait({
                'frame': frame.copy(),
                'query': query,
                'timestamp': time.time()
            })
        except queue.Full:
            self.logger.warning("任务队列已满，跳过本次请求")
    
    def _worker_loop(self):
        """工作线程循环"""
        while self.running:
            try:
                # 从队列获取任务（阻塞等待，最多1秒）
                task = self.task_queue.get(timeout=1.0)
                
                frame = task['frame']
                query = task['query']
                
                # 压缩图像
                image_base64 = self._compress_image(frame)
                
                # 构造请求（新的简化格式）
                request_data = {
                    "image_base64": image_base64,
                    "query": query
                }
                
                # 发送HTTP请求
                try:
                    self.logger.info("发送请求到服务端...")
                    response = requests.post(
                        self.server_url,
                        json=request_data,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    
                    # 解析响应（新格式：{"response": "..."}）
                    result_data = response.json()
                    response_text = result_data.get("response", "")
                    
                    # 尝试解析 JSON（如果模型返回的是 JSON）
                    parsed_result = self._parse_response(response_text)
                    
                    # 放入结果队列
                    self.result_queue.put(parsed_result)
                    
                    # 调用回调
                    if self.callback:
                        self.callback(parsed_result)
                    
                    self.logger.info(f"服务端分析完成: {parsed_result}")
                    
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"HTTP请求失败: {e}")
                    # 可以放入错误结果或重试逻辑
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"网络工作线程出错: {e}", exc_info=True)
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        解析服务端返回的响应文本
        尝试提取 JSON 格式的分析结果
        
        Args:
            response_text: 服务端返回的原始文本
            
        Returns:
            解析后的结果字典
        """
        result = {
            "raw_response": response_text,
            "is_danger": False,
            "alert_type": "",
            "alert_message": "",
            "reasoning": "",
            "confidence": 0.5
        }
        
        try:
            # 清理输出，提取 JSON 部分
            response_clean = response_text.strip()
            
            # 移除可能的 markdown 代码块标记
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            elif response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            # 查找 JSON 部分
            json_start = response_clean.find('{')
            json_end = response_clean.rfind('}') + 1
            
            if json_start != -1 and json_end > 0:
                json_str = response_clean[json_start:json_end]
                json_data = json.loads(json_str)
                
                # 提取字段
                result["is_danger"] = bool(json_data.get("is_danger", False))
                result["alert_type"] = str(json_data.get("alert_type", ""))
                result["alert_message"] = str(json_data.get("alert_message", ""))
                result["reasoning"] = str(json_data.get("reasoning", ""))
                result["confidence"] = float(json_data.get("confidence", 0.5))
                result["confidence"] = max(0.0, min(1.0, result["confidence"]))
            else:
                # 如果没有找到 JSON，尝试从文本中提取信息
                result["reasoning"] = response_text
                # 简单的关键词检测
                if any(keyword in response_text.lower() for keyword in ["danger", "危险", "异常", "受伤"]):
                    result["is_danger"] = True
                    
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON 解析失败: {e}，使用原始文本")
            result["reasoning"] = response_text
        except Exception as e:
            self.logger.warning(f"解析响应时出错: {e}")
            result["reasoning"] = response_text
        
        return result
    
    def _compress_image(self, frame: np.ndarray, target_size: int = 640, quality: int = 80) -> str:
        """
        压缩图像：Resize到640x640，JPEG压缩，转换为Base64
        
        Args:
            frame: 输入图像帧
            target_size: 目标尺寸（正方形）
            quality: JPEG质量（1-100）
            
        Returns:
            Base64编码的字符串
        """
        # Resize到目标尺寸（保持宽高比）
        h, w = frame.shape[:2]
        scale = min(target_size / w, target_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 如果尺寸不足，填充到正方形
        if new_w != target_size or new_h != target_size:
            padded = np.zeros((target_size, target_size, 3), dtype=np.uint8)
            y_offset = (target_size - new_h) // 2
            x_offset = (target_size - new_w) // 2
            padded[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
            resized = padded
        
        # 转换为PIL Image进行JPEG压缩
        image = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
        
        # JPEG压缩
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        image_bytes = buffer.getvalue()
        
        # Base64编码
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        self.logger.debug(f"图像压缩完成: {len(image_bytes)} bytes -> Base64长度: {len(image_base64)}")
        
        return image_base64
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """
        获取最新的分析结果（非阻塞）
        
        Returns:
            结果字典或None
        """
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None
    
    def stop(self):
        """停止网络工作线程"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.logger.info("网络工作线程已停止")
