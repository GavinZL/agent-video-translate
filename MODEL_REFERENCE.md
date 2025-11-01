# 千问API模型参考

## 🎯 实时音视频翻译模型

### 推荐模型

根据阿里云千问API文档，实时翻译可用的模型名称：

#### 1. qwen-omni-turbo
- **用途**: 实时多模态（音频+视频）翻译
- **特点**: 高性能实时翻译，支持音频和图像输入
- **配置**: `MODEL_NAME=qwen-omni-turbo`
- **状态**: ✅ 推荐使用

#### 2. qwen-omni-turbo-latest
- **用途**: 最新版本的实时多模态翻译
- **特点**: 自动使用最新模型版本
- **配置**: `MODEL_NAME=qwen-omni-turbo-latest`
- **状态**: ✅ 可选

#### 3. qwen-audio-turbo
- **用途**: 仅音频翻译（不支持视频帧）
- **特点**: 更快的音频处理
- **配置**: `MODEL_NAME=qwen-audio-turbo`
- **状态**: ⚠️ 不支持视频增强

---

## 📝 配置方法

### 方法1: 修改 .env 文件
```bash
# 编辑配置文件
nano .env

# 设置模型名称
MODEL_NAME=qwen-omni-turbo
```

### 方法2: 环境变量
```bash
# 临时设置
export MODEL_NAME=qwen-omni-turbo

# 运行程序
./run.sh --run
```

---

## ⚠️ 常见错误

### 错误1: Model not found
```
Error: Model not found (qwen-omni-turbo-realtime-2025-03-26)!
```
**原因**: 使用了不存在或已废弃的模型名称  
**解决**: 使用上述推荐的模型名称

### 错误2: Invalid model name
```
Error: Invalid model name
```
**原因**: 模型名称拼写错误  
**解决**: 检查 `.env` 文件中的 `MODEL_NAME` 配置

---

## 🔍 验证配置

### 检查当前配置
```bash
grep MODEL_NAME .env
```

### 测试连接
```bash
# 运行测试
./run.sh --run

# 查看日志
tail -f logs/*.log | grep "model_name"
```

---

## 📚 API文档参考

- [阿里云千问API文档](https://help.aliyun.com/zh/dashscope/developer-reference/api-details)
- [实时语音翻译](https://help.aliyun.com/zh/dashscope/developer-reference/use-qwen-omni-turbo-to-translate-audio-and-video-in-real-time)

---

## 🔄 更新历史

- **2025-10-30**: 修复模型名称为 `qwen-omni-turbo`
- **初始版本**: 使用 `qwen3-livetranslate-flash-realtime`（已废弃）

---

## 💡 提示

1. **模型版本**: 千问API的模型名称会定期更新，建议关注官方文档
2. **兼容性**: 使用 `-latest` 后缀可以自动使用最新版本
3. **性能**: 不同模型的处理速度和质量可能有差异
4. **费用**: 不同模型的计费标准可能不同，请查看阿里云定价

---

**最后更新**: 2025-10-30  
**维护者**: Qoder AI Assistant
