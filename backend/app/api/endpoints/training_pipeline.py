"""
训练Pipeline API端点

提供完整的训练流程API
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger

from app.core.auth import get_current_user
from app.training.training_pipeline import TrainingPipeline, run_training_pipeline

router = APIRouter(prefix="/training-pipeline", tags=["training-pipeline"])


# ========== 请求/响应模型 ==========

class PipelineStartRequest(BaseModel):
    novel_id: int
    project_path: str = "training_output"
    run_imitation: bool = True
    run_lora: bool = True
    run_grpo: bool = True
    num_imitation_samples: int = 100
    lora_epochs: int = 3
    grpo_iterations: int = 10
    test_prompts: Optional[List[str]] = None


class PipelineStatusResponse(BaseModel):
    pipeline_id: str
    status: str  # "running" | "completed" | "failed"
    current_stage: str
    progress: float  # 0-100
    stages_completed: int
    stages_total: int
    message: str


class ComparisonResult(BaseModel):
    prompt: str
    baseline_output: str
    baseline_score: float
    imitation_output: str
    imitation_score: float
    lora_output: str
    lora_score: float
    grpo_output: str
    grpo_score: float
    improvements: Dict[str, float]


class PipelineResultResponse(BaseModel):
    pipeline_id: str
    novel_id: int
    status: str
    duration_seconds: float
    stages: List[Dict[str, Any]]
    comparisons: List[ComparisonResult]
    overall_improvement: float
    output_files: Dict[str, str]


# ========== 全局Pipeline存储（简化实现） ==========
# 实际生产环境应该使用Redis或数据库
_active_pipelines: Dict[str, TrainingPipeline] = {}
_pipeline_results: Dict[str, Dict[str, Any]] = {}


# ========== API端点 ==========

@router.post("/start", response_model=Dict[str, Any])
async def start_training_pipeline(
    request: PipelineStartRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    启动完整训练Pipeline
    
    异步执行：模仿学习 → LoRA微调 → GRPO训练 → 评估对比
    """
    try:
        pipeline = TrainingPipeline(
            novel_id=request.novel_id,
            project_path=request.project_path,
        )
        
        # 保存Pipeline引用
        _active_pipelines[pipeline.result.pipeline_id] = pipeline
        
        # 后台执行训练
        background_tasks.add_task(
            _run_pipeline_async,
            pipeline,
            request
        )
        
        return {
            "success": True,
            "message": "训练Pipeline已启动",
            "pipeline_id": pipeline.result.pipeline_id,
            "stages": ["imitation_learning", "lora_finetune", "grpo_training", "evaluation"],
            "status": "running",
        }
        
    except Exception as e:
        logger.error(f"启动训练Pipeline失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_pipeline_async(pipeline: TrainingPipeline, request: PipelineStartRequest):
    """后台运行Pipeline"""
    try:
        result = await pipeline.run_full_pipeline(
            run_imitation=request.run_imitation,
            run_lora=request.run_lora,
            run_grpo=request.run_grpo,
            num_imitation_samples=request.num_imitation_samples,
            lora_epochs=request.lora_epochs,
            grpo_iterations=request.grpo_iterations,
            test_prompts=request.test_prompts,
        )
        
        # 保存结果
        _pipeline_results[result.pipeline_id] = result.to_dict()
        
        logger.info(f"Pipeline {result.pipeline_id} 完成")
        
    except Exception as e:
        logger.error(f"Pipeline执行失败: {e}")
        if pipeline.result.pipeline_id in _active_pipelines:
            del _active_pipelines[pipeline.result.pipeline_id]


@router.get("/status/{pipeline_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    pipeline_id: str,
    current_user = Depends(get_current_user)
):
    """获取Pipeline执行状态"""
    if pipeline_id in _active_pipelines:
        pipeline = _active_pipelines[pipeline_id]
        
        # 计算进度
        total_stages = 4
        completed_stages = len(pipeline.result.stages)
        progress = (completed_stages / total_stages) * 100
        
        # 获取当前阶段
        current_stage = "completed"
        if completed_stages < total_stages:
            stages = ["imitation_learning", "lora_finetune", "grpo_training", "evaluation"]
            current_stage = stages[min(completed_stages, len(stages) - 1)]
        
        return PipelineStatusResponse(
            pipeline_id=pipeline_id,
            status="running" if completed_stages < total_stages else "completed",
            current_stage=current_stage,
            progress=progress,
            stages_completed=completed_stages,
            stages_total=total_stages,
            message=f"正在执行: {current_stage}" if completed_stages < total_stages else "训练完成",
        )
    
    elif pipeline_id in _pipeline_results:
        return PipelineStatusResponse(
            pipeline_id=pipeline_id,
            status="completed",
            current_stage="completed",
            progress=100.0,
            stages_completed=4,
            stages_total=4,
            message="训练已完成",
        )
    
    else:
        raise HTTPException(status_code=404, detail="Pipeline不存在")


@router.get("/result/{pipeline_id}", response_model=PipelineResultResponse)
async def get_pipeline_result(
    pipeline_id: str,
    current_user = Depends(get_current_user)
):
    """获取Pipeline执行结果"""
    if pipeline_id not in _pipeline_results:
        raise HTTPException(status_code=404, detail="结果不存在或Pipeline仍在运行")
    
    result_data = _pipeline_results[pipeline_id]
    
    # 构建对比结果
    comparisons = []
    if "comparison_results" in result_data and "comparisons" in result_data["comparison_results"]:
        for comp in result_data["comparison_results"]["comparisons"]:
            outputs = comp.get("outputs", {})
            comparisons.append(ComparisonResult(
                prompt=comp["prompt"],
                baseline_output=outputs.get("baseline", {}).get("text", ""),
                baseline_score=outputs.get("baseline", {}).get("score", 0),
                imitation_output=outputs.get("imitation", {}).get("text", ""),
                imitation_score=outputs.get("imitation", {}).get("score", 0),
                lora_output=outputs.get("lora_finetuned", {}).get("text", ""),
                lora_score=outputs.get("lora_finetuned", {}).get("score", 0),
                grpo_output=outputs.get("grpo_optimized", {}).get("text", ""),
                grpo_score=outputs.get("grpo_optimized", {}).get("score", 0),
                improvements=comp.get("improvement", {}),
            ))
    
    # 计算总体提升
    overall_improvement = 0.0
    if comparisons:
        overall_improvement = sum(c.improvements.get("grpo_vs_baseline", 0) for c in comparisons) / len(comparisons)
    
    return PipelineResultResponse(
        pipeline_id=pipeline_id,
        novel_id=result_data.get("novel_id", 0),
        status="completed",
        duration_seconds=result_data.get("total_duration_seconds", 0) or 0,
        stages=result_data.get("stages", []),
        comparisons=comparisons,
        overall_improvement=overall_improvement,
        output_files={
            "final_report": f"{result_data.get('novel_id', 0)}/training_output/FINAL_REPORT.json",
            "comparison_report": f"{result_data.get('novel_id', 0)}/training_output/04_evaluation/comparison_report.md",
        }
    )


@router.get("/comparison/{pipeline_id}", response_model=Dict[str, Any])
async def get_comparison_detail(
    pipeline_id: str,
    test_case: int = 0,
    current_user = Depends(get_current_user)
):
    """
    获取详细的对比结果
    
    Args:
        test_case: 测试用例索引
    """
    if pipeline_id not in _pipeline_results:
        raise HTTPException(status_code=404, detail="结果不存在")
    
    result_data = _pipeline_results[pipeline_id]
    
    if "comparison_results" not in result_data:
        raise HTTPException(status_code=404, detail="对比结果不存在")
    
    comparisons = result_data["comparison_results"].get("comparisons", [])
    
    if test_case >= len(comparisons):
        raise HTTPException(status_code=404, detail="测试用例索引超出范围")
    
    comp = comparisons[test_case]
    
    return {
        "pipeline_id": pipeline_id,
        "test_case": test_case,
        "prompt": comp["prompt"],
        "outputs": comp["outputs"],
        "improvements": comp["improvement"],
        "analysis": {
            "best_stage": max(comp["outputs"].items(), key=lambda x: x[1]["score"])[0],
            "max_improvement": max(comp["improvement"].values()),
        }
    }


@router.post("/run-sync", response_model=PipelineResultResponse)
async def run_pipeline_sync(
    request: PipelineStartRequest,
    current_user = Depends(get_current_user)
):
    """
    同步运行训练Pipeline（等待完成）
    
    注意：这可能需要较长时间，建议用于小规模测试
    """
    try:
        result = await run_training_pipeline(
            novel_id=request.novel_id,
            project_path=request.project_path,
            run_imitation=request.run_imitation,
            run_lora=request.run_lora,
            run_grpo=request.run_grpo,
            num_imitation_samples=request.num_imitation_samples,
            lora_epochs=request.lora_epochs,
            grpo_iterations=request.grpo_iterations,
            test_prompts=request.test_prompts,
        )
        
        # 保存结果
        _pipeline_results[result.pipeline_id] = result.to_dict()
        
        # 构建响应
        comparisons = []
        if result.comparison_results and "comparisons" in result.comparison_results:
            for comp in result.comparison_results["comparisons"]:
                outputs = comp.get("outputs", {})
                comparisons.append(ComparisonResult(
                    prompt=comp["prompt"],
                    baseline_output=outputs.get("baseline", {}).get("text", ""),
                    baseline_score=outputs.get("baseline", {}).get("score", 0),
                    imitation_output=outputs.get("imitation", {}).get("text", ""),
                    imitation_score=outputs.get("imitation", {}).get("score", 0),
                    lora_output=outputs.get("lora_finetuned", {}).get("text", ""),
                    lora_score=outputs.get("lora_finetuned", {}).get("score", 0),
                    grpo_output=outputs.get("grpo_optimized", {}).get("text", ""),
                    grpo_score=outputs.get("grpo_optimized", {}).get("score", 0),
                    improvements=comp.get("improvement", {}),
                ))
        
        overall_improvement = 0.0
        if comparisons:
            overall_improvement = sum(c.improvements.get("grpo_vs_baseline", 0) for c in comparisons) / len(comparisons)
        
        return PipelineResultResponse(
            pipeline_id=result.pipeline_id,
            novel_id=result.novel_id,
            status="completed",
            duration_seconds=(result.end_time - result.start_time).total_seconds() if result.end_time else 0,
            stages=[s.to_dict() for s in result.stages],
            comparisons=comparisons,
            overall_improvement=overall_improvement,
            output_files={
                "final_report": f"{request.project_path}/training_output/FINAL_REPORT.json",
                "comparison_report": f"{request.project_path}/training_output/04_evaluation/comparison_report.md",
            }
        )
        
    except Exception as e:
        logger.error(f"同步运行Pipeline失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[Dict[str, Any]])
async def list_pipelines(
    current_user = Depends(get_current_user)
):
    """列出所有Pipeline"""
    pipelines = []
    
    # 合并活跃和已完成
    all_ids = set(_active_pipelines.keys()) | set(_pipeline_results.keys())
    
    for pid in all_ids:
        if pid in _pipeline_results:
            result = _pipeline_results[pid]
            pipelines.append({
                "pipeline_id": pid,
                "status": "completed",
                "novel_id": result.get("novel_id"),
                "duration_seconds": result.get("total_duration_seconds"),
                "stages_count": len(result.get("stages", [])),
            })
        else:
            pipelines.append({
                "pipeline_id": pid,
                "status": "running",
            })
    
    return pipelines


@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    current_user = Depends(get_current_user)
):
    """删除Pipeline记录"""
    if pipeline_id in _active_pipelines:
        del _active_pipelines[pipeline_id]
    
    if pipeline_id in _pipeline_results:
        del _pipeline_results[pipeline_id]
    
    return {"success": True, "message": f"Pipeline {pipeline_id} 已删除"}
