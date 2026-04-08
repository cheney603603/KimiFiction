"""
AI Chat API 客户端示例
支持 Kimi、DeepSeek、腾讯元宝
演示如何通过代码调用 AI Chat API
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def get_providers():
    """获取支持的 AI 提供商列表"""
    response = requests.get(f"{BASE_URL}/api/providers")
    return response.json()


def check_status(provider: str = "kimi"):
    """
    检查指定 AI 的登录状态
    
    Args:
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    response = requests.get(f"{BASE_URL}/api/status/{provider}")
    return response.json()


def check_all_status():
    """检查所有 AI 的登录状态"""
    response = requests.get(f"{BASE_URL}/api/status")
    return response.json()


def get_features(provider: str = "kimi") -> dict:
    """
    获取指定 AI 支持的功能列表
    
    Args:
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    response = requests.get(f"{BASE_URL}/api/{provider}/features")
    return response.json()


def send_message(message: str, provider: str = "kimi", timeout: int = 120,
                enable_web_search: bool = False,
                enable_deep_think: bool = False,
                enable_deep_research: bool = False,
                model: str = None) -> dict:
    """
    发送消息到指定 AI
    
    Args:
        message: 要发送的消息
        provider: AI 提供商 (kimi/deepseek/yuanbao)
        timeout: 等待回复的超时时间（秒）
        enable_web_search: 是否开启联网搜索（元宝、DeepSeek支持）
        enable_deep_think: 是否开启深度思考（元宝、DeepSeek支持）
        enable_deep_research: 是否开启深度研究
        model: 模型选择（Kimi支持: k2.5 / k2.5-reasoning）
        
    Returns:
        包含回复的字典
    """
    payload = {"message": message, "timeout": timeout}
    
    # 根据提供商添加功能参数
    if provider == "yuanbao":
        payload["enable_web_search"] = enable_web_search
        payload["enable_deep_think"] = enable_deep_think
    elif provider == "deepseek":
        payload["enable_deep_think"] = enable_deep_think
    elif provider == "doubao":
        payload["enable_deep_research"] = enable_deep_research
        payload["enable_web_search"] = enable_web_search
    elif provider == "kimi" and model:
        payload["model"] = model
    
    response = requests.post(
        f"{BASE_URL}/api/{provider}/chat",
        json=payload
    )
    return response.json()


def start_login(provider: str = "kimi") -> dict:
    """
    启动指定 AI 的登录流程
    
    Args:
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    response = requests.post(f"{BASE_URL}/api/{provider}/login/start")
    return response.json()


def confirm_login(provider: str = "kimi") -> dict:
    """
    确认指定 AI 的登录完成
    
    Args:
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    response = requests.post(f"{BASE_URL}/api/{provider}/login/confirm")
    return response.json()


def restart_browser(provider: str = "kimi") -> dict:
    """
    重启指定 AI 的浏览器
    
    Args:
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    response = requests.post(f"{BASE_URL}/api/{provider}/browser/restart")
    return response.json()


def print_providers():
    """打印所有支持的 AI 提供商"""
    print("\n" + "=" * 60)
    print("支持的 AI 提供商")
    print("=" * 60)
    
    data = get_providers()
    providers = data.get("providers", {})
    default = data.get("default", "kimi")
    
    for key, info in providers.items():
        marker = " [默认]" if key == default else ""
        print(f"\n  {key}: {info['display_name']}{marker}")
        print(f"       {info['description']}")
    
    print("\n" + "=" * 60)


def print_features(provider: str = "kimi"):
    """打印指定 AI 支持的功能"""
    print("\n" + "=" * 60)
    print(f"{provider.upper()} 支持的功能")
    print("=" * 60)
    
    data = get_features(provider)
    features = data.get("features", {})
    
    if not features:
        print(f"\n  {provider} 暂不支持功能开关")
    else:
        for key, feature in features.items():
            print(f"\n  • {feature['name']} ({key})")
            print(f"    类型: {feature['type']}")
            print(f"    默认: {feature['default']}")
            if feature.get('description'):
                print(f"    说明: {feature['description']}")
            if feature.get('options'):
                print(f"    选项: {', '.join(feature['options'])}")
    
    print("\n" + "=" * 60)


def print_all_status():
    """打印所有 AI 的登录状态"""
    print("\n" + "=" * 60)
    print("AI 登录状态")
    print("=" * 60)
    
    data = check_all_status()
    for provider, status in data.items():
        login_status = "✅ 已登录" if status['is_logged_in'] else "❌ 未登录"
        print(f"\n  {provider}: {login_status}")
        print(f"       消息: {status['message']}")
    
    print("\n" + "=" * 60)


def chat_loop(provider: str = "kimi"):
    """
    交互式聊天循环
    
    Args:
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    print("\n" + "=" * 60)
    print(f"AI Chat 客户端 - {provider.upper()}")
    print("=" * 60)
    
    # 检查状态
    status = check_status(provider)
    print(f"\n登录状态: {'已登录' if status['is_logged_in'] else '未登录'}")
    print(f"消息: {status['message']}\n")
    
    if not status['is_logged_in']:
        print("请先完成登录:")
        print(f"  1. 打开 http://localhost:8000")
        print(f"  2. 选择 '{provider}' AI 助手")
        print(f"  3. 点击'打开登录页面'按钮")
        print(f"  4. 在浏览器中完成登录")
        print(f"  5. 点击'确认已登录'按钮")
        print(f"  6. 然后返回这里开始聊天\n")
        return
    
    print("开始聊天（输入 'quit' 或 'exit' 退出，输入 'switch' 切换 AI）\n")
    
    while True:
        user_input = input("你: ").strip()
        
        if not user_input:
            continue
            
        if user_input.lower() in ['quit', 'exit', '退出']:
            print("再见！")
            break
            
        if user_input.lower() in ['switch', '切换']:
            print_providers()
            new_provider = input("请选择 AI (kimi/deepseek/yuanbao): ").strip()
            if new_provider in ['kimi', 'deepseek', 'yuanbao']:
                chat_loop(new_provider)
                return
            else:
                print("无效的 AI 提供商")
                continue
            
        try:
            print(f"{provider.upper()}: 思考中...")
            result = send_message(user_input, provider=provider)
            
            if result.get('success'):
                print(f"{provider.upper()}: {result['data']}\n")
            else:
                print(f"错误: {result.get('message', '未知错误')}\n")
                
        except Exception as e:
            print(f"请求失败: {e}\n")


def simple_chat(message: str, provider: str = "kimi"):
    """
    单次聊天示例
    
    Args:
        message: 要发送的消息
        provider: AI 提供商 (kimi/deepseek/yuanbao)
    """
    print(f"\n[{provider.upper()}] 发送: {message}")
    result = send_message(message, provider=provider)
    if result.get('success'):
        print(f"[{provider.upper()}] 回复: {result['data']}")
    else:
        print(f"[{provider.upper()}] 失败: {result.get('message')}")


def multi_ai_chat(message: str):
    """
    同时向所有 AI 发送相同的消息
    
    Args:
        message: 要发送的消息
    """
    print("\n" + "=" * 60)
    print("多 AI 对比模式")
    print("=" * 60)
    
    data = get_providers()
    providers = list(data.get("providers", {}).keys())
    
    results = {}
    for provider in providers:
        print(f"\n[{provider.upper()}] 发送中...")
        result = send_message(message, provider=provider)
        results[provider] = result
    
    print("\n" + "=" * 60)
    print("回复对比")
    print("=" * 60)
    
    for provider, result in results.items():
        print(f"\n{'─' * 60}")
        print(f"【{provider.upper()}】")
        print(f"{'─' * 60}")
        if result.get('success'):
            print(result['data'])
        else:
            print(f"失败: {result.get('message')}")


def advanced_chat_example():
    """高级功能使用示例"""
    print("\n" + "=" * 60)
    print("功能开关使用示例")
    print("=" * 60)
    
    # 示例1: 腾讯元宝 - 开启联网搜索和深度思考
    print("\n【示例1】腾讯元宝 - 联网搜索 + 深度思考")
    message = "今天有什么重要新闻？"
    print(f"消息: {message}")
    result = send_message(
        message, 
        provider="yuanbao",
        enable_web_search=True,
        enable_deep_think=True
    )
    if result.get('success'):
        print(f"回复: {result['data'][:200]}...")
    else:
        print(f"失败: {result.get('message')}")
    
    # 示例2: Kimi - 使用思考模型
    print("\n【示例2】Kimi - K2.5 思考模型")
    message = "解释量子纠缠"
    print(f"消息: {message}")
    result = send_message(
        message,
        provider="kimi",
        model="k2.5-reasoning"
    )
    if result.get('success'):
        print(f"回复: {result['data'][:200]}...")
    else:
        print(f"失败: {result.get('message')}")
    
    # 示例3: DeepSeek - 深度思考
    print("\n【示例3】DeepSeek - 深度思考(R1)")
    message = "分析二分查找算法的时间复杂度"
    print(f"消息: {message}")
    result = send_message(
        message,
        provider="deepseek",
        enable_deep_think=True
    )
    if result.get('success'):
        print(f"回复: {result['data'][:200]}...")
    else:
        print(f"失败: {result.get('message')}")
    
    print("\n" + "=" * 60)


def main_menu():
    """主菜单"""
    while True:
        print("\n" + "=" * 60)
        print("AI Chat API 客户端")
        print("=" * 60)
        print("\n1. 查看支持的 AI 提供商")
        print("2. 查看所有 AI 登录状态")
        print("3. 开始聊天 (Kimi)")
        print("4. 开始聊天 (DeepSeek)")
        print("5. 开始聊天 (豆包)")
        print("6. 开始聊天 (腾讯元宝)")
        print("7. 多 AI 对比模式")
        print("8. 简单测试（向所有 AI 发送测试消息）")
        print("9. 查看 AI 功能列表")
        print("10. 功能开关使用示例")
        print("0. 退出")
        
        choice = input("\n请选择: ").strip()
        
        if choice == "0":
            print("再见！")
            break
        elif choice == "1":
            print_providers()
        elif choice == "2":
            print_all_status()
        elif choice == "3":
            chat_loop("kimi")
        elif choice == "4":
            chat_loop("deepseek")

        elif choice == "6":
            chat_loop("yuanbao")
        elif choice == "7":
            message = input("请输入要对比的消息: ")
            if message:
                multi_ai_chat(message)
        elif choice == "8":
            test_message = "你好！请简单介绍一下你自己。"
            print(f"\n测试消息: {test_message}")
            simple_chat(test_message, "kimi")
            simple_chat(test_message, "deepseek")
            simple_chat(test_message, "doubao")
            simple_chat(test_message, "yuanbao")
        elif choice == "9":
            print("\n支持的 AI 提供商:")
            print("  1. kimi (Kimi)")
            print("  2. deepseek (DeepSeek)")

            print("  4. yuanbao (腾讯元宝)")
            provider_choice = input("\n请选择 AI (1-4 或直接输入名称): ").strip()
            provider_map = {"1": "kimi", "2": "deepseek", "3": "yuanbao"}
            provider = provider_map.get(provider_choice, provider_choice)
            if provider in ["kimi", "deepseek", "yuanbao"]:
                print_features(provider)
            else:
                print("无效的选择")
        elif choice == "10":
            advanced_chat_example()
        else:
            print("无效的选择")


if __name__ == "__main__":
    main_menu()
