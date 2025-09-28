"""
视频翻译系统主程序

这是视频翻译系统的主入口点，整合所有模块实现完整的处理流程。
从中文视频到英文视频的端到端翻译处理。
"""

import asyncio
import logging
import sys
import time
import traceback
from typing import Optional, Dict, Any
import argparse
from pathlib import Path

# 导入模块
from modules.video_processor import VideoProcessor
from modules.qwen_api import TranslationEngine
from modules.audio_processor import EnglishAudioGenerator, AudioSynchronizer
from modules.subtitle_generator import SRTGenerator
from modules.video_composer import VideoComposer
from utils.config import get_config, reload_config


class VideoTranslationPipeline:
    """视频翻译处理管道"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化翻译管道
        
        Args:
            config_file: 配置文件路径
        """
        try:
            # 加载配置
            self.config = get_config(config_file)
            if not self.config.validate():
                raise ValueError("配置验证失败")
            
            # 设置日志
            self.logger = logging.getLogger(__name__)
            self.logger.info("初始化视频翻译管道...")
            
            # 初始化各个模块
            self.video_processor = VideoProcessor(self.config)
            self.translation_engine = TranslationEngine(self.config)
            self.audio_generator = EnglishAudioGenerator(self.config)
            self.audio_synchronizer = AudioSynchronizer(self.config)
            self.subtitle_generator = SRTGenerator(self.config)
            self.video_composer = VideoComposer(self.config)
            
            # 处理状态
            self.is_processing = False
            self.processing_stats = {
                'start_time': 0,
                'end_time': 0,
                'video_duration': 0,
                'audio_chunks_processed': 0,
                'image_frames_processed': 0,
                'translation_segments': 0,
                'errors': []
            }
            
        except Exception as e:
            print(f"初始化失败: {e}")
            raise
    
    async def process_video(self, 
                          input_video_path: Optional[str] = None,
                          output_video_path: Optional[str] = None) -> bool:
        """
        处理视频翻译的主要流程
        
        Args:
            input_video_path: 输入视频路径，如果为None则使用配置中的路径
            output_video_path: 输出视频路径，如果为None则使用配置中的路径
            
        Returns:
            bool: 处理是否成功
        """
        try:
            if self.is_processing:
                self.logger.error("已有处理任务在进行中")
                return False
            
            self.is_processing = True
            self.processing_stats['start_time'] = time.time()
            
            # 确定文件路径
            input_path = input_video_path or self.config.file_paths.input_video_path
            output_path = output_video_path or self.config.file_paths.output_video_path
            
            self.logger.info(f"开始处理视频: {input_path} -> {output_path}")
            
            # 第一步：分析和验证视频
            if not await self._analyze_video(input_path):
                return False
            
            # 第二步：初始化翻译引擎
            if not await self._initialize_translation():
                return False
            
            # 第三步：并行处理音频和视频帧
            if not await self._process_audio_and_video(input_path):
                return False
            
            # 第四步：生成英文音频文件
            temp_audio_path = await self._generate_english_audio()
            if not temp_audio_path:
                return False
            
            # 第五步：生成字幕文件
            temp_subtitle_path = await self._generate_subtitles()
            if not temp_subtitle_path:
                return False
            
            # 第六步：音频同步处理
            synced_audio_path = await self._synchronize_audio(temp_audio_path)
            if not synced_audio_path:
                return False
            
            # 第七步：合成最终视频
            if not await self._compose_final_video(input_path, synced_audio_path, 
                                                 temp_subtitle_path, output_path):
                return False
            
            # 第八步：清理和验证
            await self._cleanup_and_validate(output_path)
            
            self.processing_stats['end_time'] = time.time()
            self._log_processing_summary()
            
            self.logger.info("视频翻译处理完成!")
            return True
            
        except Exception as e:
            self.logger.error(f"视频处理失败: {e}")
            self.logger.error(traceback.format_exc())
            self.processing_stats['errors'].append(str(e))
            return False
        finally:
            self.is_processing = False
            await self._cleanup_resources()
    
    async def _analyze_video(self, input_path: str) -> bool:
        """分析和验证视频"""
        try:
            self.logger.info("正在分析视频文件...")
            
            # 验证视频
            if not self.video_processor.validate_video(input_path):
                self.logger.error("视频验证失败")
                return False
            
            # 分析视频信息
            video_info = self.video_processor.analyze_video(input_path)
            self.processing_stats['video_duration'] = video_info.duration
            
            self.logger.info(f"视频信息: 时长={video_info.duration:.2f}s, "
                           f"分辨率={video_info.width}x{video_info.height}, "
                           f"帧率={video_info.fps:.2f}")
            
            # 准备处理
            processing_info = self.video_processor.prepare_processing(input_path)
            self.logger.info(f"预计处理: {processing_info['estimated_frames']} 帧, "
                           f"{processing_info['estimated_audio_chunks']} 音频块")
            
            return True
            
        except Exception as e:
            self.logger.error(f"视频分析失败: {e}")
            return False
    
    async def _initialize_translation(self) -> bool:
        """初始化翻译引擎"""
        try:
            self.logger.info("正在初始化翻译引擎...")
            
            success = await self.translation_engine.initialize()
            if not success:
                self.logger.error("翻译引擎初始化失败")
                return False
            
            self.logger.info("翻译引擎初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"翻译引擎初始化失败: {e}")
            return False
    
    async def _process_audio_and_video(self, input_path: str) -> bool:
        """并行处理音频和视频帧"""
        try:
            self.logger.info("开始处理音频和视频数据...")
            
            # 创建音频和图像数据流
            audio_stream = self._create_audio_stream(input_path)
            image_stream = self._create_image_stream(input_path)
            
            # 启动翻译引擎处理
            await self.translation_engine.translate_stream(audio_stream, image_stream)
            
            # 获取翻译结果
            translated_texts, audio_segments = self.translation_engine.get_translation_results()
            
            self.processing_stats['translation_segments'] = len(translated_texts)
            self.logger.info(f"翻译完成: {len(translated_texts)} 个文本段, "
                           f"{len(audio_segments)} 个音频段")
            
            # 保存翻译结果到生成器
            for i, (text, audio_data) in enumerate(zip(translated_texts, audio_segments)):
                # 计算时间戳（简化处理）
                timestamp = i * 3.0  # 假设每段3秒
                
                # 添加到音频生成器
                self.audio_generator.add_audio_segment(audio_data, timestamp)
                
                # 添加到字幕生成器
                self.subtitle_generator.add_translation_text(text, timestamp, timestamp + 3.0)
            
            return True
            
        except Exception as e:
            self.logger.error(f"音视频处理失败: {e}")
            return False
    
    async def _create_audio_stream(self, input_path: str):
        """创建音频数据流"""
        try:
            audio_extractor = self.video_processor.audio_extractor
            
            # 使用异步生成器
            async def audio_generator():
                for chunk in audio_extractor.extract_audio_chunks(input_path):
                    self.processing_stats['audio_chunks_processed'] += 1
                    yield chunk
                    await asyncio.sleep(0.01)  # 避免阻塞
            
            return audio_generator()
            
        except Exception as e:
            self.logger.error(f"创建音频流失败: {e}")
            raise
    
    async def _create_image_stream(self, input_path: str):
        """创建图像数据流"""
        try:
            frame_extractor = self.video_processor.frame_extractor
            
            # 使用异步生成器
            async def image_generator():
                for timestamp, image_data in frame_extractor.extract_frame_data(input_path):
                    self.processing_stats['image_frames_processed'] += 1
                    yield timestamp, image_data
                    await asyncio.sleep(0.1)  # 控制发送频率
            
            return image_generator()
            
        except Exception as e:
            self.logger.error(f"创建图像流失败: {e}")
            raise
    
    async def _generate_english_audio(self) -> Optional[str]:
        """生成英文音频文件"""
        try:
            self.logger.info("正在生成英文音频...")
            
            temp_audio_path = f"{self.config.file_paths.temp_dir}/english_audio.wav"
            
            success = self.audio_generator.generate_continuous_audio(
                temp_audio_path, 
                self.processing_stats['video_duration']
            )
            
            if success:
                self.logger.info(f"英文音频生成成功: {temp_audio_path}")
                return temp_audio_path
            else:
                self.logger.error("英文音频生成失败")
                return None
                
        except Exception as e:
            self.logger.error(f"生成英文音频失败: {e}")
            return None
    
    async def _generate_subtitles(self) -> Optional[str]:
        """生成字幕文件"""
        try:
            self.logger.info("正在生成字幕文件...")
            
            # 优化字幕时间轴
            self.subtitle_generator.optimize_timing(self.processing_stats['video_duration'])
            
            temp_subtitle_path = f"{self.config.file_paths.temp_dir}/subtitles.srt"
            
            success = self.subtitle_generator.save_to_file(temp_subtitle_path)
            
            if success:
                self.logger.info(f"字幕文件生成成功: {temp_subtitle_path}")
                return temp_subtitle_path
            else:
                self.logger.error("字幕文件生成失败")
                return None
                
        except Exception as e:
            self.logger.error(f"生成字幕文件失败: {e}")
            return None
    
    async def _synchronize_audio(self, audio_path: str) -> Optional[str]:
        """同步音频"""
        try:
            self.logger.info("正在同步音频...")
            
            synced_audio_path = f"{self.config.file_paths.temp_dir}/synced_audio.wav"
            
            success = self.audio_synchronizer.synchronize_with_video(
                audio_path,
                self.processing_stats['video_duration'],
                synced_audio_path
            )
            
            if success:
                self.logger.info(f"音频同步成功: {synced_audio_path}")
                return synced_audio_path
            else:
                self.logger.error("音频同步失败")
                return None
                
        except Exception as e:
            self.logger.error(f"音频同步失败: {e}")
            return None
    
    async def _compose_final_video(self, video_path: str, audio_path: str,
                                 subtitle_path: str, output_path: str) -> bool:
        """合成最终视频"""
        try:
            self.logger.info("正在合成最终视频...")
            
            success = self.video_composer.compose_video(
                video_path,
                audio_path,
                subtitle_path,
                output_path
            )
            
            if success:
                self.logger.info(f"视频合成成功: {output_path}")
                return True
            else:
                self.logger.error("视频合成失败")
                return False
                
        except Exception as e:
            self.logger.error(f"视频合成失败: {e}")
            return False
    
    async def _cleanup_and_validate(self, output_path: str):
        """清理和验证"""
        try:
            # 验证输出文件
            video_info = self.video_composer.get_video_info(output_path)
            if video_info:
                self.logger.info(f"输出视频验证成功: 时长={video_info['duration']:.2f}s, "
                               f"大小={video_info['size']} bytes")
            else:
                self.logger.warning("无法验证输出视频")
            
            # 可选：创建缩略图
            thumbnail_path = output_path.replace('.mp4', '_thumb.jpg')
            self.video_composer.extract_thumbnail(output_path, thumbnail_path, 10.0)
            
        except Exception as e:
            self.logger.error(f"清理和验证失败: {e}")
    
    async def _cleanup_resources(self):
        """清理资源"""
        try:
            # 关闭翻译引擎
            await self.translation_engine.shutdown()
            
            # 清空缓冲区
            self.audio_generator.clear_buffer()
            self.subtitle_generator.clear()
            
            self.logger.info("资源清理完成")
            
        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")
    
    def _log_processing_summary(self):
        """记录处理摘要"""
        total_time = self.processing_stats['end_time'] - self.processing_stats['start_time']
        video_duration = self.processing_stats['video_duration']
        processing_ratio = total_time / video_duration if video_duration > 0 else 0
        
        self.logger.info("=" * 50)
        self.logger.info("处理摘要:")
        self.logger.info(f"视频时长: {video_duration:.2f} 秒")
        self.logger.info(f"处理时间: {total_time:.2f} 秒")
        self.logger.info(f"处理比例: {processing_ratio:.2f}x")
        self.logger.info(f"音频块数: {self.processing_stats['audio_chunks_processed']}")
        self.logger.info(f"视频帧数: {self.processing_stats['image_frames_processed']}")
        self.logger.info(f"翻译段数: {self.processing_stats['translation_segments']}")
        if self.processing_stats['errors']:
            self.logger.warning(f"错误数量: {len(self.processing_stats['errors'])}")
        self.logger.info("=" * 50)
    
    def get_progress_info(self) -> Dict[str, Any]:
        """获取处理进度信息"""
        return {
            'is_processing': self.is_processing,
            'stats': self.processing_stats.copy(),
            'config': self.config.to_dict()
        }


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='视频翻译系统')
    parser.add_argument('--input', '-i', type=str, help='输入视频文件路径')
    parser.add_argument('--output', '-o', type=str, help='输出视频文件路径')
    parser.add_argument('--config', '-c', type=str, help='配置文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    try:
        # 设置日志级别
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        print("=" * 60)
        print("视频翻译系统")
        print("将中文视频翻译为包含英文音频和字幕的视频")
        print("=" * 60)
        
        # 初始化处理管道
        pipeline = VideoTranslationPipeline(args.config)
        
        # 显示配置信息
        print("\n配置信息:")
        config_dict = pipeline.config.to_dict()
        for section, values in config_dict.items():
            if section != 'api':  # 不显示API密钥
                print(f"  {section}: {values}")
        
        # 确定输入输出路径
        input_path = args.input or pipeline.config.file_paths.input_video_path
        output_path = args.output or pipeline.config.file_paths.output_video_path
        
        print(f"\n输入视频: {input_path}")
        print(f"输出视频: {output_path}")
        
        # 检查输入文件
        if not Path(input_path).exists():
            print(f"错误: 输入视频文件不存在: {input_path}")
            return 1
        
        # 确认开始处理
        print("\n准备开始处理...")
        print("按 Ctrl+C 可以随时停止处理")
        
        # 开始处理
        start_time = time.time()
        success = await pipeline.process_video(input_path, output_path)
        end_time = time.time()
        
        print(f"\n处理完成! 耗时: {end_time - start_time:.2f} 秒")
        
        if success:
            print(f"✓ 翻译成功: {output_path}")
            
            # 显示统计信息
            progress_info = pipeline.get_progress_info()
            stats = progress_info['stats']
            print(f"  - 处理时长: {stats.get('video_duration', 0):.2f} 秒")
            print(f"  - 翻译段数: {stats.get('translation_segments', 0)}")
            print(f"  - 音频块数: {stats.get('audio_chunks_processed', 0)}")
            print(f"  - 视频帧数: {stats.get('image_frames_processed', 0)}")
            
            return 0
        else:
            print("✗ 翻译失败，请查看日志了解详情")
            return 1
            
    except KeyboardInterrupt:
        print("\n用户取消处理")
        return 130
    except Exception as e:
        print(f"\n系统错误: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    # 运行主程序
    exit_code = asyncio.run(main())
    sys.exit(exit_code)