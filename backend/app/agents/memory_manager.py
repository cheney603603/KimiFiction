"""
记忆管理智能体
管理长文本记忆和RAG检索
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


class MemoryManagerAgent(BaseAgent):
    """
    记忆管理智能体
    
    负责：
    - 从章节中提取关键记忆节点
    - 生成分层摘要
    - 管理向量存储
    - 检索相关记忆
    """
    
    SYSTEM_PROMPT = """你是一位专业的内容分析师，擅长从文本中提取关键信息。

你的任务是：
1. 从章节内容中提取关键事件、人物关系、设定信息
2. 生成简洁但信息完整的摘要
3. 识别重要的伏笔和未解之谜
4. 标记需要长期记忆的信息

输出JSON格式：
{{
  "summary": "章节摘要（200字以内）",
  "key_events": ["事件1", "事件2"],
  "character_developments": [
    {{"character": "角色名", "change": "变化描述"}}
  ],
  "world_building": ["设定1", "设定2"],
  "mysteries": ["未解之谜1"],
  "foreshadowing": ["伏笔1"],
  "important_score": 0-1  // 本章重要性评分
}}"""
    
    def __init__(self):
        super().__init__("MemoryManager", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理章节内容，提取记忆
        
        Args:
            context: 包含 chapter_content, chapter_number, characters 等
            
        Returns:
            提取的记忆信息
        """
        chapter_content = context.get("chapter_content", "")
        chapter_number = context.get("chapter_number", 0)
        characters = context.get("characters", [])
        
        self.log_action("开始提取记忆", {"chapter": chapter_number})
        
        prompt = f"""请分析第{chapter_number}章，提取关键信息：

章节内容：
{chapter_content[:3000]}...

出场角色：{', '.join([c.get('name', '未知') for c in characters])}

请输出JSON格式的分析结果。"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.3,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            
            # 使用通用JSON解析工具
            result, parse_message = extract_json_from_response(response)
            
            if result is None:
                self.log_action("JSON解析失败", {"error": parse_message})
                return {
                    "success": False,
                    "error": f"JSON解析失败: {parse_message}",
                    "chapter_number": chapter_number
                }
            
            self.log_action("记忆提取完成", {
                "chapter": chapter_number,
                "key_events": len(result.get("key_events", []))
            })
            
            return {
                "success": True,
                "chapter_number": chapter_number,
                "summary": result.get("summary", ""),
                "key_events": result.get("key_events", []),
                "character_developments": result.get("character_developments", []),
                "world_building": result.get("world_building", []),
                "mysteries": result.get("mysteries", []),
                "foreshadowing": result.get("foreshadowing", []),
                "importance_score": result.get("important_score", 0.5),
                "_react_trace": react_result["trace"],
            }
            
        except Exception as e:
            self.log_action("记忆提取失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "chapter_number": chapter_number
            }
    
    async def generate_summary(
        self,
        chapters: List[Dict],
        summary_type: str = "short"
    ) -> str:
        """
        生成多章摘要
        
        Args:
            chapters: 章节列表
            summary_type: short(短摘要) / medium(中等) / long(详细)
            
        Returns:
            摘要文本
        """
        # 构建章节信息
        chapters_text = "\n\n".join([
            f"第{ch.get('chapter_number')}章 {ch.get('title')}:\n{ch.get('summary', '无摘要')}"
            for ch in chapters
        ])
        
        length_guide = {
            "short": "100字以内",
            "medium": "300字以内",
            "long": "800字以内"
        }
        
        prompt = f"""请为以下{len(chapters)}章生成{length_guide.get(summary_type, '300字以内')}的摘要：

{chapters_text}

要求：
1. 突出主要剧情发展
2. 包含关键转折点
3. 提及重要角色变化
4. 保持时间顺序

请直接输出摘要文本。"""
        
        react_result = await self.run_react_loop(
            prompt,
            context={"agent_loop_steps": 2},
            temperature=0.4,
            output_format="text",
        )
        response = react_result["final_text"] or react_result["raw_response"]
        return response.strip()
    
    async def identify_plot_holes(
        self,
        recent_chapters: List[Dict],
        all_memory_nodes: List[Dict]
    ) -> List[Dict]:
        """
        识别潜在的剧情漏洞
        
        Args:
            recent_chapters: 最近章节
            all_memory_nodes: 所有记忆节点
            
        Returns:
            潜在问题列表
        """
        recent_summary = "\n".join([
            f"第{ch.get('chapter_number')}章: {ch.get('summary', '')}"
            for ch in recent_chapters[-3:]
        ])
        
        important_memories = [
            m for m in all_memory_nodes
            if m.get("importance_score", 0) > 0.7
        ][:10]
        
        memories_text = "\n".join([
            f"- [{m.get('node_type')}] {m.get('title')}: {m.get('content', '')[:100]}"
            for m in important_memories
        ])
        
        prompt = f"""请检查以下剧情是否存在漏洞或需要关注的问题：

最近章节：
{recent_summary}

重要记忆节点：
{memories_text}

请识别：
1. 未回收的伏笔
2. 可能被遗忘的设定
3. 逻辑矛盾
4. 角色行为异常

输出JSON格式的问题列表。"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context={"agent_loop_steps": 2},
                temperature=0.3,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            
            # 使用通用JSON解析工具
            result, _ = extract_json_from_response(response)
            if result:
                return result.get("issues", [])
            return []
        except:
            return []
