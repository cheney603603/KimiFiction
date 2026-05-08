"""
实体识别与状态更新服务 (Module A)
使用LLM（OpenAI GPT-4o-mini）进行共指消解、实体抽取、状态变更识别
"""
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from app.services.llm_service import LLMService, LLMProvider


@dataclass
class EntityMention:
    """实体提及"""
    entity_id: Optional[str] = None
    canonical_name: str = ""
    aliases: List[str] = field(default_factory=list)
    entity_type: str = "character"
    state_changes: Dict[str, Any] = field(default_factory=dict)
    is_new: bool = False
    confidence: float = 0.5


@dataclass
class EntityRelationExtract:
    """关系抽取结果"""
    source_name: str = ""
    target_name: str = ""
    relation_type: str = ""


@dataclass
class ExtractionResult:
    """抽取结果"""
    mentions: List[EntityMention] = field(default_factory=list)
    relations: List[EntityRelationExtract] = field(default_factory=list)


class EntityExtractionService:
    """实体抽取服务 - 基于LLM的共指消解与状态提取"""

    SYSTEM_PROMPT = (
        "你是一个专业的小说文本分析助手。你的任务是从给定的小说段落中：\n"
        "1. 识别所有实体（角色、势力、功法、物品、地点）\n"
        "2. 共指消解：将别名、昵称映射到规范实体名\n"
        "3. 提取状态变更：如境界突破、位置移动、受伤、获得物品等\n"
        "4. 识别关系变更：如结拜、结仇、师徒、加入势力等\n"
        "输出严格的JSON格式。实体类型：character/faction/skill/item/location\n"
        "注意：首次出现的实体is_new=true；confidence表示置信度(0.0-1.0)"
    )

    def __init__(self):
        self.llm = LLMService(
            provider=LLMProvider.DEEPSEEK,
            model="deepseek-v4-pro",
            temperature=0.2,
            max_tokens=4000
        )

    async def extract_from_paragraph(
        self,
        current_paragraph: str,
        paragraph_id: int,
        existing_entities: List[Dict[str, Any]],
        novel_context: Optional[str] = None
    ) -> ExtractionResult:
        """从段落中抽取实体信息"""
        entity_hint = self._build_entity_hint(existing_entities)
        user_prompt = self._build_prompt(
            current_paragraph, paragraph_id, entity_hint, novel_context
        )
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        try:
            response = await self.llm.chat(messages, json_mode=False)
            parsed = self._parse_json_response(response)

            mentions = []
            for e in parsed.get("entities", []):
                mentions.append(EntityMention(
                    canonical_name=e.get("canonical_name", ""),
                    aliases=e.get("aliases", []),
                    entity_type=e.get("entity_type", "character"),
                    state_changes=e.get("state_changes", {}),
                    is_new=e.get("is_new", False),
                    confidence=e.get("confidence", 0.5)
                ))

            relations = []
            for r in parsed.get("relations", []):
                relations.append(EntityRelationExtract(
                    source_name=r.get("source", ""),
                    target_name=r.get("target", ""),
                    relation_type=r.get("relation_type", "")
                ))

            logger.info(
                f"[EntityExtraction] paragraph#{paragraph_id} "
                f"extracted {len(mentions)} entities, {len(relations)} relations"
            )
            return ExtractionResult(mentions=mentions, relations=relations)

        except Exception as e:
            logger.error(f"[EntityExtraction] extraction failed: {e}")
            return ExtractionResult()

    def _build_entity_hint(self, existing_entities: List[Dict[str, Any]]) -> str:
        """构建已知实体提示，帮助LLM做共指消解"""
        if not existing_entities:
            return ""
        lines = []
        for ent in existing_entities[:40]:
            aliases = ent.get("aliases", [])
            alias_str = f"（别名: {', '.join(aliases[:5])}）" if aliases else ""
            state = ent.get("state_vector", {})
            state_str = ""
            if state:
                items = [f"{k}={v}" for k, v in list(state.items())[:3]]
                state_str = f" [状态: {', '.join(items)}]"
            lines.append(
                f"- {ent.get('canonical_name', '')}{alias_str}{state_str} "
                f"-> ID: {ent.get('entity_id', '')}"
            )
        return "\n".join(lines)

    def _build_prompt(
        self,
        current_paragraph: str,
        paragraph_id: int,
        entity_hint: str,
        novel_context: Optional[str]
    ) -> str:
        """构建LLM提示词"""
        parts = ["请分析以下小说段落，提取实体信息。", ""]
        if novel_context:
            parts.append(f"【小说背景】\n{novel_context}")
            parts.append("")
        if entity_hint:
            parts.append(f"【已知实体列表】\n{entity_hint}")
        else:
            parts.append("【注意】该段落中可能包含全新实体，请仔细识别。")
        parts.append("")
        parts.append(f"【当前段落】(paragraph_id={paragraph_id})")
        parts.append(current_paragraph)
        parts.append("")
        parts.append(
            "请严格按以下JSON格式输出，不要添加任何额外解释：\n"
            '{"entities": [{"canonical_name":"...","aliases":[],'
            '"entity_type":"character","state_changes":{},'
            '"is_new":false,"confidence":0.95}], '
            '"relations": [{"source":"...","target":"...",'
            '"relation_type":"..."}]}'
        )
        return "\n".join(parts)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(pattern, response)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(response[start:end+1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[EntityExtraction] failed to parse JSON: {response[:200]}")
        return {"entities": [], "relations": []}
