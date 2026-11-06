"""
API路由汇总
注册所有API路由
"""
from fastapi import APIRouter

from app.api.endpoints import (
    auth, novels, chapters, characters, outlines,
    memory, workflow, tasks, export, llm_config, evaluation, entities, snapshots
)
from app.api.endpoints import evaluation_optimizer
from app.api.endpoints import quota
from app.api.endpoints import usage
from app.api.endpoints import rank

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
api_router.include_router(evaluation.router, tags=["评测系统"])
api_router.include_router(entities.router, prefix="/entities", tags=["实体管理"])
api_router.include_router(snapshots.router, tags=["快照管理"])
api_router.include_router(evaluation_optimizer.router, tags=["评测规则优化"])
api_router.include_router(quota.router, prefix="/quota", tags=["额度墙"])
api_router.include_router(usage.router, prefix="/usage", tags=["LLM用量"])
api_router.include_router(rank.router, prefix="/rank", tags=["番茄榜单"])
