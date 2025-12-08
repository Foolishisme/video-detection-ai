#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能分析脚本
用于分析4路并发视频处理时的性能瓶颈

使用方法:
    python scripts/benchmark_profile.py

要求:
    - 安装 py-spy: pip install py-spy 或 uv pip install py-spy
    - 如果 py-spy 不可用，将使用 cProfile 作为备选方案
"""

import sys
import os
import time
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import cv2
import queue
import threading
import logging

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志（减少输出）
logging.basicConfig(
    level=logging.ERROR,  # 只显示错误
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockVideoPipeline:
    """
    Mock视频管道，用于性能测试
    生成模拟视频帧数据，模拟真实的视频流
    """
    
    def __init__(self, source=0, width: int = 640, height: int = 480, 
                 fps: int = 30, loop_video: bool = True, target_fps: float = 0):
        """
        初始化Mock视频管道
        
        Args:
            source: 视频源标识（用于区分不同的视频源）
            width: 帧宽度
            height: 帧高度
            fps: 帧率（用于计算生成速度）
            loop_video: 是否循环（对Mock无影响）
            target_fps: 目标帧率（用于控制生成速度）
        """
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.target_fps = target_fps if target_fps > 0 else fps
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(f'MockVideoPipeline-{source}')
        
        # 帧生成控制
        self.last_frame_time = 0.0
        self.frame_counter = 0
        
        # 生成一些变化的帧（模拟真实场景）
        self.base_frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    
    def start(self) -> bool:
        """启动Mock视频采集线程"""
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        self.logger.info("Mock视频采集线程已启动")
        return True
    
    def _capture_loop(self):
        """采集循环（在独立线程中运行）"""
        frame_interval = 1.0 / self.target_fps
        
        while self.running:
            current_time = time.time()
            
            # 控制帧率
            if self.last_frame_time > 0:
                elapsed = current_time - self.last_frame_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
            
            self.last_frame_time = time.time()
            
            # 生成模拟帧（添加一些变化，模拟真实场景）
            frame = self._generate_frame()
            
            # 非阻塞方式放入队列
            try:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()  # 丢弃最旧的帧
                    except queue.Empty:
                        pass
                self.frame_queue.put_nowait(frame.copy())
            except queue.Full:
                pass  # 队列满时跳过
            
            self.frame_counter += 1
    
    def _generate_frame(self) -> np.ndarray:
        """
        生成模拟视频帧
        添加一些变化，使帧看起来更真实
        """
        # 基于base_frame生成变化
        frame = self.base_frame.copy()
        
        # 添加一些随机噪声和变化
        noise = np.random.randint(-10, 10, (self.height, self.width, 3), dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # 每100帧改变一次base_frame（模拟场景变化）
        if self.frame_counter % 100 == 0:
            self.base_frame = np.random.randint(0, 255, (self.height, self.width, 3), dtype=np.uint8)
        
        return frame
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
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
        self.logger.info("Mock视频采集已停止")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running


def check_pyspy_available() -> bool:
    """检查py-spy是否可用"""
    return shutil.which('py-spy') is not None


def run_with_pyspy(duration: int = 30) -> Optional[str]:
    """
    使用py-spy运行性能分析
    
    Args:
        duration: 分析持续时间（秒）
        
    Returns:
        性能数据文件路径，如果失败返回None
    """
    if not check_pyspy_available():
        logger.warning("py-spy 未安装，将使用 cProfile 作为备选方案")
        return None
    
    output_file = project_root / "benchmark_profile_pyspy.txt"
    
    # 获取当前Python进程ID
    pid = os.getpid()
    
    print(f"使用 py-spy 分析进程 {pid}，持续 {duration} 秒...")
    print("注意: py-spy 需要管理员权限（Windows）或sudo权限（Linux）")
    
    try:
        # 使用py-spy record命令
        cmd = [
            'py-spy', 'record',
            '-o', str(output_file),
            '--duration', str(duration),
            '--pid', str(pid),
            '--format', 'text'
        ]
        
        subprocess.run(cmd, check=True, timeout=duration + 10)
        print(f"py-spy 分析完成，结果保存到: {output_file}")
        return str(output_file)
    except subprocess.CalledProcessError as e:
        logger.error(f"py-spy 执行失败: {e}")
        return None
    except FileNotFoundError:
        logger.warning("py-spy 未找到，将使用 cProfile")
        return None
    except Exception as e:
        logger.error(f"py-spy 执行出错: {e}")
        return None


def run_with_cprofile(duration: int = 30) -> str:
    """
    使用cProfile运行性能分析
    
    Args:
        duration: 分析持续时间（秒）
        
    Returns:
        性能数据文件路径
    """
    import cProfile
    import pstats
    from io import StringIO
    
    print(f"使用 cProfile 分析，持续 {duration} 秒...")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 运行主逻辑
    run_benchmark_logic(duration)
    
    profiler.disable()
    
    # 生成报告
    output_file = project_root / "benchmark_profile_report.txt"
    
    # 创建统计对象
    stats_stream = StringIO()
    stats = pstats.Stats(profiler, stream=stats_stream)
    
    # 按cumtime排序
    stats.sort_stats('cumulative')
    
    # 生成报告
    stats.print_stats(50)  # 显示前50个最耗时的函数
    
    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("性能分析报告 (按累计时间 cumtime 排序)\n")
        f.write(f"分析时长: {duration} 秒\n")
        f.write("=" * 80 + "\n\n")
        f.write(stats_stream.getvalue())
    
    print(f"cProfile 分析完成，结果保存到: {output_file}")
    return str(output_file)


def run_benchmark_logic(duration: int = 30):
    """
    运行基准测试逻辑（4路并发）
    
    Args:
        duration: 运行时长（秒）
    """
    print(f"\n开始性能测试（{duration}秒，4路并发）...")
    print("=" * 60)
    
    # 在导入任何模块之前就替换 VideoPipeline（最稳妥的方式）
    import client.core.pipeline
    original_video_pipeline_module = client.core.pipeline.VideoPipeline
    
    # 替换模块中的 VideoPipeline 类
    client.core.pipeline.VideoPipeline = MockVideoPipeline
    
    # 导入 server.app 模块（在替换之后）
    import server.app as app_module
    # 保存 server.app 中的原始引用（如果存在）
    original_video_pipeline_app = getattr(app_module, 'VideoPipeline', None)
    # 替换 server.app 模块中的 VideoPipeline 引用
    app_module.VideoPipeline = MockVideoPipeline
    
    # 现在可以安全地导入类了
    from server.app import OptimizedMonitorService, SourceMonitor
    
    try:
        # 创建配置（4路并发）
        config = {
            'video': {
                'sources': [0, 1, 2, 3],  # 4路并发
                'width': 640,
                'height': 480,
                'fps': 30,
                'loop_video': True,
                'target_fps': 20
            },
            'cooldown_seconds': 5.0,
            'llm_provider': 'gemini',  # 使用gemini，避免网络请求阻塞
            'gemini': {
                'api_key': os.getenv('GEMINI_API_KEY', 'dummy_key'),
                'model_name': 'gemini-2.0-flash-late'
            }
        }
        
        # 创建监控服务
        monitor_service = OptimizedMonitorService.__new__(OptimizedMonitorService)
        monitor_service.config = config
        monitor_service.sources = {}
        monitor_service.frame_cache = type('FrameCache', (), {
            'get': lambda self, source_id: None,
            'set': lambda self, source_id, data: None
        })()
        monitor_service.alert_images_dir = project_root / "alerts"
        monitor_service.alert_images_dir.mkdir(exist_ok=True)
        
        # 初始化共享组件
        from server.app import DetectionTaskQueue, NetworkWorkerPool, AlertNotifier
        from client.core.detector import PersonDetector
        
        print("初始化共享检测器...")
        monitor_service.shared_detector = PersonDetector(model_path="yolov8n.pt")
        
        print("初始化批量检测任务队列...")
        # 4路并发，使用批量大小4
        monitor_service.detection_queue = DetectionTaskQueue(
            monitor_service.shared_detector,
            max_queue_size=50,
            batch_size=4,
            max_wait_time=0.05
        )
        monitor_service.detection_queue.start()
        
        print("初始化网络工作线程池...")
        # 创建Mock网络工作线程（避免真实网络请求）
        class MockNetworkWorker:
            def __init__(self):
                self.result_queue = queue.Queue()
                self.running = False
                self.thread = None
            
            def start(self):
                self.running = True
                self.thread = threading.Thread(target=self._worker_loop, daemon=True)
                self.thread.start()
            
            def _worker_loop(self):
                while self.running:
                    time.sleep(0.1)
            
            def submit_task(self, frame, query):
                # 模拟网络请求延迟
                def mock_request():
                    time.sleep(0.1)  # 模拟100ms延迟
                    result = {
                        'is_danger': False,
                        'alert_type': '安全',
                        'alert_message': '场景正常',
                        'reasoning': 'Mock分析结果',
                        'confidence': 0.9
                    }
                    self.result_queue.put(result)
                
                threading.Thread(target=mock_request, daemon=True).start()
            
            def get_result(self):
                try:
                    return self.result_queue.get_nowait()
                except queue.Empty:
                    return None
            
            def stop(self):
                self.running = False
                if self.thread:
                    self.thread.join(timeout=1)
        
        def create_mock_worker():
            worker = MockNetworkWorker()
            worker.start()
            return worker
        
        monitor_service.network_pool = NetworkWorkerPool(create_mock_worker, pool_size=2)
        monitor_service.alert_notifier = AlertNotifier()
        
        # 初始化4个视频源
        print("初始化4个视频源...")
        for idx in range(4):
            source_monitor = SourceMonitor(
                source_id=idx,
                source=idx,  # 使用索引作为source标识
                config=config,
                detection_queue=monitor_service.detection_queue,
                network_pool=monitor_service.network_pool,
                alert_notifier=monitor_service.alert_notifier,
                alert_images_dir=monitor_service.alert_images_dir,
                frame_cache=monitor_service.frame_cache
            )
            monitor_service.sources[idx] = source_monitor
        
        # 启动所有视频源
        print("启动所有视频源...")
        for source_id, source_monitor in monitor_service.sources.items():
            if not source_monitor.start():
                print(f"警告: 视频源 {source_id} 启动失败")
        
        print(f"\n性能测试运行中（{duration}秒）...")
        print("正在收集性能数据...\n")
        
        # 运行指定时长
        start_time = time.time()
        while time.time() - start_time < duration:
            time.sleep(0.1)
        
        # 停止服务
        print("\n停止服务...")
        monitor_service.stop()
        
        print("性能测试完成！")
        
    finally:
        # 恢复原始VideoPipeline引用（确保不影响主程序）
        client.core.pipeline.VideoPipeline = original_video_pipeline_module
        if original_video_pipeline_app is not None:
            app_module.VideoPipeline = original_video_pipeline_app
        elif hasattr(app_module, 'VideoPipeline'):
            # 如果原来没有，删除我们添加的引用
            delattr(app_module, 'VideoPipeline')


def generate_report_from_pyspy(pyspy_file: str) -> str:
    """
    从py-spy输出生成格式化的报告
    
    Args:
        pyspy_file: py-spy输出文件路径
        
    Returns:
        格式化报告文件路径
    """
    output_file = project_root / "benchmark_profile_report.txt"
    
    try:
        with open(pyspy_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析并格式化py-spy输出
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("性能分析报告 (基于 py-spy)\n")
            f.write("=" * 80 + "\n\n")
            f.write(content)
            f.write("\n\n注意: py-spy 输出格式可能与 cProfile 不同\n")
            f.write("建议使用 'py-spy top' 或 'py-spy record --format flamegraph' 获取更详细的信息\n")
        
        return str(output_file)
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        return str(output_file)


def main():
    """主函数"""
    print("=" * 60)
    print("视频处理性能分析工具")
    print("=" * 60)
    print("\n配置:")
    print("  - 并发数: 4路")
    print("  - 分析时长: 30秒")
    print("  - 视频分辨率: 640x480")
    print("  - 目标帧率: 20 FPS")
    print("=" * 60)
    
    duration = 30
    
    # 尝试使用py-spy
    pyspy_file = run_with_pyspy(duration)
    
    if pyspy_file:
        # 生成格式化报告
        report_file = generate_report_from_pyspy(pyspy_file)
        print(f"\n✓ 性能分析完成！")
        print(f"  报告文件: {report_file}")
    else:
        # 使用cProfile作为备选
        print("\n使用 cProfile 作为备选方案...")
        report_file = run_with_cprofile(duration)
        print(f"\n✓ 性能分析完成！")
        print(f"  报告文件: {report_file}")
    
    print("\n提示:")
    print("  - 查看报告文件了解性能瓶颈")
    print("  - 重点关注 cumtime（累计时间）较大的函数")
    print("  - 如果使用 py-spy，可以尝试生成火焰图:")
    print("    py-spy record --format flamegraph -o flamegraph.svg --duration 30 --pid <PID>")


if __name__ == "__main__":
    main()

