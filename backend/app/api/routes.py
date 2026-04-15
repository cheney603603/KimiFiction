"""
API路由汇总
注册所有API路由
"""
from fastapi import APIRouter

from app.api.endpoints import (
    auth, novels, chapters, characters, outlines,
    memory, workflow, tasks, export, llm_config, training
)
from app.api.endpoints import training_pipeline

# 创建主路由
api_router = APIRouter(prefix="/api/v1")

# 注册各模块路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(novels.router, prefix="/novels", tags=["小说管理"])
api_router.include_router(chapters.router, prefix="/chapters", tags=["章节管理"])
api_router.include_router(characters.router, prefix="/characters", tags=["角色管理"])
api_router.include_router(outlines.router, prefix="/outlines", tags=["大纲管理"])
api_router.include_router(memory.router, prefix="/memory", tags=["记忆管理"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["工作流控制"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["任务管理"])
api_router.include_router(export.router, prefix="/export", tags=["数据导出"])
api_router.include_router(llm_config.router, prefix="/llm", tags=["LLM配置"])
api_router.include_router(training.router, tags=["RL训练"])
api_router.include_router(training_pipeline.router, tags=["Training-Pipeline"])
