"""
LLM 配置 API
用于前端传递 LLM 配置到后端

支持:
- API调用 (OpenAI, DeepSeek)
- Chat2Api (Kimi, Yuanbao)
- 本地模型 (Qwen3.5-2B, Qwen3.5-35B)
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger
import httpx
import time

from app.core.llm_config_manager import LLMConfigManager
from app.core.config import settings
from app.core.auth import require_auth
from app.services.llm_user_service import LLMUserConfigService

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
async def set_llm_config(
    config: LLMConfigRequest,
    current_user: dict = Depends(require_auth),
):
    """
    保存当前用户的 BYOK LLM 配置（仅自己可见，api_key 加密落库）。

    apiKey 为空/未填时表示不修改已有 Key；不写入全局环境变量，避免跨用户串 Key。
    """
    user_id = current_user["id"]
    try:
        from app.core.database import get_session

        config_dict = {
            "provider": config.provider,
            "base_url": config.baseUrl,
            "model": config.model,
        }
        if config.apiKey:
            config_dict["api_key"] = config.apiKey

        async with get_session() as db:
            service = LLMUserConfigService(db)
            await service.upsert(user_id, config_dict)

        # 计算超时时间
        timeout = LLMConfigManager.get_timeout()

        logger.info(f"用户 {user_id} 的 LLM 配置已更新: provider={config.provider}, base_url={config.baseUrl}")
        return LLMConfigResponse(
            success=True,
            message="已保存到「我的 Key」",
            timeout=timeout
        )
    except RuntimeError as e:
        logger.error(f"保存用户 LLM 配置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"保存用户 LLM 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config")
async def clear_llm_config(
    current_user: dict = Depends(require_auth),
):
    """清除当前用户的 BYOK LLM 配置（移除其 Key）。"""
    user_id = current_user["id"]
    try:
        from app.core.database import get_session

        async with get_session() as db:
            removed = await LLMUserConfigService(db).delete(user_id)
        return {"success": True, "removed": removed, "message": "已清除我的配置"}
    except Exception as e:
        logger.error(f"清除用户 LLM 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/timeout")
async def get_timeout():
    """获取当前计算后的超时时间"""
    timeout = LLMConfigManager.get_timeout()
    return {
        "timeout": timeout,
        "response_time": LLMConfigManager.get_config().get("response_time")
    }


@router.get("/config/current")
async def get_current_config(
    current_user: dict = Depends(require_auth),
):
    """获取当前 LLM 配置（BYOK：优先展示用户自己的配置，隐藏敏感信息）"""
    user_id = current_user["id"]
    from app.core.database import get_session

    user_config = {}
    async with get_session() as db:
        user_config = await LLMUserConfigService(db).get_snapshot(user_id)

    effective = LLMConfigManager.get_config()
    merged = {**effective, **user_config}

    return {
        "provider": merged.get("provider"),
        "base_url": merged.get("base_url"),
        "model": merged.get("model"),
        "has_api_key": bool(merged.get("api_key")),
        "uses_user_key": bool(user_config.get("api_key")),
        "response_time": merged.get("response_time"),
        "timeout": merged.get("timeout"),
    }


class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    message: str
    response_time_ms: Optional[int] = None
    response: Optional[str] = None
    error: Optional[str] = None


@router.post("/config/test", response_model=TestConnectionResponse)
async def test_llm_connection(
    config: LLMConfigRequest,
    current_user: dict = Depends(require_auth),
):
    """
    测试 LLM API 连接

    通过后端代理测试，优先使用前端传入的配置，
    未传入 apiKey 时使用当前用户已保存的 Key，再回落 .env 配置。
    """
    start_time = time.time()

    try:
        provider = config.provider or "deepseek"

        # 用户已保存的 BYOK 配置兜底
        from app.core.database import get_session
        saved = {}
        async with get_session() as db:
            saved = await LLMUserConfigService(db).get_snapshot(current_user["id"])

        # 优先使用前端传入的配置
        api_key = config.apiKey or saved.get("api_key") or ""
        base_url = config.baseUrl or saved.get("base_url") or ""
        model = config.model or saved.get("model") or ""

        # 如果仍未提供，则使用后端 .env 配置
        if not api_key:
            api_key = settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
        if not base_url:
            base_url = settings.DEEPSEEK_BASE_URL if provider == "deepseek" else settings.OPENAI_BASE_URL
        if not model:
            model = settings.DEEPSEEK_MODEL if provider == "deepseek" else settings.OPENAI_MODEL
        
        if provider in ["openai", "deepseek"]:
            # OpenAI / DeepSeek 直接 API 测试
            if not api_key:
                return TestConnectionResponse(
                    success=False,
                    message=f"{provider.upper()} API Key not set",
                    error="请在 .env 中设置 API Key 或在前端页面手动输入"
                )
            
            test_url = f"{base_url}/chat/completions"
            logger.info(f"测试 {provider} API: {test_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    test_url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "You are a test assistant."},
                            {"role": "user", "content": "Reply with 'OK' only."},
                        ],
                        "max_tokens": 50,
                    }
                )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if not response.is_success:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                return TestConnectionResponse(
                    success=False,
                    message=f"{provider.upper()} API 连接失败",
                    response_time_ms=response_time_ms,
                    error=error_msg
                )
            
            data = response.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "No reply")
            
            return TestConnectionResponse(
                success=True,
                message=f"{provider.upper()} API 连接成功",
                response_time_ms=response_time_ms,
                response=reply
            )
        
        elif provider in ["kimi", "yuanbao"]:
            # Chat2Api 服务测试
            chat2api_url = base_url or settings.CHAT2API_BASE_URL
            test_url = f"{chat2api_url}/api/{provider}/chat"
            
            logger.info(f"测试 Chat2Api: {test_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    test_url,
                    json={
                        "message": "你好，这是一个测试消息，请简短回复。",
                        "timeout": 30,
                    }
                )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if not response.is_success:
                if response.status_code == 401:
                    return TestConnectionResponse(
                        success=False,
                        message=f"{provider} 未登录",
                        error="请先登录 chat2api 服务"
                    )
                return TestConnectionResponse(
                    success=False,
                    message=f"{provider} 连接失败",
                    response_time_ms=response_time_ms,
                    error=f"HTTP {response.status_code}"
                )
            
            data = response.json()
            if not data.get("success"):
                return TestConnectionResponse(
                    success=False,
                    message=f"{provider} 请求失败",
                    response_time_ms=response_time_ms,
                    error=data.get("message", "Unknown error")
                )
            
            return TestConnectionResponse(
                success=True,
                message=f"{provider} 连接成功",
                response_time_ms=response_time_ms,
                response=data.get("data", "无回复内容")
            )
        
        else:
            return TestConnectionResponse(
                success=False,
                message=f"不支持的提供商: {provider}",
                error="请选择 openai, deepseek, kimi 或 yuanbao"
            )
            
    except httpx.TimeoutException:
        response_time_ms = int((time.time() - start_time) * 1000)
        return TestConnectionResponse(
            success=False,
            message="连接超时",
            response_time_ms=response_time_ms,
            error="请求超时，请检查网络或 API 地址"
        )
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        response_time_ms = int((time.time() - start_time) * 1000)
        return TestConnectionResponse(
            success=False,
            message="测试失败",
            response_time_ms=response_time_ms,
            error=str(e)
        )


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
