"""
小说相关Pydantic模型
用于请求验证和响应序列化
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import json


class NovelBase(BaseModel):
    """小说基础模型"""
    title: str = Field(..., min_length=1, max_length=255, description="小说标题")
    genre: Optional[str] = Field(None, max_length=100, description="小说类型")
    style_prompt: Optional[str] = Field(None, description="风格提示词")
    target_chapters: int = Field(default=100, ge=1, le=1000, description="目标章节数")
    words_per_chapter: int = Field(default=3000, ge=500, le=10000, description="每章目标字数")


class NovelCreate(NovelBase):
    """创建小说请求模型"""
    pass


class NovelUpdate(BaseModel):
    """更新小说请求模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    genre: Optional[str] = Field(None, max_length=100)
    style_prompt: Optional[str] = None
    status: Optional[str] = None
    target_chapters: Optional[int] = Field(None, ge=1, le=1000)
    words_per_chapter: Optional[int] = Field(None, ge=500, le=10000)


class NovelResponse(NovelBase):
    """小说响应模型"""
    id: int
    total_chapters: int
    current_chapter: int
    total_words: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class NovelDetailResponse(NovelResponse):
    """小说详情响应模型（包含关联数据）"""
    genre_analysis: Optional[Dict[str, Any]] = None
    # 可以扩展包含chapters、characters等
    
    @field_validator('genre_analysis', mode='before')
    @classmethod
    def parse_genre_analysis(cls, v: Union[str, Dict[str, Any], None]) -> Optional[Dict[str, Any]]:
        """解析 genre_analysis 字段，如果是 JSON 字符串则转换为字典"""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                # 如果解析失败，返回 None
                return None
        return None


class NovelListItem(BaseModel):
    """小说列表项"""
    id: int
    title: str
    genre: Optional[str]
    total_chapters: int
    current_chapter: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class NovelListResponse(BaseModel):
    """小说列表响应"""
    items: List[NovelListItem]
    total: int
    skip: int
    limit: int


class NovelStats(BaseModel):
    """小说统计信息"""
    novel_id: int
    total_chapters: int
    total_words: int
    avg_words_per_chapter: float
    character_count: int
    completion_percentage: float
