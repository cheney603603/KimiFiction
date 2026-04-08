"""
数据库连接管理模块
提供异步SQLAlchemy会话管理和连接池
"""
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from loguru import logger

from app.core.config import settings

# 声明性基类
Base = declarative_base()

# 全局引擎实例
_engine: Optional[AsyncEngine] = None
# 会话工厂
_async_session_maker: Optional[async_sessionmaker] = None


def get_engine() -> AsyncEngine:
    """获取或创建数据库引擎"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=False,  # 禁用ping检查避免greenlet问题
            echo=settings.DEBUG,  # 调试模式下打印SQL
        )
        logger.info(f"数据库引擎已创建: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
    return _engine


def get_session_maker() -> async_sessionmaker:
    """获取会话工厂"""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


async def init_db():
    """初始化数据库 - 创建所有表"""
    import app.models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_mysql_schema)
    logger.info("数据库表初始化完成")


def _ensure_mysql_schema(sync_conn) -> None:
    """为旧版数据库补齐关键字段。"""
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    alter_statements = []

    if "novels" in table_names:
        novel_columns = {column["name"] for column in inspector.get_columns("novels")}
        if "world_setting" not in novel_columns:
            alter_statements.append(
                "ALTER TABLE novels "
                "ADD COLUMN world_setting TEXT NULL COMMENT '世界观设定JSON' "
                "AFTER genre_analysis"
            )

    if "outlines" in table_names:
        outline_columns = {column["name"] for column in inspector.get_columns("outlines")}
        if "outline_type" not in outline_columns:
            alter_statements.append(
                "ALTER TABLE outlines "
                "ADD COLUMN outline_type VARCHAR(50) NOT NULL DEFAULT 'main' COMMENT '大纲类型: main/detail' "
                "AFTER volume_title"
            )
        if "content" not in outline_columns:
            alter_statements.append(
                "ALTER TABLE outlines "
                "ADD COLUMN content TEXT NULL COMMENT '大纲内容JSON' "
                "AFTER arcs"
            )

    for statement in alter_statements:
        logger.warning(f"检测到旧版 MySQL 表结构，自动执行补齐: {statement}")
        sync_conn.execute(text(statement))


async def close_db():
    """关闭数据库连接"""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("数据库连接已关闭")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的上下文管理器
    使用示例:
        async with get_session() as session:
            result = await session.execute(...)
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库事务回滚: {e}")
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI依赖注入用的数据库会话生成器
    使用示例:
        @app.get("/items/")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_session() as session:
        yield session
