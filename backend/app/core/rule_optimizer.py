"""
规则优化引擎 - 迭代式规则优化

核心功能：
1. 规则副本管理
2. 迭代优化流程控制
3. 终止条件判断
4. 规则变更追踪
"""

import json
import shutil
import copy
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger


@dataclass
class RuleChange:
    """单条规则变更记录"""
    rule_id: str
    name: str
    action: str  # 'modify', 'delete', 'merge', 'add'
    old_value: Any
    new_value: Any
    reason: str
    dimension: str
    discrimination_before: float = 0.0
    discrimination_after: float = 0.0


@dataclass
class IterationMetrics:
    """单次迭代的指标"""
    avg_discrimination: float = 0.0
    min_discrimination: float = 0.0
    max_discrimination: float = 0.0
    consistency_score: float = 0.0
    rules_count: int = 0
    dimensions_count: int = 0


@dataclass
class IterationRecord:
    """单次迭代记录"""
    iteration: int
    timestamp: str
    metrics: IterationMetrics
    rule_changes: List[RuleChange] = field(default_factory=list)
    converged: bool = False
    termination_reason: str = ""


class RuleOptimizer:
    """规则优化引擎"""
    
    def __init__(
        self,
        project_dir: Path,
        max_iterations: int = 10,
        discrimination_threshold: float = 0.6,
        convergence_window: int = 3,
        convergence_threshold: float = 0.01,
        min_discrimination_to_keep: float = 0.1,
    ):
        self.project_dir = project_dir
        self.max_iterations = max_iterations
        self.discrimination_threshold = discrimination_threshold
        self.convergence_window = convergence_window
        self.convergence_threshold = convergence_threshold
        self.min_discrimination_to_keep = min_discrimination_to_keep
        
        # 规则文件路径
        self.rules_file = project_dir / "rules" / "rules.json"
        self.dims_file = project_dir / "rules" / "dimensions.json"
        
        # 备份目录
        self.backup_dir = project_dir / "rules" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 迭代历史
        self.iteration_history: List[IterationRecord] = []
        self.current_iteration = 0
        
        # 当前使用的规则（副本）
        self.current_rules: List[Dict] = []
        self.current_dims: Dict[str, Any] = {}
    
    def load_rules(self) -> Tuple[List[Dict], Dict, Optional[str]]:
        """加载规则文件"""
        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                rules = json.load(f)
            with open(self.dims_file, "r", encoding="utf-8") as f:
                dims = json.load(f)
            return rules, dims, None
        except Exception as e:
            return [], {}, str(e)
    
    def save_rules(self, rules: List[Dict], dims: Dict) -> Optional[str]:
        """保存规则文件"""
        try:
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            with open(self.dims_file, "w", encoding="utf-8") as f:
                json.dump(dims, f, ensure_ascii=False, indent=2)
            return None
        except Exception as e:
            return str(e)
    
    def create_backup(self, iteration: int) -> Path:
        """创建规则备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"iteration_{iteration}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # 复制规则文件
        shutil.copy2(self.rules_file, backup_path / "rules.json")
        shutil.copy2(self.dims_file, backup_path / "dimensions.json")
        
        # 保存迭代记录
        with open(backup_path / "history.json", "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self.iteration_history], f, ensure_ascii=False, indent=2)
        
        logger.info(f"创建备份: {backup_path}")
        return backup_path
    
    def initialize(self) -> Optional[str]:
        """初始化优化器，加载原始规则"""
        rules, dims, err = self.load_rules()
        if err:
            return err
        
        self.current_rules = copy.deepcopy(rules)
        self.current_dims = copy.deepcopy(dims)
        self.iteration_history = []
        self.current_iteration = 0
        
        # 创建初始备份
        self.create_backup(0)
        
        return None
    
    def calculate_metrics(self, rule_adjustments: List[Dict]) -> IterationMetrics:
        """计算迭代指标"""
        if not rule_adjustments:
            return IterationMetrics()
        
        discriminations = [r.get("discrimination", 0) for r in rule_adjustments]
        
        return IterationMetrics(
            avg_discrimination=sum(discriminations) / len(discriminations),
            min_discrimination=min(discriminations),
            max_discrimination=max(discriminations),
            rules_count=len(rule_adjustments),
            dimensions_count=len(set(r.get("dimension", "") for r in rule_adjustments)),
        )
    
    def check_termination(self, metrics: IterationMetrics) -> Tuple[bool, str]:
        """检查是否满足终止条件"""
        # 条件1: 区分度阈值
        if metrics.avg_discrimination >= self.discrimination_threshold:
            return True, "discrimination_threshold_reached"
        
        # 条件2: 最大迭代次数
        if self.current_iteration >= self.max_iterations:
            return True, "max_iterations_reached"
        
        # 条件3: 收敛条件（连续N次改善小于阈值）
        if len(self.iteration_history) >= self.convergence_window:
            recent = self.iteration_history[-self.convergence_window:]
            improvements = [
                recent[i].metrics.avg_discrimination - recent[i-1].metrics.avg_discrimination
                for i in range(1, len(recent))
            ]
            if all(abs(imp) < self.convergence_threshold for imp in improvements):
                return True, "converged"
        
        return False, ""
    
    def generate_rule_changes(
        self,
        rule_adjustments: List[Dict],
        consistency_issues: List[Dict]
    ) -> List[RuleChange]:
        """基于分析结果生成规则变更"""
        changes = []
        
        for adj in rule_adjustments:
            rule_id = adj.get("rule_id", "")
            discrimination = adj.get("discrimination", 0)
            action = adj.get("action", "keep")
            
            if action == "keep":
                continue
            
            # 查找当前规则
            current_rule = None
            for r in self.current_rules:
                if r.get("rule_id") == rule_id:
                    current_rule = r
                    break
            
            if not current_rule:
                continue
            
            if action == "modify":
                old_weight = current_rule.get("weight", 1.0)
                new_weight = adj.get("suggested_weight", old_weight)
                
                changes.append(RuleChange(
                    rule_id=rule_id,
                    name=adj.get("name", ""),
                    action="modify",
                    old_value=old_weight,
                    new_value=new_weight,
                    reason=adj.get("reason", ""),
                    dimension=adj.get("dimension", ""),
                    discrimination_before=discrimination,
                    discrimination_after=discrimination,  # 将在应用后更新
                ))
            
            elif action == "delete":
                if discrimination < self.min_discrimination_to_keep:
                    changes.append(RuleChange(
                        rule_id=rule_id,
                        name=adj.get("name", ""),
                        action="delete",
                        old_value=current_rule,
                        new_value=None,
                        reason=f"区分度过低 ({discrimination:.2f})，建议删除",
                        dimension=adj.get("dimension", ""),
                        discrimination_before=discrimination,
                        discrimination_after=0.0,
                    ))
            
            elif action == "merge":
                merge_target = adj.get("merge_target", "")
                if merge_target:
                    changes.append(RuleChange(
                        rule_id=rule_id,
                        name=adj.get("name", ""),
                        action="merge",
                        old_value=current_rule,
                        new_value=merge_target,
                        reason=adj.get("reason", ""),
                        dimension=adj.get("dimension", ""),
                        discrimination_before=discrimination,
                        discrimination_after=discrimination,
                    ))
        
        # 基于一致性分析添加权重调整
        for issue in consistency_issues:
            if issue.get("std_dev", 0) > 0.3:
                # 高方差规则需要调整权重
                pass
        
        return changes
    
    def apply_changes(self, changes: List[RuleChange]) -> None:
        """应用规则变更到当前规则副本"""
        for change in changes:
            if change.action == "modify":
                # 修改权重
                for rule in self.current_rules:
                    if rule.get("rule_id") == change.rule_id:
                        rule["weight"] = change.new_value
                        logger.info(f"修改规则权重: {change.rule_id} {change.old_value} -> {change.new_value}")
                        break
            
            elif change.action == "delete":
                # 删除规则
                self.current_rules = [
                    r for r in self.current_rules
                    if r.get("rule_id") != change.rule_id
                ]
                logger.info(f"删除规则: {change.rule_id}")
            
            elif change.action == "merge":
                # 合并规则（将源规则权重加到目标规则）
                source_rule = None
                target_rule = None
                
                for r in self.current_rules:
                    if r.get("rule_id") == change.rule_id:
                        source_rule = r
                    if r.get("rule_id") == change.new_value:
                        target_rule = r
                
                if source_rule and target_rule:
                    target_rule["weight"] = target_rule.get("weight", 1.0) + source_rule.get("weight", 1.0)
                    # 删除源规则
                    self.current_rules = [
                        r for r in self.current_rules
                        if r.get("rule_id") != change.rule_id
                    ]
                    logger.info(f"合并规则: {change.rule_id} -> {change.new_value}")
    
    def save_current_rules(self) -> Optional[str]:
        """保存当前规则副本到文件"""
        return self.save_rules(self.current_rules, self.current_dims)
    
    def run_iteration(
        self,
        rule_adjustments: List[Dict],
        consistency_issues: List[Dict]
    ) -> Tuple[IterationRecord, bool, str]:
        """
        运行单次迭代
        
        Returns:
            (迭代记录, 是否终止, 终止原因)
        """
        self.current_iteration += 1
        logger.info(f"开始第 {self.current_iteration} 次迭代")
        
        # 计算指标
        metrics = self.calculate_metrics(rule_adjustments)
        
        # 生成规则变更
        changes = self.generate_rule_changes(rule_adjustments, consistency_issues)
        
        # 应用变更
        if changes:
            self.apply_changes(changes)
            self.save_current_rules()
        
        # 创建备份
        self.create_backup(self.current_iteration)
        
        # 检查终止条件
        should_terminate, reason = self.check_termination(metrics)
        
        # 创建记录
        record = IterationRecord(
            iteration=self.current_iteration,
            timestamp=datetime.now().isoformat(),
            metrics=metrics,
            rule_changes=changes,
            converged=should_terminate,
            termination_reason=reason if should_terminate else "",
        )
        
        self.iteration_history.append(record)
        
        logger.info(
            f"第 {self.current_iteration} 次迭代完成: "
            f"avg_discrimination={metrics.avg_discrimination:.3f}, "
            f"changes={len(changes)}, "
            f"terminated={should_terminate}"
        )
        
        return record, should_terminate, reason
    
    def get_final_report(self) -> Dict[str, Any]:
        """生成最终报告"""
        if not self.iteration_history:
            return {}
        
        final_iteration = self.iteration_history[-1]
        
        return {
            "total_iterations": self.current_iteration,
            "termination_reason": final_iteration.termination_reason,
            "final_metrics": asdict(final_iteration.metrics),
            "iteration_history": [
                {
                    "iteration": r.iteration,
                    "timestamp": r.timestamp,
                    "metrics": asdict(r.metrics),
                    "changes_count": len(r.rule_changes),
                    "converged": r.converged,
                }
                for r in self.iteration_history
            ],
            "all_rule_changes": [
                asdict(change)
                for record in self.iteration_history
                for change in record.rule_changes
            ],
        }
    
    def restore_backup(self, iteration: int) -> bool:
        """恢复到指定迭代的备份"""
        # 查找备份
        backup_paths = sorted(self.backup_dir.glob(f"iteration_{iteration}_*"))
        if not backup_paths:
            logger.error(f"未找到迭代 {iteration} 的备份")
            return False
        
        backup_path = backup_paths[-1]  # 使用最新的
        
        try:
            # 恢复规则文件
            shutil.copy2(backup_path / "rules.json", self.rules_file)
            shutil.copy2(backup_path / "dimensions.json", self.dims_file)
            
            # 重新加载
            self.initialize()
            
            logger.info(f"恢复到迭代 {iteration} 的备份: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False


# 全局优化器实例（用于保持状态）
_optimizers: Dict[str, RuleOptimizer] = {}


def get_optimizer(session_id: str, project_dir: Path, **kwargs) -> RuleOptimizer:
    """获取或创建优化器实例"""
    if session_id not in _optimizers:
        _optimizers[session_id] = RuleOptimizer(project_dir, **kwargs)
    return _optimizers[session_id]


def remove_optimizer(session_id: str):
    """移除优化器实例"""
    if session_id in _optimizers:
        del _optimizers[session_id]
