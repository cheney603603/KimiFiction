"""
角色服务层
处理角色的业务逻辑
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.models.character import Character, RoleType
from app.models.chapter import Chapter
from app.schemas.character import CharacterCreate, CharacterUpdate


class CharacterService:
    """角色服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_character(self, char_data: CharacterCreate) -> Character:
        """创建角色"""
        import json
        
        character = Character(
            novel_id=char_data.novel_id,
            name=char_data.name,
            role_type=RoleType(char_data.role_type) if char_data.role_type else RoleType.SUPPORTING,
            profile=char_data.profile or {},
            current_status=json.dumps(char_data.current_status) if char_data.current_status else None,
            first_appearance=char_data.first_appearance,
        )
        self.db.add(character)
        await self.db.commit()
        await self.db.refresh(character)
        logger.info(f"创建角色: {character.name} (小说ID: {character.novel_id})")
        return character
    
    async def get_character(self, character_id: int) -> Optional[Character]:
        """获取角色详情"""
        result = await self.db.execute(
            select(Character).where(Character.id == character_id)
        )
        return result.scalar_one_or_none()
    
    async def get_character_by_name(self, novel_id: int, name: str) -> Optional[Character]:
        """根据名称获取角色"""
        result = await self.db.execute(
            select(Character).where(
                Character.novel_id == novel_id,
                Character.name == name
            )
        )
        return result.scalar_one_or_none()
    
    async def list_characters(
        self,
        novel_id: int,
        role_type: Optional[str] = None
    ) -> List[Character]:
        """获取角色列表"""
        query = select(Character).where(Character.novel_id == novel_id)
        
        if role_type:
            query = query.where(Character.role_type == role_type)
        
        query = query.order_by(
            func.field(Character.role_type, 'protagonist', 'antagonist', 'supporting', 'minor'),
            Character.first_appearance.asc()
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_character(self, character_id: int, char_data: CharacterUpdate) -> Optional[Character]:
        """更新角色"""
        import json
        
        character = await self.get_character(character_id)
        if not character:
            return None
        
        update_data = char_data.model_dump(exclude_unset=True)
        
        # 特殊处理current_status（需要JSON序列化）
        if 'current_status' in update_data and update_data['current_status']:
            update_data['current_status'] = json.dumps(update_data['current_status'], ensure_ascii=False)
        
        for field, value in update_data.items():
            setattr(character, field, value)
        
        await self.db.commit()
        await self.db.refresh(character)
        logger.info(f"更新角色: {character.name} (ID: {character.id})")
        return character
    
    async def delete_character(self, character_id: int) -> bool:
        """删除角色"""
        character = await self.get_character(character_id)
        if not character:
            return False
        
        await self.db.delete(character)
        await self.db.commit()
        logger.info(f"删除角色: {character.name} (ID: {character.id})")
        return True
    
    async def update_appearance(self, character_id: int, chapter_number: int):
        """更新角色出场信息"""
        character = await self.get_character(character_id)
        if not character:
            return
        
        character.last_appearance = chapter_number
        character.appearance_count += 1
        await self.db.commit()
    
    async def get_character_timeline(self, character_id: int) -> Optional[dict]:
        """获取角色出场时间线"""
        character = await self.get_character(character_id)
        if not character:
            return None
        
        # 查询角色出场的章节
        result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == character.novel_id)
            .where(Chapter.characters_present.contains([character.name]))
            .order_by(Chapter.chapter_number.asc())
        )
        chapters = result.scalars().all()
        
        events = []
        for ch in chapters:
            events.append({
                "chapter_number": ch.chapter_number,
                "chapter_title": ch.title,
                "event_type": "appearance",
                "description": ch.summary or f"第{ch.chapter_number}章出场"
            })
        
        return {
            "character_id": character.id,
            "character_name": character.name,
            "events": events
        }
    
    async def get_main_characters(self, novel_id: int) -> List[Character]:
        """获取主要角色（主角+重要配角）"""
        result = await self.db.execute(
            select(Character)
            .where(Character.novel_id == novel_id)
            .where(Character.role_type.in_([RoleType.PROTAGONIST, RoleType.ANTAGONIST]))
            .order_by(Character.first_appearance.asc())
        )
        return list(result.scalars().all())
