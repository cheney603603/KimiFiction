"""章节语言质检（去AI味确定性扫描）。

参照 human-writing/check_prose.py 与 deai-promax（朱雀五维）的思路：
只做确定性规则判定与告警，不用 LLM；供章节生成后的"语言门禁"使用——
命中硬禁令 → 定向重写（≤1 轮）→ 仍不过标 flagged 待人工。
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# 网文 AI 套词（deai-promax fanqie 完整表 + human-writing 高频项）
AI_CLICHES = [
    "不由得", "霎时间", "殊不知", "良久", "眼底闪过一丝波澜", "眼底划过一丝",
    "喉结滚动", "周身气场", "心中五味杂陈", "气氛瞬间凝滞", "猛地", "死死",
    "狠狠", "仿佛", "紧接着", "嘴角微微上扬", "心中暗道", "心中暗想", "就在这时",
    "顿时", "瞬间", "恍然大悟", "微微一笑", "轻轻叹了口气", "眼底闪过一丝",
    "一抹惊愕", "瞳孔微缩", "周身气势", "微微一怔", "沉默片刻",
]

# 翻案句（human-writing 禁令）
_PIVOT_PATTERNS = (
    re.compile(r"不是[^。！？\n]{0,60}而是"),
    re.compile(r"并非[^。！？\n]{0,60}而是"),
    re.compile(r"不在于[^。！？\n]{0,60}而在于"),
    re.compile(r"与其说[^。！？\n]{0,60}不如说"),
    re.compile(r"表面[^。！？\n]{0,60}(?:其实|实际|实则)"),
    re.compile(r"看似[^。！？\n]{0,60}(?:其实|实际|实则)"),
)

# 模型路标词（用来说事时删除；正文本义不受影响）
ROAD_SIGNS = (
    "值得注意的是", "更重要的是", "说白了", "说穿了", "归根结底",
    "本质上", "换句话说", "更深层次",
)

# 显性逻辑连词（网文里高频出现即模板腔）
_LINKERS = ("然而", "因此", "此外", "与此同时", "首先", "其次", "最后")

# 情绪直陈探测：很/十分/非常 + 情绪形容词，或 心中/内心 + 情绪词
_EMOTION_ADJS = (
    "愤怒", "生气", "难过", "伤心", "悲伤", "高兴", "开心", "激动", "紧张",
    "害怕", "恐惧", "惊讶", "震惊", "尴尬", "羞愧", "得意", "失落", "焦虑",
)
_EMOTION_RE = re.compile(
    r"(?:很|十分|非常|特别|格外)(?:" + "|".join(_EMOTION_ADJS) + r")"
)
_INNER_EMOTION_RE = re.compile(
    r"(?:心中|内心|心里|心头)(?:" + "|".join(_EMOTION_ADJS) + r"|充满|一阵|涌起)"
)


@dataclass
class LanguageIssue:
    rule: str          # 规则名
    sample: str        # 命中示例（截断）
    count: int = 1


@dataclass
class LanguageGateResult:
    passed: bool
    failures: List[LanguageIssue] = field(default_factory=list)
    warnings: List[LanguageIssue] = field(default_factory=list)
    sentence_stddev: float = 0.0
    ai_score: int = 0          # 0-100，越高越像 AI
    checks: dict = field(default_factory=dict)

    def failure_summary(self) -> str:
        if not self.failures:
            return ""
        lines = [f"{i.rule}（{i.count}处，如\"{i.sample}\"）" for i in self.failures[:8]]
        return "；".join(lines)


def count_words(text: str) -> int:
    chinese = len(re.findall(r'[一-鿿]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english


def _unique_samples(text: str, terms: Tuple[str, ...]) -> List[LanguageIssue]:
    """统计各套词/路标词出现次数，返回非零项（按首次出现排序）。"""
    out: List[LanguageIssue] = []
    for term in terms:
        n = text.count(term)
        if n:
            idx = text.index(term)
            out.append(LanguageIssue(rule=term, sample=text[max(0, idx - 6):idx + len(term) + 6], count=n))
    return out


def _sentence_lengths(text: str) -> List[int]:
    segs = re.split(r"[。！？!?\n]", text)
    return [count_words(s) for s in segs if count_words(s) > 0]


def scan_language(content: str) -> LanguageGateResult:
    """扫描正文，返回硬禁令失败项 + 软指标告警 + AI 味评分。"""
    failures: List[LanguageIssue] = []
    warnings: List[LanguageIssue] = []
    checks: dict = {}
    total = count_words(content)

    # ── 硬禁令 ──
    for issue in _unique_samples(content, tuple(AI_CLICHES)):
        failures.append(issue)

    dash = content.count("——") + content.count("—")
    if dash >= 2:
        idx = content.find("—")
        failures.append(LanguageIssue(
            rule="破折号滥用", sample=content[max(0, idx - 6):idx + 8], count=dash,
        ))

    for pat in _PIVOT_PATTERNS:
        m = pat.search(content)
        if m:
            failures.append(LanguageIssue(rule="翻案句", sample=m.group()[:40].strip(), count=1))

    for issue in _unique_samples(content, ROAD_SIGNS):
        failures.append(LanguageIssue(rule=f"模型路标·{issue.rule}", sample=issue.sample, count=issue.count))

    # ── 软指标（告警 + 评分） ──
    linkers = {term: content.count(term) for term in _LINKERS}
    linker_hits = sum(linkers.values())
    checks["逻辑连词"] = linker_hits

    tell = len(_EMOTION_RE.findall(content))
    inner_tell = len(_INNER_EMOTION_RE.findall(content))
    checks["情绪直陈"] = tell + inner_tell
    if tell + inner_tell >= 3:
        m = (_EMOTION_RE.search(content) or _INNER_EMOTION_RE.search(content))
        warnings.append(LanguageIssue(
            rule="情绪直陈偏多", sample=m.group(0) if m else "",
            count=tell + inner_tell,
        ))

    lens = _sentence_lengths(content)
    stddev = statistics.pstdev(lens) if len(lens) >= 5 else 0.0
    checks["句长标准差"] = round(stddev, 1)

    paragraphs = [p for p in re.split(r"\n\s*\n", content) if count_words(p.strip()) >= 4]
    one_sentence = sum(1 for p in paragraphs if len(re.findall(r"[。！？!?]", p)) <= 1)
    short_ratio = (one_sentence / len(paragraphs)) if paragraphs else 0.0
    checks["单句段占比"] = round(short_ratio, 2)
    if len(paragraphs) >= 6 and short_ratio >= 0.6:
        warnings.append(LanguageIssue(
            rule="段落同构·单句段过多", sample="连续单句段可能排成鼓点",
            count=one_sentence,
        ))

    # ── AI 味评分（0-100） ──
    score = 0
    score += min(30, len(failures) * 8)                      # 硬禁令项
    score += min(15, linker_hits * 3)                        # 逻辑连词密度
    score += min(15, (tell + inner_tell) * 4)                # 情绪直陈
    if lens:
        if stddev < 5:
            score += 15                                      # 句长过匀
        elif stddev < 7:
            score += 8
    if short_ratio >= 0.6:
        score += 10
    score = min(100, score)

    return LanguageGateResult(
        passed=not failures,
        failures=failures,
        warnings=warnings,
        sentence_stddev=stddev,
        ai_score=score,
        checks=checks,
    )
