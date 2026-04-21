"""
LLM 配置和服务测试
"""
import pytest
from unittest.mock import patch, MagicMock


class TestLLMConfigManager:
    """LLM 配置管理器测试"""
    
    def test_import_config_manager(self):
        """测试导入配置管理器"""
        from app.core.llm_config_manager import LLMConfigManager, llm_config
        
        assert LLMConfigManager is not None
        assert llm_config is not None
    
    def test_get_config_defaults(self):
        """测试获取默认配置"""
        from app.core.llm_config_manager import LLMConfigManager
        
        config = LLMConfigManager.get_config()
        
        assert isinstance(config, dict)
        assert "provider" in config
        assert "local_model_id" in config
    
    def test_get_provider(self):
        """测试获取提供商"""
        from app.core.llm_config_manager import LLMConfigManager
        
        provider = LLMConfigManager.get_provider()
        assert isinstance(provider, str)
    
    def test_is_local_model_mode(self):
        """测试本地模型模式检测"""
        from app.core.llm_config_manager import LLMConfigManager
        
        # 默认不是本地模型
        is_local = LLMConfigManager.is_local_model_mode()
        assert isinstance(is_local, bool)
    
    def test_get_local_model_config(self):
        """测试获取本地模型配置"""
        from app.core.llm_config_manager import LLMConfigManager
        
        config = LLMConfigManager.get_local_model_config()
        
        assert isinstance(config, dict)
        assert "model_id" in config
        assert "n_ctx" in config
    
    def test_set_local_model(self):
        """测试设置本地模型"""
        from app.core.llm_config_manager import LLMConfigManager
        
        LLMConfigManager.set_local_model("qwen-35b", n_ctx=8192, n_gpu_layers=0)
        
        config = LLMConfigManager.get_local_model_config()
        assert config["model_id"] == "qwen-35b"


class TestLocalLLM:
    """本地 LLM 测试"""
    
    def test_import_local_llm(self):
        """测试导入本地 LLM 模块"""
        from app.core.local_llm import (
            LocalLLMConfig,
            LocalLLMService,
            PREDEFINED_MODELS,
        )
        
        assert LocalLLMConfig is not None
        assert LocalLLMService is not None
        assert PREDEFINED_MODELS is not None
    
    def test_predefined_models(self):
        """测试预定义模型"""
        from app.core.local_llm import PREDEFINED_MODELS
        
        assert "qwen-2b" in PREDEFINED_MODELS
        assert "qwen-35b" in PREDEFINED_MODELS
        
        # 检查模型配置
        qwen_2b = PREDEFINED_MODELS["qwen-2b"]
        assert "path" in qwen_2b
        assert "n_ctx" in qwen_2b
        
        qwen_35b = PREDEFINED_MODELS["qwen-35b"]
        assert "path" in qwen_35b
    
    def test_local_llm_config_defaults(self):
        """测试本地 LLM 配置默认值"""
        from app.core.local_llm import LocalLLMConfig
        
        config = LocalLLMConfig()
        
        assert config.n_ctx == 4096
        assert config.n_gpu_layers == 0
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
    
    def test_list_available_models(self):
        """测试列出可用模型"""
        from app.core.local_llm import list_available_models
        
        models = list_available_models()
        
        assert isinstance(models, dict)
        assert "qwen-2b" in models
        assert "qwen-35b" in models
        
        # 检查模型信息包含 exists 字段
        for model_id, info in models.items():
            assert "exists" in info
            assert "size_gb" in info
    
    def test_get_model_config(self):
        """测试获取模型配置"""
        from app.core.local_llm import get_model_config
        
        config = get_model_config("qwen-2b")
        assert config is not None
        assert config.model_name == "qwen-2b"
        
        # 未知模型返回 None
        config = get_model_config("unknown")
        assert config is None


class TestLLMService:
    """LLM 服务测试"""
    
    def test_import_llm_service(self):
        """测试导入 LLM 服务"""
        from app.services.llm_service import LLMService, LLMProvider
        
        assert LLMService is not None
        assert LLMProvider is not None
    
    def test_llm_provider_enum(self):
        """测试 LLM Provider 枚举"""
        from app.services.llm_service import LLMProvider
        
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.DEEPSEEK.value == "deepseek"
        assert LLMProvider.LOCAL_QWEN.value == "local_qwen"
        assert LLMProvider.KIMI.value == "kimi"
