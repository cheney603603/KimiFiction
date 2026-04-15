"""
SFT 训练数据质量审查工具
==========================

对模仿学习生成的训练数据进行自动化质量检查：
1. 去重（精确重复 + 模糊去重）
2. 格式校验（prompt/completion 完整性、长度范围）
3. 质量过滤（过短/过长、空值、异常字符）
4. 分布分析（场景覆盖、长度分布）
5. 生成审查报告

使用方式:
    python -m app.training.data_quality_audit  # 命令行运行
    # 或在代码中:
    from app.training.data_quality_audit import DataQualityAuditor
    auditor = DataQualityAuditor("path/to/samples.json")
    report = auditor.audit()
    cleaned_data = auditor.get_cleaned_data()
"""

import json
import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from loguru import logger


@dataclass
class QualityIssue:
    """数据质量问题"""
    index: int              # 样本索引
    issue_type: str         # 问题类型
    severity: str           # "error" / "warning" / "info"
    description: str        # 问题描述
    field: Optional[str] = None  # 问题字段


@dataclass
class AuditResult:
    """审查结果"""
    total_samples: int
    valid_samples: int
    error_count: int
    warning_count: int
    issues: List[QualityIssue] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return self.valid_samples / self.total_samples

    @property
    def has_critical(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


# ── 配置常量 ──
MIN_PROMPT_LENGTH = 20          # prompt 最小长度
MIN_COMPLETION_LENGTH = 50      # completion 最小长度
MAX_PROMPT_LENGTH = 8000        # prompt 最大长度（截断警告）
MAX_COMPLETION_LENGTH = 10000   # completion 最大长度
TARGET_COMPLETION_LENGTH = (500, 6000)  # 理想 completion 长度范围
DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # 模糊去重阈值

# 异常模式检测
SUSPICIOUS_PATTERNS = [
    (r'^[。！？\s]+$', "纯标点"),
    (r'^(.)\1{20,}$', "单字符重复"),
    (r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffefa-zA-Z0-9，。！？、；：""\'\'（）【】《》…—\s\n\r\t.,!?;:\'\"\[\]()\-]', "异常字符"),
]


class DataQualityAuditor:
    """
    SFT 数据质量审查器

    功能:
    - 加载 JSON 格式的训练样本
    - 执行多维质量检查
    - 输出清洗后的数据和报告
    """

    def __init__(
        self,
        data_path: str,
        strict_mode: bool = False,
    ):
        """
        Args:
            data_path: samples.json 文件路径
            strict_mode: True=更严格的检查标准
        """
        self.data_path = Path(data_path)
        self.strict_mode = strict_mode
        self.raw_data: List[Dict[str, Any]] = []
        self.clean_indices: List[int] = []  # 通过检查的样本索引
        self._result: Optional[AuditResult] = None

    def load_data(self) -> bool:
        """加载数据文件"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self.raw_data = json.load(f)
            if not isinstance(self.raw_data, list):
                logger.error(f"[DataAudit] 数据格式错误: 期望 list, 得到 {type(self.raw_data)}")
                self.raw_data = []
                return False
            logger.info(f"[DataAudit] 加载了 {len(self.raw_data)} 条样本")
            return True
        except FileNotFoundError:
            logger.error(f"[DataAudit] 文件不存在: {self.data_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"[DataAudit] JSON 解析失败: {e}")
            return False

    def audit(self) -> AuditResult:
        """
        执行完整质量审查

        Returns:
            AuditResult 包含所有问题和建议
        """
        if not self.raw_data:
            self.load_data()

        issues: List[QualityIssue] = []
        self.clean_indices = []

        # ── 逐样本检查 ──
        for idx, sample in enumerate(self.raw_data):
            sample_issues = self._check_sample(idx, sample)
            if sample_issues:
                issues.extend(sample_issues)
            else:
                self.clean_indices.append(idx)

        # ── 全局级别检查（去重等）──
        dup_issues = self._check_duplicates()
        issues.extend(dup_issues)

        # 更新 clean_indices（移除重复项的后者）
        dup_indices = {i.index for i in dup_issues}
        self.clean_indices = [i for i in self.clean_indices if i not in dup_indices]

        # ── 统计分析 ──
        stats = self._compute_statistics()

        # ── 生成建议 ──
        recommendations = self._generate_recommendations(issues, stats)

        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        self._result = AuditResult(
            total_samples=len(self.raw_data),
            valid_samples=len(self.clean_indices),
            error_count=error_count,
            warning_count=warning_count,
            issues=issues,
            statistics=stats,
            recommendations=recommendations,
        )

        logger.info(f"[DataAudit] 审查完成: "
                   f"{self._result.total_samples} 条 → "
                   f"{self._result.valid_samples} 条有效 "
                   f"(通过率 {self._result.pass_rate:.1%})")
        return self._result

    def get_cleaned_data(self) -> List[Dict[str, Any]]:
        """获取清洗后的数据"""
        return [self.raw_data[i] for i in self.clean_indices]

    def save_cleaned_data(self, output_path: str) -> str:
        """保存清洗后的数据"""
        cleaned = self.get_cleaned_data()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        logger.info(f"[DataAudit] 清洗后数据已保存: {output_path} ({len(cleaned)} 条)")
        return output_path

    def save_report(self, output_path: str) -> str:
        """保存审查报告（Markdown 格式）"""
        if not self._result:
            self.audit()

        report = self._format_report(self._result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"[DataAudit] 审查报告已保存: {output_path}")
        return output_path

    # =========================================================================
    # 内部检查方法
    # =========================================================================

    def _check_sample(self, idx: int, sample: Dict) -> List[QualityIssue]:
        """检查单个样本的质量"""
        issues: List[QualityIssue] = []

        # 1. 结构完整性
        if not isinstance(sample, dict):
            issues.append(QualityIssue(
                index=idx, issue_type="invalid_format",
                severity="error", description="样本不是字典格式",
            ))
            return issues  # 非字典无法继续检查

        prompt = sample.get("prompt", "")
        completion = sample.get("completion", "")
        metadata = sample.get("metadata", {})

        # 2. Prompt 检查
        if not prompt or not isinstance(prompt, str):
            issues.append(QualityIssue(
                index=idx, issue_type="missing_prompt",
                severity="error", description="prompt 为空或非字符串",
                field="prompt",
            ))
        else:
            plen = len(prompt.strip())
            if plen < MIN_PROMPT_LENGTH:
                issues.append(QualityIssue(
                    index=idx, issue_type="short_prompt",
                    severity="warning", description=f"prompt 过短 ({plen} 字符 < {MIN_PROMPT_LENGTH})",
                    field="prompt",
                ))
            elif plen > MAX_PROMPT_LENGTH:
                issues.append(QualityIssue(
                    index=idx, issue_type="long_prompt",
                    severity="info", description=f"prompt 过长 ({plen} 字符 > {MAX_PROMPT_LENGTH}, 可能被截断)",
                    field="prompt",
                ))

        # 3. Completion 检查
        if not completion or not isinstance(completion, str):
            issues.append(QualityIssue(
                index=idx, issue_type="missing_completion",
                severity="error", description="completion 为空或非字符串",
                field="completion",
            ))
        else:
            clen = len(completion.strip())
            if clen < MIN_COMPLETION_LENGTH:
                issues.append(QualityIssue(
                    index=idx, issue_type="short_completion",
                    severity="error", description=f"completion 过短 ({clen} 字符 < {MIN_COMPLETION_LENGTH})",
                    field="completion",
                ))
            elif clen > MAX_COMPLETION_LENGTH:
                issues.append(QualityIssue(
                    index=idx, issue_type="long_completion",
                    severity="warning", description=f"completion 过长 ({clen} 字符)",
                    field="completion",
                ))
            elif clen < TARGET_COMPLETION_LENGTH[0]:
                issues.append(QualityIssue(
                    index=idx, issue_type="suboptimal_length",
                    severity="info", description=f"completion 长度偏短 ({clen} 字符，理想 ≥{TARGET_COMPLETION_LENGTH[0]})",
                    field="completion",
                ))
            elif clen > TARGET_COMPLETION_LENGTH[1]:
                issues.append(QualityIssue(
                    index=idx, issue_type="suboptimal_length",
                    severity="info", description=f"completion 长度偏长 ({clen} 字符，理想 ≤{TARGET_COMPLETION_LENGTH[1]})",
                    field="completion",
                ))

            # 异常内容检测
            for pattern, desc in SUSPICIOUS_PATTERNS:
                if re.search(pattern, completion.strip()):
                    issues.append(QualityIssue(
                        index=idx, issue_type="suspicious_content",
                        severity="warning", description=f"检测到异常内容: {desc}",
                        field="completion",
                    ))

        # 4. Metadata 检查
        if not metadata:
            issues.append(QualityIssue(
                index=idx, issue_type="missing_metadata",
                severity="info", description="缺少元信息（scene_type 等）",
                field="metadata",
            ))

        return issues

    def _check_duplicates(self) -> List[QualityIssue]:
        """检查精确和模糊重复"""
        issues: List[QualityIssue] = []
        
        # 精确重复（基于 prompt + completion 的 hash）
        seen_hashes: Dict[str, int] = {}  # hash → first_index
        
        for idx, sample in enumerate(self.raw_data):
            key = f"{sample.get('prompt', '')}|||{sample.get('completion', '')}"
            hash_val = hashlib.md5(key.encode()).hexdigest()
            
            if hash_val in seen_hashes:
                issues.append(QualityIssue(
                    index=idx, issue_type="duplicate_exact",
                    severity="error",
                    description=f"与样本 #{seen_hashes[hash_val]} 完全相同",
                    field="all",
                ))
            else:
                seen_hashes[hash_val] = idx

        # 模糊重复（仅检查 completion 的前200字）
        if self.strict_mode:
            prefix_map: Dict[str, int] = {}
            for idx, sample in enumerate(self.raw_data):
                comp = sample.get("completion", "")[:200]
                if len(comp) < 30:
                    continue
                
                comp_hash = hashlib.md5(comp.encode()).hexdigest()
                if comp_hash in prefix_map:
                    issues.append(QualityIssue(
                        index=idx, issue_type="duplicate_fuzzy",
                        severity="warning",
                        description=f"与样本 #{prefix_map[comp_hash]} 开头高度相似",
                        field="completion",
                    ))
                else:
                    prefix_map[comp_hash] = idx

        return issues

    def _compute_statistics(self) -> Dict[str, Any]:
        """计算数据集统计信息"""
        if not self.raw_data:
            return {}

        prompt_lengths = []
        completion_lengths = []
        scene_types: Counter = Counter()
        prompt_types: Counter = Counter()

        for sample in self.raw_data:
            p = sample.get("prompt", "")
            c = sample.get("completion", "")
            meta = sample.get("metadata", {})
            
            prompt_lengths.append(len(p))
            completion_lengths.append(len(c))
            
            st = meta.get("scene_type", "unknown")
            pt = meta.get("prompt_type", "unknown")
            scene_types[st] += 1
            prompt_types[pt] += 1

        def _stats(values: List[int]) -> Dict[str, float]:
            if not values:
                return {"count": 0, "mean": 0, "min": 0, "max": 0, "median": 0}
            s = sorted(values)
            n = len(s)
            return {
                "count": n,
                "mean": round(sum(s) / n, 1),
                "min": s[0],
                "max": s[-1],
                "median": s[n // 2],
            }

        return {
            "total": len(self.raw_data),
            "prompt_lengths": _stats(prompt_lengths),
            "completion_lengths": _stats(completion_lengths),
            "scene_distribution": dict(scene_types.most_common()),
            "prompt_type_distribution": dict(prompt_types.most_common()),
            "cleaned_count": len(self.clean_indices),
        }

    def _generate_recommendations(
        self,
        issues: List[QualityIssue],
        stats: Dict[str, Any],
    ) -> List[str]:
        """根据问题生成改进建议"""
        recs = []

        issue_types = Counter(i.issue_type for i in issues)

        if issue_types.get("short_completion", 0) > 0:
            count = issue_types["short_completion"]
            total = len(self.raw_data)
            pct = count / max(total, 1) * 100
            recs.append(
                f"🔴 有 {count}/{total} ({pct:.1f}%) 的样本 completion 过短。"
                f"建议增加目标输出的最小长度要求或重新生成这些样本。"
            )

        if issue_types.get("duplicate_exact", 0) > 0:
            recs.append(
                f"🔴 发现 {issue_types['duplicate_exact']} 组完全重复的样本。"
                f"已自动去除，但建议检查数据生成逻辑是否产生重复。"
            )

        if issue_types.get("missing_prompt", 0) > 0 or issue_types.get("missing_completion", 0) > 0:
            recs.append(
                "🔴 存在空字段样本，可能是导出过程中的异常。"
            )

        # 场景覆盖不均
        dist = stats.get("scene_distribution", {})
        if dist:
            counts = list(dist.values())
            if counts:
                max_c, min_c = max(counts), min(counts)
                if max_c > 0 and min_c / max_c < 0.3:
                    recs.append(
                        f"⚠️ 场景分布不均衡（最多 {max_c} vs 最少 {min_c}），"
                        f"建议增加低频场景的样本数量以提高泛化能力。"
                    )

        # 长度分布
        cl_stats = stats.get("completion_lengths", {})
        mean_cl = cl_stats.get("mean", 0)
        if mean_cl < 300:
            recs.append(
                f"⚠️ 平均 completion 长度仅为 {mean_cl:.0f} 字符，可能影响模型生成能力。"
                f"建议目标长度 ≥500 字符。"
            )
        elif mean_cl > 4000:
            recs.append(
                f"ℹ️ 平均 completion 长度为 {mean_cl:.0f} 字符，较长样本可能增加训练时间。"
                f"考虑按长度分层采样以平衡效率和质量。"
            )

        if not recs:
            recs.append("✅ 数据质量良好，未发现明显问题。")

        return recs

    def _format_report(self, result: AuditResult) -> str:
        """格式化 Markdown 报告"""
        lines = [
            "# SFT 训练数据质量审查报告",
            "",
            f"**审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**数据源**: `{self.data_path}`",
            f"**严格模式**: {'是' if self.strict_mode else '否'}",
            "",
            "---",
            "",
            "## 总体评估",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总样本数 | {result.total_samples} |",
            f"| 有效样本数 | {result.valid_samples} |",
            f"| 通过率 | **{result.pass_rate:.1%}** |",
            f"| 错误数 | 🔴 {result.error_count} |",
            f"| 警告数 | 🟡 {result.warning_count} |",
            "",
        ]

        # 严重程度判定
        if result.pass_rate >= 0.95:
            status = "✅ **优秀** — 数据质量高，可直接用于训练"
        elif result.pass_rate >= 0.80:
            status = "⚠️ **良好** — 大部分数据合格，建议修复少量问题"
        elif result.pass_rate >= 0.60:
            status = "🟡 **及格** — 存在一定质量问题，需要清理后再训练"
        else:
            status = "❌ **不合格** — 数据质量严重不足，必须重新生成"

        lines.extend([f"**结论**: {status}", ""])

        # 详细统计
        stats = result.statistics
        if stats:
            lines.extend([
                "## 数据统计",
                "",
                "### 长度分布",
                "",
                "| 指标 | Prompt | Completion |",
                "|------|--------|------------|",
                f"| 平均 | {stats.get('prompt_lengths', {}).get('mean', '?')} | "
                f"{stats.get('completion_lengths', {}).get('mean', '?')} |",
                f"| 中位数 | {stats.get('prompt_lengths', {}).get('median', '?')} | "
                f"{stats.get('completion_lengths', {}).get('median', '?')} |",
                f"| 最小 | {stats.get('prompt_lengths', {}).get('min', '?')} | "
                f"{stats.get('completion_lengths', {}).get('min', '?')} |",
                f"| 最大 | {stats.get('prompt_lengths', {}).get('max', '?')} | "
                f"{stats.get('completion_lengths', {}).get('max', '?')} |",
                "",
            ])

            # 场景分布
            scene_dist = stats.get("scene_distribution", {})
            if scene_dist:
                lines.extend(["### 场景类型分布", "", "| 场景 | 样本数 | 占比 |", "|------|--------|------|"])
                total_scenes = sum(scene_dist.values())
                for st, cnt in sorted(scene_dist.items(), key=lambda x: -x[1]):
                    pct = cnt / max(total_scenes, 1) * 100
                    lines.append(f"| {st} | {cnt} | {pct:.1f}% |")
                lines.append("")

        # 问题详情
        if result.issues:
            # 只展示前 50 个问题避免报告过长
            display_issues = result.issues[:50]
            lines.extend([
                "## 问题详情",
                "",
                f"(共 {len(result.issues)} 个问题，显示前 {len(display_issues)} 个)",
                "",
                "| # | 索引 | 类型 | 严重程度 | 描述 | 字段 |",
                "|---|------|------|---------|------|------|",
            ])
            for i, issue in enumerate(display_issues, 1):
                sev_icon = {"error": "🔴", "warning": "🟡", "info": "ℹ️"}.get(issue.severity, "?")
                lines.append(
                    f"| {i} | #{issue.index} | {issue.issue_type} | "
                    f"{sev_icon} {issue.severity} | {issue.description[:40]} | {issue.field or '-'} |"
                )
            lines.append("")
        else:
            lines.extend(["## 问题详情", "", "*未发现任何问题 ✅*", ""])

        # 建议
        lines.extend([
            "---",
            "",
            "## 改进建议",
            "",
        ])
        for j, rec in enumerate(result.recommendations, 1):
            lines.append(f"{j}. {rec}")

        lines.extend([
            "",
            "---",
            f"*报告由 DataQualityAuditor 自动生成*",
        ])

        return "\n".join(lines)


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """命令行入口"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="SFT 训练数据质量审查工具")
    parser.add_argument("data_path", help="samples.json 文件路径")
    parser.add_argument("--output-dir", "-o", default=None, help="输出目录（默认与输入同目录）")
    parser.add_argument("--strict", action="store_true", help="启用严格模式")
    args = parser.parse_args()

    data_path = args.data_path
    output_dir = args.output_dir or str(Path(data_path).parent / "audit_reports")

    print(f"\n{'='*60}")
    print(f"SFT 数据质量审查")
    print(f"{'='*60}")
    print(f"输入文件: {data_path}")
    print(f"输出目录: {output_dir}")

    auditor = DataQualityAuditor(data_path, strict_mode=args.strict)

    # 加载
    if not auditor.load_data():
        print("\n❌ 无法加载数据文件")
        sys.exit(1)

    # 审查
    result = auditor.audit()

    # 输出摘要
    print(f"\n📊 审查结果:")
    print(f"   总样本: {result.total_samples}")
    print(f"   有效:   {result.valid_samples} ({result.pass_rate:.1%})")
    print(f"   错误:   {result.error_count}")
    print(f"   警告:   {result.warning_count}")

    # 保存
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = auditor.save_report(str(out_dir / "quality_report.md"))
    cleaned_path = auditor.save_cleaned_data(str(out_dir / "samples_cleaned.json"))

    print(f"\n📁 输出文件:")
    print(f"   报告: {report_path}")
    print(f"   清洗数据: {cleaned_path} ({len(auditor.get_cleaned_data())} 条)")

    # 返回退出码
    if result.has_critical and result.pass_rate < 0.7:
        print(f"\n⛔ 数据质量不合格，请查看报告并处理")
        sys.exit(1)
    else:
        print(f"\n✅ 完成")
        sys.exit(0)


if __name__ == "__main__":
    main()
