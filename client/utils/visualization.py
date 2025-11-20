"""
骨架绘制工具
在视频帧上绘制检测结果和状态信息
支持中文显示
"""

import cv2
import numpy as np
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont
import os


def draw_status_overlay(
    frame: np.ndarray,
    status: str,
    color: tuple = (0, 255, 255),
    position: tuple = (10, 30)
) -> np.ndarray:
    """
    在帧上绘制状态信息
    
    Args:
        frame: 输入图像帧
        status: 状态文本
        color: 文本颜色 (B, G, R)
        position: 文本位置 (x, y)
        
    Returns:
        绘制后的图像帧
    """
    frame_copy = frame.copy()
    cv2.putText(frame_copy, status, position, cv2.FONT_HERSHEY_SIMPLEX, 
               0.7, color, 2, cv2.LINE_AA)
    return frame_copy


def draw_analysis_result(
    frame: np.ndarray,
    result: Dict[str, Any],
    position: tuple = (10, 60)
) -> np.ndarray:
    """
    在帧上绘制服务端分析结果
    
    Args:
        frame: 输入图像帧
        result: 分析结果字典，包含 is_danger, reasoning, confidence
        position: 文本位置 (x, y)
        
    Returns:
        绘制后的图像帧
    """
    frame_copy = frame.copy()
    
    if result.get('is_danger', False):
        status = "DANGER"
        color = (0, 0, 255)  # 红色
    else:
        status = "SAFE"
        color = (0, 255, 0)  # 绿色
    
    text = f"Analysis: {status} (Conf: {result.get('confidence', 0):.2f})"
    cv2.putText(frame_copy, text, position, cv2.FONT_HERSHEY_SIMPLEX, 
               0.6, color, 2, cv2.LINE_AA)
    
    # 绘制推理说明（如果空间足够）
    reasoning = result.get('reasoning', '')
    if reasoning and len(reasoning) < 50:
        cv2.putText(frame_copy, reasoning, (position[0], position[1] + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    
    return frame_copy


def _get_chinese_font(size: int = 20):
    """
    获取中文字体
    
    Args:
        size: 字体大小
        
    Returns:
        PIL ImageFont 对象，如果找不到中文字体则返回默认字体
    """
    # 尝试使用系统中文字体
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
        "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux
        "/System/Library/Fonts/PingFang.ttc",  # macOS
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    
    # 如果找不到中文字体，返回默认字体（可能不支持中文）
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def cv2_add_chinese_text(
    frame: np.ndarray,
    text: str,
    position: tuple,
    font_size: int = 20,
    color: tuple = (255, 255, 255),
    bg_color: Optional[tuple] = None
) -> np.ndarray:
    """
    在 OpenCV 图像上添加中文文本（使用 PIL）
    
    Args:
        frame: OpenCV 图像 (BGR)
        text: 要显示的文本（支持中文）
        position: 文本位置 (x, y)
        font_size: 字体大小
        color: 文本颜色 (B, G, R)
        bg_color: 背景颜色 (B, G, R)，如果为 None 则不绘制背景
        
    Returns:
        绘制后的图像
    """
    frame_copy = frame.copy()
    
    # 转换为 PIL Image (RGB)
    img_pil = Image.fromarray(cv2.cvtColor(frame_copy, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # 获取字体
    font = _get_chinese_font(font_size)
    
    # 获取文本边界框（用于计算位置）
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 调整位置：OpenCV 的 putText 使用基线左下角，PIL 使用左上角
    # 所以需要调整 y 坐标
    x, y = position
    pil_y = y - text_height  # 转换为左上角坐标
    
    # 绘制背景（如果需要）
    if bg_color is not None:
        # 绘制背景矩形
        bg_rect = [
            x - 5,
            pil_y - 5,
            x + text_width + 5,
            y + 5
        ]
        draw.rectangle(bg_rect, fill=bg_color[::-1])  # PIL 使用 RGB，需要反转
    
    # 绘制文本（PIL 使用 RGB，位置为左上角）
    draw.text((x, pil_y), text, font=font, fill=color[::-1])  # 反转颜色为 RGB
    
    # 转换回 OpenCV 格式 (BGR)
    frame_copy = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    return frame_copy


def draw_alert_overlay(
    frame: np.ndarray,
    alert_text: str,
    severity: str = "high"
) -> np.ndarray:
    """
    在帧上绘制报警信息（红色警示，支持中文）
    
    Args:
        frame: 输入图像帧
        alert_text: 报警文本（支持中文）
        severity: 严重程度 ("low", "medium", "high")
        
    Returns:
        绘制后的图像帧
    """
    frame_copy = frame.copy()
    h, w = frame_copy.shape[:2]
    
    # 根据严重程度选择颜色
    if severity == "high":
        color = (0, 0, 255)  # 红色
        thickness = 5
    elif severity == "medium":
        color = (0, 165, 255)  # 橙色
        thickness = 3
    else:
        color = (0, 255, 255)  # 黄色
        thickness = 2
    
    # 绘制半透明背景
    overlay = frame_copy.copy()
    cv2.rectangle(overlay, (0, 0), (w, 100), color, -1)
    cv2.addWeighted(overlay, 0.4, frame_copy, 0.6, 0, frame_copy)
    
    # 使用支持中文的文本绘制函数
    # 估算文本宽度（中文字符按2倍宽度计算）
    estimated_width = len(alert_text.encode('utf-8')) * 30 // 2
    text_x = (w - estimated_width) // 2
    text_y = 60
    
    frame_copy = cv2_add_chinese_text(
        frame_copy,
        alert_text,
        (text_x, text_y),
        font_size=32,
        color=(255, 255, 255),  # 白色
        bg_color=None
    )
    
    return frame_copy


def draw_enhanced_overlay(
    frame: np.ndarray,
    info_lines: List[str],
    position: tuple = (10, 30),
    line_height: int = 25,
    font_size: int = 18
) -> np.ndarray:
    """
    绘制增强的信息覆盖层（多行文本，支持中文）
    
    Args:
        frame: 输入图像帧
        info_lines: 要显示的信息行列表，格式为 ["标签: 值", ...]
        position: 起始位置 (x, y)
        line_height: 行高
        font_size: 字体大小
        
    Returns:
        绘制后的图像帧
    """
    frame_copy = frame.copy()
    x, y = position
    
    # 计算背景大小
    max_width = 0
    for line in info_lines:
        # 估算文本宽度（中文字符按 2 倍宽度计算）
        estimated_width = len(line.encode('utf-8')) * font_size // 2
        max_width = max(max_width, estimated_width)
    
    bg_width = max_width + 20
    bg_height = len(info_lines) * line_height + 10
    
    # 绘制半透明背景
    overlay = frame_copy.copy()
    cv2.rectangle(overlay, (x - 5, y - 20), (x + bg_width, y + bg_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame_copy, 0.4, 0, frame_copy)
    
    # 绘制每行文本（支持中文）
    for i, line in enumerate(info_lines):
        y_pos = y + i * line_height
        frame_copy = cv2_add_chinese_text(
            frame_copy,
            line,
            (x, y_pos),
            font_size=font_size,
            color=(0, 255, 255),  # 青色
            bg_color=None
        )
    
    return frame_copy
