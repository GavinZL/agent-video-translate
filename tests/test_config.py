"""
配置管理模块测试
"""

import pytest
import os
import tempfile
from unittest.mock import patch, mock_open
from src.utils.config import Config, get_config, reload_config


class TestConfig:
    """配置管理测试类"""
    
    def setup_method(self):
        """每个测试方法的设置"""
        # 创建临时环境变量
        self.test_env_vars = {
            'DASHSCOPE_API_KEY': 'test_api_key_123',
            'INPUT_SAMPLE_RATE': '16000',
            'OUTPUT_SAMPLE_RATE': '24000',
            'MAX_RETRY_COUNT': '3'
        }
    
    def test_config_initialization(self):
        """测试配置初始化"""
        with patch.dict(os.environ, self.test_env_vars):
            config = Config()
            
            assert config.api.api_key == 'test_api_key_123'
            assert config.audio.input_sample_rate == 16000
            assert config.audio.output_sample_rate == 24000
            assert config.process.max_retry_count == 3
    
    def test_api_config_validation(self):
        """测试API配置验证"""
        # 测试缺少API密钥
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DASHSCOPE_API_KEY环境变量未设置"):
                Config()
    
    def test_config_validation_success(self):
        """测试配置验证成功"""
        with patch.dict(os.environ, self.test_env_vars):
            config = Config()
            assert config.validate() == True
    
    def test_config_validation_failure(self):
        """测试配置验证失败"""
        invalid_env = self.test_env_vars.copy()
        invalid_env['DASHSCOPE_API_KEY'] = 'your_api_key_here'  # 无效密钥
        
        with patch.dict(os.environ, invalid_env):
            config = Config()
            assert config.validate() == False
    
    def test_config_to_dict(self):
        """测试配置转换为字典"""
        with patch.dict(os.environ, self.test_env_vars):
            config = Config()
            config_dict = config.to_dict()
            
            assert 'api' in config_dict
            assert 'audio' in config_dict
            assert 'video' in config_dict
            assert config_dict['api']['api_key'] == '***masked***'
    
    def test_get_config_singleton(self):
        """测试配置单例模式"""
        with patch.dict(os.environ, self.test_env_vars):
            config1 = get_config()
            config2 = get_config()
            
            assert config1 is config2
    
    def test_reload_config(self):
        """测试重新加载配置"""
        with patch.dict(os.environ, self.test_env_vars):
            config1 = get_config()
            config2 = reload_config()
            
            assert config1 is not config2
            assert config2.api.api_key == 'test_api_key_123'
    
    def test_env_file_loading(self):
        """测试从文件加载环境变量"""
        env_content = """
DASHSCOPE_API_KEY=test_file_key
INPUT_SAMPLE_RATE=22050
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(env_content)
            f.flush()
            
            try:
                config = Config(f.name)
                assert config.api.api_key == 'test_file_key'
                assert config.audio.input_sample_rate == 22050
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    pytest.main([__file__])