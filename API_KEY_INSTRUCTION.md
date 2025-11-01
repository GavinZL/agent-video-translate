# ⚠️ 重要提示：API密钥和模型配置

## 🔑 关于API密钥

当前项目使用的API密钥可能存在以下问题：

### 问题分析

1. **模型访问权限**: 您的API密钥可能没有访问实时翻译模型的权限
2. **模型名称变更**: 阿里云千问API的模型名称可能已更新
3. **服务未开通**: 实时音视频翻译服务可能需要单独开通

### 错误信息
```
Model not found (qwen-omni-turbo-realtime-2025-03-26)!
```

这表明服务器无法找到指定的模型。

---

## 🛠️ 解决方案

### 方案1: 检查API密钥权限

1. 登录 [阿里云百炼平台控制台](https://bailian.console.aliyun.com/)
2. 检查您的API密钥是否有以下权限：
   - ✅ 实时语音翻译
   - ✅ 多模态模型访问
   - ✅ Qwen-Omni系列模型

3. 如果没有权限，需要：
   - 申请开通实时翻译服务
   - 升级API密钥权限
   - 或创建新的具有足够权限的API密钥

### 方案2: 确认可用的模型列表

访问 [千问API文档](https://help.aliyun.com/zh/dashscope/developer-reference/api-details) 查看当前可用的实时翻译模型：

可能的模型名称：
- `qwen-audio-turbo` - 音频理解模型
- `qwen-audio-chat` - 音频对话模型  
- `qwen2-audio-instruct` - 音频指令模型

**注意**: 实时音视频翻译功能可能需要特殊的企业版API密钥。

### 方案3: 联系阿里云技术支持

如果以上方案都无法解决，建议：
1. 提交工单到阿里云技术支持
2. 说明您需要使用实时音视频翻译功能
3. 咨询正确的模型名称和API配置

---

## 📝 当前配置检查

### 检查API密钥
```bash
grep DASHSCOPE_API_KEY .env
```

### 检查模型名称
```bash
grep MODEL_NAME .env
```

### 测试API连接
您可以使用阿里云提供的测试工具验证API密钥：
```python
import dashscope

# 设置API密钥
dashscope.api_key = 'your-api-key'

# 测试模型列表
models = dashscope.Models.list()
print(models)
```

---

## 🔄 临时解决方案

如果您只想测试系统的其他功能（不使用实际的翻译API），可以：

1. **使用Mock模式**: 修改代码以跳过实际的API调用
2. **使用其他翻译服务**: 集成Google Translate API等替代方案
3. **本地测试**: 使用预录制的翻译结果进行测试

---

## 💡 建议的行动步骤

1. ✅ **验证API密钥**: 确保密钥有效且权限充足
2. ✅ **查看服务状态**: 检查阿里云服务是否正常
3. ✅ **更新配置**: 使用正确的模型名称
4. ✅ **测试连接**: 运行简单的API测试
5. ✅ **联系支持**: 如需要，提交技术支持工单

---

## 📚 相关文档

- [阿里云百炼平台](https://bailian.console.aliyun.com/)
- [DashScope API文档](https://help.aliyun.com/zh/dashscope/)
- [Qwen模型文档](https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction)
- [API密钥管理](https://help.aliyun.com/zh/dashscope/developer-reference/api-key)

---

## ⚠️ 重要提醒

**实时音视频翻译是一个高级功能，可能需要:**
- 企业版API密钥
- 特殊的服务开通
- 额外的费用

请确认您的账号已开通相关服务后再使用此功能。

---

**最后更新**: 2025-10-30  
**问题状态**: 🔴 待解决 - 需要验证API密钥权限和模型可用性
