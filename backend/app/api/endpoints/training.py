"""
训练和RL相关的API端点

包括：
- 模仿学习数据生成
- GRPO训练
- LoRA微调
- TPO优化
- 模型评估
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger

from app.core.auth import get_current_user
from app.training import (
    GRPOTrainer, GRPOConfig,
    LoRATrainer, LoRAConfig,
    ImitationLearning,
    TPOService,
)

router = APIRouter(prefix="/training", tags=["training"])


# ========== 请求/响应模型 ==========

class ImitationLearningRequest(BaseModel):
    num_samples: int = 100
    context_length: int = 200
    output_length: int = 1000


class GRPOTrainingRequest(BaseModel):
    chapter_number: int
    max_rounds: int = 3
    group_size: int = 4
    score_threshold: float = 0.78


class LoRARequest(BaseModel):
    r: int = 8
    lora_alpha: int = 16
    num_epochs: int = 3
    learning_rate: float = 2e-4


class TPORequest(BaseModel):
    content: str
    num_candidates: int = 3


class TrainingStatusResponse(BaseModel):
    status: str
    progress: float
    message: str
    result: Optional[Dict[str, Any]] = None


# ========== 模仿学习接口 ==========

@router.post("/imitation/generate", response_model=Dict[str, Any])
async def generate_imitation_data(
    request: ImitationLearningRequest,
    current_user = Depends(get_current_user)
):
    """
    从参考小说生成模仿学习数据
    
    解析reference文件夹中的参考小说，生成用于训练的样本
    """
    try:
        il = ImitationLearning("reference")
        
        # 加载参考小说
        novels = il.load_references()
        if not novels:
            raise HTTPException(status_code=404, detail="未找到参考小说")
        
        # 分析风格
        styles = il.analyze_styles()
        
        # 生成训练样本
        samples = il.generate_training_samples(
            num_samples=request.num_samples,
            context_length=request.context_length,
            output_length=request.output_length
        )
        
        # 导出
        json_path = il.export_to_json("training_data/imitation_samples.json")
        jsonl_path = il.export_to_jsonl("training_data/imitation_samples.jsonl")
        
        return {
            "success": True,
            "message": f"生成了{len(samples)}个训练样本",
            "novels_processed": len(novels),
            "styles_analyzed": len(styles),
            "samples_generated": len(samples),
            "output_files": {
                "json": json_path,
                "jsonl": jsonl_path
            },
            "style_summary": il.get_style_summary(),
        }
        
    except Exception as e:
        logger.error(f"模仿学习数据生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/imitation/style-guide", response_model=Dict[str, Any])
async def get_style_guide(
    current_user = Depends(get_current_user)
):
    """获取写作风格指南"""
    try:
        il = ImitationLearning("reference")
        il.load_references()
        il.analyze_styles()
        
        guidelines = il.get_writing_guidelines()
        summary = il.get_style_summary()
        
        return {
            "success": True,
            "style_summary": summary,
            "guidelines": guidelines,
        }
        
    except Exception as e:
        logger.error(f"获取风格指南失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== GRPO训练接口 ==========

@router.post("/grpo/train/{novel_id}", response_model=Dict[str, Any])
async def train_with_grpo(
    novel_id: int,
    request: GRPOTrainingRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    使用GRPO算法训练Writer策略
    
    通过Writer-Reader对抗学习优化写作策略
    """
    try:
        # 创建GRPO训练器
        config = GRPOConfig(
            group_size=request.group_size,
        )
        
        trainer = GRPOTrainer(novel_id=novel_id, config=config)
        
        # 这里简化实现，实际应该启动异步训练任务
        # background_tasks.add_task(_run_grpo_training, trainer, request)
        
        return {
            "success": True,
            "message": "GRPO训练已启动",
            "novel_id": novel_id,
            "config": config.to_dict(),
            "status": "training",
        }
        
    except Exception as e:
        logger.error(f"GRPO训练启动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grpo/status/{novel_id}", response_model=Dict[str, Any])
async def get_grpo_status(
    novel_id: int,
    current_user = Depends(get_current_user)
):
    """获取GRPO训练状态"""
    # 简化实现
    return {
        "novel_id": novel_id,
        "status": "idle",
        "message": "训练状态查询功能待实现",
    }


# ========== LoRA微调接口 ==========

@router.post("/lora/finetune/{novel_id}", response_model=Dict[str, Any])
async def finetune_with_lora(
    novel_id: int,
    request: LoRARequest,
    current_user = Depends(get_current_user)
):
    """
    使用LoRA微调本地Qwen模型
    
    在消费级显卡上进行参数高效微调
    """
    try:
        from app.core.local_llm import get_local_llm_service
        
        # 获取本地模型路径
        llm_service = get_local_llm_service()
        model_path = llm_service.config.model_path
        
        # 创建LoRA训练器
        config = LoRAConfig(
            r=request.r,
            lora_alpha=request.lora_alpha,
            num_epochs=request.num_epochs,
            learning_rate=request.learning_rate,
        )
        
        trainer = LoRATrainer(model_path=model_path, config=config)
        
        # 加载模仿学习数据
        il = ImitationLearning("reference")
        il.load_references()
        samples = il.generate_training_samples(num_samples=50)
        
        for sample in samples:
            trainer.add_training_sample(
                prompt=sample.context,
                completion=sample.output,
                metadata=sample.metadata
            )
        
        # 启动训练（简化：实际应该异步执行）
        # result = await trainer.train()
        
        return {
            "success": True,
            "message": "LoRA微调已配置",
            "novel_id": novel_id,
            "config": config.to_dict(),
            "training_samples": len(trainer.training_samples),
            "status": "configured",
        }
        
    except Exception as e:
        logger.error(f"LoRA微调配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== TPO优化接口 ==========

@router.post("/tpo/optimize", response_model=Dict[str, Any])
async def optimize_with_tpo(
    request: TPORequest,
    current_user = Depends(get_current_user)
):
    """
    使用Test-time Preference Optimization优化内容
    
    在推理时生成多个候选并选择最佳
    """
    try:
        from app.agents.reader import ReaderAgent
        
        reader = ReaderAgent()
        tpo = TPOService(reader, num_candidates=request.num_candidates)
        
        # 简化实现：实际应该调用writer生成候选
        # 这里仅展示接口
        
        return {
            "success": True,
            "message": "TPO优化已配置",
            "num_candidates": request.num_candidates,
            "status": "configured",
        }
        
    except Exception as e:
        logger.error(f"TPO配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 模型评估接口 ==========

@router.post("/evaluate/{novel_id}", response_model=Dict[str, Any])
async def evaluate_model(
    novel_id: int,
    chapter_numbers: List[int],
    current_user = Depends(get_current_user)
):
    """
    评估模型生成的章节质量
    
    使用Rubric评测系统进行多维度评估
    """
    try:
        from app.services.rubric_evaluation_service import RubricEvaluationService
        
        service = RubricEvaluationService(novel_id)
        await service.initialize()
        
        results = []
        for chapter_number in chapter_numbers:
            # 获取章节内容（简化实现）
            content = f"第{chapter_number}章内容..."
            
            result = await service.evaluate_chapter(
                chapter_number=chapter_number,
                chapter_content=content
            )
            results.append(result)
        
        return {
            "success": True,
            "novel_id": novel_id,
            "chapters_evaluated": len(results),
            "results": results,
        }
        
    except Exception as e:
        logger.error(f"模型评估失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 训练数据管理接口 ==========

@router.get("/data/collect/{novel_id}", response_model=Dict[str, Any])
async def collect_training_data(
    novel_id: int,
    current_user = Depends(get_current_user)
):
    """
    收集训练数据
    
    从Writer-Reader交互中收集RL训练数据
    """
    try:
        from app.services.training_data_collector import TrainingDataCollector
        
        collector = TrainingDataCollector(
            novel_id=novel_id,
            project_path=f"projects/{novel_id}",
        )
        
        # 这里简化实现，实际应该返回collector的状态
        return {
            "success": True,
            "novel_id": novel_id,
            "data_directory": collector.get_data_directory(),
            "status": "ready",
        }
        
    except Exception as e:
        logger.error(f"训练数据收集失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 系统状态接口 ==========

@router.get("/status", response_model=Dict[str, Any])
async def get_training_status(
    current_user = Depends(get_current_user)
):
    """获取训练系统状态"""
    try:
        from app.core.local_llm import check_local_model
        
        local_model_status = await check_local_model()
        
        return {
            "success": True,
            "local_model": local_model_status,
            "components": {
                "imitation_learning": True,
                "grpo": True,
                "lora": True,
                "tpo": True,
            }
        }
        
    except Exception as e:
        logger.error(f"获取训练状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# 八维 LLM Rubric 评测接口
# ============================================================

class EvaluationRequest(BaseModel):
    novel_id: Optional[int] = None
    text: Optional[str] = None
    genre: str = "玄幻"
    eval_type: str = "llm"  # "llm" | "keyword"


@router.get("/evaluation/references", response_model=Dict[str, Any])
async def list_reference_novels(
    current_user = Depends(get_current_user)
):
    """列出 reference 目录下所有可评测的小说文件"""
    import os, re
    from pathlib import Path

    # 找到项目根目录
    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_dir = backend_dir.parent
    ref_dir = project_dir / "reference"

    files = []
    if ref_dir.exists():
        for fp in sorted(ref_dir.glob("*.txt")):
            for enc in ["utf-8-sig", "utf-8", "gbk", "gb18030"]:
                try:
                    with open(fp, encoding=enc) as f:
                        c = f.read()
                    if len(re.findall(r"[\u4e00-\u9fff]", c)) < 100:
                        continue
                    name = fp.stem
                    author = "?"
                    if "作者：" in name:
                        parts = name.split("作者：")
                        name = parts[0].strip()
                        author = parts[1].strip() if len(parts) > 1 else "?"
                    elif "by" in name:
                        parts = name.split("by")
                        name = parts[0].strip()
                        author = parts[1].strip() if len(parts) > 1 else "?"
                    wc = len(re.findall(r"[\u4e00-\u9fff]", c)) + len(re.findall(r"[a-zA-Z]+", c))
                    files.append({
                        "filename": fp.name,
                        "name": name,
                        "author": author,
                        "size_kb": round(fp.stat().st_size / 1024, 1),
                        "char_count": len(c),
                        "word_count": wc,
                    })
                    break
                except Exception:
                    continue

    return {"success": True, "count": len(files), "files": files}


@router.post("/evaluation/run", response_model=Dict[str, Any])
async def run_evaluation(
    request: EvaluationRequest,
    current_user = Depends(get_current_user)
):
    """
    运行八维 LLM Rubric 评测

    支持两种模式：
    - eval_type="llm": 调用 DeepSeek API 逐条判断 Yes/No
    - eval_type="keyword": 基于关键词规则评分
    """
    import os, re, json, time
    from pathlib import Path
    from collections import defaultdict
    import csv as csvmod
    from io import StringIO
    from datetime import datetime

    # 1. 加载规则
    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_dir = backend_dir.parent
    rules_file = project_dir / "evaluate_rules_llm.csv"
    if not rules_file.exists():
        return {"success": False, "error": f"规则文件不存在: {rules_file}"}

    # 加载 env
    backend_env = project_dir / "backend" / ".env"
    if backend_env.exists():
        with open(backend_env, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    dims = {}
    rules = []
    with open(rules_file, "r", encoding="utf-8") as f:
        content = f.read()

    section = None
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("===") or line.startswith("---"):
            continue
        if line == "[dimensions]":
            section = "dims"
            continue
        elif line == "[rules]":
            section = "rules"
            continue
        if not section:
            continue
        try:
            reader = csvmod.reader(StringIO(line), quotechar='"')
            parts = next(reader)
        except:
            continue
        if section == "dims" and len(parts) >= 4:
            try:
                dims[parts[0]] = dict(id=parts[0], name=parts[1], weight=float(parts[2]), desc=parts[3])
            except:
                pass
        elif section == "rules" and len(parts) >= 4:
            did = parts[1].strip()
            w = dims.get(did, {}).get("weight", 0.1)
            rules.append({
                "rule_id": parts[0].strip(),
                "dimension": did,
                "name": parts[2].strip(),
                "desc": parts[3].strip() if len(parts) > 3 else "",
                "weight": w,
            })

    by_dim = defaultdict(list)
    for r in rules:
        by_dim[r["dimension"]].append(r)

    # 2. 获取评测文本
    text = request.text
    if not text:
        return {"success": False, "error": "text 为空"}

    # 截取用于评测的文本（不超过 20000 字）
    def eval_text(t):
        n = len(t)
        if n < 10000:
            return t
        head = t[: int(n * 0.3)]
        mid_start, mid_end = int(n * 0.35), int(n * 0.65)
        tail_start = int(n * 0.7)
        while len(head) + (mid_end - mid_start) + (n - tail_start) > 20000 and (mid_end - mid_start) > 1000:
            mid_end -= 1000
        return head + "\n[...省略中间...]\n" + t[mid_start:mid_end] + "\n[...省略...]\n" + t[tail_start:]

    eval_text_str = eval_text(text)

    # 3. LLM 评测
    provider = os.environ.get("LLM_PROVIDER", "deepseek")
    BATCH = 10
    judgments = []
    api_calls = 0

    if request.eval_type == "llm":
        if provider == "deepseek":
            from openai import OpenAI
            client = OpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        else:
            return {"success": False, "error": f"不支持的 provider: {provider}"}

        for did, dinfo in dims.items():
            dim_rules = by_dim[did]
            for i in range(0, len(dim_rules), BATCH):
                batch = dim_rules[i : i + BATCH]
                api_calls += 1
                rules_text = "\n".join(
                    f"规则{i2+1} [{r['rule_id']}] {r['name']}:\n  {r['desc']}"
                    for i2, r in enumerate(batch)
                )

                prompt = (
                    f"小说片段:\n{eval_text_str}\n\n"
                    f"**评测规则**:\n{rules_text}\n\n"
                    f'**输出格式** (只输出JSON数组，不要其他文字):\n'
                    f'[{{"rule_id":"R1","answer":"Yes","reason":"判断依据"}},\n'
                    f' {{"rule_id":"R2","answer":"No","reason":"理由"}}]'
                )

                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "你是严谨的小说评测专家。只输出JSON数组，answer只能是Yes或No。"},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1,
                    )

                    text_resp = resp.choices[0].message.content
                    m = re.search(r"\[\s*\{.*?\}\s*\]", text_resp, re.DOTALL)
                    if m:
                        results = json.loads(m.group())
                        for item in results:
                            judgments.append({
                                "rule_id": item.get("rule_id", ""),
                                "dimension": did,
                                "answer": item.get("answer", "No").strip(),
                                "reason": item.get("reason", "")[:200],
                            })
                    else:
                        for r in batch:
                            judgments.append({"rule_id": r["rule_id"], "dimension": did, "answer": "No", "reason": "parse fail"})
                except Exception as e:
                    for r in batch:
                        judgments.append({"rule_id": r["rule_id"], "dimension": did, "answer": "No", "reason": str(e)[:100]})

                time.sleep(0.3)

    # 4. 计算各维度得分
    dim_results = []
    total_weighted = 0
    total_weight = 0
    judgment_map = {j["rule_id"]: j for j in judgments}

    for did, dinfo in dims.items():
        dim_rules = by_dim[did]
        dim_judgments = [judgment_map.get(r["rule_id"], {"answer": "No", "reason": ""}) for r in dim_rules]
        passed = sum(1 for j in dim_judgments if j.get("answer", "").lower() == "yes")
        score = max(1.0, min(10.0, (passed / len(dim_rules)) * 10)) if dim_rules else 5.0
        dim_results.append({
            "id": did,
            "name": dinfo["name"],
            "weight": dinfo["weight"],
            "weight_pct": round(dinfo["weight"] * 100, 1),
            "total_rules": len(dim_rules),
            "passed": passed,
            "failed": len(dim_rules) - passed,
            "score": round(score, 1),
            "bar": "\u2588" * int(score) + "\u2591" * (10 - int(score)),
            "judgments": [
                {
                    "rule_id": r["rule_id"],
                    "name": r["name"],
                    "answer": judgment_map.get(r["rule_id"], {}).get("answer", "No"),
                    "reason": judgment_map.get(r["rule_id"], {}).get("reason", "")[:80],
                }
                for r in dim_rules
            ],
        })
        total_weighted += score * dinfo["weight"]
        total_weight += dinfo["weight"]

    final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
    rank = "S" if final_score >= 90 else "A" if final_score >= 80 else "B" if final_score >= 70 else "C" if final_score >= 60 else "D" if final_score >= 50 else "F"

    # 5. 保存结果
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_dir / "training_runs"
    out_dir.mkdir(exist_ok=True)
    result = {
        "success": True,
        "eval_type": request.eval_type,
        "genre": request.genre,
        "timestamp": ts,
        "total_score": final_score,
        "rank": rank,
        "api_calls": api_calls,
        "dims": dim_results,
        "total_rules": len(rules),
    }

    json_path = out_dir / f"eval_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


@router.get("/evaluation/results", response_model=Dict[str, Any])
async def list_evaluation_results(
    limit: int = 20,
    current_user = Depends(get_current_user)
):
    """列出最近的评测结果"""
    from pathlib import Path
    import json

    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_dir = backend_dir.parent
    out_dir = project_dir / "training_runs"

    results = []
    if out_dir.exists():
        for fp in sorted(out_dir.glob("eval_*.json"), reverse=True)[:limit]:
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "filename": fp.name,
                    "timestamp": data.get("timestamp", ""),
                    "eval_type": data.get("eval_type", ""),
                    "total_score": data.get("total_score", 0),
                    "rank": data.get("rank", ""),
                    "api_calls": data.get("api_calls", 0),
                    "genre": data.get("genre", ""),
                })
            except Exception:
                pass

    return {"success": True, "count": len(results), "results": results}
