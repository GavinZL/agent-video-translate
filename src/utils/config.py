"""
系统配置管理模块

这个模块负责管理视频翻译系统的所有配置参数，包括API配置、音视频处理参数等。
支持从环境变量和配置文件读取参数，并提供默认值。
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class APIConfig:
    """API相关配置"""
    api_key: str
    api_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    model_name: str = "qwen3-livetranslate-flash-realtime"
    target_language: str = "en"
    voice_type: str = "Cherry"


@dataclass
class AudioConfig:
    """音频处理配置"""
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    audio_chunk_size: int = 1600
    audio_format: str = "pcm16"
    channels: int = 1


@dataclass
class VideoConfig:
    """视频处理配置"""
    frame_extract_rate: int = 2
    output_video_quality: str = "high"
    video_codec: str = "h264"
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"


@dataclass
class ProcessConfig:
    """处理流程配置"""
    max_retry_count: int = 3
    timeout_seconds: int = 30
    concurrent_workers: int = 4
    buffer_size: int = 8192


@dataclass
class FilePathConfig:
    """文件路径配置"""
    input_video_path: str = "videos/cn-agent.mp4"
    output_video_path: str = "output/cn-agent-en.mp4"
    temp_dir: str = "temp/"
    log_dir: str = "logs/"


@dataclass
class LogConfig:
    """日志配置"""
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None


class Config:
    """主配置类，整合所有配置信息"""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        初始化配置
        
        Args:
            env_file: 环境变量文件路径，默认为.env
        """
        # 加载环境变量
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # 初始化各模块配置
        self.api = self._load_api_config()
        self.audio = self._load_audio_config()
        self.video = self._load_video_config()
        self.process = self._load_process_config()
        self.file_paths = self._load_file_path_config()
        self.log = self._load_log_config()
        
        # 设置日志
        self._setup_logging()
    
    def _load_api_config(self) -> APIConfig:
        """加载API配置"""
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY环境变量未设置")
        
        return APIConfig(
            api_key=api_key,
            api_url=os.getenv("API_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"),
            model_name=os.getenv("MODEL_NAME", "qwen3-livetranslate-flash-realtime"),
            target_language=os.getenv("TARGET_LANGUAGE", "en"),
            voice_type=os.getenv("VOICE_TYPE", "Cherry")
        )
    
    def _load_audio_config(self) -> AudioConfig:
        """加载音频配置"""
        return AudioConfig(
            input_sample_rate=int(os.getenv("INPUT_SAMPLE_RATE", "16000")),
            output_sample_rate=int(os.getenv("OUTPUT_SAMPLE_RATE", "24000")),
            audio_chunk_size=int(os.getenv("AUDIO_CHUNK_SIZE", "1600")),
            audio_format=os.getenv("AUDIO_FORMAT", "pcm16"),
            channels=int(os.getenv("CHANNELS", "1"))
        )
    
    def _load_video_config(self) -> VideoConfig:
        """加载视频配置"""
        return VideoConfig(
            frame_extract_rate=int(os.getenv("FRAME_EXTRACT_RATE", "2")),
            output_video_quality=os.getenv("OUTPUT_VIDEO_QUALITY", "high"),
            video_codec=os.getenv("VIDEO_CODEC", "h264"),
            audio_codec=os.getenv("AUDIO_CODEC", "aac"),
            audio_bitrate=os.getenv("AUDIO_BITRATE", "128k")
        )
    
    def _load_process_config(self) -> ProcessConfig:
        """加载处理流程配置"""
        return ProcessConfig(
            max_retry_count=int(os.getenv("MAX_RETRY_COUNT", "3")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
            concurrent_workers=int(os.getenv("CONCURRENT_WORKERS", "4")),
            buffer_size=int(os.getenv("BUFFER_SIZE", "8192"))
        )
    
    def _load_file_path_config(self) -> FilePathConfig:
        """加载文件路径配置"""
        return FilePathConfig(
            input_video_path=os.getenv("INPUT_VIDEO_PATH", "videos/cn-agent.mp4"),
            output_video_path=os.getenv("OUTPUT_VIDEO_PATH", "output/cn-agent-en.mp4"),
            temp_dir=os.getenv("TEMP_DIR", "temp/"),
            log_dir=os.getenv("LOG_DIR", "logs/")
        )
    
    def _load_log_config(self) -> LogConfig:
        """加载日志配置"""
        return LogConfig(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            log_file=os.getenv("LOG_FILE")
        )
    
    def _setup_logging(self):
        """设置日志系统"""
        # 创建日志目录
        os.makedirs(self.file_paths.log_dir, exist_ok=True)
        
        # 配置日志级别
        log_level = getattr(logging, self.log.log_level.upper(), logging.INFO)
        
        # 配置日志处理器
        handlers = [logging.StreamHandler()]
        
        if self.log.log_file:
            log_file_path = os.path.join(self.file_paths.log_dir, self.log.log_file)
            handlers.append(logging.FileHandler(log_file_path, encoding='utf-8'))
        
        # 设置日志配置
        logging.basicConfig(
            level=log_level,
            format=self.log.log_format,
            handlers=handlers
        )
    
    def validate(self) -> bool:
        """
        验证配置的有效性
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # 验证API密钥
            if not self.api.api_key or self.api.api_key == "your_api_key_here":
                logging.error("无效的API密钥")
                return False
            
            # 验证音频参数
            if self.audio.input_sample_rate <= 0 or self.audio.output_sample_rate <= 0:
                logging.error("无效的音频采样率")
                return False
            
            if self.audio.audio_chunk_size <= 0:
                logging.error("无效的音频块大小")
                return False
            
            # 验证视频参数
            if self.video.frame_extract_rate <= 0:
                logging.error("无效的视频帧提取率")
                return False
            
            # 验证处理参数
            if self.process.max_retry_count <= 0:
                logging.error("无效的最大重试次数")
                return False
            
            if self.process.timeout_seconds <= 0:
                logging.error("无效的超时时间")
                return False
            
            # 验证文件路径
            input_dir = os.path.dirname(self.file_paths.input_video_path)
            if input_dir and not os.path.exists(input_dir):
                logging.warning(f"输入视频目录不存在: {input_dir}")
            
            # 创建必要的目录
            os.makedirs(os.path.dirname(self.file_paths.output_video_path), exist_ok=True)
            os.makedirs(self.file_paths.temp_dir, exist_ok=True)
            os.makedirs(self.file_paths.log_dir, exist_ok=True)
            
            logging.info("配置验证通过")
            return True
            
        except Exception as e:
            logging.error(f"配置验证失败: {e}")
            return False
    
    def to_dict(self) -> dict:
        """
        将配置转换为字典格式
        
        Returns:
            dict: 配置字典
        """
        return {
            'api': {
                'api_key': '***masked***',  # 隐藏敏感信息
                'api_url': self.api.api_url,
                'model_name': self.api.model_name,
                'target_language': self.api.target_language,
                'voice_type': self.api.voice_type
            },
            'audio': {
                'input_sample_rate': self.audio.input_sample_rate,
                'output_sample_rate': self.audio.output_sample_rate,
                'audio_chunk_size': self.audio.audio_chunk_size,
                'audio_format': self.audio.audio_format,
                'channels': self.audio.channels
            },
            'video': {
                'frame_extract_rate': self.video.frame_extract_rate,
                'output_video_quality': self.video.output_video_quality,
                'video_codec': self.video.video_codec,
                'audio_codec': self.video.audio_codec,
                'audio_bitrate': self.video.audio_bitrate
            },
            'process': {
                'max_retry_count': self.process.max_retry_count,
                'timeout_seconds': self.process.timeout_seconds,
                'concurrent_workers': self.process.concurrent_workers,
                'buffer_size': self.process.buffer_size
            },
            'file_paths': {
                'input_video_path': self.file_paths.input_video_path,
                'output_video_path': self.file_paths.output_video_path,
                'temp_dir': self.file_paths.temp_dir,
                'log_dir': self.file_paths.log_dir
            },
            'log': {
                'log_level': self.log.log_level,
                'log_format': self.log.log_format,
                'log_file': self.log.log_file
            }
        }


# 全局配置实例
_config = None


def get_config(env_file: Optional[str] = None) -> Config:
    """
    获取全局配置实例（单例模式）
    
    Args:
        env_file: 环境变量文件路径
        
    Returns:
        Config: 配置实例
    """
    global _config
    if _config is None:
        _config = Config(env_file)
    return _config


def reload_config(env_file: Optional[str] = None) -> Config:
    """
    重新加载配置
    
    Args:
        env_file: 环境变量文件路径
        
    Returns:
        Config: 新的配置实例
    """
    global _config
    _config = Config(env_file)
    return _config


if __name__ == "__main__":
    # 测试配置模块
    try:
        config = get_config()
        if config.validate():
            print("配置加载成功!")
            print("配置信息:")
            import json
            print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("配置验证失败!")
    except Exception as e:
        print(f"配置加载失败: {e}")