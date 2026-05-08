"""
记忆管理智能体
管理小说记忆和上下文
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class MemoryManagerAgent(BaseAgent):
    """
    记忆管理智能体
    
    管理小说的长期记忆，包括：
    - 前文摘要
    - 角色状态
    - 剧情进度
    - 伏笔追踪
    """
    
    SYSTEM_PROMPT = """你是一位记忆管理员，负责整理和维护小说的上下文信息。

你的任务是：
1. 提取和更新前文摘要
2. 追踪角色状态变化
3. 记录剧情进度
4. 管理伏笔和回收

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("MemoryManager", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="memory_manager",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """管理记忆"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="memory_manager",
                    auto_track=True
                )
        
        operation = context.get("operation", "summarize")
        content = context.get("content", "")
        
        if operation == "summarize":
            prompt = f"""请总结以下内容：

{content[:8000]}

请输出JSON格式：
{{
  "summary": "摘要内容",
  "key_events": ["关键事件1"],
  "character_changes": [{{"character": "角色名", "change": "变化"}}],
  "new_mysteries": ["新伏笔"],
  "resolved_mysteries": ["回收的伏笔"]
}}"""
        else:
            prompt = f"""请处理记忆管理任务：

操作：{operation}
内容：{content[:5000]}

请输出JSON格式：
{{
  "result": "处理结果"
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "memory_result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
