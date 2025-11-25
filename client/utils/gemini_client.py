"""
Google Gemini API 客户端
支持调用 Gemini-2.0-flash-exp 或 Gemini-1.5-flash-lite 模型
实现与 NetworkWorker 相同的接口，支持异步处理
"""

import os
import base64
import json
import threading
import queue
import time
import logging
from typing import Optional, Callable, Dict, Any
import cv2
import numpy as np
from PIL import Image
import io

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class GeminiWorker:
    """
    Gemini API 工作线程
    负责异步调用 Google Gemini API，不阻塞主视频循环
    实现与 NetworkWorker 相同的接口
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash-exp", timeout: int = 30):
        """
        初始化 Gemini 工作线程
        
        Args:
            api_key: Gemini API KEY（如果为None，则从环境变量 GEMINI_API_KEY 读取）
            model_name: 模型名称，默认为 "gemini-2.0-flash-exp"
            timeout: 请求超时时间（秒）
        """
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai 未安装。请运行: pip install google-generativeai"
            )
        
        # 获取 API KEY
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Gemini API KEY 未设置。请设置环境变量 GEMINI_API_KEY 或在配置中提供 api_key"
            )
        
        # 配置 Gemini API
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.timeout = timeout
        
        # 初始化模型
        try:
            self.model = genai.GenerativeModel(model_name)
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"Gemini 模型已加载: {model_name}")
        except Exception as e:
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"加载 Gemini 模型失败: {e}")
            raise
        
        # 任务队列和结果队列
        self.task_queue: queue.Queue = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def start(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        启动 Gemini 工作线程
        
        Args:
            callback: 结果回调函数，当收到 API 响应时调用
        """
        self.callback = callback
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        self.logger.info("Gemini 工作线程已启动")
    
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
                
                # 处理图像和调用 API
                try:
                    self.logger.info("发送请求到 Gemini API...")
                    
                    # 压缩图像并转换为 PIL Image
                    pil_image = self._frame_to_pil_image(frame)
                    
                    # 调用 Gemini API
                    response = self.model.generate_content([query, pil_image])
                    
                    # 获取响应文本
                    response_text = response.text if response.text else ""
                    
                    # 解析响应
                    parsed_result = self._parse_response(response_text)
                    
                    # 放入结果队列
                    self.result_queue.put(parsed_result)
                    
                    # 调用回调
                    if self.callback:
                        self.callback(parsed_result)
                    
                    self.logger.info(f"Gemini API 分析完成: {parsed_result}")
                    
                except Exception as e:
                    self.logger.error(f"Gemini API 调用失败: {e}", exc_info=True)
                    # 可以放入错误结果
                    error_result = {
                        "raw_response": f"API 调用失败: {str(e)}",
                        "is_danger": False,
                        "reasoning": f"API 调用出错: {str(e)}",
                        "confidence": 0.0
                    }
                    self.result_queue.put(error_result)
                    if self.callback:
                        self.callback(error_result)
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Gemini 工作线程出错: {e}", exc_info=True)
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        解析 Gemini API 返回的响应文本
        尝试提取 JSON 格式的分析结果
        
        Args:
            response_text: API 返回的原始文本
            
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
    
    def _frame_to_pil_image(self, frame: np.ndarray, target_size: int = 640, quality: int = 80) -> Image.Image:
        """
        将 OpenCV 帧转换为 PIL Image，并进行压缩
        
        Args:
            frame: 输入图像帧（BGR格式）
            target_size: 目标尺寸（正方形）
            quality: JPEG质量（1-100）
            
        Returns:
            PIL Image 对象（RGB格式）
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
        
        # 转换为PIL Image（BGR -> RGB）
        image = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
        
        # 可选：进一步压缩（如果需要）
        if quality < 100:
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=quality, optimize=True)
            image = Image.open(buffer)
        
        return image
    
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
        """停止 Gemini 工作线程"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.logger.info("Gemini 工作线程已停止")

