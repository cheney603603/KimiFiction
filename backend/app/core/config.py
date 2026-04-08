"""
系统配置管理模块
使用 Pydantic Settings 管理所有环境变量和配置
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 应用基本信息
    APP_NAME: str = Field(default="NovelGen System", description="应用名称")
    APP_VERSION: str = Field(default="1.0.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式")
    PORT: int = Field(default=8080, description="后端服务端口")
    SECRET_KEY: str = Field(default="change-this-in-production", description="密钥")
    
    # MySQL数据库配置
    MYSQL_HOST: str = Field(default="localhost", description="MySQL主机")
    MYSQL_PORT: int = Field(default=3306, description="MySQL端口")
    MYSQL_USER: str = Field(default="novel_user", description="MySQL用户名")
    MYSQL_PASSWORD: str = Field(default="novel_password", description="MySQL密码")
    MYSQL_DATABASE: str = Field(default="novel_system", description="MySQL数据库名")
    
    # 数据库连接池配置
    DB_POOL_SIZE: int = Field(default=10, description="连接池大小")
    DB_MAX_OVERFLOW: int = Field(default=20, description="连接池最大溢出")
    DB_POOL_RECYCLE: int = Field(default=3600, description="连接回收时间(秒)")
    
    # Redis配置
    REDIS_HOST: str = Field(default="localhost", description="Redis主机")
    REDIS_PORT: int = Field(default=6379, description="Redis端口")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis密码")
    REDIS_DB: int = Field(default=0, description="Redis数据库编号")
    
    # Qdrant向量数据库配置
    QDRANT_HOST: str = Field(default="localhost", description="Qdrant主机")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant端口")
    QDRANT_COLLECTION: str = Field(default="novel_memories", description="Qdrant集合名")
    QDRANT_API_KEY: Optional[str] = Field(default=None, description="Qdrant API密钥")
    
    # OpenAI API配置
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API密钥")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1", description="OpenAI基础URL")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview", description="默认模型")
    OPENAI_TEMPERATURE: float = Field(default=0.7, description="生成温度")
    OPENAI_MAX_TOKENS: int = Field(default=4000, description="最大token数")
    
    # LLM提供商配置
    LLM_PROVIDER: str = Field(default="openai", description="LLM提供商: openai/kimi/deepseek/yuanbao")
    CHAT2API_BASE_URL: str = Field(default="http://localhost:8000", description="chat2api服务地址")
    
    # 小说生成配置
    MAX_CHAPTERS: int = Field(default=1000, description="最大章节数")
    DEFAULT_CHAPTER_WORDS: int = Field(default=3000, description="默认章节字数")
    SUMMARY_INTERVAL: int = Field(default=10, description="摘要生成间隔(章)")
    
    # 记忆管理配置
    WORKING_MEMORY_CHAPTERS: int = Field(default=3, description="工作记忆章节数")
    SHORT_TERM_MEMORY_CHAPTERS: int = Field(default=10, description="短期记忆章节数")
    MID_TERM_MEMORY_INTERVAL: int = Field(default=10, description="中期记忆间隔(章)")
    LONG_TERM_MEMORY_INTERVAL: int = Field(default=100, description="长期记忆间隔(章)")
    
    # CORS配置
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"], description="允许的CORS来源")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_value(cls, value):
        """兼容布尔值和常见运行模式字符串。"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return value
    
    @property
    def database_url(self) -> str:
        """生成MySQL连接URL（异步）"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )
    
    @property
    def database_url_sync(self) -> str:
        """生成MySQL连接URL（同步，用于Alembic）"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )
    
    @property
    def redis_url(self) -> str:
        """生成Redis连接URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 全局配置实例
settings = get_settings()
