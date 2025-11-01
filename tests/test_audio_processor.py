"""
音频处理模块测试
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import patch, MagicMock, mock_open
from src.modules.audio_processor import (
    AudioFormat, AudioSegment, AudioPreprocessor, 
    EnglishAudioGenerator, AudioSynchronizer
)


class TestAudioFormat:
    """音频格式测试类"""
    
    def test_audio_format_initialization(self):
        """测试音频格式初始化"""
        format_info = AudioFormat(44100, 2, 2)
        
        assert format_info.sample_rate == 44100
        assert format_info.channels == 2
        assert format_info.sample_width == 2
        assert format_info.frame_size == 4  # 2 channels * 2 bytes


class TestAudioSegment:
    """音频片段测试类"""
    
    def test_audio_segment_initialization(self):
        """测试音频片段初始化"""
        format_info = AudioFormat(44100, 1, 2)
        audio_data = b'\\x00\\x01' * 1000  # 1000个样本
        
        segment = AudioSegment(audio_data, 0.0, 1.0, format_info)
        
        assert segment.data == audio_data
        assert segment.timestamp == 0.0
        assert segment.duration == 1.0
        assert segment.sample_count == 1000
    
    def test_audio_segment_to_numpy(self):
        """测试音频片段转换为numpy数组"""
        format_info = AudioFormat(44100, 1, 2)  # 16位单声道
        audio_data = np.array([100, -200, 300, -400], dtype=np.int16).tobytes()
        
        segment = AudioSegment(audio_data, 0.0, 1.0, format_info)
        array = segment.to_numpy()
        
        assert isinstance(array, np.ndarray)
        assert array.dtype == np.int16
        assert len(array) == 4
        assert array[0] == 100
        assert array[1] == -200
    
    def test_audio_segment_from_numpy(self):
        """测试从numpy数组创建音频片段"""
        format_info = AudioFormat(44100, 1, 2)
        array = np.array([100, -200, 300, -400], dtype=np.int16)
        
        segment = AudioSegment.from_numpy(array, 0.5, format_info)
        
        assert segment.timestamp == 0.5
        assert len(segment.data) == 8  # 4 samples * 2 bytes
        assert segment.sample_count == 4


class TestAudioPreprocessor:
    """音频预处理器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.preprocessor = AudioPreprocessor()
    
    def test_normalize_audio(self):
        """测试音频规范化"""
        # 创建测试音频数据（16位PCM）
        original_data = np.array([16000, -16000, 8000, -8000], dtype=np.int16).tobytes()
        
        normalized_data = self.preprocessor.normalize_audio(original_data)
        
        assert len(normalized_data) == len(original_data)
        
        # 转换回numpy检查结果
        normalized_array = np.frombuffer(normalized_data, dtype=np.int16)
        assert len(normalized_array) == 4
    
    def test_remove_silence(self):
        """测试静音移除"""
        # 创建包含静音的测试数据
        silence = np.zeros(1600, dtype=np.int16)  # 静音段
        sound = np.full(1600, 1000, dtype=np.int16)  # 有声段
        mixed_data = np.concatenate([silence, sound, silence]).tobytes()
        
        filtered_data = self.preprocessor.remove_silence(mixed_data, threshold=0.001)
        
        # 静音移除后数据应该更短
        assert len(filtered_data) <= len(mixed_data)
    
    @patch('src.modules.audio_processor.subprocess.run')
    @patch('src.modules.audio_processor.tempfile.NamedTemporaryFile')
    def test_resample_audio(self, mock_tempfile, mock_run):
        """测试音频重采样"""
        # 模拟临时文件
        mock_temp = MagicMock()
        mock_temp.name = 'temp_audio.wav'
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        # 模拟subprocess成功执行
        mock_run.return_value = MagicMock(returncode=0)
        
        # 模拟文件读写
        with patch.object(self.preprocessor, '_write_wav_file'), \
             patch.object(self.preprocessor, '_read_wav_file', return_value=b'resampled_data'):
            
            original_data = b'original_audio_data'
            result = self.preprocessor.resample_audio(original_data, 44100, 16000)
            
            assert result == b'resampled_data'
    
    def test_resample_audio_same_rate(self):
        """测试相同采样率的重采样"""
        original_data = b'audio_data'
        result = self.preprocessor.resample_audio(original_data, 44100, 44100)
        
        assert result == original_data  # 应该返回原始数据


class TestEnglishAudioGenerator:
    """英文音频生成器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.generator = EnglishAudioGenerator()
    
    def test_add_audio_segment(self):
        """测试添加音频片段"""
        audio_data = b'\\x00\\x01' * 1000
        
        self.generator.add_audio_segment(audio_data, 1.0)
        
        buffer_info = self.generator.get_buffer_info()
        assert buffer_info['segments_count'] == 1
        assert buffer_info['time_range'][0] == 1.0
    
    def test_add_audio_segment_auto_timestamp(self):
        """测试自动时间戳添加音频片段"""
        audio_data1 = b'\\x00\\x01' * 1000
        audio_data2 = b'\\x00\\x02' * 1000
        
        self.generator.add_audio_segment(audio_data1, 0.0)
        self.generator.add_audio_segment(audio_data2)  # 自动计算时间戳
        
        buffer_info = self.generator.get_buffer_info()
        assert buffer_info['segments_count'] == 2
    
    @patch.object(EnglishAudioGenerator, '_save_audio_file')
    @patch.object(EnglishAudioGenerator, '_apply_audio_effects')
    def test_generate_continuous_audio(self, mock_effects, mock_save):
        """测试生成连续音频"""
        mock_effects.side_effect = lambda x: x  # 直接返回输入
        mock_save.return_value = None
        
        # 添加测试音频片段
        audio_data = np.array([100, -100] * 500, dtype=np.int16).tobytes()
        self.generator.add_audio_segment(audio_data, 0.0)
        self.generator.add_audio_segment(audio_data, 1.0)
        
        result = self.generator.generate_continuous_audio('output.wav', 3.0)
        
        assert result == True
        mock_save.assert_called_once()
    
    def test_generate_continuous_audio_no_segments(self):
        """测试无音频片段时的连续音频生成"""
        result = self.generator.generate_continuous_audio('output.wav', 1.0)
        
        assert result == False
    
    def test_clear_buffer(self):
        """测试清空缓冲区"""
        audio_data = b'\\x00\\x01' * 1000
        self.generator.add_audio_segment(audio_data, 0.0)
        
        assert self.generator.get_buffer_info()['segments_count'] == 1
        
        self.generator.clear_buffer()
        
        assert self.generator.get_buffer_info()['segments_count'] == 0
    
    def test_get_buffer_info(self):
        """测试获取缓冲区信息"""
        info = self.generator.get_buffer_info()
        
        assert 'segments_count' in info
        assert 'total_duration' in info
        assert 'time_range' in info
        assert 'sample_rate' in info
        assert 'channels' in info
    
    def test_apply_compression(self):
        """测试音频压缩"""
        # 创建测试音频数组
        audio_float = np.array([0.5, -0.9, 0.8, -0.6], dtype=np.float32)
        
        compressed = self.generator._apply_compression(audio_float, threshold=0.7, ratio=4.0)
        
        assert len(compressed) == len(audio_float)
        assert isinstance(compressed, np.ndarray)
        # 检查压缩效果：超过阈值的值应该被压缩
        assert abs(compressed[1]) < abs(audio_float[1])  # -0.9 应该被压缩
        assert abs(compressed[2]) < abs(audio_float[2])  # 0.8 应该被压缩


class TestAudioSynchronizer:
    """音频同步器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.synchronizer = AudioSynchronizer()
    
    @patch('src.modules.audio_processor.subprocess.run')
    def test_synchronize_with_video_success(self, mock_run):
        """测试音频与视频同步成功"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.synchronizer.synchronize_with_video(
            'input_audio.wav', 60.0, 'output_audio.wav'
        )
        
        assert result == True
        mock_run.assert_called_once()
        
        # 检查ffmpeg命令参数
        call_args = mock_run.call_args[0][0]
        assert 'ffmpeg' in call_args
        assert 'apad=whole_dur=60.0' in str(call_args)
    
    @patch('src.modules.audio_processor.subprocess.run')
    def test_synchronize_with_video_failure(self, mock_run):
        """测试音频与视频同步失败"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg', stderr='Error')
        
        result = self.synchronizer.synchronize_with_video(
            'input_audio.wav', 60.0, 'output_audio.wav'
        )
        
        assert result == False


class TestIntegration:
    """集成测试类"""
    
    def test_audio_processing_pipeline(self):
        """测试音频处理流水线"""
        # 创建测试组件
        preprocessor = AudioPreprocessor()
        generator = EnglishAudioGenerator()
        
        # 创建测试音频数据
        test_audio = np.array([1000, -1000, 500, -500], dtype=np.int16).tobytes()
        
        # 预处理音频
        processed_audio = preprocessor.normalize_audio(test_audio)
        
        # 添加到生成器
        generator.add_audio_segment(processed_audio, 0.0)
        generator.add_audio_segment(processed_audio, 1.0)
        
        # 检查缓冲区状态
        buffer_info = generator.get_buffer_info()
        assert buffer_info['segments_count'] == 2
        assert buffer_info['total_duration'] > 0
    
    @patch('src.modules.audio_processor.wave.open')
    def test_save_audio_file(self, mock_wave_open):
        """测试音频文件保存"""
        generator = EnglishAudioGenerator()
        
        # 模拟wave文件操作
        mock_wav_file = MagicMock()
        mock_wave_open.return_value.__enter__.return_value = mock_wav_file
        
        # 创建测试音频数组
        test_array = np.array([100, -100, 200, -200], dtype=np.int16)
        
        # 调用保存方法
        generator._save_audio_file('test.wav', test_array)
        
        # 验证wav文件设置
        mock_wav_file.setnchannels.assert_called_once()
        mock_wav_file.setsampwidth.assert_called_once()
        mock_wav_file.setframerate.assert_called_once()
        mock_wav_file.writeframes.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])