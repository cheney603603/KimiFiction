"""
Kimi 浏览器自动化模块
使用 Playwright 实现登录和聊天功能
"""

import asyncio
import json
import os
from typing import Optional, Callable, Dict
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from config import KIMI_URL, KIMI_CHAT_URL, COOKIES_FILE
from settings_manager import get_browser_settings, get_timeout_settings


class KimiBrowser:
    """Kimi 浏览器自动化类"""
    
    def __init__(self, window_name: str = "default"):
        self.window_name = window_name
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._message_callbacks = []
        self._is_logged_in = False
        
    def get_login_url(self) -> str:
        """获取登录页面 URL"""
        return KIMI_URL
    
    def get_chat_url(self) -> str:
        """获取聊天页面 URL"""
        return KIMI_CHAT_URL
        
    async def navigate_to_login(self):
        """访问登录页面"""
        await self.page.goto(self.get_login_url(), wait_until="networkidle")
        print(f"[KimiBrowser] 已访问 {self.get_login_url()}")
        await asyncio.sleep(2)
        
    async def start(self):
        """启动浏览器"""
        browser_settings = get_browser_settings()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=browser_settings.headless,
            slow_mo=browser_settings.slow_mo
        )
        
        # 尝试加载已保存的 cookies
        cookies = self._load_cookies()
        if cookies:
            self.context = await self.browser.new_context()
            await self.context.add_cookies(cookies)
            print("[KimiBrowser] 已加载保存的登录状态")
        else:
            self.context = await self.browser.new_context()
            
        self.page = await self.context.new_page()
        
        # 设置页面视窗大小
        await self.page.set_viewport_size({"width": 1280, "height": 800})
        
        print("[KimiBrowser] 浏览器启动成功")
        
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
        print("[KimiBrowser] 浏览器已关闭")
        
    def _load_cookies(self) -> list:
        """加载保存的 cookies - 支持多窗口"""
        # 根据窗口名称生成不同的 cookie 文件
        if self.window_name and self.window_name != "default":
            cookie_file = COOKIES_FILE.replace(".json", f"_{self.window_name}.json")
        else:
            cookie_file = COOKIES_FILE
            
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[KimiBrowser] 加载 cookies 失败: {e}")
        return []
    
    def _save_cookies(self, cookies: list):
        """保存 cookies - 支持多窗口"""
        # 根据窗口名称生成不同的 cookie 文件
        if self.window_name and self.window_name != "default":
            cookie_file = COOKIES_FILE.replace(".json", f"_{self.window_name}.json")
        else:
            cookie_file = COOKIES_FILE
            
        try:
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"[KimiBrowser] Cookies 已保存到 {cookie_file}")
        except Exception as e:
            print(f"[KimiBrowser] 保存 cookies 失败: {e}")
            
    async def navigate_to_kimi(self):
        """访问 Kimi 网站"""
        await self.page.goto(KIMI_URL, wait_until="networkidle")
        print(f"[KimiBrowser] 已访问 {KIMI_URL}")
        await asyncio.sleep(2)
        
    async def check_login_status(self) -> bool:
        """
        检查是否已登录
        判断标准：能否使用聊天输入框发送消息
        """
        try:
            # 首先检查是否存在登录按钮
            login_button = await self.page.query_selector('button:has-text("登录"), a:has-text("登录")')
            if login_button:
                # 检查登录按钮是否可见
                is_visible = await login_button.is_visible()
                if is_visible:
                    print("[KimiBrowser] 未登录状态（发现登录按钮）")
                    self._is_logged_in = False
                    return False
            
            # 检查是否有可用的聊天输入框
            # Kimi的输入框通常是textarea，有placeholder包含"输入"或"发送消息"
            input_selectors = [
                'textarea[placeholder*="输入"]',
                'textarea[placeholder*="发送消息"]',
                'textarea[placeholder*="问"]',
                'textarea',
                '[contenteditable="true"]'
            ]
            
            for selector in input_selectors:
                try:
                    chat_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if chat_input:
                        # 检查输入框是否可见且可交互
                        is_visible = await chat_input.is_visible()
                        is_enabled = await chat_input.is_enabled() if hasattr(chat_input, 'is_enabled') else True
                        
                        if is_visible:
                            print(f"[KimiBrowser] 已登录状态（发现输入框: {selector}）")
                            self._is_logged_in = True
                            return True
                except:
                    continue
                    
            print("[KimiBrowser] 未检测到登录状态")
            self._is_logged_in = False
            return False
            
        except Exception as e:
            print(f"[KimiBrowser] 检查登录状态失败: {e}")
            self._is_logged_in = False
            return False
        
    async def wait_for_login(self, timeout: int = None):
        """等待用户手动登录完成"""
        if timeout is None:
            timeout = get_timeout_settings().login_timeout
        print("[KimiBrowser] 请手动完成登录（输入手机号和验证码）...")
        print(f"[KimiBrowser] 等待登录完成，超时时间: {timeout}秒")
        
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
        
    def get_available_features(self) -> dict:
        """
        获取Kimi支持的功能
        Kimi只有一个模型选择功能：K2.5快速 / K2.5思考
        """
        return {
            "model": {
                "name": "模型",
                "type": "select",
                "options": ["k2.5", "k2.5-reasoning"],
                "option_names": {
                    "k2.5": "K2.5 快速", 
                    "k2.5-reasoning": "K2.5 思考"
                },
                "default": "k2.5",
                "description": "切换K2.5快速或K2.5思考模型"
            }
        }
    
    async def set_feature(self, feature_name: str, enabled: bool = True, value: str = None):
        """
        设置Kimi功能
        """
        if feature_name == "model":
            await self._select_model(value)
        else:
            print(f"[KimiBrowser] 不支持的功能: {feature_name}")
    
    async def _select_model(self, model: str):
        """
        选择模型 (K2.5 快速 / K2.5 思考)
        """
        if not model:
            return
            
        try:
            print(f"[KimiBrowser] 尝试切换模型到: {model}")
            
            # 查找模型选择按钮 - 尝试多种选择器
            selectors = [
                'button:has-text("K2.5")',
                'button:has-text("思考")',
                'button:has-text("快速")',
                '[class*="model"]',
                '[class*="select"]',
            ]
            
            model_btn = None
            for selector in selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=2000)
                    if btn:
                        text = await btn.inner_text()
                        print(f"[KimiBrowser] 找到按钮: {text[:30]}")
                        if any(kw in text for kw in ['K2.5', '思考', '快速', 'model']):
                            model_btn = btn
                            break
                except:
                    continue
            
            if not model_btn:
                print(f"[KimiBrowser] 未找到模型选择按钮，可能已是目标模型")
                return
            
            # 点击打开模型选择菜单
            await model_btn.click()
            await asyncio.sleep(0.5)
            
            # 查找目标模型选项
            target_text = "思考" if model == "k2.5-reasoning" else "快速"
            option_selector = f'text={target_text}'
            
            try:
                option = await self.page.wait_for_selector(option_selector, timeout=3000)
                if option:
                    await option.click()
                    await asyncio.sleep(0.5)
                    print(f"[KimiBrowser] 已切换到K2.5{target_text}模型")
            except:
                print(f"[KimiBrowser] 未找到{target_text}选项，可能已是目标模型")
                
        except Exception as e:
            print(f"[KimiBrowser] 切换模型失败: {e}")
    
    async def send_message(self, message: str, timeout: int = None, model: str = "k2.5") -> str:
        """
        发送消息并获取回复
        
        Args:
            message: 要发送的消息
            timeout: 等待回复的超时时间（秒），默认从配置读取
            model: 模型选择 (k2.5 或 k2.5-reasoning)
            
        Returns:
            AI 的回复文本
        """
        if timeout is None:
            timeout = get_timeout_settings().chat_timeout
        
        if not self._is_logged_in:
            raise Exception("未登录，请先登录")
        
        # 设置模型
        if model:
            await self.set_feature("model", value=model)
        
        print(f"[KimiBrowser] 发送消息: {message[:50]}...")
        print(f"[KimiBrowser] 使用超时时间: {timeout} 秒")
        
        # 记录发送前的消息数量
        prev_message_count = await self.page.evaluate("""
            () => {
                return document.querySelectorAll('.segment-content, .message, .chat-message').length;
            }
        """)
        print(f"[KimiBrowser] 发送前消息数: {prev_message_count}")
        
        # 找到输入框并输入消息
        # Kimi 可能有不同的输入框选择器，尝试多种方式
        input_selectors = [
            'textarea[placeholder*="输入"]',
            'textarea[placeholder*="发送消息"]',
            'textarea[placeholder*="问"]',
            'textarea',
            '[contenteditable="true"]',
            'div[contenteditable="true"]',
            '.chat-input textarea',
            '.input-box textarea'
        ]
        
        input_element = None
        for selector in input_selectors:
            try:
                input_element = await self.page.wait_for_selector(selector, timeout=2000)
                if input_element:
                    print(f"[KimiBrowser] 找到输入框: {selector}")
                    break
            except:
                continue
                
        if not input_element:
            # 尝试通过 JavaScript 找到输入框
            try:
                input_element = await self.page.query_selector('textarea, [contenteditable="true"]')
                if input_element:
                    print("[KimiBrowser] 通过通用选择器找到输入框")
            except:
                pass
                
        if not input_element:
            raise Exception("无法找到输入框")
            
        # 点击输入框并输入消息
        await input_element.click()
        await asyncio.sleep(0.3)
        
        # 清除原有内容并输入新消息
        await input_element.fill(message)
        await asyncio.sleep(0.5)
        
        # 发送消息 - 先尝试按 Enter
        try:
            await input_element.press("Enter")
            print("[KimiBrowser] 已按 Enter 发送")
        except Exception as e:
            print(f"[KimiBrowser] 按 Enter 失败: {e}")
        
        # 也可以尝试点击发送按钮
        send_button_selectors = [
            'button[type="submit"]',
            'button:has-text("发送")',
            'button:has-text("Send")',
            '[data-testid="send-button"]',
            '.send-button',
            '.submit-button',
            'button svg',  # 有些发送按钮是图标
            'button:not([disabled])'  # 尝试找到启用的按钮
        ]
        
        for selector in send_button_selectors:
            try:
                send_btn = await self.page.wait_for_selector(selector, timeout=500)
                if send_btn:
                    await send_btn.click()
                    print(f"[KimiBrowser] 点击发送按钮: {selector}")
                    break
            except:
                continue
        
        # 等待新消息出现
        print("[KimiBrowser] 等待消息发送...")
        await asyncio.sleep(1)
        
        # 等待新的回复出现
        max_wait = 10
        for i in range(max_wait):
            current_count = await self.page.evaluate("""
                () => {
                    return document.querySelectorAll('.segment-content, .message, .chat-message').length;
                }
            """)
            if current_count > prev_message_count:
                print(f"[KimiBrowser] 检测到新消息，当前消息数: {current_count}")
                break
            await asyncio.sleep(0.5)
                
        print("[KimiBrowser] 消息已发送，等待回复生成...")
        
        # 等待并获取回复
        return await self._wait_for_response(timeout)
        
    async def _wait_for_response(self, timeout: int = None) -> str:
        """
        等待并获取 AI 回复
        
        Args:
            timeout: 超时时间（秒），默认从配置读取
            
        Returns:
            AI 回复文本
        """
        if timeout is None:
            timeout = get_timeout_settings().response_timeout
        
        # 从配置读取等待参数
        timeout_settings = get_timeout_settings()
        max_stable_time = timeout_settings.max_stable_time
        min_wait_time = timeout_settings.min_wait_time
        
        start_time = asyncio.get_event_loop().time()
        last_response = ""
        stable_count = 0
        no_update_count = 0  # 连续没有更新的计数
        content_growing = True  # 内容是否还在增长
        last_length = 0  # 上一次的长度
        
        print("[KimiBrowser] 等待回复生成...")
        print(f"[KimiBrowser] 超时时间: {timeout} 秒，最少等待 {min_wait_time} 秒，稳定时间需 {max_stable_time} 秒")
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # 使用 JavaScript 获取最新的 AI 回复内容
                response_data = await self.page.evaluate("""
                    () => {
                        // 尝试多种选择器来获取 Kimi 的回复内容
                        const selectors = [
                            // 主要的回复内容选择器（根据用户提供的 HTML 结构）
                            '.segment-content .markdown',
                            '.segment-content .markdown-container .markdown',
                            '.segment-container .segment-content .markdown',
                            '[data-v-b7eff404] .segment-content .markdown',
                            // 备用选择器
                            '.markdown-body',
                            '.message-content',
                            '.chat-message:last-child .content',
                            '.assistant-message .content',
                            '[data-testid="assistant-message"]'
                        ];
                        
                        for (const selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                // 获取最后一个元素（最新的回复）
                                const lastElement = elements[elements.length - 1];
                                const text = lastElement.innerText || lastElement.textContent;
                                if (text && text.trim().length > 0) {
                                    return {
                                        text: text.trim(),
                                        html: lastElement.innerHTML,
                                        length: text.trim().length
                                    };
                                }
                            }
                        }
                        
                        // 如果没找到，尝试获取所有 .segment-content 的文本
                        const segments = document.querySelectorAll('.segment-content');
                        if (segments.length > 0) {
                            const lastSegment = segments[segments.length - 1];
                            // 排除用户自己的消息（通常有特定的 class）
                            if (!lastSegment.closest('.segment-user')) {
                                const text = lastSegment.innerText || lastSegment.textContent;
                                if (text && text.trim().length > 0) {
                                    return {
                                        text: text.trim(),
                                        html: lastSegment.innerHTML,
                                        length: text.trim().length
                                    };
                                }
                            }
                        }
                        
                        return { text: '', html: '', length: 0 };
                    }
                """)
                
                response_text = response_data.get('text', '')
                response_length = response_data.get('length', 0)
                
                # 检查是否还在生成中
                is_generating = await self.page.evaluate("""
                    () => {
                        // 检查是否有生成中的指示器
                        const indicators = document.querySelectorAll(
                            '.loading, .generating, .thinking, .cursor, [class*="loading"], [class*="generating"], .animate-pulse'
                        );
                        // 检查是否有停止按钮（通常表示正在生成）
                        const stopButton = document.querySelector('button[class*="stop"], button[title*="停止"], button svg[class*="stop"]');
                        return indicators.length > 0 || !!stopButton;
                    }
                """)
                
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if response_text and len(response_text) > len(last_response):
                    # 内容有更新
                    last_response = response_text
                    stable_count = 0
                    no_update_count = 0
                    print(f"[KimiBrowser] 收到新内容，长度: {len(last_response)}，已等待: {elapsed:.1f}s，生成中: {is_generating}")
                elif response_text and response_text == last_response and len(last_response) > 10:
                    # 内容稳定
                    if not is_generating:
                        stable_count += 1
                        print(f"[KimiBrowser] 内容稳定 {stable_count}/{max_stable_time}s，长度: {len(last_response)}，已等待: {elapsed:.1f}s")
                        
                        # 如果已经等待了最小时间且内容稳定，认为回复完成
                        if elapsed >= min_wait_time and stable_count >= max_stable_time:
                            print(f"[KimiBrowser] 回复完成（已等待 {elapsed:.1f}s），总长度: {len(last_response)}")
                            return last_response
                    else:
                        # 还在生成中，重置稳定计数
                        stable_count = 0
                        print(f"[KimiBrowser] 仍在生成中，长度: {len(last_response)}，已等待: {elapsed:.1f}s")
                        
                    # 如果长时间没有更新（30秒），即使还在生成也返回
                    no_update_count += 1
                    if no_update_count > 30 and elapsed > 30:
                        print(f"[KimiBrowser] 长时间无更新，返回当前内容（长度: {len(last_response)}）")
                        return last_response
                        
            except Exception as e:
                print(f"[KimiBrowser] 获取回复时出错: {e}")
                
            # 每5秒滚动一次，确保内容被加载
            if int(elapsed) % 5 == 0:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                
            await asyncio.sleep(1)
            
        # 超时返回当前收集到的回复
        print(f"[KimiBrowser] 等待回复超时，返回已收集内容（长度: {len(last_response)}）")
        
        # 最后尝试一次获取完整内容 - 滚动到底部并获取
        try:
            # 先滚动到底部
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(1)
            
            # 尝试多种方式获取完整内容
            final_response = await self.page.evaluate("""
                () => {
                    // 方法1: 获取所有 segment-content 中的最后一个
                    const segments = document.querySelectorAll('.segment-content');
                    if (segments.length > 0) {
                        const lastSegment = segments[segments.length - 1];
                        const text = lastSegment.innerText || lastSegment.textContent;
                        if (text && text.trim().length > 50) {
                            return { method: 'segment', text: text.trim() };
                        }
                    }
                    
                    // 方法2: 获取 markdown 内容
                    const markdowns = document.querySelectorAll('.markdown');
                    if (markdowns.length > 0) {
                        const lastMarkdown = markdowns[markdowns.length - 1];
                        const text = lastMarkdown.innerText || lastMarkdown.textContent;
                        if (text && text.trim().length > 50) {
                            return { method: 'markdown', text: text.trim() };
                        }
                    }
                    
                    // 方法3: 获取整个聊天区域文本
                    const chatArea = document.querySelector('.chat-container, .chat-area, .conversation, main');
                    if (chatArea) {
                        const messages = chatArea.querySelectorAll('.segment-container, .message, [data-v-b7eff404]');
                        if (messages.length > 0) {
                            const lastMsg = messages[messages.length - 1];
                            const text = lastMsg.innerText || lastMsg.textContent;
                            if (text && text.trim().length > 50) {
                                return { method: 'chat-area', text: text.trim() };
                            }
                        }
                    }
                    
                    return { method: 'none', text: last_response };
                }
            """)
            
            final_text = final_response.get('text', '')
            final_method = final_response.get('method', 'none')
            
            if final_text and len(final_text) > len(last_response):
                last_response = final_text
                print(f"[KimiBrowser] 最终获取到更长内容 ({final_method}): {len(last_response)}")
            elif final_text and len(final_text) > 0:
                print(f"[KimiBrowser] 最终检查未获得更长内容 (当前: {len(last_response)}, 获取: {len(final_text)}, 方法: {final_method})")
                # 如果长度差不多，可能是一样的内容
                if abs(len(final_text) - len(last_response)) < 100:
                    print(f"[KimiBrowser] 内容长度相近，使用最终获取的内容")
                    last_response = final_text
                
        except Exception as e:
            print(f"[KimiBrowser] 最终获取失败: {e}")
            
        return last_response if last_response else "等待回复超时"
        
    async def get_chat_history(self) -> list:
        """获取聊天记录"""
        # 这里可以实现获取历史记录的逻辑
        return []
        
    async def clear_chat(self):
        """清空当前对话"""
        # 这里可以实现清空对话的逻辑
        pass


# 全局浏览器实例 - 支持多窗口
_browsers: Dict[str, KimiBrowser] = {}


async def get_browser(window_name: str = "default") -> KimiBrowser:
    """获取或创建浏览器实例"""
    if window_name not in _browsers:
        _browsers[window_name] = KimiBrowser(window_name=window_name)
        await _browsers[window_name].start()
    return _browsers[window_name]


async def close_browser(window_name: str = "default"):
    """关闭浏览器实例"""
    if window_name in _browsers:
        await _browsers[window_name].stop()
        del _browsers[window_name]


async def close_all_browsers():
    """关闭所有浏览器实例"""
    for window_name in list(_browsers.keys()):
        await close_browser(window_name)
