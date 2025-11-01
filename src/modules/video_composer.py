"""
视频合成模块

这个模块负责将原始视频流、英文音频轨道和SRT字幕文件合成为最终的MP4视频文件。
支持多种编码格式、质量控制和高效的渲染过程。
"""

import os
import logging
import subprocess
import tempfile
from typing import Optional, Dict, Any, List, Tuple
import json
import shutil
from pathlib import Path

from ..utils.config import get_config


class VideoComposer:
    """视频合成器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # 编码参数
        self.video_codec = self.config.video.video_codec
        self.audio_codec = self.config.video.audio_codec
        self.audio_bitrate = self.config.video.audio_bitrate
        self.output_quality = self.config.video.output_video_quality
        
        # 临时文件管理
        self.temp_files = []
    
    def compose_video(self, 
                     original_video_path: str,
                     english_audio_path: str,
                     subtitle_path: Optional[str] = None,
                     output_path: str = None) -> bool:
        """
        合成最终视频
        
        Args:
            original_video_path: 原始视频文件路径
            english_audio_path: 英文音频文件路径
            subtitle_path: 字幕文件路径（可选）
            output_path: 输出视频文件路径
            
        Returns:
            bool: 合成是否成功
        """
        try:
            if output_path is None:
                output_path = self.config.file_paths.output_video_path
            
            self.logger.info(f"开始视频合成: {output_path}")
            
            # 验证输入文件
            if not self._validate_input_files(original_video_path, english_audio_path, subtitle_path):
                return False
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 构建ffmpeg命令
            cmd = self._build_ffmpeg_command(
                original_video_path, 
                english_audio_path, 
                subtitle_path, 
                output_path
            )
            
            # 执行合成
            success = self._execute_ffmpeg_command(cmd)
            
            if success:
                # 验证输出文件
                if self._validate_output_file(output_path):
                    self.logger.info(f"视频合成成功: {output_path}")
                    return True
                else:
                    self.logger.error("输出文件验证失败")
                    return False
            else:
                self.logger.error("视频合成失败")
                return False
                
        except Exception as e:
            self.logger.error(f"视频合成过程中发生错误: {e}")
            return False
        finally:
            # 清理临时文件
            self._cleanup_temp_files()
    
    def _validate_input_files(self, video_path: str, audio_path: str, 
                            subtitle_path: Optional[str] = None) -> bool:
        """验证输入文件"""
        try:
            # 检查视频文件
            if not os.path.exists(video_path):
                self.logger.error(f"视频文件不存在: {video_path}")
                return False
            
            # 检查音频文件
            if not os.path.exists(audio_path):
                self.logger.error(f"音频文件不存在: {audio_path}")
                return False
            
            # 检查字幕文件（如果提供）
            if subtitle_path and not os.path.exists(subtitle_path):
                self.logger.error(f"字幕文件不存在: {subtitle_path}")
                return False
            
            # 使用ffprobe验证文件格式
            if not self._validate_media_file(video_path, 'video'):
                return False
            
            if not self._validate_media_file(audio_path, 'audio'):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"输入文件验证失败: {e}")
            return False
    
    def _validate_media_file(self, file_path: str, media_type: str) -> bool:
        """验证媒体文件格式"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)
            
            # 检查是否包含指定类型的流
            has_required_stream = any(
                stream['codec_type'] == media_type 
                for stream in probe_data.get('streams', [])
            )
            
            if not has_required_stream:
                self.logger.error(f"文件 {file_path} 不包含 {media_type} 流")
                return False
            
            return True
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"媒体文件验证失败 {file_path}: {e}")
            return False
    
    def _build_ffmpeg_command(self, video_path: str, audio_path: str,
                            subtitle_path: Optional[str], output_path: str) -> List[str]:
        """构建ffmpeg命令"""
        cmd = ['ffmpeg']
        
        # 输入文件
        cmd.extend(['-i', video_path])    # 视频输入
        cmd.extend(['-i', audio_path])    # 音频输入
        
        # 视频编码设置
        cmd.extend(['-c:v', self.video_codec])
        
        # 音频编码设置
        cmd.extend(['-c:a', self.audio_codec])
        cmd.extend(['-b:a', self.audio_bitrate])
        
        # 音频映射（使用新的英文音频）
        cmd.extend(['-map', '0:v:0'])  # 使用原视频的视频流
        cmd.extend(['-map', '1:a:0'])  # 使用新音频文件的音频流
        
        # 质量设置
        quality_settings = self._get_quality_settings()
        cmd.extend(quality_settings)
        
        # 字幕处理
        if subtitle_path:
            subtitle_filter = self._build_subtitle_filter(subtitle_path)
            if subtitle_filter:
                cmd.extend(['-vf', subtitle_filter])
        
        # 输出设置
        cmd.extend(['-movflags', '+faststart'])  # 优化流媒体播放
        cmd.extend(['-y'])  # 覆盖输出文件
        cmd.append(output_path)
        
        self.logger.debug(f"FFmpeg命令: {' '.join(cmd)}")
        return cmd
    
    def _get_quality_settings(self) -> List[str]:
        """获取质量设置参数"""
        settings = []
        
        if self.output_quality == 'high':
            settings.extend(['-crf', '18'])  # 高质量
            settings.extend(['-preset', 'slow'])
        elif self.output_quality == 'medium':
            settings.extend(['-crf', '23'])  # 中等质量
            settings.extend(['-preset', 'medium'])
        elif self.output_quality == 'low':
            settings.extend(['-crf', '28'])  # 低质量
            settings.extend(['-preset', 'fast'])
        else:
            # 默认设置
            settings.extend(['-crf', '23'])
            settings.extend(['-preset', 'medium'])
        
        return settings
    
    def _build_subtitle_filter(self, subtitle_path: str) -> Optional[str]:
        """构建字幕滤镜"""
        try:
            # 创建字幕样式
            subtitle_style = self._get_subtitle_style()
            
            # 构建字幕滤镜
            # 使用ass格式提供更好的样式控制
            subtitle_filter = f"subtitles='{subtitle_path}':force_style='{subtitle_style}'"
            
            return subtitle_filter
            
        except Exception as e:
            self.logger.error(f"构建字幕滤镜失败: {e}")
            return None
    
    def _get_subtitle_style(self) -> str:
        """获取字幕样式设置"""
        style_options = [
            'Fontname=Arial',
            'Fontsize=24',
            'PrimaryColour=&Hffffff',  # 白色文字
            'OutlineColour=&H000000',  # 黑色边框
            'BackColour=&H80000000',   # 半透明背景
            'Outline=2',
            'Shadow=1',
            'Alignment=2',  # 底部居中
            'MarginV=20'    # 底部边距
        ]
        
        return ','.join(style_options)
    
    def _execute_ffmpeg_command(self, cmd: List[str]) -> bool:
        """执行ffmpeg命令"""
        try:
            self.logger.info("开始执行视频合成...")
            
            # 执行命令并实时输出进度
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # 读取输出以监控进度
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # 解析进度信息
                    if 'time=' in output:
                        self._parse_progress(output)
            
            # 等待进程完成
            return_code = process.wait()
            
            if return_code == 0:
                self.logger.info("FFmpeg执行成功")
                return True
            else:
                stderr_output = process.stderr.read()
                self.logger.error(f"FFmpeg执行失败，返回码: {return_code}")
                self.logger.error(f"错误输出: {stderr_output}")
                return False
                
        except Exception as e:
            self.logger.error(f"执行FFmpeg命令失败: {e}")
            return False
    
    def _parse_progress(self, output: str):
        """解析ffmpeg进度输出"""
        try:
            # 提取时间信息
            if 'time=' in output:
                import re
                time_match = re.search(r'time=(\d{2}:\d{2}:\d{2}\.\d{2})', output)
                if time_match:
                    current_time = time_match.group(1)
                    self.logger.debug(f"处理进度: {current_time}")
        except Exception:
            pass  # 忽略进度解析错误
    
    def _validate_output_file(self, output_path: str) -> bool:
        """验证输出文件"""
        try:
            # 检查文件是否存在
            if not os.path.exists(output_path):
                self.logger.error(f"输出文件不存在: {output_path}")
                return False
            
            # 检查文件大小
            file_size = os.path.getsize(output_path)
            if file_size < 1024:  # 小于1KB可能是空文件
                self.logger.error(f"输出文件过小: {file_size} bytes")
                return False
            
            # 使用ffprobe验证文件完整性
            cmd = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,duration',
                '-of', 'csv=p=0', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                self.logger.error("输出文件没有有效的视频流")
                return False
            
            self.logger.info(f"输出文件验证成功: {output_path} ({file_size} bytes)")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"输出文件验证失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"验证输出文件时发生错误: {e}")
            return False
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    self.logger.debug(f"已删除临时文件: {temp_file}")
            except Exception as e:
                self.logger.warning(f"删除临时文件失败 {temp_file}: {e}")
        
        self.temp_files.clear()
    
    def create_preview(self, video_path: str, output_path: str,
                      start_time: float = 0, duration: float = 30) -> bool:
        """
        创建视频预览
        
        Args:
            video_path: 输入视频路径
            output_path: 输出预览路径
            start_time: 开始时间（秒）
            duration: 预览时长（秒）
            
        Returns:
            bool: 创建是否成功
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-crf', '28',
                '-preset', 'fast',
                '-y', output_path
            ]
            
            self.logger.info(f"创建预览: {start_time}s 开始，时长 {duration}s")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if os.path.exists(output_path):
                self.logger.info(f"预览创建成功: {output_path}")
                return True
            else:
                self.logger.error("预览文件创建失败")
                return False
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"创建预览失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"创建预览时发生错误: {e}")
            return False
    
    def extract_thumbnail(self, video_path: str, output_path: str,
                         timestamp: float = 0) -> bool:
        """
        提取视频缩略图
        
        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径
            timestamp: 提取时间点（秒）
            
        Returns:
            bool: 提取是否成功
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(timestamp),
                '-vframes', '1',
                '-q:v', '2',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if os.path.exists(output_path):
                self.logger.info(f"缩略图提取成功: {output_path}")
                return True
            else:
                self.logger.error("缩略图提取失败")
                return False
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"提取缩略图失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"提取缩略图时发生错误: {e}")
            return False
    
    def get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Dict[str, Any]: 视频信息
        """
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)
            
            # 提取关键信息
            format_info = probe_data.get('format', {})
            streams = probe_data.get('streams', [])
            
            video_stream = next((s for s in streams if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in streams if s['codec_type'] == 'audio'), None)
            
            info = {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bit_rate': int(format_info.get('bit_rate', 0)),
                'format_name': format_info.get('format_name', ''),
                'video_codec': video_stream.get('codec_name', '') if video_stream else '',
                'audio_codec': audio_stream.get('codec_name', '') if audio_stream else '',
                'width': int(video_stream.get('width', 0)) if video_stream else 0,
                'height': int(video_stream.get('height', 0)) if video_stream else 0,
                'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0
            }
            
            return info
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"获取视频信息失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取视频信息时发生错误: {e}")
            return None


if __name__ == "__main__":
    # 测试视频合成模块
    def test_video_composer():
        """测试视频合成功能"""
        try:
            composer = VideoComposer()
            
            # 模拟文件路径（实际使用时需要真实文件）
            video_path = "test_video.mp4"
            audio_path = "test_audio.wav"
            subtitle_path = "test_subtitles.srt"
            output_path = "test_output.mp4"
            
            # 这里只是展示API使用方式，实际需要真实文件
            print("视频合成器测试:")
            print(f"输入视频: {video_path}")
            print(f"输入音频: {audio_path}")
            print(f"输入字幕: {subtitle_path}")
            print(f"输出视频: {output_path}")
            
            # 如果有真实文件，可以取消下面的注释进行测试
            # success = composer.compose_video(video_path, audio_path, subtitle_path, output_path)
            # print(f"合成结果: {'成功' if success else '失败'}")
            
            print("视频合成器初始化成功")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    test_video_composer()