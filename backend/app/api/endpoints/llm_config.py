"""
LLM 配置 API
用于前端传递 LLM 配置到后端

支持:
- API调用 (OpenAI, DeepSeek)
- Chat2Api (Kimi, Yuanbao)
- 本地模型 (Qwen3.5-2B, Qwen3.5-35B)
"""
from typing import Optional, List
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
    # 本地模型配置
    localModelId: Optional[str] = None  # qwen-2b 或 qwen-35b
    localNCtx: Optional[int] = None
    localNGpuLayers: Optional[int] = None


class LLMConfigResponse(BaseModel):
    """LLM 配置响应"""
    success: bool
    message: str
    timeout: int  # 计算后的超时时间（秒）


class LocalModelInfo(BaseModel):
    """本地模型信息"""
    id: str
    name: str
    path: str
    exists: bool
    size_gb: float
    description: str
    n_ctx: int
    n_gpu_layers: int


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
        
        # 本地模型配置
        if config.localModelId:
            config_dict["local_model_id"] = config.localModelId
        if config.localNCtx:
            config_dict["local_n_ctx"] = config.localNCtx
        if config.localNGpuLayers is not None:
            config_dict["local_n_gpu_layers"] = config.localNGpuLayers
        
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


@router.get("/local-models", response_model=List[LocalModelInfo])
async def list_local_models():
    """
    列出所有可用的本地模型
    
    Returns:
        本地模型列表
    """
    try:
        from app.core.local_llm import list_available_models
        
        models = list_available_models()
        result = []
        
        for model_id, info in models.items():
            result.append(LocalModelInfo(
                id=model_id,
                name=info.get("name", model_id),
                path=info.get("path", ""),
                exists=info.get("exists", False),
                size_gb=round(info.get("size_gb", 0), 2),
                description=info.get("description", ""),
                n_ctx=info.get("n_ctx", 4096),
                n_gpu_layers=info.get("n_gpu_layers", 0),
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"获取本地模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/local-models/select")
async def select_local_model(model_id: str, n_ctx: int = None, n_gpu_layers: int = None):
    """
    选择本地模型
    
    Args:
        model_id: 模型ID (qwen-2b, qwen-35b)
        n_ctx: 上下文长度（可选）
        n_gpu_layers: GPU层数（可选）
    """
    try:
        from app.core.local_llm import PREDEFINED_MODELS
        
        if model_id not in PREDEFINED_MODELS:
            raise HTTPException(status_code=400, detail=f"未知的模型ID: {model_id}")
        
        # 检查模型文件是否存在
        model_info = PREDEFINED_MODELS[model_id]
        from pathlib import Path
        if not Path(model_info["path"]).exists():
            raise HTTPException(status_code=400, detail=f"模型文件不存在: {model_info['path']}")
        
        # 设置本地模型
        LLMConfigManager.set_local_model(model_id, n_ctx, n_gpu_layers)
        
        return {
            "success": True,
            "message": f"已选择模型: {model_info['name']}",
            "model_id": model_id,
            "model_path": model_info["path"],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"选择本地模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local-models/status")
async def get_local_model_status():
    """
    获取本地模型状态
    
    Returns:
        当前选中的模型和加载状态
    """
    try:
        from app.core.local_llm import get_local_llm_service, list_available_models
        
        config = LLMConfigManager.get_local_model_config()
        models = list_available_models()
        
        # 检查当前模型是否加载
        service = get_local_llm_service()
        model_info = service.get_model_info()
        
        return {
            "current_model_id": config.get("model_id"),
            "loaded": model_info.get("loaded", False),
            "model_info": model_info,
            "available_models": {k: v.get("exists", False) for k, v in models.items()},
        }
        
    except Exception as e:
        logger.error(f"获取本地模型状态失败: {e}")
        return {
            "current_model_id": None,
            "loaded": False,
            "error": str(e),
        }
