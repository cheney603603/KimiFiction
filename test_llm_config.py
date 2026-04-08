#!/usr/bin/env python3
"""
测试LLM服务配置
验证Chat2API连接和Agent调用
"""
import asyncio
import sys
import os

# 清理可能导致冲突的环境变量
for key in list(os.environ.keys()):
    if 'DEBUG' in key or 'PYTHON' in key:
        os.environ.pop(key, None)

# 设置后端环境
os.environ['PYTHONPATH'] = os.path.join(os.path.dirname(__file__), 'backend')

# 添加项目路径
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from app.core.llm_config_manager import LLMConfigManager
from app.services.llm_service import LLMService, LLMProvider, get_llm_service
from app.agents.analyzer import GenreAnalyzerAgent
from loguru import logger

async def test_config():
    """测试配置读取"""
    logger.info("=== 测试1: 读取配置 ===")
    config = LLMConfigManager.get_config()
    logger.info(f"Provider: {config.get('provider')}")
    logger.info(f"Base URL: {config.get('base_url')}")
    logger.info(f"Model: {config.get('model')}")
    logger.info(f"Response Time: {config.get('response_time')}")
    return config

async def test_llm_service():
    """测试LLM服务初始化"""
    logger.info("\n=== 测试2: LLM服务初始化 ===")
    service = get_llm_service()
    logger.info(f"Provider: {service.provider.value}")
    logger.info(f"Model: {service.model}")
    logger.info(f"Chat2API Base URL: {service.chat2api_base_url}")

    # 测试健康检查
    logger.info("\n=== 测试3: 健康检查 ===")
    status = await service.check_chat2api_status()
    logger.info(f"Status: {status}")

    return service

async def test_agent():
    """测试Agent调用"""
    logger.info("\n=== 测试4: Agent调用 ===")
    agent = GenreAnalyzerAgent()
    logger.info(f"Agent初始化: {agent.name}")

    try:
        result = await agent.process({
            "user_input": "我想写一个修仙小说"
        })
        logger.info(f"Agent调用结果: {result.get('success')}")
        if result.get("success"):
            analysis = result.get("analysis", {})
            logger.info(f"类型: {analysis.get('suggested_genre')}")
        else:
            logger.error(f"Agent调用失败: {result.get('error')}")
    except Exception as e:
        logger.error(f"Agent调用异常: {e}")
        import traceback
        traceback.print_exc()

async def test_direct_llm():
    """测试直接LLM调用"""
    logger.info("\n=== 测试5: 直接LLM调用 ===")
    service = get_llm_service()

    try:
        messages = [
            {"role": "system", "content": "你是一个测试助手，请简短回复。"},
            {"role": "user", "content": "你好，请回复'测试成功'。"}
        ]
        response = await service.chat(messages, timeout=30)
        logger.info(f"LLM响应: {response[:100]}")
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    logger.info("开始LLM服务测试...")

    # 测试配置
    config = await test_config()

    # 测试LLM服务
    service = await test_llm_service()

    # 测试直接LLM调用（可选，如果Kimi已登录）
    # await test_direct_llm()

    # 测试Agent调用（可选，如果Kimi已登录）
    # await test_agent()

    logger.info("\n=== 测试完成 ===")
    logger.info("如果Chat2API未登录，请:")
    logger.info("1. 访问 http://localhost:8088")
    logger.info("2. 点击对应AI提供商的登录按钮")
    logger.info("3. 完成登录后，重新运行此测试")

if __name__ == "__main__":
    asyncio.run(main())
