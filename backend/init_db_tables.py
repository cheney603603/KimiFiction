#!/usr/bin/env python3
"""
数据库初始化脚本
创建所有表（包括rubric相关新表）
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import init_db
from loguru import logger


async def main():
    logger.info("=" * 60)
    logger.info("开始初始化数据库...")
    logger.info("=" * 60)
    
    try:
        await init_db()
        logger.info("✅ 数据库初始化成功！")
        
        # 验证表是否创建
        from app.core.database import get_engine
        from sqlalchemy import inspect
        
        engine = get_engine()
        async with engine.connect() as conn:
            inspector = inspect(conn.sync_connection)
            tables = await conn.run_sync(lambda sync_conn: inspector.get_table_names())
            
        logger.info("\n创建的表:")
        for table in sorted(tables):
            logger.info(f"  - {table}")
        
        # 检查新表是否存在
        new_tables = [
            'rubric_templates',
            'rubric_dimensions', 
            'rubric_evaluations',
            'training_episodes',
            'training_batches',
            'comparison_reports'
        ]
        
        logger.info("\n新表检查:")
        for table in new_tables:
            exists = table in tables
            status = "✅" if exists else "❌"
            logger.info(f"  {status} {table}")
        
        if all(table in tables for table in new_tables):
            logger.info("\n🎉 所有新表创建成功！")
        else:
            logger.warning("\n⚠️ 部分表未创建")
            
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
