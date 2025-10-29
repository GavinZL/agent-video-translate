#!/bin/bash

# 视频翻译系统运行脚本
# 用法: ./run.sh [选项]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    print_info "检查系统依赖..."
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3未安装"
        exit 1
    fi
    
    # 检查FFmpeg
    if ! command -v ffmpeg &> /dev/null; then
        print_error "FFmpeg未安装，请先安装FFmpeg"
        print_info "Ubuntu/Debian: sudo apt install ffmpeg"
        print_info "CentOS/RHEL: sudo yum install ffmpeg"
        print_info "macOS: brew install ffmpeg"
        exit 1
    fi
    
    # 检查ffprobe
    if ! command -v ffprobe &> /dev/null; then
        print_error "ffprobe未安装，请确保FFmpeg完整安装"
        exit 1
    fi
    
    print_success "系统依赖检查通过"
}

# 设置环境
setup_environment() {
    print_info "设置Python环境..."
    
    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        print_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 安装依赖
    if [ ! -f ".deps_installed" ]; then
        print_info "安装Python依赖包..."
        pip install --upgrade pip
        pip install -r requirements.txt
        touch .deps_installed
        print_success "依赖安装完成"
    else
        print_info "依赖已安装，跳过安装步骤"
    fi
}

# 检查配置
check_config() {
    print_info "检查配置文件..."
    
    if [ ! -f ".env" ]; then
        print_warning "配置文件.env不存在，复制示例配置"
        cp .env.example .env
        print_error "请编辑.env文件，设置你的API密钥："
        print_info "DASHSCOPE_API_KEY=your_actual_api_key_here"
        exit 1
    fi
    
    # 检查API密钥
    if grep -q "your_api_key_here" .env; then
        print_error "请在.env文件中设置真实的API密钥"
        exit 1
    fi
    
    print_success "配置检查通过"
}

# 创建必要目录
create_directories() {
    print_info "创建必要目录..."
    mkdir -p videos output temp logs
    print_success "目录创建完成"
}

# 运行测试
run_tests() {
    print_info "运行测试套件..."
    source venv/bin/activate
    cd tests
    python -m pytest -v
    cd ..
    print_success "测试完成"
}

# 运行翻译程序
run_translation() {
    print_info "启动视频翻译程序..."
    source venv/bin/activate
    # 使用 -m 方式运行，支持相对导入
    python -m src.main "$@"
}

# 显示帮助信息
show_help() {
    echo "视频翻译系统运行脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --setup          设置环境和依赖"
    echo "  --test           运行测试"
    echo "  --run            运行翻译程序"
    echo "  --check          检查系统状态"
    echo "  --clean          清理临时文件"
    echo "  --help           显示此帮助信息"
    echo ""
    echo "翻译选项（与--run一起使用）:"
    echo "  -i, --input      输入视频文件路径"
    echo "  -o, --output     输出视频文件路径"
    echo "  -v, --verbose    详细输出"
    echo ""
    echo "示例:"
    echo "  $0 --setup                           # 初始设置"
    echo "  $0 --run                             # 使用默认配置运行"
    echo "  $0 --run -i video.mp4 -o output.mp4 # 指定输入输出文件"
    echo "  $0 --test                            # 运行测试"
}

# 检查系统状态
check_status() {
    print_info "检查系统状态..."
    
    echo "Python版本:"
    python3 --version
    
    echo "FFmpeg版本:"
    ffmpeg -version | head -n1
    
    echo "虚拟环境状态:"
    if [ -d "venv" ]; then
        echo "  虚拟环境: 已创建"
    else
        echo "  虚拟环境: 未创建"
    fi
    
    echo "配置文件状态:"
    if [ -f ".env" ]; then
        echo "  配置文件: 已存在"
    else
        echo "  配置文件: 不存在"
    fi
    
    echo "目录状态:"
    for dir in videos output temp logs; do
        if [ -d "$dir" ]; then
            echo "  $dir/: 存在"
        else
            echo "  $dir/: 不存在"
        fi
    done
}

# 清理临时文件
clean_temp() {
    print_info "清理临时文件..."
    rm -rf temp/*
    rm -rf logs/*.log
    rm -rf __pycache__
    rm -rf src/__pycache__
    rm -rf src/*/__pycache__
    print_success "清理完成"
}

# 主逻辑
main() {
    case "$1" in
        --setup)
            check_dependencies
            setup_environment
            create_directories
            check_config
            print_success "环境设置完成！"
            print_info "请确保已在.env文件中设置正确的API密钥"
            ;;
        --test)
            check_dependencies
            setup_environment
            run_tests
            ;;
        --run)
            check_dependencies
            setup_environment
            check_config
            create_directories
            shift
            run_translation "$@"
            ;;
        --check)
            check_status
            ;;
        --clean)
            clean_temp
            ;;
        --help|-h)
            show_help
            ;;
        "")
            print_error "请指定操作选项"
            show_help
            exit 1
            ;;
        *)
            print_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
}

# 脚本开始
echo "================================================"
echo "         视频翻译处理系统"
echo "================================================"

# 确保在项目根目录
if [ ! -f "requirements.txt" ]; then
    print_error "请在项目根目录下运行此脚本"
    exit 1
fi

# 执行主逻辑
main "$@"