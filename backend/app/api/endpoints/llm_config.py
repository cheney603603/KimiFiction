"""
LLM 配置 API
用于前端传递 LLM 配置到后端
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.core.llm_config_manager import LLMConfigManager

router = APIRouter()


class LLMConfigRequest(BaseModel):
    """LLM 配置请求"""
    provider: str = "openai"
    apiKey: Optional[str] = None
    baseUrl: Optional[str] = None
    model: Optional[str] = None
    responseTime: Optional[float] = None  # 测试返回时长（秒）
    timeout: Optional[int] = None  # 手动设置的超时时间（秒）


class LLMConfigResponse(BaseModel):
    """LLM 配置响应"""
    success: bool
    message: str
    timeout: int  # 计算后的超时时间（秒）


@router.post("/config", response_model=LLMConfigResponse)
async def set_llm_config(config: LLMConfigRequest):
    """
    设置 LLM 配置
    
    前端调用此 API 将用户配置的 LLM 设置传递给后端
    """
    try:
        # 将配置保存到全局配置
        config_dict = {
            "provider": config.provider,
            "api_key": config.apiKey,
            "base_url": config.baseUrl,
            "model": config.model,
            "response_time": config.responseTime,
            "timeout": config.timeout,
        }
        
        # 使用配置管理器设置全局配置
        LLMConfigManager.set_config(config_dict)
        
        # 同时设置环境变量（用于兼容）
        import os
        os.environ["LLM_PROVIDER"] = config.provider
        if config.apiKey:
            os.environ["LLM_API_KEY"] = config.apiKey
        if config.baseUrl:
            os.environ["LLM_BASE_URL"] = config.baseUrl
        if config.model:
            os.environ["LLM_MODEL"] = config.model
        if config.responseTime:
            os.environ["LLM_RESPONSE_TIME"] = str(config.responseTime)
        
        # 计算超时时间
        timeout = LLMConfigManager.get_timeout()
        
        logger.info(f"LLM 配置已更新: provider={config.provider}, base_url={config.baseUrl}, timeout={timeout}s")
        
        return LLMConfigResponse(
            success=True,
            message="配置已保存",
            timeout=timeout
        )
        
    except Exception as e:
        logger.error(f"保存 LLM 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/timeout")
async def get_timeout():
    """获取当前计算后的超时时间"""
    timeout = LLMConfigManager.get_timeout()
    return {
        "timeout": timeout,
        "response_time": LLMConfigManager.get_config().get("response_time")
    }
