"""
字幕生成模块

这个模块负责从翻译文本生成SRT格式的字幕文件。
支持时间轴同步、文本分段、字幕格式化等功能。
"""

import os
import re
import logging
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import timedelta
import math

from ..utils.config import get_config


@dataclass
class SubtitleSegment:
    """字幕片段类"""
    index: int
    start_time: float  # 开始时间（秒）
    end_time: float    # 结束时间（秒）
    text: str          # 字幕文本
    confidence: float = 1.0  # 置信度（可选）
    
    def duration(self) -> float:
        """获取片段时长"""
        return self.end_time - self.start_time
    
    def is_valid(self) -> bool:
        """检查片段是否有效"""
        return (self.start_time >= 0 and 
                self.end_time > self.start_time and 
                len(self.text.strip()) > 0)


class TimeFormatter:
    """时间格式化工具"""
    
    @staticmethod
    def seconds_to_srt_time(seconds: float) -> str:
        """
        将秒数转换为SRT时间格式 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒数
            
        Returns:
            str: SRT格式的时间字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    @staticmethod
    def srt_time_to_seconds(srt_time: str) -> float:
        """
        将SRT时间格式转换为秒数
        
        Args:
            srt_time: SRT格式的时间字符串
            
        Returns:
            float: 秒数
        """
        try:
            # 解析 HH:MM:SS,mmm 格式
            time_part, ms_part = srt_time.split(',')
            hours, minutes, seconds = map(int, time_part.split(':'))
            milliseconds = int(ms_part)
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
            return total_seconds
            
        except (ValueError, IndexError) as e:
            raise ValueError(f"无效的SRT时间格式: {srt_time}")


class TextSegmenter:
    """文本分段器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # 分段参数
        self.max_chars_per_line = 42  # 每行最大字符数
        self.max_lines_per_subtitle = 2  # 每个字幕最大行数
        self.min_duration = 1.0  # 最小显示时长（秒）
        self.max_duration = 6.0  # 最大显示时长（秒）
        self.reading_speed = 200  # 每分钟阅读字符数
    
    def segment_text(self, text: str, start_time: float, end_time: float) -> List[SubtitleSegment]:
        """
        将长文本分段为多个字幕片段
        
        Args:
            text: 输入文本
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[SubtitleSegment]: 字幕片段列表
        """
        try:
            # 清理文本
            cleaned_text = self._clean_text(text)
            if not cleaned_text:
                return []
            
            # 按句子分割
            sentences = self._split_into_sentences(cleaned_text)
            if not sentences:
                return []
            
            # 计算总时长
            total_duration = end_time - start_time
            
            # 为每个句子分配时间
            segments = self._allocate_time_to_sentences(sentences, start_time, total_duration)
            
            # 进一步分段以适应显示要求
            final_segments = []
            for segment in segments:
                sub_segments = self._split_long_segment(segment)
                final_segments.extend(sub_segments)
            
            # 分配索引
            for i, segment in enumerate(final_segments):
                segment.index = i + 1
            
            return final_segments
            
        except Exception as e:
            self.logger.error(f"文本分段失败: {e}")
            return []
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符（保留基本标点）
        text = re.sub(r'[^\w\s.,!?;:\'\"()-]', '', text)
        
        # 首尾去空格
        return text.strip()
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割为句子"""
        # 使用正则表达式分割句子
        sentence_endings = r'[.!?]+(?:\s|$)'
        sentences = re.split(sentence_endings, text)
        
        # 清理并过滤空句子
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _allocate_time_to_sentences(self, sentences: List[str], 
                                  start_time: float, total_duration: float) -> List[SubtitleSegment]:
        """为句子分配时间"""
        segments = []
        
        # 计算每个句子的相对长度
        sentence_lengths = [len(sentence) for sentence in sentences]
        total_length = sum(sentence_lengths)
        
        if total_length == 0:
            return segments
        
        current_time = start_time
        
        for i, (sentence, length) in enumerate(zip(sentences, sentence_lengths)):
            # 计算基于长度的时间分配
            time_ratio = length / total_length
            duration = total_duration * time_ratio
            
            # 应用最小和最大时长限制
            duration = max(self.min_duration, min(duration, self.max_duration))
            
            # 基于阅读速度调整时长
            reading_duration = (length / self.reading_speed) * 60  # 转换为秒
            duration = max(duration, reading_duration)
            
            end_time = current_time + duration
            
            segment = SubtitleSegment(
                index=i + 1,
                start_time=current_time,
                end_time=end_time,
                text=sentence.strip()
            )
            
            segments.append(segment)
            current_time = end_time
        
        return segments
    
    def _split_long_segment(self, segment: SubtitleSegment) -> List[SubtitleSegment]:
        """分割过长的字幕片段"""
        text = segment.text
        max_chars = self.max_chars_per_line * self.max_lines_per_subtitle
        
        if len(text) <= max_chars:
            return [segment]
        
        # 分割长文本
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= max_chars:
                current_chunk.append(word)
                current_length += len(word) + 1
            else:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # 为每个块分配时间
        total_duration = segment.duration()
        chunk_duration = total_duration / len(chunks)
        
        segments = []
        for i, chunk in enumerate(chunks):
            start_time = segment.start_time + i * chunk_duration
            end_time = start_time + chunk_duration
            
            new_segment = SubtitleSegment(
                index=segment.index,
                start_time=start_time,
                end_time=end_time,
                text=chunk
            )
            segments.append(new_segment)
        
        return segments


class SRTGenerator:
    """SRT字幕生成器"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.text_segmenter = TextSegmenter(config)
        self.time_formatter = TimeFormatter()
        
        # 字幕列表
        self.subtitles: List[SubtitleSegment] = []
    
    def add_translation_text(self, text: str, start_time: float, end_time: float):
        """
        添加翻译文本
        
        Args:
            text: 翻译文本
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        """
        try:
            # 分段处理文本
            segments = self.text_segmenter.segment_text(text, start_time, end_time)
            
            # 调整索引
            base_index = len(self.subtitles)
            for segment in segments:
                segment.index = base_index + segment.index
            
            # 添加到字幕列表
            self.subtitles.extend(segments)
            
            self.logger.debug(f"添加字幕片段: {len(segments)} 个，文本: {text[:50]}...")
            
        except Exception as e:
            self.logger.error(f"添加翻译文本失败: {e}")
    
    def generate_srt_content(self) -> str:
        """
        生成SRT格式的字幕内容
        
        Returns:
            str: SRT格式的字幕内容
        """
        try:
            if not self.subtitles:
                self.logger.warning("没有字幕内容可生成")
                return ""
            
            # 排序字幕（按开始时间）
            sorted_subtitles = sorted(self.subtitles, key=lambda x: x.start_time)
            
            # 重新分配索引
            for i, subtitle in enumerate(sorted_subtitles):
                subtitle.index = i + 1
            
            # 生成SRT内容
            srt_lines = []
            
            for subtitle in sorted_subtitles:
                if not subtitle.is_valid():
                    self.logger.warning(f"跳过无效字幕片段: {subtitle}")
                    continue
                
                # 索引行
                srt_lines.append(str(subtitle.index))
                
                # 时间行
                start_time_str = self.time_formatter.seconds_to_srt_time(subtitle.start_time)
                end_time_str = self.time_formatter.seconds_to_srt_time(subtitle.end_time)
                time_line = f"{start_time_str} --> {end_time_str}"
                srt_lines.append(time_line)
                
                # 文本行
                formatted_text = self._format_subtitle_text(subtitle.text)
                srt_lines.append(formatted_text)
                
                # 空行分隔
                srt_lines.append("")
            
            return '\n'.join(srt_lines)
            
        except Exception as e:
            self.logger.error(f"生成SRT内容失败: {e}")
            return ""
    
    def _format_subtitle_text(self, text: str) -> str:
        """
        格式化字幕文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 格式化后的文本
        """
        # 按最大行长度分行
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= self.text_segmenter.max_chars_per_line:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # 限制最大行数
        if len(lines) > self.text_segmenter.max_lines_per_subtitle:
            lines = lines[:self.text_segmenter.max_lines_per_subtitle]
        
        return '\n'.join(lines)
    
    def save_to_file(self, file_path: str) -> bool:
        """
        保存字幕到SRT文件
        
        Args:
            file_path: 输出文件路径
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 生成SRT内容
            srt_content = self.generate_srt_content()
            
            if not srt_content:
                self.logger.error("没有SRT内容可保存")
                return False
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            self.logger.info(f"SRT字幕已保存: {file_path}, 共 {len(self.subtitles)} 个字幕片段")
            return True
            
        except Exception as e:
            self.logger.error(f"保存SRT文件失败: {e}")
            return False
    
    def load_from_file(self, file_path: str) -> bool:
        """
        从SRT文件加载字幕
        
        Args:
            file_path: SRT文件路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.subtitles = self._parse_srt_content(content)
            
            self.logger.info(f"从SRT文件加载字幕: {file_path}, 共 {len(self.subtitles)} 个片段")
            return True
            
        except Exception as e:
            self.logger.error(f"加载SRT文件失败: {e}")
            return False
    
    def _parse_srt_content(self, content: str) -> List[SubtitleSegment]:
        """
        解析SRT内容
        
        Args:
            content: SRT文件内容
            
        Returns:
            List[SubtitleSegment]: 字幕片段列表
        """
        segments = []
        
        try:
            # 按空行分割字幕块
            blocks = re.split(r'\n\s*\n', content.strip())
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 3:
                    continue
                
                # 解析索引
                try:
                    index = int(lines[0].strip())
                except ValueError:
                    continue
                
                # 解析时间
                time_line = lines[1].strip()
                time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
                
                if not time_match:
                    continue
                
                start_time = self.time_formatter.srt_time_to_seconds(time_match.group(1))
                end_time = self.time_formatter.srt_time_to_seconds(time_match.group(2))
                
                # 解析文本
                text = '\n'.join(lines[2:]).strip()
                
                # 创建字幕片段
                segment = SubtitleSegment(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text
                )
                
                if segment.is_valid():
                    segments.append(segment)
            
        except Exception as e:
            self.logger.error(f"解析SRT内容失败: {e}")
        
        return segments
    
    def optimize_timing(self, video_duration: float):
        """
        优化字幕时间轴
        
        Args:
            video_duration: 视频总时长
        """
        try:
            if not self.subtitles:
                return
            
            # 排序字幕
            self.subtitles.sort(key=lambda x: x.start_time)
            
            # 调整重叠和间隙
            for i in range(len(self.subtitles) - 1):
                current = self.subtitles[i]
                next_subtitle = self.subtitles[i + 1]
                
                # 处理重叠
                if current.end_time > next_subtitle.start_time:
                    # 缩短当前字幕
                    gap = 0.1  # 100ms间隙
                    current.end_time = next_subtitle.start_time - gap
                    
                    # 确保最小时长
                    if current.duration() < self.text_segmenter.min_duration:
                        current.end_time = current.start_time + self.text_segmenter.min_duration
                
                # 处理过大间隙
                gap = next_subtitle.start_time - current.end_time
                if gap > 2.0:  # 间隙超过2秒
                    # 延长当前字幕
                    extension = min(gap / 2, 1.0)  # 最多延长1秒
                    current.end_time += extension
            
            # 确保最后一个字幕不超过视频时长
            if self.subtitles:
                last_subtitle = self.subtitles[-1]
                if last_subtitle.end_time > video_duration:
                    last_subtitle.end_time = video_duration
            
            self.logger.info("字幕时间轴优化完成")
            
        except Exception as e:
            self.logger.error(f"字幕时间轴优化失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取字幕统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self.subtitles:
            return {
                'total_segments': 0,
                'total_duration': 0,
                'average_duration': 0,
                'total_characters': 0,
                'average_characters': 0
            }
        
        total_segments = len(self.subtitles)
        total_duration = sum(s.duration() for s in self.subtitles)
        total_characters = sum(len(s.text) for s in self.subtitles)
        
        return {
            'total_segments': total_segments,
            'total_duration': total_duration,
            'average_duration': total_duration / total_segments,
            'total_characters': total_characters,
            'average_characters': total_characters / total_segments,
            'time_range': (
                min(s.start_time for s in self.subtitles),
                max(s.end_time for s in self.subtitles)
            )
        }
    
    def clear(self):
        """清空字幕列表"""
        self.subtitles.clear()
        self.logger.info("字幕列表已清空")


if __name__ == "__main__":
    # 测试字幕生成模块
    def test_subtitle_generation():
        """测试字幕生成功能"""
        try:
            generator = SRTGenerator()
            
            # 添加测试文本
            test_texts = [
                ("Hello, this is a test of the subtitle generation system.", 0.0, 3.0),
                ("The system can handle multiple sentences and proper timing.", 3.5, 7.0),
                ("It also supports text segmentation and formatting for better readability.", 7.5, 11.0)
            ]
            
            for text, start, end in test_texts:
                generator.add_translation_text(text, start, end)
            
            # 生成SRT内容
            srt_content = generator.generate_srt_content()
            print("生成的SRT内容:")
            print(srt_content)
            
            # 保存到文件
            output_file = "test_subtitles.srt"
            if generator.save_to_file(output_file):
                print(f"字幕已保存到: {output_file}")
            
            # 获取统计信息
            stats = generator.get_statistics()
            print("字幕统计信息:")
            import json
            print(json.dumps(stats, indent=2))
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    test_subtitle_generation()