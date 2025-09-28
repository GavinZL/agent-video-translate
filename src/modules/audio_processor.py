"""
音频处理模块

这个模块负责音频的预处理、格式转换、音频合成和后处理等功能。
支持从翻译API接收的音频片段进行拼接和优化，生成最终的英文音频轨道。
"""

import os
import logging
import numpy as np
import wave
import struct
import tempfile
from typing import List, Optional, Tuple, Generator
import subprocess
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from ..utils.config import get_config


class AudioFormat:
    """音频格式定义"""
    
    def __init__(self, sample_rate: int, channels: int, sample_width: int):
        self.sample_rate = sample_rate  # 采样率
        self.channels = channels        # 声道数
        self.sample_width = sample_width # 采样位深度（字节数）
        self.frame_size = channels * sample_width  # 帧大小


class AudioSegment:
    """音频片段类"""
    
    def __init__(self, data: bytes, timestamp: float, duration: float, format_info: AudioFormat):
        self.data = data
        self.timestamp = timestamp
        self.duration = duration
        self.format_info = format_info
        self.sample_count = len(data) // format_info.frame_size
    
    def to_numpy(self) -> np.ndarray:
        """转换为numpy数组"""
        if self.format_info.sample_width == 2:  # 16位
            dtype = np.int16
        elif self.format_info.sample_width == 4:  # 32位
            dtype = np.int32
        else:
            raise ValueError(f"不支持的采样位深度: {self.format_info.sample_width}")
        
        return np.frombuffer(self.data, dtype=dtype)
    
    @classmethod
    def from_numpy(cls, array: np.ndarray, timestamp: float, format_info: AudioFormat) -> 'AudioSegment':
        """从numpy数组创建音频片段"""
        data = array.tobytes()
        duration = len(array) / (format_info.sample_rate * format_info.channels)
        return cls(data, timestamp, duration, format_info)


class AudioPreprocessor:
    """音频预处理器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # 输入和输出格式
        self.input_format = AudioFormat(
            sample_rate=self.config.audio.input_sample_rate,
            channels=self.config.audio.channels,
            sample_width=2  # 16位PCM
        )
        
        self.output_format = AudioFormat(
            sample_rate=self.config.audio.output_sample_rate,
            channels=self.config.audio.channels,
            sample_width=2  # 16位PCM
        )
    
    def normalize_audio(self, audio_data: bytes) -> bytes:
        """
        音频规范化处理
        
        Args:
            audio_data: 原始音频数据
            
        Returns:
            bytes: 规范化后的音频数据
        """
        try:
            # 转换为numpy数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # 规范化到[-1, 1]范围
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # 应用增益控制
            max_amplitude = np.max(np.abs(audio_float))
            if max_amplitude > 0:
                target_amplitude = 0.8  # 目标最大振幅
                gain = min(target_amplitude / max_amplitude, 2.0)  # 限制最大增益
                audio_float = audio_float * gain
            
            # 转换回int16
            audio_normalized = (audio_float * 32767).astype(np.int16)
            
            return audio_normalized.tobytes()
            
        except Exception as e:
            self.logger.error(f"音频规范化失败: {e}")
            return audio_data  # 返回原始数据
    
    def remove_silence(self, audio_data: bytes, threshold: float = 0.01) -> bytes:
        """
        移除静音段
        
        Args:
            audio_data: 音频数据
            threshold: 静音检测阈值
            
        Returns:
            bytes: 移除静音后的音频数据
        """
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # 计算音频能量
            window_size = int(self.input_format.sample_rate * 0.1)  # 100ms窗口
            energy = []
            
            for i in range(0, len(audio_float), window_size):
                window = audio_float[i:i + window_size]
                window_energy = np.mean(window ** 2)
                energy.append(window_energy)
            
            # 标记非静音段
            non_silence_mask = np.array(energy) > threshold
            
            # 扩展掩码到原始音频长度
            full_mask = np.repeat(non_silence_mask, window_size)[:len(audio_float)]
            
            # 应用掩码
            filtered_audio = audio_float[full_mask]
            
            # 转换回int16
            result = (filtered_audio * 32767).astype(np.int16)
            
            return result.tobytes()
            
        except Exception as e:
            self.logger.error(f"静音移除失败: {e}")
            return audio_data
    
    def resample_audio(self, audio_data: bytes, 
                      from_rate: int, to_rate: int) -> bytes:
        """
        音频重采样
        
        Args:
            audio_data: 音频数据
            from_rate: 原始采样率
            to_rate: 目标采样率
            
        Returns:
            bytes: 重采样后的音频数据
        """
        try:
            if from_rate == to_rate:
                return audio_data
            
            # 使用ffmpeg进行重采样
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_input:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_output:
                    try:
                        # 写入原始音频
                        self._write_wav_file(temp_input.name, audio_data, from_rate)
                        
                        # 使用ffmpeg重采样
                        cmd = [
                            'ffmpeg', '-i', temp_input.name,
                            '-ar', str(to_rate),
                            '-ac', str(self.input_format.channels),
                            '-y', temp_output.name
                        ]
                        
                        subprocess.run(cmd, capture_output=True, check=True)
                        
                        # 读取结果
                        result = self._read_wav_file(temp_output.name)
                        
                        return result
                        
                    finally:
                        # 清理临时文件
                        for temp_file in [temp_input.name, temp_output.name]:
                            if os.path.exists(temp_file):
                                os.unlink(temp_file)
            
        except Exception as e:
            self.logger.error(f"音频重采样失败: {e}")
            return audio_data
    
    def _write_wav_file(self, file_path: str, audio_data: bytes, sample_rate: int):
        """写入WAV文件"""
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(self.input_format.channels)
            wav_file.setsampwidth(self.input_format.sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
    
    def _read_wav_file(self, file_path: str) -> bytes:
        """读取WAV文件"""
        with wave.open(file_path, 'rb') as wav_file:
            return wav_file.readframes(wav_file.getnframes())


class EnglishAudioGenerator:
    """英文音频生成器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.preprocessor = AudioPreprocessor(config)
        
        # 音频片段缓冲区
        self._audio_buffer = []
        self._buffer_lock = threading.Lock()
        
        # 输出格式
        self.output_format = AudioFormat(
            sample_rate=self.config.audio.output_sample_rate,
            channels=self.config.audio.channels,
            sample_width=2
        )
    
    def add_audio_segment(self, audio_data: bytes, timestamp: float = None):
        """
        添加音频片段到缓冲区
        
        Args:
            audio_data: 音频数据
            timestamp: 时间戳（如果为None则自动计算）
        """
        try:
            if timestamp is None:
                # 计算时间戳
                with self._buffer_lock:
                    if self._audio_buffer:
                        last_segment = self._audio_buffer[-1]
                        timestamp = last_segment.timestamp + last_segment.duration
                    else:
                        timestamp = 0.0
            
            # 创建音频片段
            duration = len(audio_data) / (self.output_format.sample_rate * 
                                        self.output_format.channels * 
                                        self.output_format.sample_width)
            
            segment = AudioSegment(audio_data, timestamp, duration, self.output_format)
            
            # 添加到缓冲区
            with self._buffer_lock:
                self._audio_buffer.append(segment)
            
            self.logger.debug(f"添加音频片段: 时间戳={timestamp:.2f}, 时长={duration:.2f}秒")
            
        except Exception as e:
            self.logger.error(f"添加音频片段失败: {e}")
    
    def generate_continuous_audio(self, output_path: str, 
                                total_duration: Optional[float] = None) -> bool:
        """
        生成连续的英文音频轨道
        
        Args:
            output_path: 输出文件路径
            total_duration: 总时长（如果指定，会填充静音）
            
        Returns:
            bool: 生成是否成功
        """
        try:
            with self._buffer_lock:
                segments = self._audio_buffer.copy()
            
            if not segments:
                self.logger.warning("没有音频片段可以合成")
                return False
            
            self.logger.info(f"开始合成音频，共 {len(segments)} 个片段")
            
            # 按时间戳排序
            segments.sort(key=lambda x: x.timestamp)
            
            # 计算最终音频的长度
            if total_duration:
                final_duration = total_duration
            else:
                last_segment = segments[-1]
                final_duration = last_segment.timestamp + last_segment.duration
            
            # 计算总样本数
            total_samples = int(final_duration * self.output_format.sample_rate * 
                              self.output_format.channels)
            
            # 创建输出数组
            output_audio = np.zeros(total_samples, dtype=np.int16)
            
            # 填充音频片段
            for segment in segments:
                start_sample = int(segment.timestamp * self.output_format.sample_rate * 
                                 self.output_format.channels)
                
                # 预处理音频片段
                processed_data = self.preprocessor.normalize_audio(segment.data)
                segment_array = np.frombuffer(processed_data, dtype=np.int16)
                
                # 确保不超出边界
                end_sample = min(start_sample + len(segment_array), total_samples)
                actual_length = end_sample - start_sample
                
                if actual_length > 0:
                    output_audio[start_sample:end_sample] = segment_array[:actual_length]
            
            # 应用后处理
            output_audio = self._apply_audio_effects(output_audio)
            
            # 保存到文件
            self._save_audio_file(output_path, output_audio)
            
            self.logger.info(f"音频合成完成: {output_path}, 时长: {final_duration:.2f}秒")
            return True
            
        except Exception as e:
            self.logger.error(f"音频合成失败: {e}")
            return False
    
    def _apply_audio_effects(self, audio_array: np.ndarray) -> np.ndarray:
        """
        应用音频效果
        
        Args:
            audio_array: 音频数组
            
        Returns:
            np.ndarray: 处理后的音频数组
        """
        try:
            # 转换为浮点数
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # 应用淡入淡出效果
            fade_samples = int(0.1 * self.output_format.sample_rate)  # 100ms淡入淡出
            
            if len(audio_float) > 2 * fade_samples:
                # 淡入
                fade_in = np.linspace(0, 1, fade_samples)
                audio_float[:fade_samples] *= fade_in
                
                # 淡出
                fade_out = np.linspace(1, 0, fade_samples)
                audio_float[-fade_samples:] *= fade_out
            
            # 压缩动态范围
            audio_float = self._apply_compression(audio_float)
            
            # 转换回int16
            return (audio_float * 32767).astype(np.int16)
            
        except Exception as e:
            self.logger.error(f"音频效果处理失败: {e}")
            return audio_array
    
    def _apply_compression(self, audio_float: np.ndarray, 
                          threshold: float = 0.7, ratio: float = 4.0) -> np.ndarray:
        """
        应用音频压缩
        
        Args:
            audio_float: 浮点音频数组
            threshold: 压缩阈值
            ratio: 压缩比
            
        Returns:
            np.ndarray: 压缩后的音频数组
        """
        try:
            # 计算音频包络
            abs_audio = np.abs(audio_float)
            
            # 应用压缩
            compressed = np.where(
                abs_audio > threshold,
                threshold + (abs_audio - threshold) / ratio,
                abs_audio
            )
            
            # 保持原始符号
            return np.sign(audio_float) * compressed
            
        except Exception as e:
            self.logger.error(f"音频压缩失败: {e}")
            return audio_float
    
    def _save_audio_file(self, file_path: str, audio_array: np.ndarray):
        """
        保存音频文件
        
        Args:
            file_path: 文件路径
            audio_array: 音频数组
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 保存为WAV文件
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(self.output_format.channels)
                wav_file.setsampwidth(self.output_format.sample_width)
                wav_file.setframerate(self.output_format.sample_rate)
                wav_file.writeframes(audio_array.tobytes())
            
            self.logger.info(f"音频文件已保存: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存音频文件失败: {e}")
            raise
    
    def clear_buffer(self):
        """清空音频缓冲区"""
        with self._buffer_lock:
            self._audio_buffer.clear()
        self.logger.info("音频缓冲区已清空")
    
    def get_buffer_info(self) -> dict:
        """
        获取缓冲区信息
        
        Returns:
            dict: 缓冲区统计信息
        """
        with self._buffer_lock:
            segments_count = len(self._audio_buffer)
            if segments_count > 0:
                total_duration = sum(segment.duration for segment in self._audio_buffer)
                first_timestamp = self._audio_buffer[0].timestamp
                last_segment = self._audio_buffer[-1]
                last_timestamp = last_segment.timestamp + last_segment.duration
            else:
                total_duration = 0
                first_timestamp = 0
                last_timestamp = 0
        
        return {
            'segments_count': segments_count,
            'total_duration': total_duration,
            'time_range': (first_timestamp, last_timestamp),
            'sample_rate': self.output_format.sample_rate,
            'channels': self.output_format.channels
        }


class AudioSynchronizer:
    """音频同步器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
    
    def synchronize_with_video(self, audio_path: str, video_duration: float,
                             output_path: str) -> bool:
        """
        将音频与视频时长同步
        
        Args:
            audio_path: 输入音频文件路径
            video_duration: 视频时长（秒）
            output_path: 输出音频文件路径
            
        Returns:
            bool: 同步是否成功
        """
        try:
            self.logger.info(f"开始音频同步: 目标时长 {video_duration:.2f}秒")
            
            # 使用ffmpeg进行时长调整
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-af', f'apad=whole_dur={video_duration}',  # 填充到指定时长
                '-ac', str(self.config.audio.channels),
                '-ar', str(self.config.audio.output_sample_rate),
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.logger.info(f"音频同步完成: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"音频同步失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"音频同步过程中发生错误: {e}")
            return False


if __name__ == "__main__":
    # 测试音频处理模块
    def test_audio_processing():
        """测试音频处理功能"""
        try:
            # 创建测试音频数据
            sample_rate = 24000
            duration = 2.0  # 2秒
            samples = int(sample_rate * duration)
            
            # 生成正弦波测试音频
            t = np.linspace(0, duration, samples, False)
            frequency = 440  # A4音符
            amplitude = 16000
            audio_data = (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.int16)
            
            # 测试音频生成器
            generator = EnglishAudioGenerator()
            
            # 添加音频片段
            chunk_size = sample_rate // 10  # 100ms chunks
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                timestamp = i / sample_rate
                generator.add_audio_segment(chunk.tobytes(), timestamp)
            
            # 生成连续音频
            output_path = "test_output.wav"
            if generator.generate_continuous_audio(output_path, duration):
                print(f"测试音频生成成功: {output_path}")
                
                # 获取缓冲区信息
                info = generator.get_buffer_info()
                print("缓冲区信息:", info)
            else:
                print("测试音频生成失败")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    test_audio_processing()