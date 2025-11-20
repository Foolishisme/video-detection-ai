"""
Pydantic 模型 (FrameData, Alert)
前后端共用的数据结构定义，确保数据格式一致
"""

from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any


class Keypoint(BaseModel):
    """关键点坐标"""
    x: float
    y: float
    conf: float


class PersonDetection(BaseModel):
    """人体检测结果"""
    track_id: int
    bbox: List[float]  # [x1, y1, x2, y2]
    keypoints: Optional[List[Keypoint]] = None
    # 计算属性
    torso_angle: Optional[float] = None


class AlertType:
    """报警类型常量"""
    FALL = "FALL"
    VIOLENCE = "VIOLENCE"
    PERSON_DETECTED = "PERSON_DETECTED"  # 简化版：检测到人


class AnalysisRequest(BaseModel):
    """发送给服务端的请求"""
    image_base64: str
    alert_type: str  # 疑似的类型，用于 Prompt 引导
    metadata: Dict[str, Any]  # 包含置信度等信息


class AnalysisResponse(BaseModel):
    """服务端返回的仲裁结果"""
    is_danger: bool
    reasoning: str
    confidence: float
