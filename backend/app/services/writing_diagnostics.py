"""
三尺度写作诊断指标（§5.3）
===========================

微观：句长方差 burstiness、AI 高频词句命中率
中观：段落长度分布熵、总结句密度
宏观：跨章开头相似度、情绪曲线形状相关

强制约束（R1）：**只做诊断与告警，不进 reward、不进硬门禁**。
指标用于让编辑/作者看见问题，而非让模型追逐数字。
"""
import math
import re
from typing import Dict, List, Optional, Sequence

# AI 高频词/模板句黑名单（正则）
_AI_PHRASE_PATTERNS = [
    r"仿佛", r"似乎", r"不禁", r"微微", r"淡淡", r"缓缓", r"轻轻", r"默默",
    r"隐隐", r"若有所思", r"喃喃自语", r"眼神中", r"嘴角", r"空气中弥漫",
    r"心中涌起", r"一种说不出的", r"气氛", r"若有所思地", r"若有所思道",
]

# 总结/收束句模式（AI 常用"这意味着/从今往后"收尾）
_SUMMARY_PATTERNS = [
    "这意味着", "从今往后", "从此以后", "一切都变了", "他终于明白",
    "仿佛看到了", "似乎一切都", "这一刻，他", "也许是时候",
]

_BURSTINESS_FLAG = 0.45    # 低于该值标记"机器节奏"
_PARA_ENTROPY_FLAG = 0.50  # 归一化熵低于该值标记"段落过匀"
_OPENING_SIM_FLAG = 0.30   # 跨章首200字 n-gram 重合率高于该值标记"章间同构"


def _split_sentences(text: str) -> List[str]:
    """按句末标点切句。"""
    return [s for s in re.split(r"(?<=[。！？；])", text) if s.strip()]


def _split_paragraphs(text: str) -> List[str]:
    """按空行切段。"""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def compute_diagnostics(
    content: str,
    prev_openings: Optional[Sequence[str]] = None,
    prev_emotion_curves: Optional[Sequence[Sequence[float]]] = None,
) -> Dict[str, object]:
    """计算三尺度诊断指标。

    Args:
        content: 本章正文
        prev_openings: 近 5 章开头各 200 字（宏观·章间同构）
        prev_emotion_curves: 近几章逐段情绪起伏曲线（宏观·曲线雷同）
    """
    result: Dict[str, object] = {}
    if not content:
        return result

    # ── 微观 ──────────────────────────────
    sentences = _split_sentences(content)
    lengths = [len(s) for s in sentences]
    if lengths:
        mean = sum(lengths) / len(lengths)
        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        burstiness = math.sqrt(variance) / mean if mean else 0.0
    else:
        burstiness = 0.0
    result["burstiness"] = round(burstiness, 3)
    result["burstiness_flag"] = bool(burstiness < _BURSTINESS_FLAG)

    n = len(content)
    phrase_hits: Dict[str, int] = {}
    for pattern in _AI_PHRASE_PATTERNS:
        cnt = len(re.findall(pattern, content))
        if cnt:
            phrase_hits[pattern.rstrip("\\")] = cnt
    per1000 = sum(phrase_hits.values()) / max(n, 1) * 1000
    result["ai_phrase_hits_per_1000"] = round(per1000, 2)
    result["ai_phrases"] = sorted(phrase_hits.items(), key=lambda kv: -kv[1])[:8]
    result["ai_phrase_flag"] = bool(per1000 >= 4)

    # ── 中观 ──────────────────────────────
    paras = _split_paragraphs(content)
    if paras:
        para_lengths = [len(p) for p in paras]
        buckets = {}
        for pl in para_lengths:
            b = int(pl / 20)  # 20 字一桶
            buckets[b] = buckets.get(b, 0) + 1
        total = sum(buckets.values())
        entropy = -sum((c / total) * math.log(c / total) for c in buckets.values())
        entropy_norm = entropy / math.log(len(buckets)) if len(buckets) > 1 else 0.0
        result["para_entropy"] = round(entropy, 3)
        result["para_entropy_normalized"] = round(entropy_norm, 3)
        result["para_entropy_flag"] = bool(entropy_norm < _PARA_ENTROPY_FLAG)
    else:
        result["para_entropy"] = 0.0
        result["para_entropy_flag"] = False

    if sentences:
        summary_hits = sum(1 for s in sentences if any(p in s for p in _SUMMARY_PATTERNS))
        result["summary_sentence_ratio"] = round(summary_hits / len(sentences), 3)
        result["summary_sentence_flag"] = bool(summary_hits / max(len(sentences), 1) > 0.05)
    else:
        result["summary_sentence_ratio"] = 0.0
        result["summary_sentence_flag"] = False

    # ── 宏观 ──────────────────────────────
    opening = content[:200]
    if prev_openings:
        max_sim = max(
            (_bigram_similarity(opening, o[:200]) for o in prev_openings if o),
            default=0.0,
        )
        result["opening_similarity"] = round(max_sim, 3)
        result["opening_similarity_flag"] = bool(max_sim > _OPENING_SIM_FLAG)
    else:
        result["opening_similarity"] = None
        result["opening_similarity_flag"] = None

    current_curve = _emotion_curve(content)
    if prev_emotion_curves:
        corrs = [
            _pearson(current_curve, curve)
            for curve in prev_emotion_curves
            if curve and len(curve) > 2
        ]
        corrs = [c for c in corrs if c is not None]
        result["emotion_curve_corr"] = round(max(corrs), 3) if corrs else None
        result["emotion_curve_flag"] = bool(corrs and max(corrs) > 0.9)
    else:
        result["emotion_curve_corr"] = None
        result["emotion_curve_flag"] = None

    return result


def _bigram_similarity(a: str, b: str) -> float:
    """字符二元组 Jaccard 相似度。"""
    if not a or not b:
        return 0.0
    ga = set(a[i:i + 2] for i in range(len(a) - 1))
    gb = set(b[i:i + 2] for i in range(len(b) - 1))
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _emotion_curve(text: str) -> List[float]:
    """以感叹/疑问密度与词性为粗代理的情绪起伏曲线（逐段）。"""
    curve = []
    for para in _split_paragraphs(text):
        score = 0.0
        score += para.count("！") * 1.0 + para.count("？") * 0.6
        for w in ("怒", "惊", "恨", "喜", "哭", "笑", "痛", "愣", "颤"):
            score += para.count(w) * 0.4
        curve.append(score)
    return curve


def _pearson(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = min(len(a), len(b))
    if n < 3:
        return None
    a, b = list(a[:n]), list(b[:n])
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return None
    return num / (da * db)
