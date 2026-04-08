"""
AI Chat API 服务
支持 Kimi、DeepSeek、豆包、腾讯元宝
提供 Web 界面和 API 接口
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from config import (
    API_HOST, API_PORT, AI_PROVIDERS, DEFAULT_AI_PROVIDER
)
from settings_manager import (
    settings_manager, get_settings, get_browser_settings, get_timeout_settings
)
from kimi_browser import KimiBrowser, get_browser as get_kimi_browser, close_browser as close_kimi_browser
from deepseek_browser import DeepSeekBrowser, get_browser as get_deepseek_browser, close_browser as close_deepseek_browser
from yuanbao_browser import YuanbaoBrowser, get_browser as get_yuanbao_browser, close_browser as close_yuanbao_browser


# ==================== 浏览器管理器 ====================

class BrowserManager:
    """浏览器实例管理器 - 支持多窗口"""
    
    def __init__(self):
        # 结构: {provider: {window_name: browser_instance}}
        self.browsers: Dict[str, Dict[str, any]] = {
            "kimi": {},
            "deepseek": {},
            "yuanbao": {},
        }
        # 登录状态: {provider: {window_name: {is_logged_in, message}}}
        self.login_status: Dict[str, Dict[str, dict]] = {
            provider: {"default": {"is_logged_in": False, "message": "未启动"}}
            for provider in AI_PROVIDERS.keys()
        }
        # Playwright 实例（每个 provider 一个）
        self.playwright_instances: Dict[str, any] = {}
        
    async def get_browser(self, provider: str, window_name: str = "default"):
        """
        获取指定提供商的浏览器实例
        
        Args:
            provider: AI 提供商 (kimi/deepseek/yuanbao)
            window_name: 窗口名称，用于区分不同的会话
        """
        if provider not in AI_PROVIDERS:
            raise ValueError(f"不支持的 AI 提供商: {provider}")
        
        # 如果窗口不存在，创建新的
        if window_name not in self.browsers[provider]:
            if provider == "kimi":
                from kimi_browser import KimiBrowser
                self.browsers[provider][window_name] = KimiBrowser(window_name=window_name)
                await self.browsers[provider][window_name].start()
            elif provider == "deepseek":
                from deepseek_browser import DeepSeekBrowser
                self.browsers[provider][window_name] = DeepSeekBrowser(window_name=window_name)
                await self.browsers[provider][window_name].start()
            elif provider == "yuanbao":
                from yuanbao_browser import YuanbaoBrowser
                self.browsers[provider][window_name] = YuanbaoBrowser(window_name=window_name)
                await self.browsers[provider][window_name].start()
            
            # 初始化登录状态
            self.login_status[provider][window_name] = {"is_logged_in": False, "message": "已创建"}
        
        return self.browsers[provider][window_name]
    
    async def close_browser(self, provider: str, window_name: str = "default"):
        """关闭指定提供商的指定窗口"""
        if provider in self.browsers and window_name in self.browsers[provider]:
            await self.browsers[provider][window_name].stop()
            del self.browsers[provider][window_name]
            self.login_status[provider][window_name] = {"is_logged_in": False, "message": "已关闭"}
    
    async def close_all(self):
        """关闭所有浏览器实例"""
        for provider in self.browsers:
            for window_name in list(self.browsers[provider].keys()):
                await self.close_browser(provider, window_name)
    
    async def close_provider(self, provider: str):
        """关闭指定提供商的所有窗口"""
        if provider in self.browsers:
            for window_name in list(self.browsers[provider].keys()):
                await self.close_browser(provider, window_name)
    
    def get_login_status(self, provider: str, window_name: str = "default") -> dict:
        """获取指定提供商指定窗口的登录状态"""
        if provider in self.login_status and window_name in self.login_status[provider]:
            return self.login_status[provider][window_name]
        return {"is_logged_in": False, "message": "未知状态"}
    
    def set_login_status(self, provider: str, window_name: str, is_logged_in: bool, message: str):
        """设置指定提供商指定窗口的登录状态"""
        if provider not in self.login_status:
            self.login_status[provider] = {}
        self.login_status[provider][window_name] = {"is_logged_in": is_logged_in, "message": message}
    
    def list_windows(self, provider: str = None) -> Dict[str, list]:
        """列出所有窗口"""
        if provider:
            return {provider: list(self.browsers.get(provider, {}).keys())}
        return {p: list(windows.keys()) for p, windows in self.browsers.items()}


# 全局浏览器管理器
browser_manager = BrowserManager()


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("[Main] 启动 AI Chat 服务...")
    print("[Main] 支持的 AI 提供商:", list(AI_PROVIDERS.keys()))
    
    yield
    
    # 关闭时清理
    print("[Main] 关闭 AI Chat 服务...")
    await browser_manager.close_all()


app = FastAPI(title="AI Chat API", lifespan=lifespan)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 添加缓存控制头，防止浏览器缓存旧版本
@app.middleware("http")
async def add_cache_control_header(request, call_next):
    response = await call_next(request)
    # 对 HTML 文件禁用缓存
    if request.url.path.endswith(".html") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ==================== API 模型 ====================

class ChatRequest(BaseModel):
    message: str
    timeout: int = None  # 从配置读取，默认None表示使用配置值
    window_name: str = "default"  # 窗口名称，用于多会话
    # 功能开关参数
    enable_web_search: bool = False
    enable_deep_think: bool = False
    enable_deep_research: bool = False
    model: str = "k2.5"  # 用于Kimi等模型选择


class ChatResponse(BaseModel):
    success: bool
    message: str
    data: Optional[str] = None
    provider: Optional[str] = None


class LoginStatusResponse(BaseModel):
    is_logged_in: bool
    message: str
    provider: str


class ProvidersResponse(BaseModel):
    providers: dict
    default: str


class SettingsResponse(BaseModel):
    browser: dict
    timeout: dict


class SettingsUpdateRequest(BaseModel):
    browser: Optional[dict] = None
    timeout: Optional[dict] = None


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index():
    """主页面"""
    return FileResponse("static/index.html")


# ==================== API 路由 ====================

@app.get("/api/providers", response_model=ProvidersResponse)
async def get_providers():
    """获取所有支持的 AI 提供商"""
    return ProvidersResponse(
        providers=AI_PROVIDERS,
        default=DEFAULT_AI_PROVIDER
    )


@app.get("/api/status/{provider}", response_model=LoginStatusResponse)
async def get_status(provider: str, window_name: str = "default"):
    """获取指定提供商的指定窗口的登录状态"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    status = browser_manager.get_login_status(provider, window_name)
    
    # 如果浏览器已启动，刷新登录状态
    if provider in browser_manager.browsers and window_name in browser_manager.browsers[provider]:
        try:
            browser = await browser_manager.get_browser(provider, window_name)
            is_logged = await browser.check_login_status()
            browser_manager.set_login_status(
                provider, 
                window_name,
                is_logged, 
                "已登录" if is_logged else "未登录"
            )
            status = browser_manager.get_login_status(provider, window_name)
        except Exception as e:
            status["message"] = f"检查状态失败: {str(e)}"
            
    return LoginStatusResponse(
        is_logged_in=status["is_logged_in"],
        message=status["message"],
        provider=provider
    )


@app.get("/api/status")
async def get_all_status(window_name: str = "default"):
    """获取所有提供商的登录状态"""
    result = {}
    for provider in AI_PROVIDERS.keys():
        status = browser_manager.get_login_status(provider, window_name)
        # 尝试刷新状态
        if provider in browser_manager.browsers and window_name in browser_manager.browsers[provider]:
            try:
                browser = await browser_manager.get_browser(provider, window_name)
                is_logged = await browser.check_login_status()
                browser_manager.set_login_status(
                    provider,
                    window_name,
                    is_logged,
                    "已登录" if is_logged else "未登录"
                )
                status = browser_manager.get_login_status(provider, window_name)
            except:
                pass
        result[provider] = status
    return result


@app.post("/api/{provider}/login/start")
async def start_login(provider: str, window_name: str = "default"):
    """开始登录流程（打开登录页面）"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    try:
        browser = await browser_manager.get_browser(provider, window_name)
        await browser.navigate_to_login()
        browser_manager.set_login_status(provider, window_name, False, "请在打开的浏览器窗口中完成登录")
        return {
            "success": True, 
            "message": f"请在浏览器中完成 {AI_PROVIDERS[provider]['display_name']} 的登录",
            "provider": provider,
            "window_name": window_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动登录失败: {str(e)}")


@app.post("/api/{provider}/login/confirm")
async def confirm_login(provider: str, window_name: str = "default"):
    """确认登录完成"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    try:
        browser = await browser_manager.get_browser(provider, window_name)
        is_logged = await browser.check_login_status()
        browser_manager.set_login_status(
            provider,
            window_name,
            is_logged,
            "登录成功" if is_logged else "未登录"
        )
        
        if is_logged:
            return {
                "success": True, 
                "message": f"{AI_PROVIDERS[provider]['display_name']} 登录成功",
                "provider": provider,
                "window_name": window_name
            }
        else:
            return {
                "success": False, 
                "message": "未检测到登录状态，请完成登录",
                "provider": provider,
                "window_name": window_name
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认登录失败: {str(e)}")


@app.get("/api/{provider}/features")
async def get_features(provider: str, window_name: str = "default"):
    """获取指定AI提供商支持的功能列表"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    try:
        browser = await browser_manager.get_browser(provider, window_name)
        features = browser.get_available_features()
        return {
            "success": True,
            "provider": provider,
            "window_name": window_name,
            "features": features
        }
    except Exception as e:
        return {
            "success": False,
            "provider": provider,
            "features": {},
            "error": str(e)
        }


@app.post("/api/{provider}/chat", response_model=ChatResponse)
async def chat(provider: str, request: ChatRequest):
    """发送聊天消息"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    # 使用请求中的 window_name 或默认值
    window_name = request.window_name or "default"
    
    try:
        browser = await browser_manager.get_browser(provider, window_name)
        
        # 检查登录状态
        is_logged = await browser.check_login_status()
        if not is_logged:
            browser_manager.set_login_status(provider, window_name, False, "未登录")
            raise HTTPException(status_code=401, detail="未登录，请先登录")
            
        browser_manager.set_login_status(provider, window_name, True, "已登录")
        
        # 使用请求中的timeout或配置中的默认值
        config_timeout = get_timeout_settings().chat_timeout
        timeout = request.timeout if request.timeout is not None else config_timeout
        print(f"[Main] 请求timeout: {request.timeout}, 配置timeout: {config_timeout}, 实际使用: {timeout}, window: {window_name}")
        
        # 根据提供商传递不同的参数
        send_kwargs = {
            "message": request.message,
            "timeout": timeout
        }
        
        # 添加功能开关参数（如果浏览器支持）
        if provider == "yuanbao":
            send_kwargs["enable_web_search"] = request.enable_web_search
            send_kwargs["enable_deep_think"] = request.enable_deep_think
        elif provider == "deepseek":
            send_kwargs["enable_deep_think"] = request.enable_deep_think
            send_kwargs["enable_web_search"] = request.enable_web_search
        elif provider == "kimi":
            send_kwargs["model"] = request.model
        
        response = await browser.send_message(**send_kwargs)
        
        return ChatResponse(
            success=True,
            message="发送成功",
            data=response,
            provider=provider
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return ChatResponse(
            success=False,
            message=f"聊天失败: {str(e)}",
            data=None,
            provider=provider
        )


@app.post("/api/chat")
async def chat_default(request: ChatRequest, provider: str = Query(default=DEFAULT_AI_PROVIDER)):
    """使用默认 AI 发送聊天消息"""
    return await chat(provider, request)


@app.get("/api/features")
async def get_all_features():
    """获取所有AI提供商支持的功能列表"""
    result = {}
    for provider in AI_PROVIDERS.keys():
        try:
            browser = await browser_manager.get_browser(provider)
            result[provider] = {
                "success": True,
                "features": browser.get_available_features()
            }
        except Exception as e:
            result[provider] = {
                "success": False,
                "features": {},
                "error": str(e)
            }
    return result


@app.post("/api/{provider}/clear")
async def clear_chat(provider: str, window_name: str = "default"):
    """清空对话"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    try:
        browser = await browser_manager.get_browser(provider, window_name)
        await browser.clear_chat()
        return {
            "success": True, 
            "message": "对话已清空",
            "provider": provider,
            "window_name": window_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")


@app.post("/api/{provider}/browser/restart")
async def restart_browser(provider: str, window_name: str = "default"):
    """重启浏览器"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    try:
        await browser_manager.close_browser(provider, window_name)
        browser = await browser_manager.get_browser(provider, window_name)
        await browser.navigate_to_login()
        
        is_logged = await browser.check_login_status()
        browser_manager.set_login_status(
            provider,
            window_name,
            is_logged,
            "浏览器已重启" + ("，已登录" if is_logged else "，请登录")
        )
        
        return {
            "success": True, 
            "message": browser_manager.get_login_status(provider, window_name)["message"],
            "provider": provider,
            "window_name": window_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")


@app.post("/api/{provider}/window/close")
async def close_window(provider: str, window_name: str = "default"):
    """关闭指定窗口"""
    if provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {provider}")
    
    try:
        await browser_manager.close_browser(provider, window_name)
        return {
            "success": True,
            "message": f"窗口 {window_name} 已关闭",
            "provider": provider,
            "window_name": window_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关闭窗口失败: {str(e)}")


@app.get("/api/windows")
async def list_windows(provider: str = None):
    """列出所有窗口"""
    return browser_manager.list_windows(provider)


# ==================== 配置管理 API ====================

@app.get("/api/settings", response_model=SettingsResponse)
async def get_all_settings():
    """获取所有配置参数"""
    settings_dict = settings_manager.get_settings_dict()
    return SettingsResponse(
        browser=settings_dict["browser"],
        timeout=settings_dict["timeout"]
    )


@app.post("/api/settings")
async def update_all_settings(request: SettingsUpdateRequest):
    """更新配置参数"""
    try:
        update_data = {}
        if request.browser is not None:
            update_data["browser"] = request.browser
        if request.timeout is not None:
            update_data["timeout"] = request.timeout
        
        if not update_data:
            raise HTTPException(status_code=400, detail="没有提供要更新的配置")
        
        success = settings_manager.update_settings(update_data)
        if success:
            return {
                "success": True,
                "message": "配置已更新",
                "settings": settings_manager.get_settings_dict()
            }
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新配置失败: {str(e)}")


@app.post("/api/settings/browser")
async def update_browser_settings_endpoint(settings: dict):
    """更新浏览器配置"""
    try:
        success = settings_manager.update_browser_settings(settings)
        if success:
            return {
                "success": True,
                "message": "浏览器配置已更新",
                "browser": settings_manager.get_browser_settings().model_dump()
            }
        else:
            raise HTTPException(status_code=500, detail="保存浏览器配置失败")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新浏览器配置失败: {str(e)}")


@app.post("/api/settings/timeout")
async def update_timeout_settings_endpoint(settings: dict):
    """更新超时配置"""
    try:
        success = settings_manager.update_timeout_settings(settings)
        if success:
            return {
                "success": True,
                "message": "超时配置已更新",
                "timeout": settings_manager.get_timeout_settings().model_dump()
            }
        else:
            raise HTTPException(status_code=500, detail="保存超时配置失败")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新超时配置失败: {str(e)}")


@app.post("/api/settings/reset")
async def reset_settings():
    """重置配置为默认值"""
    try:
        success = settings_manager.reset_to_default()
        if success:
            return {
                "success": True,
                "message": "配置已重置为默认值",
                "settings": settings_manager.get_settings_dict()
            }
        else:
            raise HTTPException(status_code=500, detail="重置配置失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置配置失败: {str(e)}")


# ==================== 主入口 ====================

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 AI Chat API 服务                             ║
╠══════════════════════════════════════════════════════════════╣
║  支持的 AI: Kimi, DeepSeek, 豆包, 腾讯元宝                    ║
║  访问地址: http://localhost:{API_PORT}                         ║
║  API 文档: http://localhost:{API_PORT}/docs                    ║
╚══════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)
