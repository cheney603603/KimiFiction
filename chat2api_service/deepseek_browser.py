"""
DeepSeek 浏览器自动化模块
使用 Playwright 实现登录和聊天功能
"""

import asyncio
from typing import Optional
from playwright.async_api import Page
from base_browser import BaseAIBrowser
from config import (
    DEEPSEEK_URL, DEEPSEEK_CHAT_URL,
    DEEPSEEK_COOKIES_FILE
)
from settings_manager import get_browser_settings, get_timeout_settings


class DeepSeekBrowser(BaseAIBrowser):
    """DeepSeek 浏览器自动化类"""
    
    def __init__(self):
        super().__init__("DeepSeek", DEEPSEEK_COOKIES_FILE)
        
    def get_login_url(self) -> str:
        """获取登录页面 URL"""
        return DEEPSEEK_URL
    
    def get_chat_url(self) -> str:
        """获取聊天页面 URL"""
        return DEEPSEEK_CHAT_URL
        
    async def check_login_status(self) -> bool:
        """
        检查是否已登录
        判断标准：能否使用聊天输入框发送消息
        """
        try:
            # 检查是否有登录按钮
            login_button = await self.page.query_selector(
                'button:has-text("登录"), button:has-text("Login"), a:has-text("登录")'
            )
            if login_button:
                is_visible = await login_button.is_visible()
                if is_visible:
                    print(f"[{self.name}] 未登录状态（发现登录按钮）")
                    self._is_logged_in = False
                    return False
            
            # 检查是否有可用的聊天输入框
            input_selectors = [
                'textarea[placeholder*="发送消息"]',
                'textarea[placeholder*="Message"]',
                'textarea[placeholder*="输入"]',
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
        获取DeepSeek支持的功能
        """
        return {
            "deep_think": {
                "name": "深度思考",
                "type": "toggle",
                "default": False,
                "description": "使用DeepSeek-R1模型进行深度思考"
            },
            "web_search": {
                "name": "智能搜索",
                "type": "toggle",
                "default": False,
                "description": "开启智能搜索功能，可搜索互联网信息"
            }
        }
    
    async def set_feature(self, feature_name: str, enabled: bool = True, value: str = None):
        """
        设置DeepSeek功能
        """
        if feature_name == "deep_think":
            await self._toggle_deep_think(enabled)
        elif feature_name == "web_search":
            await self._toggle_web_search(enabled)
        else:
            print(f"[{self.name}] 不支持的功能: {feature_name}")
    
    async def _toggle_deep_think(self, enabled: bool):
        """切换深度思考(R1)开关"""
        try:
            # 使用用户提供的 class 模式来定位深度思考按钮
            # DeepSeek的深度思考按钮通常有 ds-toggle-button 类
            selectors = [
                '.ds-toggle-button:has-text("深度思考")',
                '.ds-toggle-button:has-text("R1")',
                'button:has-text("深度思考")',
                'button:has-text("R1")',
                '[class*="toggle-button"]:has-text("深度思考")',
                '[class*="toggle-button"]:has-text("R1")',
            ]
            
            btn = None
            for sel in selectors:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=2000)
                    if btn:
                        text = await btn.inner_text()
                        print(f"[{self.name}] 找到深度思考按钮: {sel}, 文本: {text[:20]}")
                        break
                except:
                    continue
            
            if not btn:
                print(f"[{self.name}] 未找到深度思考按钮，尝试通用选择器...")
                # 尝试查找所有 toggle-button 类按钮
                buttons = await self.page.query_selector_all('.ds-toggle-button')
                for btn in buttons:
                    try:
                        text = await btn.inner_text()
                        if '深度思考' in text or 'R1' in text:
                            print(f"[{self.name}] 通过通用选择器找到深度思考按钮: {text[:20]}")
                            break
                    except:
                        continue
            
            if not btn:
                print(f"[{self.name}] 未找到深度思考按钮")
                return
            
            # 检查当前状态（通过class或aria-pressed）
            class_name = await btn.get_attribute('class') or ''
            aria_pressed = await btn.get_attribute('aria-pressed')
            
            # DeepSeek的选中状态通常通过 --selected 类或 aria-pressed="true" 表示
            is_currently_enabled = (aria_pressed == "true") or ('--selected' in class_name) or ('active' in class_name.lower())
            
            print(f"[{self.name}] 深度思考当前: {'开启' if is_currently_enabled else '关闭'}, 目标: {'开启' if enabled else '关闭'}")
            
            if is_currently_enabled != enabled:
                await btn.click()
                await asyncio.sleep(0.5)
                print(f"[{self.name}] 深度思考已{'开启' if enabled else '关闭'}")
            else:
                print(f"[{self.name}] 深度思考状态无需改变")
                
        except Exception as e:
            print(f"[{self.name}] 切换深度思考失败: {e}")
    
    async def _toggle_web_search(self, enabled: bool):
        """切换智能搜索开关"""
        try:
            # 使用用户提供的 class 模式来定位智能搜索按钮
            # 智能搜索按钮也有 ds-toggle-button 类，文本为"智能搜索"
            selectors = [
                '.ds-toggle-button:has-text("智能搜索")',
                '.ds-toggle-button:has-text("搜索")',
                'button:has-text("智能搜索")',
                '[class*="toggle-button"]:has-text("智能搜索")',
                '[class*="toggle-button"]:has-text("搜索")',
            ]
            
            btn = None
            for sel in selectors:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=2000)
                    if btn:
                        text = await btn.inner_text()
                        print(f"[{self.name}] 找到智能搜索按钮: {sel}, 文本: {text[:20]}")
                        break
                except:
                    continue
            
            if not btn:
                print(f"[{self.name}] 未找到智能搜索按钮，尝试通用选择器...")
                # 尝试查找所有 toggle-button 类按钮
                buttons = await self.page.query_selector_all('.ds-toggle-button')
                for btn in buttons:
                    try:
                        text = await btn.inner_text()
                        if '智能搜索' in text or '搜索' in text:
                            print(f"[{self.name}] 通过通用选择器找到智能搜索按钮: {text[:20]}")
                            break
                    except:
                        continue
            
            if not btn:
                print(f"[{self.name}] 未找到智能搜索按钮")
                return
            
            # 检查当前状态
            class_name = await btn.get_attribute('class') or ''
            aria_pressed = await btn.get_attribute('aria-pressed')
            is_currently_enabled = (aria_pressed == "true") or ('--selected' in class_name) or ('active' in class_name.lower())
            
            print(f"[{self.name}] 智能搜索当前: {'开启' if is_currently_enabled else '关闭'}, 目标: {'开启' if enabled else '关闭'}")
            
            if is_currently_enabled != enabled:
                await btn.click()
                await asyncio.sleep(0.5)
                print(f"[{self.name}] 智能搜索已{'开启' if enabled else '关闭'}")
            else:
                print(f"[{self.name}] 智能搜索状态无需改变")
                
        except Exception as e:
            print(f"[{self.name}] 切换智能搜索失败: {e}")
    
    async def send_message(self, message: str, timeout: int = None, 
                          enable_deep_think: bool = False,
                          enable_web_search: bool = False) -> str:
        """
        发送消息并获取回复
        
        Args:
            message: 要发送的消息
            timeout: 等待回复的超时时间（秒），默认从配置读取
            enable_deep_think: 是否开启深度思考(R1)
            enable_web_search: 是否开启智能搜索
            
        Returns:
            AI 的回复文本（Markdown 格式）
        """
        if timeout is None:
            timeout = get_timeout_settings().chat_timeout
        if not self._is_logged_in:
            raise Exception("未登录，请先登录")
        
        # 设置功能开关
        await self.set_feature("deep_think", enable_deep_think)
        await self.set_feature("web_search", enable_web_search)
        
        print(f"[{self.name}] 深度思考: {'开启' if enable_deep_think else '关闭'}, 智能搜索: {'开启' if enable_web_search else '关闭'}")
        
        # 找到输入框
        input_selectors = [
            'textarea[placeholder*="发送消息"]',
            'textarea[placeholder*="Message"]',
            'textarea[placeholder*="输入"]',
            '#chat-input',
            'textarea',
            '[contenteditable="true"]',
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
        
        # 记录发送前的消息数量
        prev_message_count = await self.page.evaluate("""
            () => {
                return document.querySelectorAll('.message, .chat-message, .assistant-message, .user-message').length;
            }
        """)
        
        # 发送消息 - 按 Enter
        try:
            await input_element.press("Enter")
            print(f"[{self.name}] 已按 Enter 发送")
        except Exception as e:
            print(f"[{self.name}] 按 Enter 失败: {e}")
        
        # 等待新消息出现
        print(f"[{self.name}] 等待消息发送...")
        await asyncio.sleep(1)
        
        # 等待并获取回复
        return await self._wait_for_deepseek_response(timeout)
        
    async def _wait_for_deepseek_response(self, timeout: int = None) -> str:
        """
        等待并获取 DeepSeek 的回复
        
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
                # DeepSeek 的回复选择器 - 根据实际HTML结构调整
                response_data = await self.page.evaluate("""
                    () => {
                        // 1. 首先尝试获取最新的 AI 回复消息
                        const messages = document.querySelectorAll('.ds-message');
                        if (messages.length > 0) {
                            // 获取最后一条消息
                            const lastMessage = messages[messages.length - 1];
                            
                            // 检查是否是用户消息（通常是第一条或包含用户标识的）
                            const isUserMessage = lastMessage.querySelector('.fbb737a4') !== null ||
                                                  lastMessage.textContent.includes('深度思考');
                            
                            // 获取 Markdown 内容
                            const markdown = lastMessage.querySelector('.ds-markdown');
                            if (markdown) {
                                const text = markdown.innerText || markdown.textContent;
                                const html = markdown.innerHTML;
                                if (text && text.trim().length > 0) {
                                    return {
                                        text: text.trim(),
                                        html: html,
                                        length: text.trim().length,
                                        source: 'ds-markdown-last'
                                    };
                                }
                            }
                        }
                        
                        // 2. 尝试获取所有 .ds-markdown 元素
                        const allMarkdowns = document.querySelectorAll('.ds-markdown');
                        if (allMarkdowns.length > 0) {
                            const lastMarkdown = allMarkdowns[allMarkdowns.length - 1];
                            const text = lastMarkdown.innerText || lastMarkdown.textContent;
                            const html = lastMarkdown.innerHTML;
                            if (text && text.trim().length > 0) {
                                return {
                                    text: text.trim(),
                                    html: html,
                                    length: text.trim().length,
                                    source: 'ds-markdown-all'
                                };
                            }
                        }
                        
                        // 3. 备用选择器
                        const backupSelectors = [
                            '.ds-message:last-child',
                            '.chat-message:last-child',
                            '.assistant-message:last-child',
                            '.markdown-body:last-child',
                            '[class*="message"]:last-child',
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
                        // 检查是否有生成中的指示器
                        const indicators = document.querySelectorAll(
                            '.loading, .generating, .thinking, .cursor, .animate-pulse, ' +
                            '[class*="loading"], [class*="generating"], [class*="thinking"]'
                        );
                        // 检查停止按钮（使用标准CSS选择器）
                        const stopBtn = document.querySelector('[class*="stop"]');
                        // 检查思考中状态
                        const thinking = document.querySelector('.ds-think-content, [class*="think"]');
                        return indicators.length > 0 || !!stopBtn || !!thinking;
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
        
    def _format_as_markdown(self, html: str) -> str:
        """
        将 HTML 转换为 Markdown 格式
        这里可以根据 DeepSeek 的 HTML 结构进行优化
        """
        # 简单清理 HTML 标签，保留基本格式
        # 实际应用中可以使用 html2text 等库
        return html


# 全局浏览器实例
_deepseek_browser: Optional[DeepSeekBrowser] = None


async def get_browser() -> DeepSeekBrowser:
    """获取或创建浏览器实例"""
    global _deepseek_browser
    if _deepseek_browser is None:
        _deepseek_browser = DeepSeekBrowser()
        await _deepseek_browser.start()  # 参数从配置自动读取
    return _deepseek_browser


async def close_browser():
    """关闭浏览器实例"""
    global _deepseek_browser
    if _deepseek_browser:
        await _deepseek_browser.stop()
        _deepseek_browser = None
