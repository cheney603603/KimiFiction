"""
AI 浏览器自动化基类
提供通用的浏览器操作功能
"""

import asyncio
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Callable
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from settings_manager import get_browser_settings, get_timeout_settings


class BaseAIBrowser(ABC):
    """AI 浏览器自动化基类"""
    
    def __init__(self, name: str, cookies_file: str):
        self.name = name
        self.cookies_file = cookies_file
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self._is_logged_in = False
        
    async def start(self, headless: bool = None, slow_mo: int = None):
        """启动浏览器"""
        # 从配置读取浏览器设置
        browser_settings = get_browser_settings()
        if headless is None:
            headless = browser_settings.headless
        if slow_mo is None:
            slow_mo = browser_settings.slow_mo
            
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo
        )
        
        # 尝试加载已保存的 cookies
        cookies = self._load_cookies()
        if cookies:
            self.context = await self.browser.new_context()
            await self.context.add_cookies(cookies)
            print(f"[{self.name}] 已加载保存的登录状态")
        else:
            self.context = await self.browser.new_context()
            
        self.page = await self.context.new_page()
        
        # 设置页面视窗大小
        await self.page.set_viewport_size({"width": 1280, "height": 800})
        
        print(f"[{self.name}] 浏览器启动成功")
        
    async def stop(self):
        """关闭浏览器"""
        if self.context:
            # 保存 cookies
            cookies = await self.context.cookies()
            self._save_cookies(cookies)
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print(f"[{self.name}] 浏览器已关闭")
        
    def _load_cookies(self) -> list:
        """加载保存的 cookies"""
        if os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[{self.name}] 加载 cookies 失败: {e}")
        return []
    
    def _save_cookies(self, cookies: list):
        """保存 cookies"""
        try:
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"[{self.name}] Cookies 已保存")
        except Exception as e:
            print(f"[{self.name}] 保存 cookies 失败: {e}")
            
    @abstractmethod
    def get_login_url(self) -> str:
        """获取登录页面 URL"""
        pass
    
    @abstractmethod
    def get_chat_url(self) -> str:
        """获取聊天页面 URL"""
        pass
    
    async def navigate_to_login(self):
        """访问登录页面"""
        url = self.get_login_url()
        await self.page.goto(url, wait_until="networkidle")
        print(f"[{self.name}] 已访问 {url}")
        await asyncio.sleep(2)
        
    async def navigate_to_chat(self):
        """访问聊天页面"""
        url = self.get_chat_url()
        await self.page.goto(url, wait_until="networkidle")
        print(f"[{self.name}] 已访问 {url}")
        await asyncio.sleep(2)
        
    @abstractmethod
    async def check_login_status(self) -> bool:
        """检查是否已登录"""
        pass
        
    async def wait_for_login(self, timeout: int = None):
        """等待用户手动登录完成"""
        if timeout is None:
            timeout = get_timeout_settings().login_timeout
        print(f"[{self.name}] 请手动完成登录...")
        print(f"[{self.name}] 等待登录完成，超时时间: {timeout}秒")
        
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            is_logged_in = await self.check_login_status()
            if is_logged_in:
                # 保存登录状态
                cookies = await self.context.cookies()
                self._save_cookies(cookies)
                return True
            await asyncio.sleep(2)
            
        return False
        
    @abstractmethod
    async def send_message(self, message: str, timeout: int = None) -> str:
        """
        发送消息并获取回复
        
        Args:
            message: 要发送的消息
            timeout: 等待回复的超时时间（秒），默认从配置读取
            
        Returns:
            AI 的回复文本（Markdown 格式）
        """
        pass
    
    def get_available_features(self) -> dict:
        """
        获取该AI提供商支持的功能列表
        
        Returns:
            功能列表，格式如:
            {
                "web_search": {"name": "联网搜索", "type": "toggle", "default": False},
                "deep_think": {"name": "深度思考", "type": "toggle", "default": False},
                "model": {"name": "模型选择", "type": "select", "options": ["快速", "思考"], "default": "快速"}
            }
        """
        return {}
    
    async def set_feature(self, feature_name: str, enabled: bool = True, value: str = None):
        """
        设置功能开关/选项
        
        Args:
            feature_name: 功能名称
            enabled: 是否启用（toggle类型）
            value: 选项值（select类型）
        """
        pass
        
    async def _wait_for_response(
        self, 
        timeout: int = None,
        content_selector: str = "",
        generating_indicator_selector: str = "",
        min_wait_time: int = None,
        max_stable_time: int = None
    ) -> str:
        """
        通用方法：等待并获取 AI 回复
        
        Args:
            timeout: 超时时间（秒），默认从配置读取
            content_selector: 内容元素选择器
            generating_indicator_selector: 生成中指示器选择器
            min_wait_time: 最少等待时间，默认从配置读取
            max_stable_time: 内容稳定时间，默认从配置读取
            
        Returns:
            AI 回复文本
        """
        # 从配置读取参数
        timeout_settings = get_timeout_settings()
        if timeout is None:
            timeout = timeout_settings.response_timeout
        if min_wait_time is None:
            min_wait_time = timeout_settings.min_wait_time
        if max_stable_time is None:
            max_stable_time = timeout_settings.max_stable_time
        start_time = asyncio.get_event_loop().time()
        last_response = ""
        stable_count = 0
        no_update_count = 0
        
        print(f"[{self.name}] 等待回复生成...")
        print(f"[{self.name}] 最少等待 {min_wait_time} 秒，稳定时间需 {max_stable_time} 秒")
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # 获取最新回复内容
                if content_selector:
                    response_data = await self.page.evaluate(f"""
                        () => {{
                            const elements = document.querySelectorAll('{content_selector}');
                            if (elements.length > 0) {{
                                const lastElement = elements[elements.length - 1];
                                const text = lastElement.innerText || lastElement.textContent;
                                const html = lastElement.innerHTML;
                                return {{
                                    text: text ? text.trim() : '',
                                    html: html || '',
                                    length: text ? text.trim().length : 0
                                }};
                            }}
                            return {{ text: '', html: '', length: 0 }};
                        }}
                    """)
                else:
                    response_data = {"text": "", "html": "", "length": 0}
                
                response_text = response_data.get('text', '')
                
                # 检查是否还在生成中
                is_generating = False
                if generating_indicator_selector:
                    is_generating = await self.page.evaluate(f"""
                        () => {{
                            const indicators = document.querySelectorAll('{generating_indicator_selector}');
                            return indicators.length > 0;
                        }}
                    """)
                
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if response_text and len(response_text) > len(last_response):
                    # 内容有更新
                    last_response = response_text
                    stable_count = 0
                    no_update_count = 0
                    print(f"[{self.name}] 收到新内容，长度: {{len(last_response)}}，已等待: {{elapsed:.1f}}s，生成中: {{is_generating}}")
                elif response_text and response_text == last_response and len(last_response) > 10:
                    # 内容稳定
                    if not is_generating:
                        stable_count += 1
                        print(f"[{self.name}] 内容稳定 {{stable_count}}/{{max_stable_time}}s，长度: {{len(last_response)}}，已等待: {{elapsed:.1f}}s")
                        
                        # 如果已经等待了最小时间且内容稳定，认为回复完成
                        if elapsed >= min_wait_time and stable_count >= max_stable_time:
                            print(f"[{self.name}] 回复完成（已等待 {{elapsed:.1f}}s），总长度: {{len(last_response)}}")
                            return last_response
                    else:
                        # 还在生成中，重置稳定计数
                        stable_count = 0
                        print(f"[{self.name}] 仍在生成中，长度: {{len(last_response)}}，已等待: {{elapsed:.1f}}s")
                        
                    # 如果长时间没有更新（30秒），即使还在生成也返回
                    no_update_count += 1
                    if no_update_count > 30 and elapsed > 30:
                        print(f"[{self.name}] 长时间无更新，返回当前内容（长度: {{len(last_response)}}）")
                        return last_response
                        
            except Exception as e:
                print(f"[{self.name}] 获取回复时出错: {{e}}")
                
            await asyncio.sleep(1)
            
        # 超时返回当前收集到的回复
        print(f"[{self.name}] 等待回复超时，返回已收集内容（长度: {{len(last_response)}}）")
        return last_response if last_response else "等待回复超时"
        
    async def get_chat_history(self) -> list:
        """获取聊天记录"""
        return []
        
    async def clear_chat(self):
        """清空当前对话"""
        pass
        
    @property
    def is_logged_in(self) -> bool:
        """获取登录状态"""
        return self._is_logged_in
