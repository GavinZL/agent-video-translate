# 快速开始指南

## 5分钟快速上手

### 第1步：系统准备
确保你的系统满足以下要求：
- Python 3.8+
- FFmpeg (通过`ffmpeg -version`验证)
- 稳定的网络连接

### 第2步：获取API密钥
1. 注册[阿里云百炼平台](https://bailian.console.aliyun.com/)账号
2. 开通千问模型服务
3. 获取API密钥

### 第3步：一键安装和配置
```bash
# 克隆项目
git clone <repository-url>
cd agent-video-translate

# 一键设置环境
./run.sh --setup

# 编辑配置文件，设置API密钥
nano .env
```

在`.env`文件中设置：
```env
DASHSCOPE_API_KEY=your_actual_api_key_here
```

### 第4步：准备视频文件
将中文视频文件放入`videos/`目录，命名为`cn-agent.mp4`

### 第5步：开始翻译
```bash
# 使用默认配置翻译
./run.sh --run

# 或者指定输入输出文件
./run.sh --run -i videos/my-video.mp4 -o output/my-video-en.mp4
```

### 第6步：查看结果
翻译完成的英文视频保存在`output/`目录中。

## 常见问题

**Q: 提示FFmpeg未找到？**
A: 
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
choco install ffmpeg
```

**Q: API连接失败？**
A: 检查网络连接和API密钥是否正确设置

**Q: 处理很慢？**
A: 这是正常的，翻译时间通常是视频时长的1-3倍

**Q: 内存不足？**
A: 尝试处理较短的视频，或增加系统内存

## 高级用法

### 自定义配置
编辑`.env`文件调整处理参数：
```env
# 视频质量（high/medium/low）
OUTPUT_VIDEO_QUALITY=high

# 帧提取频率（帧/秒）
FRAME_EXTRACT_RATE=2

# 音频采样率
OUTPUT_SAMPLE_RATE=24000
```

### 批量处理
```bash
# 处理多个文件
for video in videos/*.mp4; do
    ./run.sh --run -i "$video" -o "output/$(basename "$video" .mp4)-en.mp4"
done
```

### 测试系统
```bash
# 运行测试套件
./run.sh --test

# 检查系统状态
./run.sh --check
```

## 技术支持

- 查看详细文档：`README.md`
- 运行测试：`./run.sh --test`
- 查看日志：`logs/`目录
- 问题反馈：提交Issue

## 性能建议

1. **硬件要求**：建议4GB+内存，多核CPU
2. **网络要求**：稳定的互联网连接，建议带宽>10Mbps
3. **存储要求**：处理过程需要约3倍原视频大小的临时空间
4. **处理时间**：通常为视频时长的1-3倍，取决于视频长度和复杂度

开始你的视频翻译之旅吧！🚀