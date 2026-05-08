"""
实体相关Pydantic模型
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class EntityBase(BaseModel):
    """实体基础模型"""
    novel_id: int = Field(..., description="所属小说ID")
    canonical_name: str = Field(..., min_length=1, max_length=255, description="规范名称")
    entity_type: str = Field(..., description="实体类型: character, faction, skill, item, location")


class EntityCreate(EntityBase):
    """创建实体请求模型"""
    aliases: Optional[List[str]] = Field(default_factory=list, description="别名列表")
    state_vector: Optional[Dict[str, Any]] = Field(default_factory=dict, description="状态向量(JSON对象)")
    narrative_summary: Optional[str] = Field(None, description="叙事摘要")


class EntityUpdate(BaseModel):
    """更新实体请求模型"""
    canonical_name: Optional[str] = Field(None, min_length=1, max_length=255)
    aliases: Optional[List[str]] = None
    entity_type: Optional[str] = None
    state_vector: Optional[Dict[str, Any]] = None
    narrative_summary: Optional[str] = None


class EntityResponse(BaseModel):
    """实体响应模型"""
    id: int
    entity_id: str
    novel_id: int
    canonical_name: str
    aliases: List[str]
    entity_type: str
    state_vector: Dict[str, Any]
    narrative_summary: Optional[str]
    last_mentioned_paragraph_id: Optional[int]
    last_mentioned_chapter_number: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class EntityListResponse(BaseModel):
    """实体列表响应"""
    items: List[EntityResponse]
    total: int


# ===== 关系模型 =====

class EntityRelationshipCreate(BaseModel):
    """创建关系请求"""
    novel_id: int
    source_id: str
    target_id: str
    relation_type: str


class EntityRelationshipResponse(BaseModel):
    """关系响应"""
    id: int
    novel_id: int
    source_id: str
    target_id: str
    relation_type: str
    established_at_paragraph_id: Optional[int]
    established_at_chapter_number: Optional[int]
    created_at: Optional[str]
