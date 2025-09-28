"""
集成测试 - 测试整个视频翻译流程的集成
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import patch, MagicMock, AsyncMock
from src.main import VideoTranslationPipeline
from src.utils.config import Config


class TestVideoTranslationPipeline:
    """视频翻译流水线集成测试"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        with patch.dict(os.environ, {
            'DASHSCOPE_API_KEY': 'test_api_key',
            'INPUT_VIDEO_PATH': 'test_input.mp4',
            'OUTPUT_VIDEO_PATH': 'test_output.mp4',
            'TEMP_DIR': 'temp_test/',
            'LOG_LEVEL': 'DEBUG'
        }):
            config = Config()
            return config
    
    @pytest.fixture
    def pipeline(self, mock_config):
        """创建测试流水线"""
        with patch('src.main.get_config', return_value=mock_config):
            return VideoTranslationPipeline()
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, pipeline):
        """测试流水线初始化"""
        assert pipeline.video_processor is not None
        assert pipeline.translation_engine is not None
        assert pipeline.audio_generator is not None
        assert pipeline.subtitle_generator is not None
        assert pipeline.video_composer is not None
        assert pipeline.is_processing == False
    
    @pytest.mark.asyncio
    async def test_analyze_video_success(self, pipeline):
        """测试视频分析成功"""
        # 模拟视频处理器
        mock_video_info = MagicMock()
        mock_video_info.duration = 30.0
        mock_video_info.width = 1920
        mock_video_info.height = 1080
        mock_video_info.fps = 30.0
        
        with patch.object(pipeline.video_processor, 'validate_video', return_value=True), \
             patch.object(pipeline.video_processor, 'analyze_video', return_value=mock_video_info), \
             patch.object(pipeline.video_processor, 'prepare_processing', return_value={
                 'estimated_frames': 60,
                 'estimated_audio_chunks': 100
             }):
            
            result = await pipeline._analyze_video('test_input.mp4')
            
            assert result == True
            assert pipeline.processing_stats['video_duration'] == 30.0
    
    @pytest.mark.asyncio
    async def test_analyze_video_failure(self, pipeline):
        """测试视频分析失败"""
        with patch.object(pipeline.video_processor, 'validate_video', return_value=False):
            result = await pipeline._analyze_video('test_input.mp4')
            
            assert result == False
    
    @pytest.mark.asyncio
    async def test_initialize_translation_success(self, pipeline):
        """测试翻译引擎初始化成功"""
        with patch.object(pipeline.translation_engine, 'initialize', return_value=True):
            result = await pipeline._initialize_translation()
            
            assert result == True
    
    @pytest.mark.asyncio
    async def test_initialize_translation_failure(self, pipeline):
        """测试翻译引擎初始化失败"""
        with patch.object(pipeline.translation_engine, 'initialize', return_value=False):
            result = await pipeline._initialize_translation()
            
            assert result == False
    
    @pytest.mark.asyncio
    async def test_process_audio_and_video(self, pipeline):
        """测试音视频处理"""
        # 模拟翻译引擎
        mock_translate_stream = AsyncMock()
        mock_translated_texts = ["Hello world", "How are you?"]
        mock_audio_segments = [b'audio1', b'audio2']
        
        with patch.object(pipeline.translation_engine, 'translate_stream', mock_translate_stream), \
             patch.object(pipeline.translation_engine, 'get_translation_results', 
                         return_value=(mock_translated_texts, mock_audio_segments)), \
             patch.object(pipeline, '_create_audio_stream'), \
             patch.object(pipeline, '_create_image_stream'):
            
            result = await pipeline._process_audio_and_video('test_input.mp4')
            
            assert result == True
            assert pipeline.processing_stats['translation_segments'] == 2
    
    @pytest.mark.asyncio
    async def test_generate_english_audio(self, pipeline):
        """测试英文音频生成"""
        with patch.object(pipeline.audio_generator, 'generate_continuous_audio', return_value=True):
            result = await pipeline._generate_english_audio()
            
            assert result is not None
            assert 'english_audio.wav' in result
    
    @pytest.mark.asyncio
    async def test_generate_subtitles(self, pipeline):
        """测试字幕生成"""
        with patch.object(pipeline.subtitle_generator, 'optimize_timing'), \
             patch.object(pipeline.subtitle_generator, 'save_to_file', return_value=True):
            
            result = await pipeline._generate_subtitles()
            
            assert result is not None
            assert 'subtitles.srt' in result
    
    @pytest.mark.asyncio
    async def test_synchronize_audio(self, pipeline):
        """测试音频同步"""
        with patch.object(pipeline.audio_synchronizer, 'synchronize_with_video', return_value=True):
            result = await pipeline._synchronize_audio('input_audio.wav')
            
            assert result is not None
            assert 'synced_audio.wav' in result
    
    @pytest.mark.asyncio
    async def test_compose_final_video(self, pipeline):
        """测试最终视频合成"""
        with patch.object(pipeline.video_composer, 'compose_video', return_value=True):
            result = await pipeline._compose_final_video(
                'input.mp4', 'audio.wav', 'subtitles.srt', 'output.mp4'
            )
            
            assert result == True
    
    @pytest.mark.asyncio
    async def test_complete_process_video_success(self, pipeline):
        """测试完整的视频处理流程成功"""
        # 模拟所有步骤成功
        with patch.object(pipeline, '_analyze_video', return_value=True), \
             patch.object(pipeline, '_initialize_translation', return_value=True), \
             patch.object(pipeline, '_process_audio_and_video', return_value=True), \
             patch.object(pipeline, '_generate_english_audio', return_value='audio.wav'), \
             patch.object(pipeline, '_generate_subtitles', return_value='subtitles.srt'), \
             patch.object(pipeline, '_synchronize_audio', return_value='synced_audio.wav'), \
             patch.object(pipeline, '_compose_final_video', return_value=True), \
             patch.object(pipeline, '_cleanup_and_validate'), \
             patch.object(pipeline, '_cleanup_resources'):
            
            result = await pipeline.process_video('input.mp4', 'output.mp4')
            
            assert result == True
            assert pipeline.is_processing == False
    
    @pytest.mark.asyncio
    async def test_complete_process_video_failure(self, pipeline):
        """测试完整的视频处理流程失败"""
        # 模拟视频分析失败
        with patch.object(pipeline, '_analyze_video', return_value=False), \
             patch.object(pipeline, '_cleanup_resources'):
            
            result = await pipeline.process_video('input.mp4', 'output.mp4')
            
            assert result == False
            assert pipeline.is_processing == False
    
    @pytest.mark.asyncio
    async def test_process_video_already_processing(self, pipeline):
        """测试处理中时的重复调用"""
        pipeline.is_processing = True
        
        result = await pipeline.process_video('input.mp4', 'output.mp4')
        
        assert result == False
    
    def test_get_progress_info(self, pipeline):
        """测试获取进度信息"""
        progress_info = pipeline.get_progress_info()
        
        assert 'is_processing' in progress_info
        assert 'stats' in progress_info
        assert 'config' in progress_info
        assert progress_info['is_processing'] == False
    
    @pytest.mark.asyncio
    async def test_create_audio_stream(self, pipeline):
        """测试创建音频流"""
        mock_chunks = [b'chunk1', b'chunk2', b'chunk3']
        
        with patch.object(pipeline.video_processor.audio_extractor, 'extract_audio_chunks', 
                         return_value=mock_chunks):
            
            audio_stream = pipeline._create_audio_stream('input.mp4')
            
            # 收集异步生成器的结果
            chunks = []
            async for chunk in audio_stream:
                chunks.append(chunk)
                if len(chunks) >= 3:  # 限制测试范围
                    break
            
            assert len(chunks) == 3
            assert chunks[0] == b'chunk1'
            assert pipeline.processing_stats['audio_chunks_processed'] >= 3
    
    @pytest.mark.asyncio
    async def test_create_image_stream(self, pipeline):
        """测试创建图像流"""
        mock_frames = [(0.0, b'frame1'), (0.5, b'frame2'), (1.0, b'frame3')]
        
        with patch.object(pipeline.video_processor.frame_extractor, 'extract_frame_data', 
                         return_value=mock_frames):
            
            image_stream = pipeline._create_image_stream('input.mp4')
            
            # 收集异步生成器的结果
            frames = []
            async for timestamp, frame_data in image_stream:
                frames.append((timestamp, frame_data))
                if len(frames) >= 3:  # 限制测试范围
                    break
            
            assert len(frames) == 3
            assert frames[0] == (0.0, b'frame1')
            assert pipeline.processing_stats['image_frames_processed'] >= 3
    
    @pytest.mark.asyncio
    async def test_cleanup_and_validate(self, pipeline):
        """测试清理和验证"""
        mock_video_info = {
            'duration': 30.0,
            'size': 1024000
        }
        
        with patch.object(pipeline.video_composer, 'get_video_info', return_value=mock_video_info), \
             patch.object(pipeline.video_composer, 'extract_thumbnail', return_value=True):
            
            # 应该不抛出异常
            await pipeline._cleanup_and_validate('output.mp4')
    
    @pytest.mark.asyncio
    async def test_cleanup_resources(self, pipeline):
        """测试资源清理"""
        with patch.object(pipeline.translation_engine, 'shutdown'), \
             patch.object(pipeline.audio_generator, 'clear_buffer'), \
             patch.object(pipeline.subtitle_generator, 'clear'):
            
            # 应该不抛出异常
            await pipeline._cleanup_resources()


class TestMainFunction:
    """主函数测试"""
    
    @pytest.mark.asyncio
    @patch('src.main.VideoTranslationPipeline')
    @patch('src.main.Path.exists')
    @patch('sys.argv', ['main.py', '--input', 'test.mp4', '--output', 'output.mp4'])
    async def test_main_function_success(self, mock_exists, mock_pipeline_class):
        """测试主函数成功执行"""
        # 模拟文件存在
        mock_exists.return_value = True
        
        # 模拟流水线
        mock_pipeline = MagicMock()
        mock_pipeline.process_video = AsyncMock(return_value=True)
        mock_pipeline.get_progress_info.return_value = {
            'stats': {
                'video_duration': 30.0,
                'translation_segments': 5,
                'audio_chunks_processed': 100,
                'image_frames_processed': 60
            }
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # 导入并运行main (需要实际的实现来测试)
        # 这里只是示例结构
        pass
    
    @pytest.mark.asyncio
    @patch('src.main.VideoTranslationPipeline')
    @patch('src.main.Path.exists')
    @patch('sys.argv', ['main.py', '--input', 'nonexistent.mp4'])
    async def test_main_function_file_not_found(self, mock_exists, mock_pipeline_class):
        """测试主函数文件不存在"""
        # 模拟文件不存在
        mock_exists.return_value = False
        
        # 主函数应该返回错误码
        # 这里只是示例结构
        pass


class TestErrorHandling:
    """错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_exception_handling_in_process_video(self):
        """测试process_video中的异常处理"""
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test_key'}):
            pipeline = VideoTranslationPipeline()
            
            # 模拟异常
            with patch.object(pipeline, '_analyze_video', side_effect=Exception("Test error")):
                result = await pipeline.process_video('input.mp4')
                
                assert result == False
                assert 'Test error' in pipeline.processing_stats['errors']
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_exception(self):
        """测试异常时的资源清理"""
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test_key'}):
            pipeline = VideoTranslationPipeline()
            
            with patch.object(pipeline, '_analyze_video', side_effect=Exception("Test error")), \
                 patch.object(pipeline, '_cleanup_resources') as mock_cleanup:
                
                await pipeline.process_video('input.mp4')
                
                # 确保清理被调用
                mock_cleanup.assert_called_once()


class TestPerformanceMetrics:
    """性能指标测试"""
    
    @pytest.mark.asyncio
    async def test_processing_stats_collection(self):
        """测试处理统计信息收集"""
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test_key'}):
            pipeline = VideoTranslationPipeline()
            
            # 模拟成功的处理流程
            with patch.object(pipeline, '_analyze_video', return_value=True), \
                 patch.object(pipeline, '_initialize_translation', return_value=True), \
                 patch.object(pipeline, '_process_audio_and_video', return_value=True), \
                 patch.object(pipeline, '_generate_english_audio', return_value='audio.wav'), \
                 patch.object(pipeline, '_generate_subtitles', return_value='subtitles.srt'), \
                 patch.object(pipeline, '_synchronize_audio', return_value='synced_audio.wav'), \
                 patch.object(pipeline, '_compose_final_video', return_value=True), \
                 patch.object(pipeline, '_cleanup_and_validate'), \
                 patch.object(pipeline, '_cleanup_resources'):
                
                await pipeline.process_video('input.mp4')
                
                # 检查统计信息
                stats = pipeline.processing_stats
                assert 'start_time' in stats
                assert 'end_time' in stats
                assert stats['end_time'] > stats['start_time']


if __name__ == "__main__":
    pytest.main([__file__])