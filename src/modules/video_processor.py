"""
视频处理模块

这个模块负责视频文件的解析、音频提取和视频帧提取等核心功能。
支持多种视频格式，提供高效的音视频数据处理能力。
"""

import os
import cv2
import logging
import numpy as np
from typing import Generator, Tuple, Optional, Dict, Any
import subprocess
import tempfile
import base64
from io import BytesIO
from PIL import Image

from ..utils.config import get_config


class VideoInfo:
    """视频信息类"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.duration = 0.0
        self.fps = 0.0
        self.width = 0
        self.height = 0
        self.total_frames = 0
        self.audio_sample_rate = 0
        self.audio_channels = 0
        self.has_audio = False
        self.video_codec = ""
        self.audio_codec = ""
        self.file_size = 0
        
        self._extract_info()
    
    def _extract_info(self):
        """提取视频信息"""
        try:
            # 获取文件大小
            self.file_size = os.path.getsize(self.file_path)
            
            # 使用OpenCV获取视频信息
            cap = cv2.VideoCapture(self.file_path)
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {self.file_path}")
            
            self.fps = cap.get(cv2.CAP_PROP_FPS)
            self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration = self.total_frames / self.fps if self.fps > 0 else 0
            
            cap.release()
            
            # 使用ffprobe获取更详细的信息
            self._extract_detailed_info()
            
        except Exception as e:
            logging.error(f"提取视频信息失败: {e}")
            raise
    
    def _extract_detailed_info(self):
        """使用ffprobe提取详细信息"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', self.file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            probe_data = json.loads(result.stdout)
            
            # 解析流信息
            for stream in probe_data.get('streams', []):
                if stream['codec_type'] == 'video':
                    self.video_codec = stream.get('codec_name', 'unknown')
                elif stream['codec_type'] == 'audio':
                    self.has_audio = True
                    self.audio_codec = stream.get('codec_name', 'unknown')
                    self.audio_sample_rate = int(stream.get('sample_rate', 0))
                    self.audio_channels = int(stream.get('channels', 0))
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
            logging.warning(f"无法使用ffprobe获取详细信息: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'file_path': self.file_path,
            'duration': self.duration,
            'fps': self.fps,
            'width': self.width,
            'height': self.height,
            'total_frames': self.total_frames,
            'audio_sample_rate': self.audio_sample_rate,
            'audio_channels': self.audio_channels,
            'has_audio': self.has_audio,
            'video_codec': self.video_codec,
            'audio_codec': self.audio_codec,
            'file_size': self.file_size
        }


class AudioExtractor:
    """音频提取器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
    
    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径，如果为None则自动生成
            
        Returns:
            str: 提取的音频文件路径
        """
        try:
            if output_path is None:
                # 在临时目录中生成输出文件
                temp_dir = self.config.file_paths.temp_dir
                os.makedirs(temp_dir, exist_ok=True)
                output_path = os.path.join(temp_dir, "extracted_audio.wav")
            
            # 使用ffmpeg提取音频并转换为指定格式
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # 不处理视频流
                '-acodec', 'pcm_s16le',  # 使用PCM 16位编码
                '-ar', str(self.config.audio.input_sample_rate),  # 设置采样率
                '-ac', str(self.config.audio.channels),  # 设置声道数
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            self.logger.info(f"开始提取音频: {video_path} -> {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"音频提取失败，输出文件不存在: {output_path}")
            
            self.logger.info(f"音频提取成功: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg音频提取失败: {e.stderr}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            self.logger.error(f"音频提取过程中发生错误: {e}")
            raise
    
    def extract_audio_chunks(self, video_path: str) -> Generator[bytes, None, None]:
        """
        流式提取音频数据块
        
        Args:
            video_path: 视频文件路径
            
        Yields:
            bytes: 音频数据块
        """
        try:
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # 不处理视频流
                '-acodec', 'pcm_s16le',  # 使用PCM 16位编码
                '-ar', str(self.config.audio.input_sample_rate),  # 设置采样率
                '-ac', str(self.config.audio.channels),  # 设置声道数
                '-f', 'wav',  # 输出格式
                'pipe:1'  # 输出到标准输出
            ]
            
            self.logger.info(f"开始流式提取音频: {video_path}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 跳过WAV头部（44字节）
            wav_header = process.stdout.read(44)
            if len(wav_header) != 44:
                raise RuntimeError("WAV头部读取失败")
            
            chunk_size = self.config.audio.audio_chunk_size
            
            while True:
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk
            
            # 等待进程结束
            return_code = process.wait()
            if return_code != 0:
                stderr = process.stderr.read().decode('utf-8')
                raise RuntimeError(f"ffmpeg进程失败，返回码: {return_code}, 错误信息: {stderr}")
            
            self.logger.info("音频流式提取完成")
            
        except Exception as e:
            self.logger.error(f"流式音频提取失败: {e}")
            raise


class FrameExtractor:
    """视频帧提取器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
    
    def extract_frames(self, video_path: str, output_dir: Optional[str] = None) -> Generator[str, None, None]:
        """
        按指定频率提取视频帧并保存为图片文件
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录，如果为None则使用临时目录
            
        Yields:
            str: 保存的图片文件路径
        """
        try:
            if output_dir is None:
                output_dir = os.path.join(self.config.file_paths.temp_dir, "frames")
            
            os.makedirs(output_dir, exist_ok=True)
            
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_interval = int(fps / self.config.video.frame_extract_rate)
            
            self.logger.info(f"开始提取视频帧: {video_path}, FPS: {fps}, 提取间隔: {frame_interval}")
            
            frame_count = 0
            extracted_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % frame_interval == 0:
                    # 保存帧
                    frame_filename = f"frame_{extracted_count:06d}.jpg"
                    frame_path = os.path.join(output_dir, frame_filename)
                    
                    cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    extracted_count += 1
                    
                    yield frame_path
                
                frame_count += 1
            
            cap.release()
            self.logger.info(f"视频帧提取完成，共提取 {extracted_count} 帧")
            
        except Exception as e:
            self.logger.error(f"视频帧提取失败: {e}")
            if 'cap' in locals():
                cap.release()
            raise
    
    def extract_frame_data(self, video_path: str) -> Generator[Tuple[float, bytes], None, None]:
        """
        流式提取视频帧数据（不保存文件）
        
        Args:
            video_path: 视频文件路径
            
        Yields:
            Tuple[float, bytes]: (时间戳, Base64编码的JPEG图片数据)
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_interval = int(fps / self.config.video.frame_extract_rate)
            
            self.logger.info(f"开始流式提取视频帧数据: {video_path}")
            
            frame_count = 0
            extracted_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % frame_interval == 0:
                    # 将帧转换为JPEG格式
                    success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if success:
                        # 计算时间戳
                        timestamp = frame_count / fps
                        
                        # 转换为Base64
                        jpg_bytes = buffer.tobytes()
                        base64_data = base64.b64encode(jpg_bytes)
                        
                        extracted_count += 1
                        yield timestamp, base64_data
                
                frame_count += 1
            
            cap.release()
            self.logger.info(f"视频帧数据提取完成，共提取 {extracted_count} 帧")
            
        except Exception as e:
            self.logger.error(f"视频帧数据提取失败: {e}")
            if 'cap' in locals():
                cap.release()
            raise


class VideoProcessor:
    """视频处理器主类"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.audio_extractor = AudioExtractor(config)
        self.frame_extractor = FrameExtractor(config)
    
    def analyze_video(self, video_path: str) -> VideoInfo:
        """
        分析视频文件信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            VideoInfo: 视频信息对象
        """
        try:
            self.logger.info(f"开始分析视频: {video_path}")
            
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"视频文件不存在: {video_path}")
            
            video_info = VideoInfo(video_path)
            
            self.logger.info(f"视频分析完成: {video_info.to_dict()}")
            return video_info
            
        except Exception as e:
            self.logger.error(f"视频分析失败: {e}")
            raise
    
    def validate_video(self, video_path: str) -> bool:
        """
        验证视频文件是否有效
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            bool: 视频是否有效
        """
        try:
            video_info = self.analyze_video(video_path)
            
            # 检查基本要求
            if video_info.duration <= 0:
                self.logger.error("视频时长无效")
                return False
            
            if video_info.width <= 0 or video_info.height <= 0:
                self.logger.error("视频分辨率无效")
                return False
            
            if not video_info.has_audio:
                self.logger.warning("视频不包含音频轨道")
                # 可以根据需求决定是否允许无音频的视频
            
            self.logger.info("视频验证通过")
            return True
            
        except Exception as e:
            self.logger.error(f"视频验证失败: {e}")
            return False
    
    def prepare_processing(self, video_path: str) -> Dict[str, Any]:
        """
        为处理准备视频数据
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Dict[str, Any]: 处理准备信息
        """
        try:
            # 验证视频
            if not self.validate_video(video_path):
                raise ValueError("视频验证失败")
            
            # 分析视频信息
            video_info = self.analyze_video(video_path)
            
            # 创建临时目录
            temp_dir = self.config.file_paths.temp_dir
            os.makedirs(temp_dir, exist_ok=True)
            
            processing_info = {
                'video_info': video_info.to_dict(),
                'temp_dir': temp_dir,
                'estimated_frames': int(video_info.duration * self.config.video.frame_extract_rate),
                'estimated_audio_chunks': int(video_info.duration * self.config.audio.input_sample_rate * 2 / self.config.audio.audio_chunk_size),
                'processing_time_estimate': video_info.duration * 2  # 预估处理时间为视频时长的2倍
            }
            
            self.logger.info(f"处理准备完成: {processing_info}")
            return processing_info
            
        except Exception as e:
            self.logger.error(f"处理准备失败: {e}")
            raise


if __name__ == "__main__":
    # 测试视频处理模块
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python video_processor.py <视频文件路径>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    
    try:
        processor = VideoProcessor()
        
        # 分析视频
        video_info = processor.analyze_video(video_path)
        print("视频信息:")
        import json
        print(json.dumps(video_info.to_dict(), indent=2, ensure_ascii=False))
        
        # 验证视频
        if processor.validate_video(video_path):
            print("视频验证通过")
        else:
            print("视频验证失败")
            sys.exit(1)
        
        # 准备处理
        processing_info = processor.prepare_processing(video_path)
        print("处理信息:")
        print(json.dumps(processing_info, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"测试失败: {e}")
        sys.exit(1)