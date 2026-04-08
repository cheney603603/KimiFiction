"""
服务配置管理器
提供配置的读取、保存和管理功能
配置文件保存在 service_settings.json 中
"""

import json
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class BrowserSettings(BaseModel):
    """浏览器设置"""
    headless: bool = Field(default=False, description="是否无头模式（False方便调试，True用于生产）")
    slow_mo: int = Field(default=100, description="操作延迟（毫秒）", ge=0, le=5000)


class TimeoutSettings(BaseModel):
    """超时时间设置（单位：秒）"""
    chat_timeout: int = Field(default=240, description="API聊天请求默认超时时间", ge=30, le=600)
    login_timeout: int = Field(default=300, description="等待登录完成超时时间", ge=60, le=600)
    response_timeout: int = Field(default=240, description="等待AI回复超时时间", ge=30, le=600)
    min_wait_time: int = Field(default=15, description="等待回复的最少时间", ge=5, le=60)
    max_stable_time: int = Field(default=5, description="内容稳定判定时间", ge=1, le=30)
    element_wait_timeout: int = Field(default=5, description="等待页面元素超时时间", ge=1, le=30)


class ServiceSettings(BaseModel):
    """服务整体配置"""
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    timeout: TimeoutSettings = Field(default_factory=TimeoutSettings)
    
    class Config:
        json_encoders = {
            # 自定义JSON编码器（如果需要）
        }


class SettingsManager:
    """配置管理器"""
    
    _instance: Optional['SettingsManager'] = None
    _settings: ServiceSettings
    _config_file: str = "service_settings.json"
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_settings()
        return cls._instance
    
    def _load_settings(self):
        """从文件加载配置"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._settings = ServiceSettings(**data)
                print(f"[SettingsManager] 已加载配置文件: {self._config_file}")
            except Exception as e:
                print(f"[SettingsManager] 加载配置失败: {e}，使用默认配置")
                self._settings = ServiceSettings()
                self._save_settings()
        else:
            print(f"[SettingsManager] 配置文件不存在，创建默认配置")
            self._settings = ServiceSettings()
            self._save_settings()
    
    def _save_settings(self):
        """保存配置到文件"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings.model_dump(), f, ensure_ascii=False, indent=2)
            print(f"[SettingsManager] 配置已保存到: {self._config_file}")
            return True
        except Exception as e:
            print(f"[SettingsManager] 保存配置失败: {e}")
            return False
    
    def get_settings(self) -> ServiceSettings:
        """获取当前配置"""
        return self._settings
    
    def get_browser_settings(self) -> BrowserSettings:
        """获取浏览器配置"""
        return self._settings.browser
    
    def get_timeout_settings(self) -> TimeoutSettings:
        """获取超时配置"""
        return self._settings.timeout
    
    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        更新配置
        
        Args:
            settings: 新的配置字典，格式如:
                {
                    "browser": {"headless": true, "slow_mo": 200},
                    "timeout": {"chat_timeout": 300, "response_timeout": 300}
                }
        
        Returns:
            是否更新成功
        """
        try:
            # 验证并合并配置
            new_settings = ServiceSettings(**settings)
            self._settings = new_settings
            return self._save_settings()
        except Exception as e:
            print(f"[SettingsManager] 更新配置失败: {e}")
            return False
    
    def update_browser_settings(self, browser_settings: Dict[str, Any]) -> bool:
        """更新浏览器配置"""
        try:
            current = self._settings.browser.model_dump()
            current.update(browser_settings)
            self._settings.browser = BrowserSettings(**current)
            return self._save_settings()
        except Exception as e:
            print(f"[SettingsManager] 更新浏览器配置失败: {e}")
            return False
    
    def update_timeout_settings(self, timeout_settings: Dict[str, Any]) -> bool:
        """更新超时配置"""
        try:
            current = self._settings.timeout.model_dump()
            current.update(timeout_settings)
            self._settings.timeout = TimeoutSettings(**current)
            return self._save_settings()
        except Exception as e:
            print(f"[SettingsManager] 更新超时配置失败: {e}")
            return False
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        self._settings = ServiceSettings()
        return self._save_settings()
    
    def get_settings_dict(self) -> Dict[str, Any]:
        """获取配置字典（用于API返回）"""
        return {
            "browser": {
                "headless": self._settings.browser.headless,
                "slow_mo": self._settings.browser.slow_mo,
                "descriptions": {
                    "headless": "是否无头模式（False方便调试，True用于生产）",
                    "slow_mo": "操作延迟（毫秒）"
                }
            },
            "timeout": {
                "chat_timeout": self._settings.timeout.chat_timeout,
                "login_timeout": self._settings.timeout.login_timeout,
                "response_timeout": self._settings.timeout.response_timeout,
                "min_wait_time": self._settings.timeout.min_wait_time,
                "max_stable_time": self._settings.timeout.max_stable_time,
                "element_wait_timeout": self._settings.timeout.element_wait_timeout,
                "descriptions": {
                    "chat_timeout": "API聊天请求默认超时时间（秒）",
                    "login_timeout": "等待登录完成超时时间（秒）",
                    "response_timeout": "等待AI回复超时时间（秒）",
                    "min_wait_time": "等待回复的最少时间（秒）",
                    "max_stable_time": "内容稳定判定时间（秒）",
                    "element_wait_timeout": "等待页面元素超时时间（秒）"
                },
                "ranges": {
                    "chat_timeout": {"min": 30, "max": 600},
                    "login_timeout": {"min": 60, "max": 600},
                    "response_timeout": {"min": 30, "max": 600},
                    "min_wait_time": {"min": 5, "max": 60},
                    "max_stable_time": {"min": 1, "max": 30},
                    "element_wait_timeout": {"min": 1, "max": 30}
                }
            }
        }


# 全局配置管理器实例
settings_manager = SettingsManager()


def get_settings() -> ServiceSettings:
    """获取配置的便捷函数"""
    return settings_manager.get_settings()


def get_browser_settings() -> BrowserSettings:
    """获取浏览器配置的便捷函数"""
    return settings_manager.get_browser_settings()


def get_timeout_settings() -> TimeoutSettings:
    """获取超时配置的便捷函数"""
    return settings_manager.get_timeout_settings()
