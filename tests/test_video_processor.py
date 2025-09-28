"""
视频处理模块测试
"""

import pytest
import os
import tempfile
import numpy as np
import cv2
from unittest.mock import patch, MagicMock, mock_open
from src.modules.video_processor import VideoProcessor, VideoInfo, AudioExtractor, FrameExtractor


class TestVideoInfo:
    """视频信息测试类"""
    
    @patch('src.modules.video_processor.cv2.VideoCapture')
    @patch('src.modules.video_processor.os.path.getsize')
    def test_video_info_initialization(self, mock_getsize, mock_videocapture):
        """测试视频信息初始化"""
        # 模拟文件大小
        mock_getsize.return_value = 1024000
        
        # 模拟OpenCV VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_WIDTH: 1920,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080,
            cv2.CAP_PROP_FRAME_COUNT: 900
        }.get(prop, 0)
        mock_videocapture.return_value = mock_cap
        
        video_info = VideoInfo('test_video.mp4')
        
        assert video_info.fps == 30.0
        assert video_info.width == 1920
        assert video_info.height == 1080
        assert video_info.total_frames == 900
        assert video_info.duration == 30.0  # 900 frames / 30 fps
        assert video_info.file_size == 1024000
    
    def test_video_info_to_dict(self):
        """测试视频信息转换为字典"""
        with patch('src.modules.video_processor.cv2.VideoCapture'), \
             patch('src.modules.video_processor.os.path.getsize', return_value=1024):
            
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.return_value = 0
            
            video_info = VideoInfo('test.mp4')
            info_dict = video_info.to_dict()
            
            assert 'file_path' in info_dict
            assert 'duration' in info_dict
            assert 'fps' in info_dict
            assert 'width' in info_dict
            assert 'height' in info_dict


class TestAudioExtractor:
    """音频提取器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.extractor = AudioExtractor()
    
    @patch('src.modules.video_processor.subprocess.run')
    @patch('src.modules.video_processor.os.path.exists')
    def test_extract_audio_success(self, mock_exists, mock_run):
        """测试音频提取成功"""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.extractor.extract_audio('input.mp4', 'output.wav')
        
        assert result == 'output.wav'
        mock_run.assert_called_once()
    
    @patch('src.modules.video_processor.subprocess.run')
    def test_extract_audio_failure(self, mock_run):
        """测试音频提取失败"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg', stderr='Error')
        
        with pytest.raises(RuntimeError, match="ffmpeg音频提取失败"):
            self.extractor.extract_audio('input.mp4')
    
    @patch('src.modules.video_processor.subprocess.Popen')
    def test_extract_audio_chunks(self, mock_popen):
        """测试流式音频提取"""
        # 模拟ffmpeg进程
        mock_process = MagicMock()
        mock_process.stdout.read.side_effect = [
            b'RIFF' + b'\\x00' * 40,  # WAV头部
            b'\\x00\\x01' * 800,      # 音频数据块1
            b'\\x00\\x02' * 800,      # 音频数据块2
            b''                       # 结束
        ]
        mock_process.poll.side_effect = [None, None, 0]
        mock_process.wait.return_value = 0
        mock_process.stderr.read.return_value = b''
        mock_popen.return_value = mock_process
        
        chunks = list(self.extractor.extract_audio_chunks('input.mp4'))
        
        assert len(chunks) == 2
        assert len(chunks[0]) == 1600  # 音频块大小
        assert len(chunks[1]) == 1600


class TestFrameExtractor:
    """视频帧提取器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.extractor = FrameExtractor()
    
    @patch('src.modules.video_processor.cv2.VideoCapture')
    @patch('src.modules.video_processor.cv2.imwrite')
    @patch('src.modules.video_processor.os.makedirs')
    def test_extract_frames(self, mock_makedirs, mock_imwrite, mock_videocapture):
        """测试视频帧提取"""
        # 模拟VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0  # FPS
        
        # 模拟帧读取
        frames = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)  # 结束
        ]
        mock_cap.read.side_effect = frames
        mock_videocapture.return_value = mock_cap
        
        mock_imwrite.return_value = True
        
        frame_paths = list(self.extractor.extract_frames('input.mp4'))
        
        assert len(frame_paths) >= 1
        mock_imwrite.assert_called()
    
    @patch('src.modules.video_processor.cv2.VideoCapture')
    @patch('src.modules.video_processor.cv2.imencode')
    def test_extract_frame_data(self, mock_imencode, mock_videocapture):
        """测试流式帧数据提取"""
        # 模拟VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0  # FPS
        
        # 模拟帧读取
        frames = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)  # 结束
        ]
        mock_cap.read.side_effect = frames
        mock_videocapture.return_value = mock_cap
        
        # 模拟JPEG编码
        mock_imencode.return_value = (True, np.array([0xFF, 0xD8, 0xFF]))
        
        frame_data = list(self.extractor.extract_frame_data('input.mp4'))
        
        assert len(frame_data) >= 1
        timestamp, image_data = frame_data[0]
        assert timestamp >= 0
        assert len(image_data) > 0


class TestVideoProcessor:
    """视频处理器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.processor = VideoProcessor()
    
    @patch('src.modules.video_processor.VideoInfo')
    @patch('src.modules.video_processor.os.path.exists')
    def test_analyze_video(self, mock_exists, mock_video_info):
        """测试视频分析"""
        mock_exists.return_value = True
        
        # 模拟VideoInfo
        mock_info = MagicMock()
        mock_info.duration = 30.0
        mock_info.width = 1920
        mock_info.height = 1080
        mock_info.fps = 30.0
        mock_video_info.return_value = mock_info
        
        result = self.processor.analyze_video('test.mp4')
        
        assert result == mock_info
        mock_video_info.assert_called_once_with('test.mp4')
    
    def test_analyze_video_file_not_found(self):
        """测试分析不存在的视频文件"""
        with pytest.raises(FileNotFoundError):
            self.processor.analyze_video('nonexistent.mp4')
    
    @patch.object(VideoProcessor, 'analyze_video')
    def test_validate_video_success(self, mock_analyze):
        """测试视频验证成功"""
        # 模拟有效的视频信息
        mock_info = MagicMock()
        mock_info.duration = 30.0
        mock_info.width = 1920
        mock_info.height = 1080
        mock_info.has_audio = True
        mock_analyze.return_value = mock_info
        
        result = self.processor.validate_video('test.mp4')
        
        assert result == True
    
    @patch.object(VideoProcessor, 'analyze_video')
    def test_validate_video_invalid_duration(self, mock_analyze):
        """测试无效时长的视频验证"""
        # 模拟无效的视频信息
        mock_info = MagicMock()
        mock_info.duration = 0  # 无效时长
        mock_info.width = 1920
        mock_info.height = 1080
        mock_analyze.return_value = mock_info
        
        result = self.processor.validate_video('test.mp4')
        
        assert result == False
    
    @patch.object(VideoProcessor, 'validate_video')
    @patch.object(VideoProcessor, 'analyze_video')
    @patch('src.modules.video_processor.os.makedirs')
    def test_prepare_processing(self, mock_makedirs, mock_analyze, mock_validate):
        """测试处理准备"""
        mock_validate.return_value = True
        
        # 模拟视频信息
        mock_info = MagicMock()
        mock_info.duration = 60.0
        mock_info.to_dict.return_value = {'duration': 60.0}
        mock_analyze.return_value = mock_info
        
        result = self.processor.prepare_processing('test.mp4')
        
        assert 'video_info' in result
        assert 'estimated_frames' in result
        assert 'estimated_audio_chunks' in result
        assert result['video_info']['duration'] == 60.0


if __name__ == "__main__":
    pytest.main([__file__])