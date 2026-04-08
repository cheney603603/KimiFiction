"""
上下文管理器
负责RAG检索和上下文压缩，为章节写作提供完整的背景信息
"""
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

from app.core.vector_store import vector_store
from app.services.memory_service import MemoryService
from app.core.database import get_session


@dataclass
class ContextBlock:
    """上下文块"""
    content: str
    source_type: str  # "chapter_summary" | "character_status" | "mystery" | "foreshadowing" | "world_setting"
    source_id: str
    importance: float  # 0-1
    chapter_range: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressedContext:
    """压缩后的上下文"""
    blocks: List[ContextBlock]
    total_tokens: int
    compression_ratio: float
    strategy_used: str


class ContextManager:
    """
    上下文管理器
    
    职责：
    1. 从向量数据库检索相关上下文（RAG）
    2. 从数据库获取角色状态、伏笔等
    3. 压缩上下文以适应Token限制
    4. 为章节写作构建完整上下文
    """
    
    # Token限制（估算，中文约1字=1-2token）
    MAX_CONTEXT_TOKENS = 12000
    TARGET_CONTEXT_TOKENS = 8000
    
    # 压缩策略优先级
    COMPRESSION_PRIORITY = [
        "world_setting",      # 世界观优先保留
        "character_status",   # 角色状态
        "mystery",           # 未解伏笔
        "foreshadowing",     # 伏笔
        "recent_chapters",   # 最近章节
        "older_chapters",    # 早期章节
    ]
    
    def __init__(self, novel_id: int, workflow_state: Any = None):
        self.novel_id = novel_id
        self.workflow_state = workflow_state

    # ===== RAG检索 =====
    
    async def retrieve_relevant_context(
        self,
        query: str,
        top_k: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[ContextBlock]:
        """
        从向量数据库检索相关上下文

        Args:
            query: 查询文本（可以是章节大纲、关键词等）
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            相关的上下文块列表
        """
        blocks = []

        # 如果查询为空，直接返回空列表
        if not query or query.strip() == '':
            logger.debug("RAG检索: 查询为空，跳过检索")
            return blocks

        try:
            # 获取embedding（EmbeddingService不需要db参数）
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
            query_vector = await embedding_service.get_embedding(query)

            if query_vector:
                # 向量搜索
                results = await vector_store.search(
                    query_vector=query_vector,
                    top_k=top_k,
                    filters=filters or {"novel_id": str(self.novel_id)}
                )

                for result in results:
                    blocks.append(ContextBlock(
                        content=result.payload.get("content", ""),
                        source_type=result.payload.get("type", "unknown"),
                        source_id=result.payload.get("id", ""),
                        importance=result.score,
                        metadata=result.payload
                    ))

            logger.debug(f"RAG检索: query={query[:50]}, results={len(blocks)}")

        except Exception as e:
            logger.error(f"RAG检索失败: {e}")
        
        return blocks
    
    async def retrieve_chapter_context(
        self,
        chapter_number: int,
        num_chapters: int = 5
    ) -> List[ContextBlock]:
        """
        检索与特定章节相关的上下文

        Args:
            chapter_number: 章节号
            num_chapters: 检索前后多少章

        Returns:
            相关上下文块
        """
        blocks = []

        # 第一章没有前文，直接返回空列表
        if chapter_number <= 1:
            logger.info(f"第{chapter_number}章：第一章没有前文上下文")
            return blocks

        try:
            async with get_session() as db:
                memory_service = MemoryService(db)
                
                # 获取最近章节摘要
                recent_nodes = await memory_service.list_nodes(
                    self.novel_id,
                    node_type="chapter_summary"
                )
                
                for node in recent_nodes[-num_chapters:]:
                    chapter_str = node.chapter_range or str(node.specific_chapter or "")
                    try:
                        chapter_num = int(chapter_str)
                        if abs(chapter_num - chapter_number) <= num_chapters:
                            blocks.append(ContextBlock(
                                content=node.content,
                                source_type="chapter_summary",
                                source_id=str(node.id),
                                importance=1.0 if chapter_num == chapter_number else 0.7,
                                chapter_range=chapter_str,
                            ))
                    except:
                        pass
                
                # 获取未解伏笔
                mysteries = await memory_service.list_nodes(
                    self.novel_id,
                    node_type="mystery",
                    unresolved_only=True
                )
                
                for node in mysteries[:5]:
                    blocks.append(ContextBlock(
                        content=f"[伏笔] {node.title}: {node.content}",
                        source_type="mystery",
                        source_id=str(node.id),
                        importance=0.8,
                        metadata={"chapter_range": node.chapter_range}
                    ))
                
                # 获取重要记忆节点
                important_nodes = await memory_service.list_nodes(self.novel_id)
                for node in important_nodes[:10]:
                    if node.importance_score >= 0.7:
                        blocks.append(ContextBlock(
                            content=f"[重要] {node.title}: {node.content}",
                            source_type="important_memory",
                            source_id=str(node.id),
                            importance=node.importance_score,
                        ))
                        
        except Exception as e:
            logger.error(f"章节上下文检索失败: {e}")
        
        return blocks
    
    # ===== 上下文构建 =====
    
    async def build_chapter_context(
        self,
        chapter_number: int,
        outline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        为章节写作构建完整上下文
        
        Args:
            chapter_number: 章节号
            outline: 章节大纲
            
        Returns:
            完整的上下文字典
        """
        # 1. 收集各类上下文
        blocks = []
        
        # 世界观设定
        if self.workflow_state and self.workflow_state.world_setting:
            world = self.workflow_state.world_setting
            blocks.append(ContextBlock(
                content=json.dumps(world, ensure_ascii=False, indent=2),
                source_type="world_setting",
                source_id="world_setting",
                importance=1.0,
            ))
        
        # 角色状态
        if self.workflow_state and self.workflow_state.characters:
            char_context = self._build_character_context(
                self.workflow_state.characters,
                chapter_number
            )
            blocks.append(ContextBlock(
                content=char_context,
                source_type="character_status",
                source_id="character_status",
                importance=1.0,
            ))
        
        # 冲突伏笔设定
        if self.workflow_state and self.workflow_state.plot_setting:
            plot = self.workflow_state.plot_setting
            blocks.append(ContextBlock(
                content=json.dumps(plot, ensure_ascii=False, indent=2),
                source_type="plot_setting",
                source_id="plot_setting",
                importance=0.9,
            ))
        
        # 大纲
        if self.workflow_state and self.workflow_state.outline:
            outline_context = self._build_outline_context(
                self.workflow_state.outline,
                chapter_number
            )
            blocks.append(ContextBlock(
                content=outline_context,
                source_type="outline",
                source_id="outline",
                importance=0.95,
            ))
        
        # RAG检索相关上下文
        query = outline.get("summary", "") + " " + " ".join(outline.get("key_events", []))
        rag_results = await self.retrieve_relevant_context(query, top_k=5)
        blocks.extend(rag_results)
        
        # 章节相关上下文
        chapter_context = await self.retrieve_chapter_context(chapter_number, num_chapters=3)
        blocks.extend(chapter_context)
        
        # 2. 压缩上下文
        compressed = self._compress_context(blocks)
        
        # 3. 构建最终上下文
        context = {
            "chapter_number": chapter_number,
            "chapter_outline": outline,
            "compressed_context": {
                "blocks": [
                    {
                        "content": b.content,
                        "source_type": b.source_type,
                        "source_id": b.source_id,
                        "importance": b.importance,
                    }
                    for b in compressed.blocks
                ],
                "total_tokens": compressed.total_tokens,
                "compression_ratio": compressed.compression_ratio,
            },
            # 单独提取关键信息便于使用
            "world_setting": self._extract_field(blocks, "world_setting"),
            "character_status": self._extract_characters(blocks),
            "unresolved_mysteries": self._extract_mysteries(blocks),
            "recent_events": self._extract_recent_events(blocks),
            "foreshadowing": self._extract_foreshadowing(blocks),
        }
        
        return context
    
    def _build_character_context(
        self,
        characters: List[Dict],
        chapter_number: int
    ) -> str:
        """构建角色上下文"""
        lines = ["【角色状态】"]
        for char in characters[:8]:  # 最多8个角色
            name = char.get("name", "未知")
            role = char.get("role_type", char.get("role", "配角"))
            profile = char.get("profile", {})
            current_status = char.get("current_status", profile.get("current_status", ""))
            arc_progress = char.get("arc_progress", "")
            
            lines.append(f"\n■ {name}（{role}）")
            if current_status:
                lines.append(f"  当前状态: {current_status}")
            if arc_progress:
                lines.append(f"  成长弧: {arc_progress}")
            
            # 关键性格/能力
            personality = profile.get("personality", "")
            skills = profile.get("skills", [])
            if personality:
                lines.append(f"  性格: {personality}")
            if skills:
                lines.append(f"  技能: {', '.join(skills[:3])}")
        
        return "\n".join(lines)
    
    def _build_outline_context(
        self,
        outline: Dict,
        chapter_number: int
    ) -> str:
        """构建大纲上下文"""
        lines = ["【故事大纲】"]
        
        # 整体故事线
        if "overall_arc" in outline:
            lines.append(f"\n整体主线: {outline['overall_arc']}")
        
        # 当前卷
        volumes = outline.get("volumes", [])
        current_volume = None
        for vol in volumes:
            chapters = vol.get("chapters", [])
            for ch_range in chapters:
                if isinstance(ch_range, dict):
                    start = ch_range.get("start", 0)
                    end = ch_range.get("end", 0)
                else:
                    start = end = ch_range
                if start <= chapter_number <= end:
                    current_volume = vol
                    break
            if current_volume:
                break
        
        if current_volume:
            lines.append(f"\n当前卷: 第{current_volume.get('volume_number', '?')}卷 {current_volume.get('title', '')}")
            
            # 当前剧情弧
            arcs = current_volume.get("arcs", [])
            for arc in arcs:
                start = arc.get("start_chapter", 0)
                end = arc.get("end_chapter", 0)
                if start <= chapter_number <= end:
                    lines.append(f"\n当前剧情弧: {arc.get('title', '')}")
                    lines.append(f"描述: {arc.get('description', '')}")
                    lines.append(f"关键事件: {', '.join(arc.get('key_events', []))}")
                    break
        
        return "\n".join(lines)
    
    # ===== 上下文压缩 =====
    
    def _compress_context(self, blocks: List[ContextBlock]) -> CompressedContext:
        """
        压缩上下文以适应Token限制
        
        策略：
        1. 按优先级排序
        2. 估算当前token数
        3. 从低优先级开始裁剪
        4. 返回压缩结果
        """
        if not blocks:
            return CompressedContext(
                blocks=[],
                total_tokens=0,
                compression_ratio=1.0,
                strategy_used="none"
            )
        
        # 按优先级排序
        priority_map = {p: i for i, p in enumerate(self.COMPRESSION_PRIORITY)}
        sorted_blocks = sorted(
            blocks,
            key=lambda b: (
                -b.importance,  # 重要性降序
                priority_map.get(b.source_type, 999)  # 优先级升序
            )
        )
        
        # 计算总token
        def estimate_tokens(text: str) -> int:
            # 简单估算：中文约1-1.5字/token，英文约0.25词/token
            chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
            english = len(re.findall(r'[a-zA-Z]+', text))
            return int(chinese * 1.2 + english * 0.25)
        
        total_tokens = sum(estimate_tokens(b.content) for b in sorted_blocks)
        
        if total_tokens <= self.TARGET_CONTEXT_TOKENS:
            return CompressedContext(
                blocks=sorted_blocks,
                total_tokens=total_tokens,
                compression_ratio=1.0,
                strategy_used="none"
            )
        
        # 需要压缩
        compressed_blocks = []
        current_tokens = 0
        
        for block in sorted_blocks:
            block_tokens = estimate_tokens(block.content)
            
            if current_tokens + block_tokens <= self.TARGET_CONTEXT_TOKENS:
                compressed_blocks.append(block)
                current_tokens += block_tokens
            else:
                # 尝试压缩这个块
                remaining = self.TARGET_CONTEXT_TOKENS - current_tokens
                if remaining > 500:  # 至少保留一些
                    compressed_content = self._compress_block(block, remaining)
                    compressed_blocks.append(ContextBlock(
                        content=compressed_content,
                        source_type=block.source_type,
                        source_id=block.source_id,
                        importance=block.importance * 0.8,  # 压缩后降低重要性
                        chapter_range=block.chapter_range,
                        metadata={**block.metadata, "compressed": True}
                    ))
                    current_tokens += estimate_tokens(compressed_content)
                break
        
        compression_ratio = current_tokens / max(total_tokens, 1)
        
        return CompressedContext(
            blocks=compressed_blocks,
            total_tokens=current_tokens,
            compression_ratio=compression_ratio,
            strategy_used="importance_priority_truncation"
        )
    
    def _compress_block(self, block: ContextBlock, max_tokens: int) -> str:
        """
        压缩单个上下文块
        """
        content = block.content
        estimated_tokens = int(len(re.findall(r'[\u4e00-\u9fff]', content)) * 1.2)
        
        if estimated_tokens <= max_tokens:
            return content
        
        # 根据类型采用不同压缩策略
        if block.source_type == "chapter_summary":
            # 章节摘要：保留关键事件
            return self._compress_chapter_summary(content, max_tokens)
        elif block.source_type == "character_status":
            # 角色状态：简化
            return self._compress_character_status(content, max_tokens)
        elif block.source_type == "mystery":
            # 伏笔：完整保留
            return content[:int(max_tokens * 2)]
        else:
            # 其他：直接截断
            return content[:int(max_tokens * 1.5)]
    
    def _compress_chapter_summary(self, content: str, max_tokens: int) -> str:
        """压缩章节摘要"""
        lines = content.split("\n")
        if len(lines) <= 3:
            return content
        
        # 保留前几行和关键信息
        kept_lines = []
        current_tokens = 0
        
        for line in lines[:5]:  # 最多5行
            line_tokens = len(re.findall(r'[\u4e00-\u9fff]', line))
            if current_tokens + line_tokens <= max_tokens:
                kept_lines.append(line)
                current_tokens += line_tokens
            else:
                # 截断最后一行
                kept_lines.append(line[:int(max_tokens * 1.5)])
                break
        
        return "\n".join(kept_lines)
    
    def _compress_character_status(self, content: str, max_tokens: int) -> str:
        """压缩角色状态"""
        lines = content.split("\n")
        kept_lines = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = len(re.findall(r'[\u4e00-\u9fff]', line))
            if current_tokens + line_tokens <= max_tokens:
                kept_lines.append(line)
                current_tokens += line_tokens
            else:
                break
        
        return "\n".join(kept_lines)
    
    # ===== 辅助方法 =====
    
    def _extract_field(self, blocks: List[ContextBlock], field_type: str) -> str:
        """提取特定类型的上下文"""
        for block in blocks:
            if block.source_type == field_type:
                return block.content
        return ""
    
    def _extract_characters(self, blocks: List[ContextBlock]) -> List[Dict]:
        """提取角色信息"""
        char_block = self._extract_field(blocks, "character_status")
        if not char_block:
            return []
        
        # 简单解析
        characters = []
        current_char = {}
        
        for line in char_block.split("\n"):
            if line.startswith("■ "):
                if current_char:
                    characters.append(current_char)
                name = line[2:].split("（")[0] if "（" in line else line[2:]
                current_char = {"name": name}
            elif "当前状态:" in line:
                current_char["status"] = line.split("当前状态:")[1].strip()
            elif "成长弧:" in line:
                current_char["arc"] = line.split("成长弧:")[1].strip()
        
        if current_char:
            characters.append(current_char)
        
        return characters
    
    def _extract_mysteries(self, blocks: List[ContextBlock]) -> List[str]:
        """提取未解伏笔"""
        mysteries = []
        for block in blocks:
            if block.source_type == "mystery":
                mysteries.append(block.content)
        return mysteries
    
    def _extract_recent_events(self, blocks: List[ContextBlock]) -> List[str]:
        """提取最近事件"""
        events = []
        for block in blocks:
            if block.source_type == "chapter_summary" and block.importance >= 0.7:
                events.append(block.content[:200])  # 截断
        return events[:5]
    
    def _extract_foreshadowing(self, blocks: List[ContextBlock]) -> List[str]:
        """提取伏笔"""
        foreshadowing = []
        for block in blocks:
            if block.source_type == "foreshadowing":
                foreshadowing.append(block.content)
        return foreshadowing
    
    # ===== 上下文格式化为提示词 =====
    
    def format_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        将上下文格式化为LLM提示词
        
        Args:
            context: build_chapter_context返回的上下文
            
        Returns:
            格式化的提示词字符串
        """
        parts = []
        
        # 章节大纲
        outline = context.get("chapter_outline", {})
        parts.append("【本章大纲】")
        parts.append(f"标题: {outline.get('title', '')}")
        parts.append(f"摘要: {outline.get('summary', '')}")
        parts.append(f"关键事件: {', '.join(outline.get('key_events', []))}")
        
        # 压缩的上下文
        parts.append("\n【相关背景】")
        compressed = context.get("compressed_context", {})
        for block in compressed.get("blocks", []):
            source = block.get("source_type", "")
            content = block.get("content", "")
            parts.append(f"\n[{source}]")
            parts.append(content[:500] + "..." if len(content) > 500 else content)
        
        # 角色状态
        characters = context.get("character_status", [])
        if characters:
            parts.append("\n【主要角色】")
            for char in characters[:5]:
                name = char.get("name", "")
                status = char.get("status", "")
                arc = char.get("arc", "")
                parts.append(f"- {name}: {status}" + (f" | {arc}" if arc else ""))
        
        # 未解伏笔
        mysteries = context.get("unresolved_mysteries", [])
        if mysteries:
            parts.append("\n【未解伏笔】")
            for m in mysteries[:3]:
                parts.append(f"- {m[:100]}")
        
        return "\n".join(parts)


# ===== 上下文压缩的替代实现（轻量级） =====

class LightweightContextManager:
    """
    轻量级上下文管理器
    不依赖向量数据库，使用简单的文本匹配
    """
    
    def __init__(self, novel_id: int, workflow_state: Any = None):
        self.novel_id = novel_id
        self.workflow_state = workflow_state
    
    async def build_context(
        self,
        chapter_number: int,
        outline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建轻量级上下文"""
        context = {
            "chapter_number": chapter_number,
            "chapter_outline": outline,
        }
        
        # 添加基本上下文
        if self.workflow_state:
            context["world_setting"] = self.workflow_state.world_setting
            context["characters"] = self.workflow_state.characters
            context["plot_setting"] = self.workflow_state.plot_setting
            context["outline"] = self.workflow_state.outline
        
        # 简单压缩
        context = self._lightweight_compress(context)
        
        return context
    
    def _lightweight_compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """轻量级压缩"""
        # JSON化后截断
        json_str = json.dumps(context, ensure_ascii=False)
        if len(json_str) > 15000:
            # 优先保留大纲
            outline = context.get("chapter_outline", {})
            context = {
                "chapter_number": context.get("chapter_number"),
                "chapter_outline": outline,
                "world_setting": str(context.get("world_setting", ""))[:1000],
                "characters": str(context.get("characters", ""))[:1000],
            }
        
        return context
