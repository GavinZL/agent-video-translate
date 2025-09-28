"""
pytest配置文件
定义测试的全局设置和fixtures
"""

import pytest
import sys
import os
import asyncio
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def event_loop():
    """创建一个事件循环用于异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_video_file():
    """创建临时视频文件用于测试"""
    import tempfile
    import numpy as np
    import cv2
    
    # 创建临时视频文件
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_path = temp_file.name
    
    # 创建一个简单的测试视频
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_path, fourcc, 30.0, (640, 480))
    
    # 写入几帧
    for i in range(90):  # 3秒的视频
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        writer.write(frame)
    
    writer.release()
    
    yield temp_path
    
    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_audio_file():
    """创建临时音频文件用于测试"""
    import tempfile
    import wave
    import numpy as np
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_path = temp_file.name
    
    # 创建一个简单的测试音频文件
    sample_rate = 16000
    duration = 3.0  # 3秒
    samples = int(sample_rate * duration)
    
    # 生成正弦波
    t = np.linspace(0, duration, samples, False)
    frequency = 440  # A4音符
    audio_data = (16000 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)
    
    # 写入WAV文件
    with wave.open(temp_path, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    yield temp_path
    
    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_srt_file():
    """创建临时SRT字幕文件用于测试"""
    import tempfile
    
    srt_content = """1
00:00:00,000 --> 00:00:03,000
Hello, this is a test subtitle.

2
00:00:03,500 --> 00:00:06,000
This is the second subtitle.

3
00:00:06,500 --> 00:00:09,000
And this is the third subtitle.

"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(srt_content)
        temp_path = temp_file.name
    
    yield temp_path
    
    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_api_response():
    """模拟API响应数据"""
    return {
        'translated_texts': [
            "Hello, this is a translation.",
            "This is another translation.",
            "And this is the final translation."
        ],
        'audio_segments': [
            b'audio_data_1',
            b'audio_data_2', 
            b'audio_data_3'
        ]
    }


@pytest.fixture
def sample_config():
    """提供测试配置"""
    return {
        'api': {
            'api_key': 'test_api_key',
            'api_url': 'wss://test.example.com/api',
            'model_name': 'test-model',
            'target_language': 'en',
            'voice_type': 'Cherry'
        },
        'audio': {
            'input_sample_rate': 16000,
            'output_sample_rate': 24000,
            'audio_chunk_size': 1600,
            'audio_format': 'pcm16',
            'channels': 1
        },
        'video': {
            'frame_extract_rate': 2,
            'output_video_quality': 'high',
            'video_codec': 'h264',
            'audio_codec': 'aac',
            'audio_bitrate': '128k'
        },
        'process': {
            'max_retry_count': 3,
            'timeout_seconds': 30,
            'concurrent_workers': 4,
            'buffer_size': 8192
        }
    }


# 标记慢速测试
def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# 跳过需要实际文件的测试
def pytest_runtest_setup(item):
    """测试运行前的设置"""
    if 'requires_ffmpeg' in item.keywords:
        import shutil
        if not shutil.which('ffmpeg'):
            pytest.skip("FFmpeg not found, skipping test")
    
    if 'requires_api_key' in item.keywords:
        if not os.getenv('DASHSCOPE_API_KEY') or os.getenv('DASHSCOPE_API_KEY') == 'test_api_key':
            pytest.skip("Real API key required, skipping test")


# 收集测试统计信息
def pytest_sessionfinish(session, exitstatus):
    """测试会话结束时的处理"""
    if hasattr(session.config, 'option') and getattr(session.config.option, 'verbose', 0) > 0:
        print(f"\nTest session completed with exit status: {exitstatus}")