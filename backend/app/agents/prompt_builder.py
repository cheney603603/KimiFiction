"""
统一提示词构建器
使用LLM融合用户输入、上一阶段结果和模板
"""
import json
from typing import Any, Dict, Optional
from loguru import logger

from app.services.llm_service import get_llm_service
from app.core.json_utils import extract_json_from_response
from app.core.llm_config_manager import LLMConfigManager


class PromptBuilder:
    """
    统一提示词构建器
    
    职责：
    1. 融合用户输入、上一阶段结果和预设模板
    2. 使用LLM智能整合信息
    3. 生成结构化的提示词
    """
    
    SYSTEM_PROMPT = """你是一位专业的提示词工程师，擅长将用户需求、历史上下文和任务模板融合为高质量的AI提示词。

你的任务是：
1. 分析用户输入的意图和需求
2. 提取上一阶段结果中的关键信息
3. 将用户需求与模板要求结合
4. 生成清晰、完整、结构化的提示词

输出必须是JSON格式，包含：
- fused_prompt: 融合后的完整提示词
- key_requirements: 关键需求列表
- context_summary: 上下文摘要
- template_adaptations: 对模板的调整说明"""

    @staticmethod
    async def build_prompt(
        phase_name: str,
        user_input: str,
        previous_results: Dict[str, Any],
        template: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        构建融合提示词
        
        Args:
            phase_name: 当前阶段名称
            user_input: 用户输入
            previous_results: 上一阶段结果
            template: 预设模板
            context: 额外上下文
            
        Returns:
            融合后的提示词数据
        """
        try:
            llm = get_llm_service()
            prompt_timeout = max(240, LLMConfigManager.get_timeout())
            
            # 构建融合请求
            prompt = f"""请为「{phase_name}」阶段构建融合提示词。

【用户输入】
{user_input if user_input else "（用户未提供特殊要求，使用默认设置）"}

【上一阶段结果】
{PromptBuilder._format_previous_results(previous_results)}

【预设模板】
{template}

【额外上下文】
{json.dumps(context, ensure_ascii=False, indent=2) if context else "无"}

请分析以上信息，生成融合后的提示词：
1. 保留用户的核心需求和创意
2. 继承上一阶段的关键设定
3. 遵循模板的结构要求
4. 确保逻辑一致性和连贯性

输出JSON格式：
{{
  "fused_prompt": "融合后的完整提示词（直接可用的文本）",
  "key_requirements": ["关键需求1", "关键需求2"],
  "context_summary": "上下文摘要（100字以内）",
  "template_adaptations": ["对模板的调整1", "调整2"],
  "user_intent": "用户意图分析"
}}"""

            messages = [
                {"role": "system", "content": PromptBuilder.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
            
            logger.info(f"[PromptBuilder] 构建提示词: phase={phase_name}")
            
            response = await llm.chat(messages, json_mode=True, timeout=prompt_timeout)
            
            # 解析响应
            try:
                result, parse_message = extract_json_from_response(response)
                if not isinstance(result, dict):
                    raise ValueError(parse_message or "PromptBuilder未返回JSON对象")
                logger.info(f"[PromptBuilder] 提示词构建成功: {result.get('context_summary', '')[:50]}")
                return {
                    "success": True,
                    "fused_prompt": result.get("fused_prompt", ""),
                    "key_requirements": result.get("key_requirements", []),
                    "context_summary": result.get("context_summary", ""),
                    "template_adaptations": result.get("template_adaptations", []),
                    "user_intent": result.get("user_intent", ""),
                    "raw_input": {
                        "user_input": user_input,
                        "previous_results": previous_results,
                        "template": template
                    }
                }
            except Exception:
                # 如果解析失败，返回原始响应作为提示词
                logger.warning(f"[PromptBuilder] JSON解析失败，使用原始响应")
                return {
                    "success": True,
                    "fused_prompt": response,
                    "key_requirements": [],
                    "context_summary": "使用原始响应",
                    "template_adaptations": [],
                    "user_intent": "",
                    "raw_input": {
                        "user_input": user_input,
                        "previous_results": previous_results,
                        "template": template
                    }
                }
                
        except Exception as e:
            logger.error(f"[PromptBuilder] 构建提示词失败: {e}")
            # 失败时返回基础融合
            return {
                "success": False,
                "error": str(e),
                "fused_prompt": PromptBuilder._basic_fusion(user_input, previous_results, template),
                "key_requirements": [],
                "context_summary": "基础融合（构建器失败）",
                "template_adaptations": [],
                "user_intent": ""
            }
    
    @staticmethod
    def _format_previous_results(results: Dict[str, Any]) -> str:
        """格式化上一阶段结果"""
        if not results:
            return "（无上一阶段结果）"
        
        formatted = []
        for key, value in results.items():
            if value:
                # 截断过长的内容
                value_str = json.dumps(value, ensure_ascii=False, indent=2)
                if len(value_str) > 1000:
                    value_str = value_str[:1000] + "...（已截断）"
                formatted.append(f"【{key}】\n{value_str}")
        
        return "\n\n".join(formatted) if formatted else "（无有效数据）"
    
    @staticmethod
    def _basic_fusion(user_input: str, previous_results: Dict[str, Any], template: str) -> str:
        """基础融合（当LLM构建失败时使用）"""
        parts = []
        
        if previous_results:
            parts.append("【前文设定】\n" + json.dumps(previous_results, ensure_ascii=False, indent=2)[:2000])
        
        if user_input:
            parts.append(f"【用户要求】\n{user_input}")
        
        parts.append(f"【任务要求】\n{template}")
        
        return "\n\n".join(parts)


# 单例实例
prompt_builder = PromptBuilder()
