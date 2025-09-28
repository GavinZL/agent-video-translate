# 视频翻译系统安装指南

## 系统要求

- Python 3.8+
- FFmpeg 4.0+
- 阿里云百炼平台API账号

## 快速安装

### 1. 安装Python依赖
```bash
pip install -r requirements.txt
```

### 2. 安装FFmpeg

#### Ubuntu/Debian
```bash
sudo apt update && sudo apt install ffmpeg
```

#### CentOS/RHEL
```bash
sudo yum install ffmpeg
# 或者 (RHEL 8+)
sudo dnf install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

#### Windows
下载FFmpeg并添加到系统PATH，或使用包管理器：
```bash
# 使用Chocolatey
choco install ffmpeg

# 使用Scoop
scoop install ffmpeg
```

### 3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，设置你的API密钥
```

### 4. 验证安装
```bash
# 检查Python依赖
python -c "import cv2, numpy, websockets; print('Dependencies OK')"

# 检查FFmpeg
ffmpeg -version
ffprobe -version

# 测试配置
cd src && python -c "from utils.config import get_config; print('Config OK')"
```

## 使用示例

### 基本使用
```bash
cd src
python main.py -i ../videos/input.mp4 -o ../output/output.mp4
```

### 详细输出
```bash
python main.py -v
```

## 疑难解答

### 常见错误
1. **ModuleNotFoundError**: 确保已安装所有依赖
2. **FFmpeg not found**: 确保FFmpeg在系统PATH中
3. **API连接失败**: 检查网络和API密钥配置