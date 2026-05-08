"""
评测规则优化分析系统

通过循环采样好小说和坏小说片段，分析评分差异，识别需要调整权重的规则。
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger

from app.core.auth import get_current_user

router = APIRouter(prefix="/training/evaluation", tags=["evaluation-optimizer"])


# ========== 请求/响应模型 ==========

class RuleAnalysisRequest(BaseModel):
    """规则分析请求"""
    good_novel_files: List[str]  # 好小说文件名列表（如 ["凡人修仙传.txt"]）
    bad_novel_files: List[str]   # 坏小说文件名列表
    blocks_per_novel: int = 5    # 每本小说采样块数
    max_bytes_per_block: int = 8000  # 每块最大字节数
    genre: str = "玄幻"


class IterativeOptimizationRequest(BaseModel):
    """迭代优化请求"""
    good_novel_files: List[str]
    bad_novel_files: List[str]
    blocks_per_novel: int = 5
    max_bytes_per_block: int = 8000
    genre: str = "玄幻"
    max_iterations: int = 10           # 最大迭代次数
    discrimination_threshold: float = 0.6  # 区分度阈值
    convergence_window: int = 3        # 收敛判断窗口
    convergence_threshold: float = 0.01    # 收敛阈值


class RuleAdjustment(BaseModel):
    """单条规则调整建议"""
    rule_id: str
    dimension: str
    name: str
    current_weight: float
    suggested_weight: float
    reason: str
    good_pass_rate: float  # 好小说通过率
    bad_pass_rate: float   # 坏小说通过率
    discrimination: float  # 区分度 (good_pass_rate - bad_pass_rate)
    action: str = "keep"  # 操作类型: keep(保持)/modify(修改)/delete(删除)/merge(合并)
    merge_target: str = ""  # 如果是merge，目标规则ID
    consistency_score: float = 0.0  # 一致性得分（同一小说内方差倒数）


class DimensionAnalysis(BaseModel):
    """维度分析结果"""
    dimension_id: str
    dimension_name: str
    current_weight: float
    suggested_weight: float
    avg_discrimination: float
    rules_count: int


class OptimizationReport(BaseModel):
    """优化报告"""
    created_at: str
    total_samples: int
    good_novels: List[str]
    bad_novels: List[str]
    
    # 规则级别分析
    rule_adjustments: List[RuleAdjustment]
    
    # 维度级别分析
    dimension_analysis: List[DimensionAnalysis]
    
    # 一致性分析
    consistency_issues: List[Dict[str, Any]]
    
    # 建议
    recommendations: List[str]
    
    # 原始数据（用于进一步分析）
    raw_data: Dict[str, Any]


# ========== 核心分析逻辑 ==========

async def _run_sampled_evaluation(
    text: str,
    num_blocks: int,
    max_bytes: int,
    genre: str,
    client,
    model_name: str,
    progress_queue=None,
    novel_name: str = "",
    novel_type: str = "",
    current_novel_idx: int = 0,
    total_novels: int = 0
) -> Dict[str, Any]:
    """
    运行采样评测，返回每块每规则的详细结果
    
    优化: 每个维度调用一次API，让LLM同时评判该维度下的所有规则
    
    Args:
        progress_queue: 可选的异步队列，用于发送进度消息
        novel_name: 小说文件名（用于进度显示）
        novel_type: 小说类型 good/bad（用于进度显示）
        current_novel_idx: 当前小说序号（用于进度显示）
        total_novels: 总小说数（用于进度显示）
    """
    from .training import _split_into_blocks, _sample_blocks, _load_rules_and_dims
    
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent
    
    dims, by_dim, err = _load_rules_and_dims(project_dir)
    if err:
        raise ValueError(err)
    
    # 切块和采样
    all_blocks = _split_into_blocks(text, max_bytes)
    if not all_blocks:
        raise ValueError("文本为空或无法切分")
    
    sampled = _sample_blocks(all_blocks, num_blocks)
    
    # 计算总API调用次数: 每块 × 维度数
    num_dims = len(dims)
    total_api_calls = len(sampled) * num_dims
    
    logger.info(f"开始采样评测: {len(sampled)} 块 × {num_dims} 维度 = {total_api_calls} 次API调用")
    
    # 辅助函数：发送进度消息
    async def send_progress(current, total, msg):
        if progress_queue:
            logger.info(f"[send_progress] Sending: {msg}")
            await progress_queue.put({
                "type": "progress",
                "stage": "evaluating",
                "novel": novel_name,
                "novel_type": novel_type,
                "progress": f"{current_novel_idx + 1}/{total_novels}",
                "api_calls": current,
                "total_calls": total,
                "message": msg,
            })
            logger.info(f"[send_progress] Sent: {msg}")
    
    # 逐块评测（每个维度调用一次API）
    block_results = []
    current_api_call = 0
    
    logger.info(f"[DEBUG] Starting loop: {len(sampled)} blocks, {len(dims)} dims")
    
    for block_idx, (orig_idx, block_text) in enumerate(sampled):
        block_judgments = {}
        
        logger.info(f"[DEBUG] Block {block_idx + 1}/{len(sampled)}")
        await send_progress(current_api_call, total_api_calls, f"开始评测第 {block_idx + 1}/{len(sampled)} 块")
        
        dim_count = 0
        for did, dinfo in dims.items():
            dim_count += 1
            logger.info(f"[DEBUG] Dim {dim_count}/{len(dims)}: {did}")
            dim_rules = by_dim[did]
            current_api_call += 1
            
            dim_name = dinfo.get('name', did)
            logger.info(f"[DEBUG] Sending progress for dim: {dim_name}")
            await send_progress(current_api_call, total_api_calls, f"评测维度: {dim_name} ({len(dim_rules)} 条规则)")
            logger.info(f"[DEBUG] Progress sent for dim: {dim_name}")
            
            # 构建该维度所有规则的提示文本
            rules_text = "\n".join(
                f"规则{i+1} [{r['rule_id']}] {r['name']}:\n  {r['desc']}"
                for i, r in enumerate(dim_rules)
            )
            
            # 构建输出格式示例（根据规则数量动态生成）
            example_items = ',\n'.join([
                f'  {{"rule_id":"{r["rule_id"]}","answer":"Yes/No","reason":"判断依据"}}'
                for r in dim_rules[:3]  # 只显示前3条作为示例
            ])
            if len(dim_rules) > 3:
                example_items += ',\n  ...'
            
            prompt = (
                f"你是一位严谨的小说质量评测专家。请根据以下小说片段，"
                f"对【{dim_name}】维度下的 {len(dim_rules)} 条规则进行评判。\n\n"
                f"小说片段:\n{'='*40}\n{block_text[:3000]}{'...' if len(block_text) > 3000 else ''}\n{'='*40}\n\n"
                f"**评测规则**:\n{rules_text}\n\n"
                f'**输出要求**:\n'
                f'1. 对每条规则判断该片段是否符合要求（Yes/No）\n'
                f'2. 给出简要判断依据（50字以内）\n'
                f'3. 只输出JSON数组，不要其他文字\n\n'
                f'**输出格式**:\n'
                f'[\n{example_items}\n]'
            )
            
            try:
                logger.info(f"[DEBUG] Calling API for dim: {dim_name}")
                resp = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "你是严谨的小说评测专家。只输出JSON数组，answer只能是Yes或No。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=2000,  # 确保有足够token输出所有规则的结果
                )
                
                text_resp = resp.choices[0].message.content
                logger.info(f"API响应长度: {len(text_resp)} 字符")
                import re
                
                # 尝试提取JSON数组
                m = re.search(r"\[\s*\{.*?\}\s*\]", text_resp, re.DOTALL)
                if m:
                    results = json.loads(m.group())
                    for item in results:
                        rule_id = item.get("rule_id", "")
                        if rule_id:
                            block_judgments[rule_id] = {
                                "answer": item.get("answer", "No").strip(),
                                "reason": item.get("reason", "")[:200],
                            }
                else:
                    # 尝试直接解析整个响应
                    try:
                        results = json.loads(text_resp)
                        if isinstance(results, list):
                            for item in results:
                                rule_id = item.get("rule_id", "")
                                if rule_id:
                                    block_judgments[rule_id] = {
                                        "answer": item.get("answer", "No").strip(),
                                        "reason": item.get("reason", "")[:200],
                                    }
                    except:
                        logger.warning(f"无法解析响应: {text_resp[:200]}")
                
                # 确保该维度所有规则都有结果
                for r in dim_rules:
                    if r["rule_id"] not in block_judgments:
                        block_judgments[r["rule_id"]] = {"answer": "No", "reason": "未返回结果"}
                        
            except Exception as e:
                logger.error(f"[DEBUG] API call failed for dim {dim_name}: {e}")
                # 该维度所有规则标记为失败
                for r in dim_rules:
                    block_judgments[r["rule_id"]] = {"answer": "No", "reason": str(e)[:100]}
            
            logger.info(f"[DEBUG] Finished dim: {dim_name}")
            await asyncio.sleep(0.2)  # 减少延迟，因为调用次数大幅减少
        
        block_results.append({
            "block_index": block_idx,
            "original_index": orig_idx,
            "judgments": block_judgments,
        })
    
    logger.info(f"[DEBUG] Loop finished, total API calls: {current_api_call}")
    
    return {
        "blocks": block_results,
        "dims": dims,
        "by_dim": {k: [{"rule_id": r["rule_id"], "name": r["name"], "weight": r["weight"]} for r in v] 
                   for k, v in by_dim.items()},
        "total_api_calls": total_api_calls,
    }


def _analyze_rule_discrimination(
    good_results: List[Dict],
    bad_results: List[Dict],
    dims: Dict,
    by_dim: Dict
) -> Tuple[List[RuleAdjustment], List[DimensionAnalysis]]:
    """
    分析每条规则的区分度
    """
    # 收集每条规则的通过情况
    rule_stats = defaultdict(lambda: {"good_pass": 0, "good_total": 0, "bad_pass": 0, "bad_total": 0})
    
    # 处理好小说结果
    for novel_result in good_results:
        for block in novel_result["blocks"]:
            for rule_id, judgment in block["judgments"].items():
                rule_stats[rule_id]["good_total"] += 1
                if judgment["answer"].lower() == "yes":
                    rule_stats[rule_id]["good_pass"] += 1
    
    # 处理坏小说结果
    for novel_result in bad_results:
        for block in novel_result["blocks"]:
            for rule_id, judgment in block["judgments"].items():
                rule_stats[rule_id]["bad_total"] += 1
                if judgment["answer"].lower() == "yes":
                    rule_stats[rule_id]["bad_pass"] += 1
    
    # 计算每条规则的区分度和调整建议
    rule_adjustments = []
    dim_discrimination = defaultdict(list)
    
    for rule_id, stats in rule_stats.items():
        # 找到规则所属维度
        dimension = None
        rule_info = None
        for dim_id, rules in by_dim.items():
            for r in rules:
                if r["rule_id"] == rule_id:
                    dimension = dim_id
                    rule_info = r
                    break
            if dimension:
                break
        
        if not rule_info:
            continue
        
        # 计算通过率
        good_pass_rate = stats["good_pass"] / stats["good_total"] if stats["good_total"] > 0 else 0
        bad_pass_rate = stats["bad_pass"] / stats["bad_total"] if stats["bad_total"] > 0 else 0
        discrimination = good_pass_rate - bad_pass_rate
        
        dim_discrimination[dimension].append(discrimination)
        
        # 判断操作类型和权重调整
        current_weight = rule_info.get("weight", 0.1)
        suggested_weight = current_weight
        action = "keep"
        merge_target = ""
        reason = ""
        
        # 计算一致性得分（需要后续补充，这里先设为0）
        consistency_score = 0.0
        
        # 判断逻辑：
        # 1. DELETE: 反向区分（坏小说通过率 > 好小说通过率）
        # 2. DELETE: 区分度极低且两头不靠（通过率都在30%-70%之间但区分度<0.05）
        # 3. MODIFY: 区分度低但可以调整（过于宽松或过于严格）
        # 4. MERGE: 同一维度内相似度高的规则（后续处理）
        # 5. KEEP: 区分度良好
        
        if discrimination < -0.1:
            # 反向区分 - 坏小说通过率更高，应该删除
            action = "delete"
            reason = f"❌ 建议删除：规则反向区分({discrimination:.2f})，坏小说通过率({bad_pass_rate:.1%})高于好小说({good_pass_rate:.1%})，说明规则定义有问题"
            suggested_weight = 0.0
        elif discrimination < 0.05 and (good_pass_rate > 0.3 and good_pass_rate < 0.7) and (bad_pass_rate > 0.3 and bad_pass_rate < 0.7):
            # 区分度极低且处于中间地带 - 建议删除
            action = "delete"
            reason = f"❌ 建议删除：区分度极低({discrimination:.2f})，好/坏小说通过率都在中间区间({good_pass_rate:.1%}/{bad_pass_rate:.1%})，规则无区分能力"
            suggested_weight = 0.0
        elif discrimination < 0.1:
            # 区分度低，但可以尝试修改
            action = "modify"
            if good_pass_rate > 0.7 and bad_pass_rate > 0.7:
                reason = f"📝 建议修改：规则过于宽松，好/坏小说通过率都高({good_pass_rate:.1%}/{bad_pass_rate:.1%})，建议收紧规则描述或降低权重"
                suggested_weight = current_weight * 0.5
            elif good_pass_rate < 0.3 and bad_pass_rate < 0.3:
                reason = f"📝 建议修改：规则过于严格，好/坏小说通过率都低({good_pass_rate:.1%}/{bad_pass_rate:.1%})，建议放宽规则描述或降低权重"
                suggested_weight = current_weight * 0.5
            else:
                reason = f"📝 建议修改：区分度不足({discrimination:.2f})，规则无法有效区分好/坏小说，建议重新设计规则描述"
                suggested_weight = current_weight * 0.7
        elif discrimination > 0.5:
            # 区分度很好
            action = "keep"
            reason = f"✅ 保持现状：区分度优秀({discrimination:.2f})，好小说通过率{good_pass_rate:.1%}，坏小说{bad_pass_rate:.1%}"
            suggested_weight = min(current_weight * 1.2, 0.15)  # 上限0.15
        elif discrimination < 0:
            # 轻微反向，尝试修改
            action = "modify"
            reason = f"📝 建议修改：轻微反向区分({discrimination:.2f})，坏小说通过率高于好小说，建议调整规则描述"
            suggested_weight = current_weight * 0.6
        else:
            # 区分度一般
            action = "keep"
            reason = f"✅ 保持现状：区分度一般({discrimination:.2f})，好小说通过率{good_pass_rate:.1%}，坏小说{bad_pass_rate:.1%}"
        
        rule_adjustments.append(RuleAdjustment(
            rule_id=rule_id,
            dimension=dimension or "unknown",
            name=rule_info.get("name", ""),
            current_weight=current_weight,
            suggested_weight=round(suggested_weight, 3),
            reason=reason,
            good_pass_rate=round(good_pass_rate, 3),
            bad_pass_rate=round(bad_pass_rate, 3),
            discrimination=round(discrimination, 3),
            action=action,
            merge_target=merge_target,
            consistency_score=round(consistency_score, 3),
        ))
    
    # 按区分度排序
    rule_adjustments.sort(key=lambda x: abs(x.discrimination), reverse=True)
    
    # 维度级别分析
    dimension_analysis = []
    for dim_id, discriminations in dim_discrimination.items():
        if not discriminations:
            continue
        avg_discrimination = sum(discriminations) / len(discriminations)
        current_weight = dims.get(dim_id, {}).get("weight", 0.1)
        
        # 根据平均区分度建议维度权重
        if avg_discrimination > 0.4:
            suggested_dim_weight = min(current_weight * 1.15, 0.25)
        elif avg_discrimination < 0.1:
            suggested_dim_weight = current_weight * 0.85
        else:
            suggested_dim_weight = current_weight
        
        dimension_analysis.append(DimensionAnalysis(
            dimension_id=dim_id,
            dimension_name=dims.get(dim_id, {}).get("name", dim_id),
            current_weight=current_weight,
            suggested_weight=round(suggested_dim_weight, 3),
            avg_discrimination=round(avg_discrimination, 3),
            rules_count=len(discriminations),
        ))
    
    # 按区分度排序
    dimension_analysis.sort(key=lambda x: x.avg_discrimination, reverse=True)
    
    return rule_adjustments, dimension_analysis


def _analyze_consistency(
    good_results: List[Dict],
    bad_results: List[Dict]
) -> List[Dict[str, Any]]:
    """
    分析同一小说内部的评分一致性
    """
    issues = []
    
    all_results = [("good", r) for r in good_results] + [("bad", r) for r in bad_results]
    
    for novel_type, novel_result in all_results:
        blocks = novel_result["blocks"]
        if len(blocks) < 2:
            continue
        
        # 计算每块的总分
        block_scores = []
        for block in blocks:
            yes_count = sum(1 for j in block["judgments"].values() if j["answer"].lower() == "yes")
            total = len(block["judgments"])
            score = yes_count / total if total > 0 else 0
            block_scores.append(score)
        
        # 计算方差
        if len(block_scores) >= 2:
            avg_score = sum(block_scores) / len(block_scores)
            variance = sum((s - avg_score) ** 2 for s in block_scores) / len(block_scores)
            std_dev = variance ** 0.5
            
            # 如果方差太大，说明同一小说内部评分不一致
            if std_dev > 0.2:
                issues.append({
                    "novel_type": novel_type,
                    "block_scores": [round(s, 3) for s in block_scores],
                    "average": round(avg_score, 3),
                    "std_dev": round(std_dev, 3),
                    "issue": "同一小说内部评分差异过大",
                    "suggestion": "某些规则可能不适合短文本采样评测，建议标记为'长文本规则'"
                })
    
    return issues


def _analyze_rule_merges(
    rule_adjustments: List[RuleAdjustment],
    good_results: List[Dict],
    bad_results: List[Dict]
) -> List[RuleAdjustment]:
    """
    分析哪些规则可以合并
    合并条件：
    1. 同一维度内
    2. 区分度相似（差值 < 0.1）
    3. 通过率模式相似（好/坏小说通过率都接近）
    4. 规则名称语义相似（简单判断：包含相同关键词）
    """
    # 按维度分组
    by_dimension = defaultdict(list)
    for rule in rule_adjustments:
        if rule.action == "keep":  # 只考虑保持的规则
            by_dimension[rule.dimension].append(rule)
    
    # 标记可合并的规则
    merge_groups = []
    
    for dim_id, rules in by_dimension.items():
        if len(rules) < 2:
            continue
        
        # 按区分度排序
        rules_sorted = sorted(rules, key=lambda r: r.discrimination)
        
        # 查找相似规则对
        used = set()
        for i, rule1 in enumerate(rules_sorted):
            if rule1.rule_id in used:
                continue
            
            group = [rule1]
            for j, rule2 in enumerate(rules_sorted[i+1:], i+1):
                if rule2.rule_id in used:
                    continue
                
                # 检查区分度相似性
                disc_diff = abs(rule1.discrimination - rule2.discrimination)
                # 检查通过率模式相似性
                good_diff = abs(rule1.good_pass_rate - rule2.good_pass_rate)
                bad_diff = abs(rule1.bad_pass_rate - rule2.bad_pass_rate)
                
                # 合并条件：区分度差 < 0.1，通过率差都 < 0.15
                if disc_diff < 0.1 and good_diff < 0.15 and bad_diff < 0.15:
                    group.append(rule2)
                    used.add(rule2.rule_id)
            
            if len(group) >= 2:
                merge_groups.append(group)
                used.add(rule1.rule_id)
    
    # 更新规则的合并标记
    for group in merge_groups:
        # 选择第一个作为主规则
        main_rule = group[0]
        for rule in group[1:]:
            # 找到对应的 rule_adjustment 并更新
            for ra in rule_adjustments:
                if ra.rule_id == rule.rule_id:
                    ra.action = "merge"
                    ra.merge_target = main_rule.rule_id
                    ra.reason = f"🔗 建议合并到 {main_rule.rule_id} ({main_rule.name})：区分度({rule.discrimination:.2f})和通过率模式与主规则相似"
                    break
    
    return rule_adjustments


def _generate_recommendations(
    rule_adjustments: List[RuleAdjustment],
    dimension_analysis: List[DimensionAnalysis],
    consistency_issues: List[Dict]
) -> List[str]:
    """
    生成优化建议
    """
    recommendations = []
    
    # 统计各类操作
    delete_rules = [r for r in rule_adjustments if r.action == "delete"]
    modify_rules = [r for r in rule_adjustments if r.action == "modify"]
    merge_rules = [r for r in rule_adjustments if r.action == "merge"]
    keep_rules = [r for r in rule_adjustments if r.action == "keep"]
    
    # 0. 总体统计
    recommendations.append(
        f"📊 规则分析完成：共 {len(rule_adjustments)} 条规则，"
        f"建议删除 {len(delete_rules)} 条，修改 {len(modify_rules)} 条，"
        f"合并 {len(merge_rules)} 条，保持 {len(keep_rules)} 条"
    )
    
    # 1. 建议删除的规则
    if delete_rules:
        reverse = [r for r in delete_rules if r.discrimination < 0]
        useless = [r for r in delete_rules if r.discrimination >= 0]
        if reverse:
            recommendations.append(
                f"❌ 发现 {len(reverse)} 条反向区分的规则（坏小说通过率更高），"
                f"建议直接删除。典型例子: {reverse[0].rule_id} ({reverse[0].name})"
            )
        if useless:
            recommendations.append(
                f"❌ 发现 {len(useless)} 条区分度极低的规则，"
                f"无法区分好/坏小说，建议删除。"
                f"典型例子: {useless[0].rule_id} ({useless[0].name})"
            )
    
    # 2. 建议修改的规则
    if modify_rules:
        too_loose = [r for r in modify_rules if r.good_pass_rate > 0.7 and r.bad_pass_rate > 0.7]
        too_strict = [r for r in modify_rules if r.good_pass_rate < 0.3 and r.bad_pass_rate < 0.3]
        if too_loose:
            recommendations.append(
                f"📝 发现 {len(too_loose)} 条过于宽松的规则，"
                f"好/坏小说通过率都高，建议收紧描述。"
                f"典型例子: {too_loose[0].rule_id} ({too_loose[0].name})"
            )
        if too_strict:
            recommendations.append(
                f"📝 发现 {len(too_strict)} 条过于严格的规则，"
                f"好/坏小说通过率都低，建议放宽描述。"
                f"典型例子: {too_strict[0].rule_id} ({too_strict[0].name})"
            )
    
    # 3. 建议合并的规则
    if merge_rules:
        recommendations.append(
            f"🔗 发现 {len(merge_rules)} 条可合并的规则，"
            f"这些规则区分度和通过率模式相似，建议合并以减少冗余。"
            f"典型例子: {merge_rules[0].rule_id} → {merge_rules[0].merge_target}"
        )
    
    # 4. 一致性问题的规则
    if consistency_issues:
        recommendations.append(
            f"⚠️ 发现 {len(consistency_issues)} 本小说存在内部评分不一致问题，"
            f"建议识别'长文本规则'（需要上下文才能判断的规则），"
            f"在采样评测时降低这些规则的权重或跳过。"
        )
    
    # 5. 维度权重调整
    high_disc_dims = [d for d in dimension_analysis if d.avg_discrimination > 0.4]
    if high_disc_dims:
        recommendations.append(
            f"✅ 维度 '{high_disc_dims[0].dimension_name}' 区分度优秀({high_disc_dims[0].avg_discrimination:.2f})，"
            f"建议将权重从 {high_disc_dims[0].current_weight} 提高到 {high_disc_dims[0].suggested_weight}"
        )
    
    low_disc_dims = [d for d in dimension_analysis if d.avg_discrimination < 0.1]
    if low_disc_dims:
        recommendations.append(
            f"⚠️ 维度 '{low_disc_dims[0].dimension_name}' 区分度不足({low_disc_dims[0].avg_discrimination:.2f})，"
            f"建议将权重从 {low_disc_dims[0].current_weight} 降低到 {low_disc_dims[0].suggested_weight}，"
            f"或修改该维度下的规则描述"
        )
    
    # 5. 采样策略建议
    recommendations.append(
        "建议将规则分为两类：'短文本规则'（可从片段判断）和'长文本规则'（需要整本上下文）。"
        "采样评测时主要使用短文本规则，整本评测时再使用全部规则。"
    )
    
    return recommendations


# ========== API 端点 ==========

@router.post("/analyze-rules", response_model=OptimizationReport)
async def analyze_evaluation_rules(
    request: RuleAnalysisRequest,
    current_user = Depends(get_current_user)
):
    """
    分析评测规则的区分度和一致性，生成优化建议
    
    示例请求:
    {
        "good_novel_files": ["凡人修仙传.txt"],
        "bad_novel_files": ["废土求生：我有修仙模板.txt"],
        "blocks_per_novel": 5,
        "max_bytes_per_block": 8000,
        "genre": "玄幻"
    }
    """
    from .training import _get_llm_client
    
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent
    reference_dir = project_dir / "reference"
    
    # 验证文件是否存在，提供更好的错误提示
    all_files = {f.name for f in reference_dir.glob("*.txt")} if reference_dir.exists() else set()
    
    missing_files = []
    for filename in request.good_novel_files + request.bad_novel_files:
        if filename not in all_files:
            missing_files.append(filename)
    
    if missing_files:
        # 尝试模糊匹配
        suggestions = {}
        for mf in missing_files:
            for af in all_files:
                if mf.replace('.txt', '') in af or af.replace('.txt', '') in mf:
                    suggestions[mf] = af
        
        hint = ""
        if suggestions:
            hint = "\n可能是指：" + ", ".join(f"{k} -> {v}" for k, v in suggestions.items())
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在: {missing_files}。可用文件: {len(all_files)}个{hint}"
        )
    
    logger.info(f"开始规则分析: 好小说={request.good_novel_files}, 坏小说={request.bad_novel_files}")
    
    # 获取 LLM 客户端
    try:
        client, model_name = _get_llm_client()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 客户端初始化失败: {e}")
    
    # 读取并评测好小说
    good_results = []
    for filename in request.good_novel_files:
        file_path = reference_dir / filename
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        result = await _run_sampled_evaluation(
            text, request.blocks_per_novel, request.max_bytes_per_block,
            request.genre, client, model_name
        )
        result["filename"] = filename
        result["novel_type"] = "good"
        good_results.append(result)
    
    # 读取并评测坏小说
    bad_results = []
    for filename in request.bad_novel_files:
        file_path = reference_dir / filename
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        result = await _run_sampled_evaluation(
            text, request.blocks_per_novel, request.max_bytes_per_block,
            request.genre, client, model_name
        )
        result["filename"] = filename
        result["novel_type"] = "bad"
        bad_results.append(result)
    
    # 获取维度信息
    dims = good_results[0]["dims"] if good_results else {}
    by_dim = good_results[0]["by_dim"] if good_results else {}
    
    # 分析规则区分度
    rule_adjustments, dimension_analysis = _analyze_rule_discrimination(
        good_results, bad_results, dims, by_dim
    )
    
    # 分析一致性
    consistency_issues = _analyze_consistency(good_results, bad_results)
    
    # 生成建议
    recommendations = _generate_recommendations(
        rule_adjustments, dimension_analysis, consistency_issues
    )
    
    # 构建报告
    report = OptimizationReport(
        created_at=datetime.now().isoformat(),
        total_samples=len(good_results) + len(bad_results),
        good_novels=request.good_novel_files,
        bad_novels=request.bad_novel_files,
        rule_adjustments=rule_adjustments,
        dimension_analysis=dimension_analysis,
        consistency_issues=consistency_issues,
        recommendations=recommendations,
        raw_data={
            "good_results": [{"filename": r["filename"], "blocks_count": len(r["blocks"])} for r in good_results],
            "bad_results": [{"filename": r["filename"], "blocks_count": len(r["blocks"])} for r in bad_results],
        }
    )
    
    return report


@router.post("/analyze-rules/stream")
async def analyze_evaluation_rules_stream(
    request: RuleAnalysisRequest,
    current_user = Depends(get_current_user)
):
    """
    流式返回规则分析进度和结果
    """
    from fastapi.responses import StreamingResponse
    
    async def generate():
        from .training import _get_llm_client
        import asyncio
        
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        project_dir = backend_dir.parent
        reference_dir = project_dir / "reference"
        
        logger.info(f"开始规则分析，参考目录: {reference_dir}")
        
        try:
            client, model_name = _get_llm_client()
            logger.info(f"LLM客户端初始化成功，模型: {model_name}")
        except ValueError as e:
            logger.error(f"LLM客户端初始化失败: {e}")
            yield json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False) + "\n"
            return
        except Exception as e:
            logger.error(f"LLM客户端初始化异常: {e}")
            yield json.dumps({"type": "error", "error": f"初始化失败: {str(e)}"}, ensure_ascii=False) + "\n"
            return
        
        total_novels = len(request.good_novel_files) + len(request.bad_novel_files)
        processed = 0
        
        good_results = []
        bad_results = []
        
        # 处理好小说
        for idx, filename in enumerate(request.good_novel_files):
            yield json.dumps({
                "type": "progress",
                "stage": "evaluating",
                "novel": filename,
                "novel_type": "good",
                "progress": f"{processed}/{total_novels}",
                "message": f"开始评测好小说: {filename}",
            }, ensure_ascii=False) + "\n"
            
            file_path = reference_dir / filename
            if not file_path.exists():
                yield json.dumps({
                    "type": "error",
                    "error": f"文件不存在: {filename} (查找路径: {file_path})"
                }, ensure_ascii=False) + "\n"
                return
            
            yield json.dumps({
                "type": "progress",
                "stage": "evaluating",
                "novel": filename,
                "novel_type": "good",
                "progress": f"{processed}/{total_novels}",
                "message": f"正在读取文件: {filename}",
            }, ensure_ascii=False) + "\n"
            
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            
            yield json.dumps({
                "type": "progress",
                "stage": "evaluating",
                "novel": filename,
                "novel_type": "good",
                "progress": f"{processed}/{total_novels}",
                "message": f"文件读取完成: {len(text)} 字符，开始采样评测...",
            }, ensure_ascii=False) + "\n"
            
            # 创建进度队列
            progress_queue = asyncio.Queue()
            
            # 启动评测任务
            eval_task = asyncio.create_task(_run_sampled_evaluation(
                text, request.blocks_per_novel, request.max_bytes_per_block,
                request.genre, client, model_name,
                progress_queue=progress_queue,
                novel_name=filename,
                novel_type="good",
                current_novel_idx=idx,
                total_novels=total_novels
            ))
            
            # 等待评测完成，同时转发进度消息
            logger.info(f"开始评测 {filename}，等待进度消息...")
            last_progress_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # 创建队列读取任务
                    queue_task = asyncio.create_task(progress_queue.get())
                    
                    # 等待队列消息或任务完成
                    done, pending = await asyncio.wait(
                        [queue_task, eval_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=300.0
                    )
                    
                    logger.info(f"收到事件，完成的任务数: {len(done)}, 待处理: {len(pending)}")
                    last_progress_time = asyncio.get_event_loop().time()
                    
                    # 处理已完成的任务
                    eval_completed = False
                    progress_received = False
                    
                    for task in done:
                        if task is eval_task:
                            # 评测完成
                            logger.info(f"评测任务完成: {filename}")
                            try:
                                result = task.result()
                                result["filename"] = filename
                                result["novel_type"] = "good"
                                good_results.append(result)
                                processed += 1
                                
                                yield json.dumps({
                                    "type": "progress",
                                    "stage": "evaluating",
                                    "novel": filename,
                                    "novel_type": "good",
                                    "progress": f"{processed}/{total_novels}",
                                    "message": f"完成评测: {filename} (共 {result.get('total_api_calls', 0)} 次API调用)",
                                }, ensure_ascii=False) + "\n"
                            except Exception as e:
                                logger.error(f"获取评测结果失败: {e}")
                            eval_completed = True
                        elif task is queue_task:
                            # 收到进度消息
                            try:
                                progress_msg = task.result()
                                logger.info(f"进度消息: {progress_msg.get('message', '')}")
                                yield json.dumps(progress_msg, ensure_ascii=False) + "\n"
                                progress_received = True
                            except Exception as e:
                                logger.warning(f"获取进度消息失败: {e}")
                    
                    # 取消未完成的任务（但不要取消 eval_task）
                    for task in pending:
                        if task is not eval_task:
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                    
                    if eval_completed:
                        # 继续读取队列中剩余的消息
                        while not progress_queue.empty():
                            try:
                                remaining_msg = progress_queue.get_nowait()
                                logger.info(f"剩余进度消息: {remaining_msg.get('message', '')}")
                                yield json.dumps(remaining_msg, ensure_ascii=False) + "\n"
                            except asyncio.QueueEmpty:
                                break
                        break
                except asyncio.TimeoutError:
                    elapsed = asyncio.get_event_loop().time() - last_progress_time
                    logger.warning(f"评测 {filename} 超时（已等待 {elapsed:.0f}秒），继续等待...")
                    yield json.dumps({
                        "type": "progress",
                        "stage": "evaluating",
                        "message": f"等待评测进度...（已等待 {elapsed:.0f}秒）",
                    }, ensure_ascii=False) + "\n"
        
        # 处理坏小说
        bad_start_idx = len(request.good_novel_files)
        for idx, filename in enumerate(request.bad_novel_files):
            actual_idx = bad_start_idx + idx
            yield json.dumps({
                "type": "progress",
                "stage": "evaluating",
                "novel": filename,
                "novel_type": "bad",
                "progress": f"{processed}/{total_novels}",
                "message": f"开始评测坏小说: {filename}",
            }, ensure_ascii=False) + "\n"
            
            file_path = reference_dir / filename
            if not file_path.exists():
                yield json.dumps({
                    "type": "error",
                    "error": f"文件不存在: {filename} (查找路径: {file_path})"
                }, ensure_ascii=False) + "\n"
                return
            
            yield json.dumps({
                "type": "progress",
                "stage": "evaluating",
                "novel": filename,
                "novel_type": "bad",
                "progress": f"{processed}/{total_novels}",
                "message": f"正在读取文件: {filename}",
            }, ensure_ascii=False) + "\n"
            
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            
            yield json.dumps({
                "type": "progress",
                "stage": "evaluating",
                "novel": filename,
                "novel_type": "bad",
                "progress": f"{processed}/{total_novels}",
                "message": f"文件读取完成: {len(text)} 字符，开始采样评测...",
            }, ensure_ascii=False) + "\n"
            
            # 创建进度队列
            progress_queue = asyncio.Queue()
            
            # 启动评测任务
            eval_task = asyncio.create_task(_run_sampled_evaluation(
                text, request.blocks_per_novel, request.max_bytes_per_block,
                request.genre, client, model_name,
                progress_queue=progress_queue,
                novel_name=filename,
                novel_type="bad",
                current_novel_idx=actual_idx,
                total_novels=total_novels
            ))
            
            # 等待评测完成，同时转发进度消息
            logger.info(f"开始评测坏小说 {filename}，等待进度消息...")
            last_progress_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    queue_task = asyncio.create_task(progress_queue.get())
                    done, pending = await asyncio.wait(
                        [queue_task, eval_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=300.0
                    )
                    
                    logger.info(f"坏小说收到事件，完成的任务数: {len(done)}, 待处理: {len(pending)}")
                    last_progress_time = asyncio.get_event_loop().time()
                    
                    # 处理已完成的任务
                    eval_completed = False
                    
                    for task in done:
                        if task is eval_task:
                            logger.info(f"坏小说评测任务完成: {filename}")
                            try:
                                result = task.result()
                                result["filename"] = filename
                                result["novel_type"] = "bad"
                                bad_results.append(result)
                                processed += 1
                                
                                yield json.dumps({
                                    "type": "progress",
                                    "stage": "evaluating",
                                    "novel": filename,
                                    "novel_type": "bad",
                                    "progress": f"{processed}/{total_novels}",
                                    "message": f"完成评测: {filename} (共 {result.get('total_api_calls', 0)} 次API调用)",
                                }, ensure_ascii=False) + "\n"
                            except Exception as e:
                                logger.error(f"获取坏小说评测结果失败: {e}")
                            eval_completed = True
                        elif task is queue_task:
                            try:
                                progress_msg = task.result()
                                logger.info(f"坏小说进度消息: {progress_msg.get('message', '')}")
                                yield json.dumps(progress_msg, ensure_ascii=False) + "\n"
                            except Exception as e:
                                logger.warning(f"获取坏小说进度消息失败: {e}")
                    
                    # 取消未完成的任务（但不要取消 eval_task）
                    for task in pending:
                        if task is not eval_task:
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                    
                    if eval_completed:
                        # 继续读取队列中剩余的消息
                        while not progress_queue.empty():
                            try:
                                remaining_msg = progress_queue.get_nowait()
                                logger.info(f"坏小说剩余进度消息: {remaining_msg.get('message', '')}")
                                yield json.dumps(remaining_msg, ensure_ascii=False) + "\n"
                            except asyncio.QueueEmpty:
                                break
                        break
                except asyncio.TimeoutError:
                    elapsed = asyncio.get_event_loop().time() - last_progress_time
                    logger.warning(f"坏小说评测 {filename} 超时（已等待 {elapsed:.0f}秒），继续等待...")
                    yield json.dumps({
                        "type": "progress",
                        "stage": "evaluating",
                        "message": f"等待评测进度...（已等待 {elapsed:.0f}秒）",
                    }, ensure_ascii=False) + "\n"
        
        # 分析
        yield json.dumps({"type": "progress", "stage": "analyzing"}, ensure_ascii=False) + "\n"
        
        dims = good_results[0]["dims"] if good_results else {}
        by_dim = good_results[0]["by_dim"] if good_results else {}
        
        rule_adjustments, dimension_analysis = _analyze_rule_discrimination(
            good_results, bad_results, dims, by_dim
        )
        
        # 分析可合并的规则
        rule_adjustments = _analyze_rule_merges(rule_adjustments, good_results, bad_results)
        
        consistency_issues = _analyze_consistency(good_results, bad_results)
        recommendations = _generate_recommendations(
            rule_adjustments, dimension_analysis, consistency_issues
        )
        
        report = OptimizationReport(
            created_at=datetime.now().isoformat(),
            total_samples=len(good_results) + len(bad_results),
            good_novels=request.good_novel_files,
            bad_novels=request.bad_novel_files,
            rule_adjustments=rule_adjustments,
            dimension_analysis=dimension_analysis,
            consistency_issues=consistency_issues,
            recommendations=recommendations,
            raw_data={}
        )
        
        yield json.dumps({
            "type": "complete",
            "report": report.dict()
        }, ensure_ascii=False) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )


@router.get("/reference-novels")
async def list_reference_novels(
    current_user = Depends(get_current_user)
):
    """列出参考小说目录中的文件"""
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent
    reference_dir = project_dir / "reference"
    
    if not reference_dir.exists():
        return {"files": []}
    
    files = [f.name for f in reference_dir.glob("*.txt")]
    # 确保返回的文件名是 UTF-8 编码
    return {"files": files}


# ========== 优化历史记录 ==========

OPTIMIZATION_HISTORY_FILE = Path(__file__).resolve().parent.parent.parent.parent.parent / "training_runs" / "optimization_history.json"

class OptimizationHistoryEntry(BaseModel):
    """优化历史记录条目"""
    id: str
    created_at: str
    description: str  # 用户填写的优化说明
    good_novels: List[str]
    bad_novels: List[str]
    blocks_per_novel: int
    total_samples: int
    rule_changes: List[Dict[str, Any]]  # 规则修改详情
    dimension_changes: List[Dict[str, Any]]  # 维度修改详情
    applied: bool  # 是否已应用
    applied_at: str = None


def _load_optimization_history() -> List[Dict]:
    """加载优化历史"""
    if not OPTIMIZATION_HISTORY_FILE.exists():
        return []
    with open(OPTIMIZATION_HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_optimization_history(history: List[Dict]):
    """保存优化历史"""
    OPTIMIZATION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OPTIMIZATION_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


@router.post("/optimization-history")
async def save_optimization_record(
    record: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """保存优化记录"""
    history = _load_optimization_history()
    
    entry = {
        "id": f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(history)}",
        "created_at": datetime.now().isoformat(),
        **record
    }
    history.insert(0, entry)  # 最新的在前面
    _save_optimization_history(history)
    return {"success": True, "id": entry["id"]}


@router.get("/optimization-history")
async def list_optimization_history(
    page: int = 1,
    page_size: int = 10,
    current_user = Depends(get_current_user)
):
    """获取优化历史列表"""
    history = _load_optimization_history()
    total = len(history)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": history[start:end]
    }


@router.get("/optimization-history/{history_id}")
async def get_optimization_detail(
    history_id: str,
    current_user = Depends(get_current_user)
):
    """获取单条优化记录详情"""
    history = _load_optimization_history()
    for entry in history:
        if entry["id"] == history_id:
            return entry
    raise HTTPException(status_code=404, detail="记录不存在")


@router.post("/optimization-history/{history_id}/apply")
async def apply_optimization(
    history_id: str,
    current_user = Depends(get_current_user)
):
    """
    应用优化建议到规则文件
    
    这会修改 evaluate_rules_llm.csv 文件
    """
    import csv
    import shutil
    
    history = _load_optimization_history()
    entry = None
    for h in history:
        if h["id"] == history_id:
            entry = h
            break
    
    if not entry:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    if entry.get("applied"):
        raise HTTPException(status_code=400, detail="该优化已应用")
    
    # 获取规则文件路径
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent
    rules_file = project_dir / "evaluate_rules_llm.csv"
    
    if not rules_file.exists():
        raise HTTPException(status_code=404, detail="规则文件不存在")
    
    # 备份原文件
    backup_file = rules_file.with_suffix(f".csv.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(rules_file, backup_file)
    
    # 读取当前规则
    rules = []
    with open(rules_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rules.append(row)
    
    # 应用规则权重修改
    rule_changes = entry.get("rule_changes", [])
    changes_applied = 0
    
    for change in rule_changes:
        rule_id = change.get("rule_id")
        new_weight = change.get("new_weight")
        
        for rule in rules:
            if rule.get("rule_id") == rule_id:
                rule["weight"] = str(new_weight)
                changes_applied += 1
                break
    
    # 写回文件
    with open(rules_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rules)
    
    # 更新历史记录
    entry["applied"] = True
    entry["applied_at"] = datetime.now().isoformat()
    entry["backup_file"] = str(backup_file)
    _save_optimization_history(history)
    
    logger.info(f"优化已应用: {history_id}, 修改了 {changes_applied} 条规则权重")
    
    return {
        "success": True, 
        "message": f"优化已应用，修改了 {changes_applied} 条规则权重",
        "backup_file": str(backup_file)
    }


# ========== 迭代优化端点 ==========

@router.post("/optimize-rules/iterative")
async def optimize_rules_iterative(
    request: IterativeOptimizationRequest,
    current_user = Depends(get_current_user)
):
    """
    迭代式规则优化（流式返回）
    
    终止条件（满足任一即停止）：
    1. 平均区分度 >= discrimination_threshold
    2. 迭代次数 >= max_iterations
    3. 连续 convergence_window 次改善 < convergence_threshold
    """
    from fastapi.responses import StreamingResponse
    from app.core.rule_optimizer import RuleOptimizer, get_optimizer, remove_optimizer
    import uuid
    
    session_id = str(uuid.uuid4())
    
    async def generate():
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        project_dir = backend_dir.parent
        reference_dir = project_dir / "reference"
        
        logger.info(f"启动迭代优化，session_id={session_id}")
        
        # 初始化优化器
        optimizer = get_optimizer(
            session_id,
            project_dir,
            max_iterations=request.max_iterations,
            discrimination_threshold=request.discrimination_threshold,
            convergence_window=request.convergence_window,
            convergence_threshold=request.convergence_threshold,
        )
        
        err = optimizer.initialize()
        if err:
            yield json.dumps({"type": "error", "error": f"初始化失败: {err}"}, ensure_ascii=False) + "\n"
            return
        
        # 初始化 LLM 客户端
        try:
            from .training import _get_llm_client
            client, model_name = _get_llm_client()
        except Exception as e:
            yield json.dumps({"type": "error", "error": f"LLM客户端初始化失败: {e}"}, ensure_ascii=False) + "\n"
            return
        
        total_novels = len(request.good_novel_files) + len(request.bad_novel_files)
        
        # 迭代循环
        for iteration in range(1, request.max_iterations + 1):
            # 发送迭代开始消息
            yield json.dumps({
                "type": "iteration_start",
                "iteration": iteration,
                "max_iterations": request.max_iterations,
                "message": f"开始第 {iteration}/{request.max_iterations} 次迭代",
            }, ensure_ascii=False) + "\n"
            
            logger.info(f"第 {iteration} 次迭代开始")
            
            # 评测好小说
            good_results = []
            for idx, filename in enumerate(request.good_novel_files):
                yield json.dumps({
                    "type": "progress",
                    "stage": "evaluating",
                    "iteration": iteration,
                    "novel": filename,
                    "novel_type": "good",
                    "progress": f"{idx + 1}/{total_novels}",
                    "message": f"[迭代 {iteration}] 评测好小说: {filename}",
                }, ensure_ascii=False) + "\n"
                
                file_path = reference_dir / filename
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                
                result = await _run_sampled_evaluation(
                    text, request.blocks_per_novel, request.max_bytes_per_block,
                    request.genre, client, model_name
                )
                result["filename"] = filename
                result["novel_type"] = "good"
                good_results.append(result)
            
            # 评测坏小说
            bad_results = []
            for idx, filename in enumerate(request.bad_novel_files):
                actual_idx = len(request.good_novel_files) + idx
                yield json.dumps({
                    "type": "progress",
                    "stage": "evaluating",
                    "iteration": iteration,
                    "novel": filename,
                    "novel_type": "bad",
                    "progress": f"{actual_idx + 1}/{total_novels}",
                    "message": f"[迭代 {iteration}] 评测坏小说: {filename}",
                }, ensure_ascii=False) + "\n"
                
                file_path = reference_dir / filename
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                
                result = await _run_sampled_evaluation(
                    text, request.blocks_per_novel, request.max_bytes_per_block,
                    request.genre, client, model_name
                )
                result["filename"] = filename
                result["novel_type"] = "bad"
                bad_results.append(result)
            
            # 分析结果
            yield json.dumps({
                "type": "progress",
                "stage": "analyzing",
                "iteration": iteration,
                "message": f"[迭代 {iteration}] 分析评测结果...",
            }, ensure_ascii=False) + "\n"
            
            dims = good_results[0]["dims"] if good_results else {}
            by_dim = good_results[0]["by_dim"] if good_results else {}
            
            rule_adjustments, dimension_analysis = _analyze_rule_discrimination(
                good_results, bad_results, dims, by_dim
            )
            consistency_issues = _analyze_consistency(good_results, bad_results)
            
            # 运行迭代
            record, should_terminate, reason = optimizer.run_iteration(
                rule_adjustments, consistency_issues
            )
            
            # 发送迭代完成消息
            yield json.dumps({
                "type": "iteration_complete",
                "iteration": iteration,
                "metrics": {
                    "avg_discrimination": record.metrics.avg_discrimination,
                    "min_discrimination": record.metrics.min_discrimination,
                    "max_discrimination": record.metrics.max_discrimination,
                    "consistency_score": record.metrics.consistency_score,
                    "rules_count": record.metrics.rules_count,
                },
                "rule_changes": [{
                    "rule_id": c.rule_id,
                    "name": c.name,
                    "action": c.action,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "reason": c.reason,
                    "dimension": c.dimension,
                } for c in record.rule_changes],
                "changes_count": len(record.rule_changes),
                "converged": should_terminate,
                "termination_reason": reason,
            }, ensure_ascii=False) + "\n"
            
            logger.info(f"第 {iteration} 次迭代完成，终止={should_terminate}，原因={reason}")
            
            if should_terminate:
                break
        
        # 生成最终报告
        final_report = optimizer.get_final_report()
        
        yield json.dumps({
            "type": "complete",
            "final_report": final_report,
            "session_id": session_id,
        }, ensure_ascii=False) + "\n"
        
        logger.info(f"迭代优化完成，session_id={session_id}")
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )


@router.post("/optimize-rules/confirm")
async def confirm_rule_changes(
    request: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """
    确认并应用规则变更
    
    请求体：
    {
        "session_id": "uuid",
        "confirmed_changes": ["rule_id_1", "rule_id_2", ...],  // 确认变更的规则ID列表
        "rejected_changes": ["rule_id_3", ...],  // 拒绝变更的规则ID列表
    }
    """
    from app.core.rule_optimizer import get_optimizer, remove_optimizer
    
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")
    
    optimizer = get_optimizer(session_id, Path("."))
    
    confirmed = request.get("confirmed_changes", [])
    rejected = request.get("rejected_changes", [])
    
    # 恢复到原始规则
    optimizer.restore_backup(0)
    
    # 只应用确认的变更
    all_changes = []
    for record in optimizer.iteration_history:
        for change in record.rule_changes:
            if change.rule_id in confirmed:
                all_changes.append(change)
    
    if all_changes:
        optimizer.apply_changes(all_changes)
        optimizer.save_current_rules()
    
    # 清理优化器实例
    remove_optimizer(session_id)
    
    return {
        "success": True,
        "message": f"已应用 {len(confirmed)} 条规则变更，拒绝 {len(rejected)} 条",
        "applied_count": len(confirmed),
        "rejected_count": len(rejected),
    }


@router.get("/optimize-rules/backups")
async def list_backups(
    current_user = Depends(get_current_user)
):
    """列出所有规则备份"""
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent
    backup_dir = project_dir / "rules" / "backups"
    
    if not backup_dir.exists():
        return {"backups": []}
    
    backups = []
    for backup_path in sorted(backup_dir.iterdir()):
        if backup_path.is_dir():
            backups.append({
                "name": backup_path.name,
                "path": str(backup_path),
                "created_at": datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
            })
    
    return {"backups": backups}


@router.post("/optimize-rules/restore")
async def restore_backup(
    request: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """恢复到指定备份"""
    from app.core.rule_optimizer import RuleOptimizer
    
    backup_name = request.get("backup_name")
    if not backup_name:
        raise HTTPException(status_code=400, detail="缺少 backup_name")
    
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    project_dir = backend_dir.parent
    
    optimizer = RuleOptimizer(project_dir)
    
    # 从备份名称解析迭代号
    try:
        iteration = int(backup_name.split("_")[1])
    except:
        iteration = 0
    
    success = optimizer.restore_backup(iteration)
    
    if success:
        return {"success": True, "message": f"已恢复到备份: {backup_name}"}
    else:
        raise HTTPException(status_code=500, detail="恢复备份失败")
