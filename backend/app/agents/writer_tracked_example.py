"""
章节撰写智能体 - 集成状态追踪的示例

展示如何将 ChapterWriterAgent 修改为使用 TrackedLLMService
实现每次LLM调用自动记录快照
"""
import json
from typing import Any, Dict
from loguru import logger

from app.agents.base import BaseAgent
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class ChapterWriterAgentTracked(BaseAgent):
    """
    章节撰写智能体（带状态追踪）
    
    使用方式：
        agent = ChapterWriterAgentTracked(novel_id=1)
        result = await agent.process(context)
    """

    SYSTEM_PROMPT = """你是一位专业的小说写手，擅长撰写引人入胜的章节内容。

请严格根据以下信息撰写章节：
- 【上下文背景】：包括世界观设定、前文摘要、进行中的剧情线、未解伏笔
- 【章节细纲】：本章的具体情节走向、关键事件、场景安排
- 【主要人物角色简介】：出场角色的性格、外貌、背景、目标、说话风格等

写作要求：
1. 情节必须严格符合章节细纲，不偏离、不跳脱
2. 人物性格必须前后一致，对话、行为要符合人物设定
3. 环境描写要服务于情节和氛围
4. 对话自然流畅，符合人物身份和情境
5. 每章字数控制在{target_words}字左右
6. 章节结构完整：开头吸引人，中间有发展，结尾留悬念或推进高潮
7. 注意呼应前文的伏笔和剧情线，保持故事连贯性

写作风格：{writing_style}
环境描写级别：{env_description_level}
对话占比：约{dialogue_ratio_pct}%

特别注意事项：{notes}

请直接输出章节正文，不需要写"第X章"标题，直接开始正文。
"""

    def __init__(self, novel_id: int):
        """
        初始化
        
        Args:
            novel_id: 小说ID，用于状态追踪
        """
        super().__init__("chapter_writer", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        
        # 使用带追踪的LLM服务
        self.llm = TrackedLLMService(
            provider=LLMProvider.DEEPSEEK,  # 或从配置读取
            model="deepseek-chat",  # 或从配置读取
            novel_id=novel_id,
            agent_name="chapter_writer",
            auto_track=True  # 启用自动追踪
        )
        
        # 设置全局上下文（用于其他可能的手动追踪）
        set_novel_context(novel_id)
        
        logger.info(f"[ChapterWriterTracked] 初始化完成，novel_id={novel_id}")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        撰写章节（带状态追踪）
        
        每次LLM调用都会自动创建快照，可在前端查看和回滚
        """
        try:
            novel_id = context.get("novel_id", self.novel_id)
            chapter_number = context.get("chapter_number", 1)
            
            # 更新上下文
            set_novel_context(novel_id, chapter_number)
            
            # ... 原有的参数提取逻辑 ...
            outline = context.get("outline", {})
            characters = context.get("characters", [])
            target_words = context.get("target_words", 4000)
            writing_style = context.get("writing_style", "叙事流畅，情节紧凑")
            
            # 构建提示词（简化示例）
            system_prompt = self.SYSTEM_PROMPT.format(
                target_words=target_words,
                writing_style=writing_style,
                env_description_level="适度描写",
                dialogue_ratio_pct=30,
                notes=context.get("notes", "")
            )
            
            user_message = self._build_user_message(context)
            
            # 使用追踪的LLM服务调用
            # 会自动：
            # 1. 创建调用前快照
            # 2. 记录输入消息
            # 3. 执行LLM调用
            # 4. 记录输出结果
            # 5. 保存完整调用记录
            logger.info(f"[ChapterWriterTracked] 开始撰写第{chapter_number}章")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 这里会自动创建快照
            content = await self.llm.chat(
                messages,
                description=f"撰写第{chapter_number}章"
            )
            
            # 处理结果
            word_count = len(content.replace(" ", "").replace("\n", ""))
            
            logger.info(f"[ChapterWriterTracked] 第{chapter_number}章完成，{word_count}字")
            
            return {
                "success": True,
                "chapter_number": chapter_number,
                "content": content,
                "word_count": word_count,
            }
            
        except Exception as e:
            logger.error(f"[ChapterWriterTracked] 撰写失败: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def _build_user_message(self, context: Dict[str, Any]) -> str:
        """构建用户消息"""
        chapter_number = context.get("chapter_number", 1)
        outline = context.get("outline", {})
        characters = context.get("characters", [])
        
        outline_text = json.dumps(outline, ensure_ascii=False) if isinstance(outline, dict) else str(outline)
        characters_text = json.dumps(characters, ensure_ascii=False, indent=2) if characters else ""
        
        return f"""请撰写小说第{chapter_number}章。

## 章节细纲
{outline_text}

## 主要人物
{characters_text}

请开始撰写章节正文："""


# ============ 使用示例 ============

async def example_usage():
    """使用示例"""
    from app.core.llm_call_tracker import create_manual_snapshot, rollback_to_snapshot
    
    novel_id = 1
    
    # 1. 在重要操作前创建手动快照
    snapshot_id = await create_manual_snapshot(
        novel_id=novel_id,
        description="开始撰写第10章前"
    )
    print(f"手动快照创建: {snapshot_id}")
    
    # 2. 使用追踪的Agent撰写章节
    agent = ChapterWriterAgentTracked(novel_id=novel_id)
    
    context = {
        "novel_id": novel_id,
        "chapter_number": 10,
        "outline": {"title": "突破", "summary": "主角突破境界..."},
        "characters": [{"name": "主角", "personality": "坚毅"}],
        "target_words": 3000,
    }
    
    result = await agent.process(context)
    
    if result["success"]:
        print(f"章节撰写成功: {result['word_count']}字")
        
        # 3. 如果不满意，可以回滚到之前的状态
        # rollback_result = await rollback_to_snapshot(novel_id, snapshot_id)
        # print(f"回滚结果: {rollback_result}")
    else:
        print(f"章节撰写失败: {result['error']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
