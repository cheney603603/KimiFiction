"""
AI Chat 服务配置
支持 Kimi、DeepSeek、豆包、腾讯元宝
"""

# ==================== AI 服务 URL 配置 ====================

# Kimi 网站配置
KIMI_URL = "https://www.kimi.com/"
KIMI_CHAT_URL = "https://www.kimi.com/chat"

# DeepSeek 网站配置
DEEPSEEK_URL = "https://chat.deepseek.com/"
DEEPSEEK_CHAT_URL = "https://chat.deepseek.com/"

# 腾讯元宝 AI 网站配置
YUANBAO_URL = "https://yuanbao.tencent.com/chat"
YUANBAO_CHAT_URL = "https://yuanbao.tencent.com/chat"

# ==================== Playwright 配置 ====================

HEADLESS = False  # 是否无头模式（False方便调试，True用于生产）
SLOW_MO = 100  # 操作延迟（毫秒）

# ==================== API 配置 ====================
import os

API_HOST = os.getenv("CHAT2API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("CHAT2API_PORT", "8088"))

# ==================== Cookies 文件配置 ====================

COOKIES_FILE = "kimi_cookies.json"
DEEPSEEK_COOKIES_FILE = "deepseek_cookies.json"
YUANBAO_COOKIES_FILE = "yuanbao_cookies.json"

# ==================== 支持的 AI 提供商 ====================

AI_PROVIDERS = {
    "kimi": {
        "name": "Kimi",
        "display_name": "Kimi AI",
        "description": "月之暗面出品的大模型助手",
        "url": KIMI_URL,
        "cookies_file": COOKIES_FILE,
    },
    "deepseek": {
        "name": "DeepSeek",
        "display_name": "DeepSeek AI",
        "description": "深度求索出品的大模型助手",
        "url": DEEPSEEK_URL,
        "cookies_file": DEEPSEEK_COOKIES_FILE,
    },
    "yuanbao": {
        "name": "Yuanbao",
        "display_name": "腾讯元宝",
        "description": "腾讯出品的 AI 助手",
        "url": YUANBAO_URL,
        "cookies_file": YUANBAO_COOKIES_FILE,
    },
}

# 默认 AI 提供商
DEFAULT_AI_PROVIDER = "kimi"
