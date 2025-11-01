# 视频翻译处理系统

## 概述

本系统是一个基于阿里云千问qwen-omni-turbo模型的视频翻译处理系统，能够将中文视频实时翻译为包含英文音频和字幕的视频文件。系统采用模块化设计，支持高质量的音视频处理和多模态翻译。

### 主要功能

- **实时音频翻译**：利用千问模型进行中文到英文的实时音频翻译
- **视觉增强翻译**：结合视频画面信息提升翻译准确性
- **智能字幕生成**：自动生成时间轴同步的英文字幕
- **高质量音频合成**：生成自然流畅的英文语音
- **视频无损合成**：保持原视频画质的同时替换音频轨道

### 技术特性

- 支持多种视频格式（MP4、AVI、MOV等）
- 实时处理，延迟低至3秒
- 模块化架构，易于扩展和维护
- 完善的错误处理和日志系统
- 支持批量处理和自动化部署

## 系统要求

### 软件要求

- **Python**: 3.8 或以上版本
- **FFmpeg**: 4.0 或以上版本（包含 ffmpeg 和 ffprobe 命令）
- **操作系统**: Linux、macOS 或 Windows

### 硬件要求

- **内存**: 建议 4GB 以上
- **存储**: 处理过程中需要额外的临时存储空间（约为原视频大小的3倍）
- **网络**: 稳定的互联网连接（用于API调用）

### API要求

- 阿里云百炼平台账号
- 千问模型访问权限
- 有效的API密钥

## 安装指南

### 1. 克隆项目

```bash
git clone <repository-url>
cd agent-video-translate
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 3. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt
```

### 4. 安装FFmpeg

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

#### Windows
下载FFmpeg二进制文件并添加到系统PATH中，或使用包管理器：
```bash
choco install ffmpeg
```

### 5. 配置环境变量

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置你的API密钥：
```env
DASHSCOPE_API_KEY=your_actual_api_key_here
```

## 使用说明

### 基本用法

1. **准备输入视频**
   将中文视频文件放入 `videos/` 目录，命名为 `cn-agent.mp4`（或修改配置文件中的路径）

2. **运行翻译程序**
   ```bash
   cd src
   python main.py
   ```

3. **查看结果**
   翻译完成的英文视频将保存在 `output/` 目录中

### 命令行参数

```bash
python main.py [选项]

选项:
  -i, --input   输入视频文件路径
  -o, --output  输出视频文件路径
  -c, --config  配置文件路径
  -v, --verbose 详细输出模式
  -h, --help    显示帮助信息
```

### 使用示例

```bash
# 使用默认配置
python main.py

# 指定输入和输出文件
python main.py -i /path/to/input.mp4 -o /path/to/output.mp4

# 使用自定义配置文件
python main.py -c /path/to/config.env

# 详细输出模式
python main.py -v
```

## 配置说明

系统配置通过环境变量进行管理，主要配置项包括：

### API配置
```env
# 阿里云百炼平台API密钥（必需）
DASHSCOPE_API_KEY=your_api_key_here

# API服务地址
API_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime

# 模型名称
MODEL_NAME=qwen3-livetranslate-flash-realtime

# 目标语言
TARGET_LANGUAGE=en

# 语音类型
VOICE_TYPE=Cherry
```

### 音频配置
```env
# 输入音频采样率
INPUT_SAMPLE_RATE=16000

# 输出音频采样率
OUTPUT_SAMPLE_RATE=24000

# 音频数据块大小
AUDIO_CHUNK_SIZE=1600
```

### 视频配置
```env
# 视频帧提取频率（帧/秒）
FRAME_EXTRACT_RATE=2

# 输出视频质量（high/medium/low）
OUTPUT_VIDEO_QUALITY=high
```

### 处理配置
```env
# 最大重试次数
MAX_RETRY_COUNT=3

# 超时时间（秒）
TIMEOUT_SECONDS=30
```

### 文件路径配置
```env
# 输入视频路径
INPUT_VIDEO_PATH=videos/cn-agent.mp4

# 输出视频路径
OUTPUT_VIDEO_PATH=output/cn-agent-en.mp4

# 临时文件目录
TEMP_DIR=temp/

# 日志级别
LOG_LEVEL=INFO
```

## 项目结构

```
agent-video-translate/
├── src/
│   ├── main.py                 # 主程序入口
│   ├── modules/                # 核心模块
│   │   ├── video_processor.py  # 视频处理模块
│   │   ├── qwen_api.py        # 千问API接口模块
│   │   ├── audio_processor.py  # 音频处理模块
│   │   ├── subtitle_generator.py # 字幕生成模块
│   │   └── video_composer.py   # 视频合成模块
│   └── utils/
│       └── config.py           # 配置管理模块
├── tests/                      # 测试文件
├── videos/                     # 输入视频目录
├── output/                     # 输出视频目录
├── temp/                       # 临时文件目录
├── logs/                       # 日志文件目录
├── requirements.txt            # Python依赖
├── .env.example               # 环境变量模板
├── .gitignore                 # Git忽略文件
└── README.md                  # 项目说明
```

## 工作流程

系统的处理流程如下：

1. **视频分析**: 解析输入视频，提取基本信息
2. **初始化翻译引擎**: 建立与千问API的WebSocket连接
3. **并行处理**: 同时提取音频数据和视频帧
4. **实时翻译**: 将音频和图像数据发送到千问API进行翻译
5. **音频生成**: 将翻译返回的音频片段合成为完整的英文音轨
6. **字幕生成**: 根据翻译文本生成时间轴同步的SRT字幕
7. **音频同步**: 调整英文音频与原视频的时长匹配
8. **视频合成**: 将原视频、英文音频和字幕合成为最终视频
9. **质量验证**: 验证输出文件的完整性和质量

## 性能优化

### 处理速度优化
- 并行处理音频和视频数据
- 流式处理，减少内存占用
- 智能缓冲区管理
- 硬件加速支持（GPU加速）

### 质量优化
- 音频降噪和增强
- 智能字幕分段和时间轴优化
- 视频质量自适应调整
- 多模态翻译提升准确性

## 故障排除

### 常见问题

1. **API连接失败**
   - 检查网络连接
   - 验证API密钥是否正确
   - 确认API服务是否可用

2. **FFmpeg命令不存在**
   - 确保FFmpeg已正确安装
   - 检查PATH环境变量配置
   - 尝试重新安装FFmpeg

3. **内存不足**
   - 减少并发处理数
   - 调整音频块大小
   - 使用更小的视频帧提取频率

4. **处理速度慢**
   - 检查网络延迟
   - 调整API调用频率
   - 优化系统硬件配置

### 日志分析

系统提供详细的日志信息，位于 `logs/` 目录中：
- 查看错误日志了解具体问题
- 使用 `-v` 参数获取详细输出
- 监控处理进度和性能统计

## 开发指南

### 代码结构

系统采用模块化设计，各模块职责清晰：
- `video_processor`: 视频文件处理和分析
- `qwen_api`: 千问API通信和翻译
- `audio_processor`: 音频处理和合成
- `subtitle_generator`: 字幕生成和格式化
- `video_composer`: 视频合成和编码
- `config`: 配置管理和验证

### 扩展开发

1. **添加新的翻译服务**
   - 实现翻译引擎接口
   - 添加配置参数
   - 更新主处理流程

2. **支持新的视频格式**
   - 扩展视频处理模块
   - 添加格式检测逻辑
   - 更新编码参数

3. **优化处理算法**
   - 改进音频处理算法
   - 优化字幕时间轴算法
   - 增强质量控制机制

### 测试

```bash
# 运行单元测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_video_processor.py

# 生成测试覆盖率报告
python -m pytest --cov=src tests/
```

## 许可证

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。

## 贡献

欢迎提交Issue和Pull Request来改进项目。

### 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 支持

如果遇到问题或需要帮助：

1. 查看本文档的故障排除部分
2. 搜索现有的Issues
3. 创建新的Issue描述问题
4. 联系维护团队

## 更新日志

### v1.0.0 (2024-01-XX)
- 初始版本发布
- 支持中文到英文的视频翻译
- 实现完整的处理流程
- 提供命令行界面

---

**注意**: 本系统需要有效的阿里云百炼平台API密钥才能正常工作。请确保在使用前正确配置API密钥。
