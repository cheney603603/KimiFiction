"""
腾讯元宝 AI 浏览器自动化模块
使用 Playwright 实现登录和聊天功能
"""

import asyncio
from typing import Optional
from playwright.async_api import Page
from base_browser import BaseAIBrowser
from config import (
    YUANBAO_URL, YUANBAO_CHAT_URL,
    YUANBAO_COOKIES_FILE
)
from settings_manager import get_browser_settings, get_timeout_settings


class YuanbaoBrowser(BaseAIBrowser):
    """腾讯元宝 AI 浏览器自动化类"""
    
    def __init__(self):
        super().__init__("Yuanbao", YUANBAO_COOKIES_FILE)
        
    def get_login_url(self) -> str:
        """获取登录页面 URL"""
        return YUANBAO_URL
    
    def get_chat_url(self) -> str:
        """获取聊天页面 URL"""
        return YUANBAO_CHAT_URL
        
    async def check_login_status(self) -> bool:
        """
        检查是否已登录
        判断标准：能否使用聊天输入框发送消息
        """
        try:
            # 检查是否有登录按钮
            login_button = await self.page.query_selector(
                'button:has-text("登录"), a:has-text("登录")'
            )
            if login_button:
                is_visible = await login_button.is_visible()
                if is_visible:
                    print(f"[{self.name}] 未登录状态（发现登录按钮）")
                    self._is_logged_in = False
                    return False
            
            # 检查是否有可用的聊天输入框
            input_selectors = [
                'textarea[placeholder*="输入"]',
                'textarea[placeholder*="发送消息"]',
                '#chat-input',
                'textarea',
                '[contenteditable="true"]'
            ]
            
            for selector in input_selectors:
                try:
                    chat_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if chat_input:
                        is_visible = await chat_input.is_visible()
                        if is_visible:
                            print(f"[{self.name}] 已登录状态（发现输入框: {selector}）")
                            self._is_logged_in = True
                            return True
                except:
                    continue
                    
            print(f"[{self.name}] 未检测到登录状态")
            self._is_logged_in = False
            return False
                
        except Exception as e:
            print(f"[{self.name}] 检查登录状态失败: {e}")
            self._is_logged_in = False
            return False
        
    def get_available_features(self) -> dict:
        """
        获取腾讯元宝支持的功能
        """
        return {
            "web_search": {
                "name": "联网搜索",
                "type": "toggle",
                "default": False,
                "description": "开启后会搜索互联网获取最新信息"
            },
            "deep_think": {
                "name": "深度思考",
                "type": "toggle", 
                "default": False,
                "description": "使用DeepSeek R1模型进行深度思考"
            }
        }
    
    async def set_feature(self, feature_name: str, enabled: bool = True, value: str = None):
        """
        设置腾讯元宝功能开关
        """
        if feature_name == "web_search":
            await self._toggle_web_search(enabled)
        elif feature_name == "deep_think":
            await self._toggle_deep_think(enabled)
        else:
            print(f"[{self.name}] 不支持的功能: {feature_name}")
    
    async def _toggle_web_search(self, enabled: bool):
        """切换联网搜索开关"""
        try:
            btn = await self.page.wait_for_selector('[dt-button-id="internet_search"]', timeout=5000)
            if not btn:
                print(f"[{self.name}] 未找到联网搜索按钮")
                return
            
            # 获取当前状态
            current_status = await btn.get_attribute('dt-internet-search')
            is_currently_enabled = (current_status == "openInternetSearch")
            
            print(f"[{self.name}] 联网搜索当前状态: {'开启' if is_currently_enabled else '关闭'}, 目标: {'开启' if enabled else '关闭'}")
            
            # 如果需要切换
            if is_currently_enabled != enabled:
                await btn.click()
                await asyncio.sleep(0.5)
                print(f"[{self.name}] 联网搜索已{'开启' if enabled else '关闭'}")
            else:
                print(f"[{self.name}] 联网搜索状态无需改变")
                
        except Exception as e:
            print(f"[{self.name}] 切换联网搜索失败: {e}")
    
    async def _toggle_deep_think(self, enabled: bool):
        """切换深度思考开关"""
        try:
            btn = await self.page.wait_for_selector('[dt-button-id="deep_think"]', timeout=5000)
            if not btn:
                print(f"[{self.name}] 未找到深度思考按钮")
                return
            
            # 获取当前激活状态
            # 深度思考按钮通常通过class或aria-pressed来表示激活状态
            aria_pressed = await btn.get_attribute('aria-pressed')
            class_name = await btn.get_attribute('class')
            
            # 检查是否已激活（根据实际页面逻辑调整）
            is_currently_enabled = (aria_pressed == "true") or ("active" in (class_name or ""))
            
            print(f"[{self.name}] 深度思考当前状态: {'开启' if is_currently_enabled else '关闭'}, 目标: {'开启' if enabled else '关闭'}")
            
            # 如果需要切换
            if is_currently_enabled != enabled:
                await btn.click()
                await asyncio.sleep(0.5)
                print(f"[{self.name}] 深度思考已{'开启' if enabled else '关闭'}")
            else:
                print(f"[{self.name}] 深度思考状态无需改变")
                
        except Exception as e:
            print(f"[{self.name}] 切换深度思考失败: {e}")
    
    async def send_message(self, message: str, timeout: int = None, 
                          enable_web_search: bool = False, 
                          enable_deep_think: bool = False) -> str:
        """
        发送消息并获取回复
        
        Args:
            message: 要发送的消息
            timeout: 等待回复的超时时间（秒），默认从配置读取
            enable_web_search: 是否开启联网搜索
            enable_deep_think: 是否开启深度思考
            
        Returns:
            AI 的回复文本（Markdown 格式）
        """
        if timeout is None:
            timeout = get_timeout_settings().chat_timeout
        if not self._is_logged_in:
            raise Exception("未登录，请先登录")
        
        # 设置功能开关
        await self.set_feature("web_search", enable_web_search)
        await self.set_feature("deep_think", enable_deep_think)
        
        print(f"[{self.name}] 发送消息: {message[:50]}...")
        print(f"[{self.name}] 联网搜索: {'开启' if enable_web_search else '关闭'}, 深度思考: {'开启' if enable_deep_think else '关闭'}")
        
        # 找到输入框
        input_selectors = [
            'textarea[placeholder*="输入"]',
            'textarea[placeholder*="发送消息"]',
            '#chat-input',
            'textarea',
            '[contenteditable="true"]',
            '.input-box textarea',
            '.chat-input',
        ]
        
        input_element = None
        for selector in input_selectors:
            try:
                input_element = await self.page.wait_for_selector(selector, timeout=2000)
                if input_element:
                    print(f"[{self.name}] 找到输入框: {selector}")
                    break
            except:
                continue
                
        if not input_element:
            raise Exception("无法找到输入框")
            
        # 点击输入框并输入消息
        await input_element.click()
        await asyncio.sleep(0.3)
        await input_element.fill(message)
        await asyncio.sleep(0.5)
        
        # 发送消息 - 按 Enter
        try:
            await input_element.press("Enter")
            print(f"[{self.name}] 已按 Enter 发送")
        except Exception as e:
            print(f"[{self.name}] 按 Enter 失败: {e}")
            
        # 也可以尝试点击发送按钮
        send_button_selectors = [
            'button[type="submit"]',
            'button:has-text("发送")',
            '.send-button',
            'button.send',
            '[data-testid="send-button"]',
            '.icon-send',
            'button svg[class*="send"]',
        ]
        
        for selector in send_button_selectors:
            try:
                send_btn = await self.page.wait_for_selector(selector, timeout=500)
                if send_btn:
                    await send_btn.click()
                    print(f"[{self.name}] 点击发送按钮: {selector}")
                    break
            except:
                continue
        
        # 等待并获取回复
        return await self._wait_for_yuanbao_response(timeout)
        
    async def _wait_for_yuanbao_response(self, timeout: int = None) -> str:
        """
        等待并获取腾讯元宝的回复
        
        Args:
            timeout: 超时时间（秒），默认从配置读取
            
        Returns:
            AI 回复文本（Markdown 格式）
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
        no_update_count = 0
        
        print(f"[{self.name}] 等待回复生成...")
        print(f"[{self.name}] 超时时间: {timeout} 秒，最少等待 {min_wait_time} 秒，稳定时间需 {max_stable_time} 秒")
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # 腾讯元宝的回复选择器 - 根据实际HTML结构调整
                response_data = await self.page.evaluate("""
                    () => {
                        // 1. 首先尝试获取最新的 AI 消息项
                        const aiMessages = document.querySelectorAll('.agent-chat__list__item--ai');
                        if (aiMessages.length > 0) {
                            const lastMessage = aiMessages[aiMessages.length - 1];
                            
                            // 获取主要内容（排除思考过程）
                            const mainContent = lastMessage.querySelector('.hyc-content-md:not(.hyc-component-deepsearch-cot__think__content *)');
                            if (mainContent) {
                                const text = mainContent.innerText || mainContent.textContent;
                                const html = mainContent.innerHTML;
                                if (text && text.trim().length > 0) {
                                    return {
                                        text: text.trim(),
                                        html: html,
                                        length: text.trim().length,
                                        source: 'hyc-content-md'
                                    };
                                }
                            }
                            
                            // 尝试获取 hyc-common-markdown
                            const markdown = lastMessage.querySelector('.hyc-common-markdown');
                            if (markdown) {
                                const text = markdown.innerText || markdown.textContent;
                                const html = markdown.innerHTML;
                                if (text && text.trim().length > 0) {
                                    return {
                                        text: text.trim(),
                                        html: html,
                                        length: text.trim().length,
                                        source: 'hyc-common-markdown'
                                    };
                                }
                            }
                        }
                        
                        // 2. 尝试获取所有 hyc-common-markdown
                        const allMarkdowns = document.querySelectorAll('.hyc-common-markdown');
                        if (allMarkdowns.length > 0) {
                            const lastMarkdown = allMarkdowns[allMarkdowns.length - 1];
                            const text = lastMarkdown.innerText || lastMarkdown.textContent;
                            const html = lastMarkdown.innerHTML;
                            if (text && text.trim().length > 0) {
                                return {
                                    text: text.trim(),
                                    html: html,
                                    length: text.trim().length,
                                    source: 'hyc-common-markdown-all'
                                };
                            }
                        }
                        
                        // 3. 备用选择器
                        const backupSelectors = [
                            '.agent-chat__bubble__content',
                            '.agent-chat__speech-text--box',
                            '.agent-chat__list__item--ai:last-child',
                        ];
                        
                        for (const selector of backupSelectors) {
                            try {
                                const elements = document.querySelectorAll(selector);
                                if (elements.length > 0) {
                                    const lastElement = elements[elements.length - 1];
                                    const text = lastElement.innerText || lastElement.textContent;
                                    if (text && text.trim().length > 50) {
                                        return {
                                            text: text.trim(),
                                            html: lastElement.innerHTML,
                                            length: text.trim().length,
                                            source: 'backup-' + selector
                                        };
                                    }
                                }
                            } catch (e) {}
                        }
                        
                        return { text: '', html: '', length: 0, source: 'none' };
                    }
                """)
                
                response_text = response_data.get('text', '')
                response_html = response_data.get('html', '')
                source = response_data.get('source', 'unknown')
                
                # 检查是否还在生成中
                is_generating = await self.page.evaluate("""
                    () => {
                        // 检查生成指示器
                        const indicators = document.querySelectorAll(
                            '.loading, .generating, .thinking, .cursor-blink, ' +
                            '.typing-indicator, .animate-pulse, [class*="loading"], [class*="generating"], ' +
                            '.hyc-component-deepsearch-cot__think__content__item-loading'
                        );
                        // 检查停止按钮（使用标准CSS选择器）
                        const stopBtn = document.querySelector('.stop-button, .icon-stop, [class*="stop"]');
                        // 检查流式输出标记
                        const streaming = document.querySelector('.streaming, .streaming-text');
                        return indicators.length > 0 || !!stopBtn || !!streaming;
                    }
                """)
                
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if response_text and len(response_text) > len(last_response):
                    # 内容有更新
                    last_response = response_text
                    stable_count = 0
                    no_update_count = 0
                    print(f"[{self.name}] 收到新内容 (来源: {source})，长度: {len(last_response)}，已等待: {elapsed:.1f}s")
                elif response_text and response_text == last_response and len(last_response) > 10:
                    # 内容稳定
                    if not is_generating:
                        stable_count += 1
                        print(f"[{self.name}] 内容稳定 {stable_count}/{max_stable_time}s，长度: {len(last_response)}")
                        
                        # 如果已经等待了最小时间且内容稳定
                        if elapsed >= min_wait_time and stable_count >= max_stable_time:
                            print(f"[{self.name}] 回复完成，总长度: {len(last_response)}")
                            return last_response
                    else:
                        stable_count = 0
                        print(f"[{self.name}] 仍在生成中，长度: {len(last_response)}")
                        
                    # 长时间无更新
                    no_update_count += 1
                    if no_update_count > 30 and elapsed > 30:
                        print(f"[{self.name}] 长时间无更新，返回当前内容")
                        return last_response
                        
            except Exception as e:
                print(f"[{self.name}] 获取回复时出错: {e}")
                
            await asyncio.sleep(1)
            
        print(f"[{self.name}] 等待回复超时")
        return last_response if last_response else "等待回复超时"


# 全局浏览器实例
_yuanbao_browser: Optional[YuanbaoBrowser] = None


async def get_browser() -> YuanbaoBrowser:
    """获取或创建浏览器实例"""
    global _yuanbao_browser
    if _yuanbao_browser is None:
        _yuanbao_browser = YuanbaoBrowser()
        await _yuanbao_browser.start()  # 参数从配置自动读取
    return _yuanbao_browser


async def close_browser():
    """关闭浏览器实例"""
    global _yuanbao_browser
    if _yuanbao_browser:
        await _yuanbao_browser.stop()
        _yuanbao_browser = None
