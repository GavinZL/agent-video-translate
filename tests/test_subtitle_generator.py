"""
字幕生成模块测试
"""

import pytest
import tempfile
import os
from src.modules.subtitle_generator import (
    SubtitleSegment, TimeFormatter, TextSegmenter, SRTGenerator
)


class TestSubtitleSegment:
    """字幕片段测试类"""
    
    def test_subtitle_segment_initialization(self):
        """测试字幕片段初始化"""
        segment = SubtitleSegment(1, 0.0, 3.0, "Hello world")
        
        assert segment.index == 1
        assert segment.start_time == 0.0
        assert segment.end_time == 3.0
        assert segment.text == "Hello world"
        assert segment.confidence == 1.0
    
    def test_subtitle_segment_duration(self):
        """测试字幕片段时长计算"""
        segment = SubtitleSegment(1, 10.5, 15.2, "Test")
        
        assert segment.duration() == 4.7
    
    def test_subtitle_segment_is_valid(self):
        """测试字幕片段有效性检查"""
        # 有效片段
        valid_segment = SubtitleSegment(1, 0.0, 3.0, "Hello")
        assert valid_segment.is_valid() == True
        
        # 无效时间
        invalid_time = SubtitleSegment(1, 3.0, 1.0, "Hello")
        assert invalid_time.is_valid() == False
        
        # 空文本
        empty_text = SubtitleSegment(1, 0.0, 3.0, "")
        assert empty_text.is_valid() == False
        
        # 负开始时间
        negative_start = SubtitleSegment(1, -1.0, 3.0, "Hello")
        assert negative_start.is_valid() == False


class TestTimeFormatter:
    """时间格式化工具测试类"""
    
    def test_seconds_to_srt_time(self):
        """测试秒数转换为SRT时间格式"""
        # 测试基本转换
        assert TimeFormatter.seconds_to_srt_time(0) == "00:00:00,000"
        assert TimeFormatter.seconds_to_srt_time(61.5) == "00:01:01,500"
        assert TimeFormatter.seconds_to_srt_time(3661.250) == "01:01:01,250"
        
        # 测试边界情况
        assert TimeFormatter.seconds_to_srt_time(3599.999) == "00:59:59,999"
        assert TimeFormatter.seconds_to_srt_time(7200) == "02:00:00,000"
    
    def test_srt_time_to_seconds(self):
        """测试SRT时间格式转换为秒数"""
        # 测试基本转换
        assert TimeFormatter.srt_time_to_seconds("00:00:00,000") == 0.0
        assert TimeFormatter.srt_time_to_seconds("00:01:01,500") == 61.5
        assert TimeFormatter.srt_time_to_seconds("01:01:01,250") == 3661.25
        
        # 测试边界情况
        assert TimeFormatter.srt_time_to_seconds("00:59:59,999") == 3599.999
        assert TimeFormatter.srt_time_to_seconds("02:00:00,000") == 7200.0
    
    def test_srt_time_invalid_format(self):
        """测试无效SRT时间格式"""
        with pytest.raises(ValueError, match="无效的SRT时间格式"):
            TimeFormatter.srt_time_to_seconds("invalid_format")
        
        with pytest.raises(ValueError):
            TimeFormatter.srt_time_to_seconds("25:70:80,999")


class TestTextSegmenter:
    """文本分段器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.segmenter = TextSegmenter()
    
    def test_clean_text(self):
        """测试文本清理"""
        # 测试多余空白字符清理
        dirty_text = "  Hello   world  \\n\\t  test  "
        clean_text = self.segmenter._clean_text(dirty_text)
        assert clean_text == "Hello world test"
        
        # 测试特殊字符移除
        special_text = "Hello@#$%world!!! Test???"
        clean_text = self.segmenter._clean_text(special_text)
        assert "Hello" in clean_text
        assert "world" in clean_text
        assert "@#$%" not in clean_text
    
    def test_split_into_sentences(self):
        """测试句子分割"""
        text = "This is the first sentence. This is the second one! And this is the third?"
        sentences = self.segmenter._split_into_sentences(text)
        
        assert len(sentences) == 3
        assert "first sentence" in sentences[0]
        assert "second one" in sentences[1]
        assert "third" in sentences[2]
    
    def test_segment_text(self):
        """测试文本分段"""
        text = "Hello, this is a test. This is another sentence."
        segments = self.segmenter.segment_text(text, 0.0, 10.0)
        
        assert len(segments) >= 1
        assert all(isinstance(seg, SubtitleSegment) for seg in segments)
        assert all(seg.is_valid() for seg in segments)
        
        # 检查时间分配
        total_duration = sum(seg.duration() for seg in segments)
        assert total_duration <= 10.0
    
    def test_segment_empty_text(self):
        """测试空文本分段"""
        segments = self.segmenter.segment_text("", 0.0, 5.0)
        assert len(segments) == 0
        
        segments = self.segmenter.segment_text("   ", 0.0, 5.0)
        assert len(segments) == 0
    
    def test_allocate_time_to_sentences(self):
        """测试句子时间分配"""
        sentences = ["Short.", "This is a longer sentence with more words."]
        segments = self.segmenter._allocate_time_to_sentences(sentences, 0.0, 10.0)
        
        assert len(segments) == 2
        assert segments[0].start_time == 0.0
        assert segments[1].start_time == segments[0].end_time
        # 较长的句子应该分配更多时间
        assert segments[1].duration() > segments[0].duration()
    
    def test_split_long_segment(self):
        """测试长片段分割"""
        # 创建一个很长的文本片段
        long_text = " ".join(["word"] * 50)  # 50个单词
        long_segment = SubtitleSegment(1, 0.0, 10.0, long_text)
        
        split_segments = self.segmenter._split_long_segment(long_segment)
        
        assert len(split_segments) > 1  # 应该被分割
        assert all(len(seg.text) <= self.segmenter.max_chars_per_line * self.segmenter.max_lines_per_subtitle for seg in split_segments)


class TestSRTGenerator:
    """SRT字幕生成器测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.generator = SRTGenerator()
    
    def test_add_translation_text(self):
        """测试添加翻译文本"""
        self.generator.add_translation_text("Hello world", 0.0, 3.0)
        self.generator.add_translation_text("How are you?", 3.5, 6.0)
        
        assert len(self.generator.subtitles) >= 2
    
    def test_generate_srt_content(self):
        """测试生成SRT内容"""
        # 添加测试字幕
        self.generator.add_translation_text("First subtitle", 0.0, 2.0)
        self.generator.add_translation_text("Second subtitle", 2.5, 5.0)
        
        srt_content = self.generator.generate_srt_content()
        
        assert len(srt_content) > 0
        assert "1" in srt_content  # 索引
        assert "00:00:00,000 --> 00:00:02,000" in srt_content  # 时间
        assert "First subtitle" in srt_content  # 文本
        assert "2" in srt_content  # 第二个字幕索引
        assert "Second subtitle" in srt_content
    
    def test_generate_srt_content_empty(self):
        """测试生成空SRT内容"""
        srt_content = self.generator.generate_srt_content()
        assert srt_content == ""
    
    def test_save_to_file(self):
        """测试保存SRT文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            # 添加测试内容
            self.generator.add_translation_text("Test subtitle", 0.0, 3.0)
            
            # 保存文件
            result = self.generator.save_to_file(temp_path)
            
            assert result == True
            assert os.path.exists(temp_path)
            
            # 验证文件内容
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "Test subtitle" in content
                assert "00:00:00,000 --> 00:00:03,000" in content
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_load_from_file(self):
        """测试从SRT文件加载"""
        srt_content = """1
00:00:00,000 --> 00:00:03,000
Hello world

2
00:00:03,500 --> 00:00:06,000
How are you?

"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            temp_path = f.name
        
        try:
            result = self.generator.load_from_file(temp_path)
            
            assert result == True
            assert len(self.generator.subtitles) == 2
            assert self.generator.subtitles[0].text == "Hello world"
            assert self.generator.subtitles[1].text == "How are you?"
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_parse_srt_content(self):
        """测试解析SRT内容"""
        srt_content = """1
00:00:00,000 --> 00:00:03,000
Test subtitle

2
00:00:05,500 --> 00:00:08,000
Another subtitle
with multiple lines

"""
        
        segments = self.generator._parse_srt_content(srt_content)
        
        assert len(segments) == 2
        assert segments[0].index == 1
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 3.0
        assert segments[0].text == "Test subtitle"
        
        assert segments[1].index == 2
        assert segments[1].start_time == 5.5
        assert segments[1].end_time == 8.0
        assert "Another subtitle\\nwith multiple lines" in segments[1].text
    
    def test_optimize_timing(self):
        """测试时间轴优化"""
        # 添加重叠的字幕
        self.generator.subtitles = [
            SubtitleSegment(1, 0.0, 5.0, "First"),
            SubtitleSegment(2, 4.0, 8.0, "Second"),  # 重叠
            SubtitleSegment(3, 12.0, 15.0, "Third")  # 大间隙
        ]
        
        self.generator.optimize_timing(20.0)
        
        # 检查重叠是否被修复
        assert self.generator.subtitles[0].end_time <= self.generator.subtitles[1].start_time + 0.1
        
        # 检查最后一个字幕不超过视频时长
        assert self.generator.subtitles[-1].end_time <= 20.0
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        # 空统计
        stats = self.generator.get_statistics()
        assert stats['total_segments'] == 0
        assert stats['total_duration'] == 0
        
        # 添加字幕后的统计
        self.generator.add_translation_text("Test", 0.0, 3.0)
        self.generator.add_translation_text("Another test", 4.0, 7.0)
        
        stats = self.generator.get_statistics()
        assert stats['total_segments'] >= 2
        assert stats['total_duration'] > 0
        assert stats['total_characters'] > 0
        assert 'time_range' in stats
    
    def test_clear(self):
        """测试清空字幕列表"""
        self.generator.add_translation_text("Test", 0.0, 3.0)
        assert len(self.generator.subtitles) > 0
        
        self.generator.clear()
        assert len(self.generator.subtitles) == 0
    
    def test_format_subtitle_text(self):
        """测试字幕文本格式化"""
        # 测试长文本分行
        long_text = "This is a very long subtitle text that should be split into multiple lines"
        formatted = self.generator._format_subtitle_text(long_text)
        
        lines = formatted.split('\\n')
        assert len(lines) > 1  # 应该被分成多行
        assert all(len(line) <= self.generator.text_segmenter.max_chars_per_line for line in lines)


class TestIntegration:
    """集成测试类"""
    
    def test_complete_subtitle_generation_workflow(self):
        """测试完整的字幕生成工作流"""
        generator = SRTGenerator()
        
        # 模拟翻译结果
        translations = [
            ("Hello, this is the first translation.", 0.0, 3.0),
            ("This is the second translation with more content.", 3.5, 7.0),
            ("And this is the final translation.", 8.0, 11.0)
        ]
        
        # 添加翻译文本
        for text, start, end in translations:
            generator.add_translation_text(text, start, end)
        
        # 优化时间轴
        generator.optimize_timing(12.0)
        
        # 生成SRT内容
        srt_content = generator.generate_srt_content()
        
        # 验证生成的内容
        assert len(srt_content) > 0
        assert srt_content.count('\\n\\n') >= 2  # 至少2个字幕分隔
        
        # 验证包含所有翻译文本
        for text, _, _ in translations:
            # 检查文本的关键词是否存在
            assert any(word in srt_content for word in text.split()[:3])
        
        # 获取统计信息
        stats = generator.get_statistics()
        assert stats['total_segments'] >= 3
        assert stats['total_duration'] > 0


if __name__ == "__main__":
    pytest.main([__file__])