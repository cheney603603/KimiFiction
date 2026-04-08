"""
角色相关Pydantic模型
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CharacterBase(BaseModel):
    """角色基础模型"""
    novel_id: int = Field(..., description="所属小说ID")
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    role_type: str = Field(default="supporting", description="角色类型")


class CharacterCreate(CharacterBase):
    """创建角色请求模型"""
    profile: Optional[Dict[str, Any]] = Field(default_factory=dict, description="详细人设")
    current_status: Optional[Dict[str, Any]] = None
    first_appearance: int = Field(default=1, ge=1)


class CharacterUpdate(BaseModel):
    """更新角色请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role_type: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    current_status: Optional[Dict[str, Any]] = None
    arc_progress: Optional[float] = Field(None, ge=0, le=1)


class CharacterResponse(BaseModel):
    """角色响应模型"""
    id: int
    novel_id: int
    name: str
    role_type: str
    profile: Dict[str, Any]
    current_status: Optional[str]
    arc_progress: float
    first_appearance: int
    last_appearance: Optional[int]
    appearance_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CharacterListResponse(BaseModel):
    """角色列表响应"""
    items: List[CharacterResponse]
    total: int


class CharacterTimelineEvent(BaseModel):
    """角色时间线事件"""
    chapter_number: int
    chapter_title: str
    event_type: str  # appearance, development, conflict, etc.
    description: str


class CharacterTimeline(BaseModel):
    """角色时间线"""
    character_id: int
    character_name: str
    events: List[CharacterTimelineEvent]
