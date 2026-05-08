"""
工作流实体同步服务 (WorkflowEntitySyncService)

职责：
  将工作流规划阶段生成的设定数据（世界观/角色/伏笔/大纲）中的
  可抽取实体，转换并写入 entities 表，使 EntityManager 页面可以
  立即看到新生成的实体。

设计原则：
  - **低耦合**：Agent 本身无需感知 Entity 系统；同步逻辑集中在此处。
  - **幂等**：同一实体重复同步只会更新，不会重复创建。
  - **降级安全**：任何异常只记录日志，不影响主工作流。

支持的抽取来源：
  - CHARACTER_DESIGN 阶段  → entity_type = character
  - WORLD_BUILDING  阶段  → entity_type = faction / location
  （后续可扩展 PLOT_DESIGN / OUTLINE_DRAFT 中的 item、skill）
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from loguru import logger

from sqlalchemy import select, and_
from app.core.database import get_session
from app.models.entity import Entity, EntityType, EntityRelationship


# ──────────────────────────────────────────────────────────────
# 核心转换规则：将原始设定字段映射到 state_vector 标准字段
# ──────────────────────────────────────────────────────────────

def _build_character_state_vector(char: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 CharacterDesignerAgent 输出的角色数据转换为 EntityManager
    中 character 类型的 state_vector。
    """
    profile = char.get("profile", {})
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}

    # 展平嵌套的 basic_info（如有）
    if "basic_info" in profile and isinstance(profile["basic_info"], dict):
        basic = profile.pop("basic_info")
        profile.update(basic)

    sv: Dict[str, Any] = {}

    def _get(*keys: str) -> Any:
        for k in keys:
            v = profile.get(k) or char.get(k)
            if v:
                return v
        return None

    for field, candidates in {
        "age":               ["age", "年龄"],
        "gender":            ["gender", "性别"],
        "appearance":        ["appearance", "外貌描述", "外貌"],
        "personality":       ["personality", "性格"],
        "background":        ["background", "背景故事", "背景"],
        "goals":             ["goals", "目标"],
        "skills":            ["skills", "技能"],
        "fears":             ["fears", "恐惧"],
        "current_location":  ["current_location", "location", "当前地点"],
        "health_status":     ["health_status", "health", "健康状态"],
        "mood":              ["mood", "心情"],
        "cultivation_level": ["cultivation_level", "level", "修为等级"],
    }.items():
        v = _get(*candidates)
        if v is not None:
            sv[field] = v

    return sv


def _build_faction_state_vector(faction: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 WorldBuilderAgent 输出的势力数据转换为 faction 类型的 state_vector。
    """
    sv: Dict[str, Any] = {}
    for field, candidates in {
        "leader":    ["leader", "领袖", "head"],
        "territory": ["territory", "regions", "地盘"],
        "strength":  ["strength", "power", "实力"],
        "ideology":  ["description", "ideology", "宗旨", "理念"],
        "enemies":   ["enemies", "opponents", "敌对"],
        "allies":    ["allies", "friends", "盟友"],
        "resources": ["resources", "资源"],
    }.items():
        for k in candidates:
            v = faction.get(k)
            if v is not None:
                sv[field] = v
                break
    # members 从 description 无法可靠抽取，留空
    return sv


def _build_location_state_vector(region: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 WorldBuilderAgent geography.regions 中的地区数据转换为
    location 类型的 state_vector。
    """
    sv: Dict[str, Any] = {}
    for field, candidates in {
        "type":                ["type", "terrain_type", "地形类型"],
        "climate":             ["climate", "气候"],
        "terrain":             ["description", "terrain", "地形"],
        "atmosphere":          ["atmosphere", "ambiance", "氛围"],
        "significance":        ["significance", "importance", "重要性"],
        "connected_locations": ["connected_locations", "neighbors", "邻近地区"],
        "inhabitants":         ["inhabitants", "controlled_by", "居民"],
    }.items():
        for k in candidates:
            v = region.get(k)
            if v is not None:
                sv[field] = v
                break
    return sv


# ──────────────────────────────────────────────────────────────
# 主服务类
# ──────────────────────────────────────────────────────────────

class WorkflowEntitySyncService:
    """
    工作流实体同步服务

    使用示例（在 workflow_engine.py 的 _save_phase_data 中）：
        sync = WorkflowEntitySyncService(novel_id)
        await sync.sync_characters(characters)
        await sync.sync_world_setting(world_setting)
    """

    def __init__(self, novel_id: int):
        self.novel_id = novel_id

    # ── 公开接口 ──────────────────────────────────────────────

    async def sync_characters(self, characters: List[Dict[str, Any]]) -> int:
        """
        将角色设计阶段的角色列表同步到 entities 表（entity_type=character）。
        返回同步成功的数量。
        """
        if not characters:
            return 0
        count = 0
        for char in characters:
            try:
                name = char.get("name", "").strip()
                if not name:
                    continue
                sv = _build_character_state_vector(char)
                narrative = (
                    char.get("arc_description")
                    or char.get("profile", {}).get("personality", "")[:100]
                    or ""
                )
                await self._upsert_entity(
                    canonical_name=name,
                    entity_type=EntityType.CHARACTER,
                    state_vector=sv,
                    narrative_summary=narrative,
                    aliases=[],
                )
                count += 1
            except Exception as e:
                logger.warning(f"[EntitySync] 同步角色失败: {char.get('name')} - {e}")
        logger.info(f"[EntitySync] 角色同步完成: {count}/{len(characters)}")
        return count

    async def sync_world_setting(self, world_setting: Dict[str, Any]) -> int:
        """
        将世界观设定中的势力（factions）和地区（locations）同步到
        entities 表（faction / location 类型）。
        返回同步成功的数量。
        """
        if not world_setting:
            return 0
        count = 0

        # ── 势力 ──
        factions = self._extract_factions(world_setting)
        for faction in factions:
            try:
                name = faction.get("name", "").strip()
                if not name:
                    continue
                sv = _build_faction_state_vector(faction)
                narrative = faction.get("description", "")[:200]
                await self._upsert_entity(
                    canonical_name=name,
                    entity_type=EntityType.FACTION,
                    state_vector=sv,
                    narrative_summary=narrative,
                    aliases=[],
                )
                count += 1
            except Exception as e:
                logger.warning(f"[EntitySync] 同步势力失败: {faction.get('name')} - {e}")

        # ── 地区 ──
        locations = self._extract_locations(world_setting)
        for loc in locations:
            try:
                name = loc.get("name", "").strip()
                if not name:
                    continue
                sv = _build_location_state_vector(loc)
                narrative = loc.get("description", "")[:200]
                await self._upsert_entity(
                    canonical_name=name,
                    entity_type=EntityType.LOCATION,
                    state_vector=sv,
                    narrative_summary=narrative,
                    aliases=[],
                )
                count += 1
            except Exception as e:
                logger.warning(f"[EntitySync] 同步地区失败: {loc.get('name')} - {e}")

        logger.info(
            f"[EntitySync] 世界观同步完成: {count} 个实体"
            f"（势力={len(factions)}, 地区={len(locations)}）"
        )
        return count

    # ── 内部工具 ──────────────────────────────────────────────

    def _extract_factions(self, world_setting: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从世界观数据中提取势力列表"""
        factions: List[Dict[str, Any]] = []

        # 路径1: social_structure.main_factions
        social = world_setting.get("social_structure", {})
        if isinstance(social, dict):
            main_factions = social.get("main_factions", [])
            if isinstance(main_factions, list):
                factions.extend(main_factions)

        # 路径2: factions 顶层字段（部分Agent可能直接输出）
        top_factions = world_setting.get("factions", [])
        if isinstance(top_factions, list):
            factions.extend(top_factions)

        # 去重（按 name）
        seen = set()
        unique = []
        for f in factions:
            n = f.get("name", "")
            if n and n not in seen:
                seen.add(n)
                unique.append(f)
        return unique

    def _extract_locations(self, world_setting: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从世界观数据中提取地区/场景列表"""
        locations: List[Dict[str, Any]] = []

        # 路径1: geography.regions
        geo = world_setting.get("geography", {})
        if isinstance(geo, dict):
            regions = geo.get("regions", [])
            if isinstance(regions, list):
                locations.extend(regions)

        # 路径2: locations 顶层字段
        top_locs = world_setting.get("locations", [])
        if isinstance(top_locs, list):
            locations.extend(top_locs)

        # 去重（按 name）
        seen = set()
        unique = []
        for loc in locations:
            n = loc.get("name", "")
            if n and n not in seen:
                seen.add(n)
                unique.append(loc)
        return unique

    async def _upsert_entity(
        self,
        canonical_name: str,
        entity_type: EntityType,
        state_vector: Dict[str, Any],
        narrative_summary: str = "",
        aliases: Optional[List[str]] = None,
    ) -> str:
        """
        创建或更新实体记录。
        - 如果同名实体已存在，则更新 state_vector（合并）和 narrative_summary。
        - 返回 entity_id。
        """
        aliases = aliases or []
        async with get_session() as db:
            # 查找是否已有同名实体
            result = await db.execute(
                select(Entity).where(
                    and_(
                        Entity.novel_id == self.novel_id,
                        Entity.canonical_name == canonical_name,
                        Entity.entity_type == entity_type,
                    )
                )
            )
            entity = result.scalar_one_or_none()

            if entity:
                # 合并 state_vector（新字段覆盖旧字段）
                current_sv = entity.get_state_dict()
                current_sv.update(state_vector)
                entity.set_state_dict(current_sv)
                # 仅在原有摘要为空时写入
                if narrative_summary and not entity.narrative_summary:
                    entity.narrative_summary = narrative_summary
                await db.commit()
                logger.debug(f"[EntitySync] 更新实体: {canonical_name} ({entity.entity_id})")
                return entity.entity_id
            else:
                entity_id = f"ent_{uuid.uuid4().hex[:8]}"
                new_entity = Entity(
                    entity_id=entity_id,
                    novel_id=self.novel_id,
                    canonical_name=canonical_name,
                    entity_type=entity_type,
                    aliases=json.dumps(aliases, ensure_ascii=False),
                    state_vector=json.dumps(state_vector, ensure_ascii=False),
                    narrative_summary=narrative_summary or None,
                )
                db.add(new_entity)
                await db.commit()
                logger.debug(f"[EntitySync] 创建实体: {canonical_name} ({entity_id})")
                return entity_id
