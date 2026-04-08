"""
章节撰写智能体
支持真正的LLM章节生成 + RAG上下文召回 + Writer-Reader RL对抗
"""
import json
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from app.agents.base import BaseAgent


class ChapterWriterAgent(BaseAgent):
    """
    章节撰写智能体
    真正调用LLM生成章节内容
    """

    SYSTEM_PROMPT = """你是一位专业的小说写手，擅长撰写引人入胜的章节内容。

请严格根据以下信息撰写章节：
- 【上下文背景】：包括世界观设定、前文摘要、进行中的剧情线、未解伏笔
- 【章节细纲】：本章的具体情节走向、关键事件、场景安排
- 【主要人物角色简介】：出场角色的性格、外貌、背景、目标、说话风格等

写作要求：
1. 情节必须严格符合章节细纲，不偏离、不跳脱
2. 人物性格必须前后一致，对话、行为要符合人物设定
3. 环境描写要服务于情节和氛围（minimal=简洁暗示，normal=适度描写，rich=丰富细腻）
4. 对话自然流畅，符合人物身份和情境
5. 每章字数控制在{target_words}字左右
6. 章节结构完整：开头吸引人，中间有发展，结尾留悬念或推进高潮
7. 注意呼应前文的伏笔和剧情线，保持故事连贯性

写作风格：{writing_style}
环境描写级别：{env_description_level}（minimal=简洁暗示，normal=适度描写，rich=丰富细腻）
对话占比：约{dialogue_ratio_pct}%（控制对话不要过多或过少）

特别注意事项：{notes}

请直接输出章节正文，不需要写"第X章"标题，直接开始正文。
"""

    def __init__(self):
        super().__init__("chapter_writer", self.SYSTEM_PROMPT)
        # 不在初始化时获取LLM服务，而是在每次调用时动态获取
        self._llm = None

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        撰写章节
        
        Args:
            context: 包含 novel_id, chapter_number, outline, context, characters,
                     target_words, writing_style, env_description_level, 
                     dialogue_ratio, notes 等信息
        """
        try:
            novel_id = context.get("novel_id")
            chapter_number = context.get("chapter_number", 1)
            outline = context.get("outline", {})
            chapter_context = context.get("context", {})
            characters = context.get("characters", [])
            target_words = context.get("target_words", 4000)
            reader_feedback = context.get("reader_feedback", {})
            previous_draft = context.get("previous_draft", "")
            rewrite_round = context.get("rewrite_round", 1)
            
            # 写作参数
            writing_style = context.get("writing_style", "叙事流畅，情节紧凑")
            env_level = context.get("env_description_level", "normal")
            dialogue_ratio = context.get("dialogue_ratio", 0.3)
            notes = context.get("notes", "无特殊要求")
            
            # 映射环境描写级别
            env_map = {
                "minimal": "简洁暗示",
                "normal": "适度描写", 
                "rich": "丰富细腻"
            }
            env_desc = env_map.get(env_level, "适度描写")
            
            dialogue_pct = int(dialogue_ratio * 100)
            
            # 构建人物信息
            characters_info = ""
            if characters:
                chars_list = []
                for char in characters[:5]:  # 最多5个主要角色
                    name = char.get("name", "未知")
                    role = char.get("role_type", char.get("role", ""))
                    
                    # 优先从 profile 获取详细信息
                    profile = char.get("profile", {})
                    if isinstance(profile, dict):
                        personality = profile.get("personality", profile.get("性格", ""))
                        dialogue_style = profile.get("dialogue_style", profile.get("说话风格", ""))
                        appearance = profile.get("appearance", profile.get("外貌描述", ""))
                        background = profile.get("background", profile.get("背景", ""))
                        goals = profile.get("goals", profile.get("目标", []))
                        fears = profile.get("fears", profile.get("恐惧", []))
                        skills = profile.get("skills", profile.get("技能", []))
                        mbti = profile.get("mbti", profile.get("mbti类型", ""))
                        relationships = profile.get("relationships", profile.get("人际关系", {}))
                    else:
                        personality = ""
                        dialogue_style = ""
                        appearance = ""
                        background = ""
                        goals = []
                        fears = []
                        skills = []
                        mbti = ""
                        relationships = {}
                    
                    # 兼容旧格式：如果 profile 中没有，从 char 顶层取
                    if not personality:
                        personality = char.get("personality", "")
                    if not dialogue_style:
                        dialogue_style = char.get("dialogue_style", "")
                    if not appearance:
                        appearance = char.get("appearance", "")
                    if not background:
                        background = char.get("background", "")
                    
                    info = f"【{name}】({role})"
                    if personality:
                        info += f"\n  性格：{personality}"
                    if mbti:
                        info += f"\n  MBTI：{mbti}"
                    if appearance:
                        info += f"\n  外貌：{appearance}"
                    if background:
                        info += f"\n  背景：{background}"
                    if goals:
                        info += f"\n  目标：{', '.join(goals) if isinstance(goals, list) else goals}"
                    if fears:
                        info += f"\n  恐惧：{', '.join(fears) if isinstance(fears, list) else fears}"
                    if skills:
                        info += f"\n  技能：{', '.join(skills) if isinstance(skills, list) else skills}"
                    if dialogue_style:
                        info += f"\n  说话风格：{dialogue_style}"
                    if relationships:
                        info += f"\n  人际关系：{json.dumps(relationships, ensure_ascii=False)}"
                    chars_list.append(info)
                characters_info = "\n\n".join(chars_list)
            
            # 构建章节大纲
            outline_content = ""
            if isinstance(outline, dict):
                outline_title = outline.get("title", outline.get("outline_title", f"第{chapter_number}章"))
                outline_summary = outline.get("summary", outline.get("content", ""))
                outline_content = f"章节标题：{outline_title}\n章节大纲：{outline_summary}"
                if outline.get("scenes"):
                    outline_content += f"\n场景设定：{json.dumps(outline.get('scenes'), ensure_ascii=False)}"
            elif outline:
                outline_content = str(outline)
            
            # 构建前文摘要（用于衔接）
            context_parts = []
            if chapter_context:
                prev_chap = chapter_context.get("previous_chapter_summary", "")
                world_info = chapter_context.get("world_setting", "")
                ongoing_plots = chapter_context.get("ongoing_plots", [])
                char_status = chapter_context.get("character_status", [])
                unresolved_mysteries = chapter_context.get("unresolved_mysteries", [])
                foreshadowing = chapter_context.get("foreshadowing", [])
                recent_events = chapter_context.get("recent_events", [])
                
                if prev_chap:
                    context_parts.append(f"前情提要：{prev_chap}")
                if world_info:
                    context_parts.append(f"世界观背景：{world_info}")
                if ongoing_plots:
                    context_parts.append(f"进行中的剧情线：{json.dumps(ongoing_plots, ensure_ascii=False)}")
                if unresolved_mysteries:
                    context_parts.append(f"未解伏笔：{'；'.join(unresolved_mysteries[:3])}")
                if foreshadowing:
                    context_parts.append(f"待回收伏笔：{'；'.join(foreshadowing[:3])}")
                if recent_events:
                    context_parts.append(f"近期事件：{'；'.join(recent_events[:3])}")
                if char_status:
                    status_texts = []
                    for cs in char_status[:5]:
                        text = f"{cs.get('name', '')}：{cs.get('status', '')}"
                        if cs.get('arc'):
                            text += f"（{cs.get('arc')}）"
                        status_texts.append(text)
                    if status_texts:
                        context_parts.append(f"角色当前状态：{'；'.join(status_texts)}")
            
            prev_summary = "\n".join(context_parts) if context_parts else ""
            
            # ── RAG 上下文召回 ──
            rag_context_str = ""
            try:
                from app.rag_system import HierarchicalRAG
                rag = HierarchicalRAG(novel_id)
                rag_result = await rag.retrieve_for_writer(outline, top_k=6)
                rag_context_str = rag_result.get("writer_context", "")
                if rag_result.get("chunks"):
                    logger.info(
                        f"[ChapterWriter] RAG召回: "
                        f"{len(rag_result['chunks'])}个块, "
                        f"方法={rag_result['retrieval_method']}, "
                        f"总分={rag_result['total_score']:.3f}"
                    )
            except Exception as e:
                logger.warning(f"[ChapterWriter] RAG召回失败（非阻塞）: {e}")
                rag_context_str = ""

            # 组合 system prompt
            system_prompt = self.SYSTEM_PROMPT.format(
                target_words=target_words,
                writing_style=writing_style,
                env_description_level=env_desc,
                dialogue_ratio_pct=dialogue_pct,
                notes=notes if notes else "无特殊要求"
            )
            
            # 构建用户消息（包含所有创作信息）
            user_message = f"""请撰写小说第{chapter_number}章。

## 上下文背景
{prev_summary if prev_summary else "（第一章，无前文背景）"}

## 相关记忆与伏笔（来自RAG召回）
{rag_context_str if rag_context_str else "（暂无相关记忆）"}

## 章节细纲
{outline_content}

## 主要人物角色简介（请保持人物性格一致）
{characters_info if characters_info else "（暂无人物设定）"}

请开始撰写章节正文：
"""
            if previous_draft:
                user_message += f"""

## 上一版草稿
{previous_draft[:6000]}

## 读者反馈（本轮必须针对性修正）
{json.dumps(reader_feedback, ensure_ascii=False, indent=2) if reader_feedback else "无"}

要求：
1. 保留上一版中最有吸引力的部分
2. 修复读者指出的困惑点、拖沓点、钩子不足问题
3. 输出完整修订后的章节正文，不要输出说明
"""
             
            logger.info(f"[ChapterWriter] 正在撰写第{chapter_number}章，target={target_words}字")
            task_prompt = f"""系统要求：
{system_prompt}

用户任务：
{user_message}

当前是第{rewrite_round}轮写作。

请以 ReAct 方式先规划和自检，再给出最终章节正文。"""

            react_result = await self.run_react_loop(
                task_prompt,
                context=context,
                temperature=0.7,
                output_format="text",
            )
            content = react_result["final_text"] or react_result["raw_response"]
            
            # 清理返回内容（可能包含markdown代码块）
            content = content.strip()
            if content.startswith("```"):
                # 去掉 markdown 代码块标记
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)
            
            word_count = len(content.replace(" ", "").replace("\n", ""))
            
            logger.info(f"[ChapterWriter] 第{chapter_number}章撰写完成，字数：{word_count}")
            
            return {
                "success": True,
                "chapter_number": chapter_number,
                "content": content,
                "word_count": word_count,
                "outline_summary": outline_content[:200] if outline_content else None,
                "rewrite_round": rewrite_round,
                "_react_trace": react_result["trace"],
            }
            
        except Exception as e:
            logger.error(f"[ChapterWriter] 撰写章节失败: {e}")
            return {
                "success": False,
                "error": str(e),
            }
