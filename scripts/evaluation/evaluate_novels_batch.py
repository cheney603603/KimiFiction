"""
长文本八维评分评测脚本
基于KimiFiction项目的Rubric Evaluation System

八维评分体系：
1. 情节一致性 (20%)
2. 逻辑合理性 (20%)
3. 角色一致性 (15%)
4. 风格匹配度 (15%)
5. 世界观一致性 (10%)
6. 叙事流畅度 (10%)
7. 情感冲击力 (5%)
8. 钩子强度 (5%)
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DimensionScore:
    """单维度评分"""
    name: str
    category: str
    weight: float
    score: float  # 1-10
    criteria_met: List[str] = field(default_factory=list)
    criteria_missed: List[str] = field(default_factory=list)
    feedback: str = ""
    evidence: str = ""


@dataclass
class NovelEvaluation:
    """小说评测结果"""
    novel_name: str
    author: str
    genre: str
    total_score: float
    weighted_score: float  # 百分制
    dimensions: List[DimensionScore]
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    summary: str = ""
    text_samples: List[str] = field(default_factory=list)
    evaluation_time: str = ""


# 八维评分标准定义
RUBRIC_DIMENSIONS = [
    {
        "category": "plot_consistency",
        "name": "情节一致性",
        "weight": 0.20,
        "criteria": [
            "情节发展逻辑清晰",
            "伏笔设置合理并得到回收",
            "时间线和因果关系正确",
            "冲突和高潮安排恰当"
        ],
        "weight_description": "核心维度，权重最高"
    },
    {
        "category": "logic_rationality",
        "name": "逻辑合理性",
        "weight": 0.20,
        "criteria": [
            "事件发展符合内在逻辑",
            "角色行为动机合理",
            "世界观设定自洽无矛盾",
            "无明显的逻辑漏洞或Bug"
        ],
        "weight_description": "核心维度，权重最高"
    },
    {
        "category": "character_consistency",
        "name": "角色一致性",
        "weight": 0.15,
        "criteria": [
            "角色性格前后一致稳定",
            "角色成长符合人设设定",
            "角色关系发展合理可信",
            "角色行为符合其背景和性格"
        ],
        "weight_description": "重要维度，影响代入感"
    },
    {
        "category": "style_matching",
        "name": "风格匹配度",
        "weight": 0.15,
        "criteria": [
            "符合小说类型/题材的风格要求",
            "语言风格前后统一稳定",
            "叙事节奏符合读者预期",
            "对话风格符合角色设定"
        ],
        "weight_description": "重要维度，影响阅读体验"
    },
    {
        "category": "world_consistency",
        "name": "世界观一致性",
        "weight": 0.10,
        "criteria": [
            "世界观设定内部自洽",
            "力量体系/规则保持一致",
            "地理、历史、社会设定无矛盾",
            "细节设定前后呼应"
        ],
        "weight_description": "支撑维度，构架世界观"
    },
    {
        "category": "narrative_flow",
        "name": "叙事流畅度",
        "weight": 0.10,
        "criteria": [
            "段落过渡自然流畅",
            "场景切换清晰不突兀",
            "视角转换恰当合理",
            "整体节奏控制得当"
        ],
        "weight_description": "支撑维度，影响阅读流畅性"
    },
    {
        "category": "emotional_impact",
        "name": "情感冲击力",
        "weight": 0.05,
        "criteria": [
            "情感描写真实动人",
            "高潮部分有强烈感染力",
            "能让读者产生情感共鸣",
            "情绪转折自然不生硬"
        ],
        "weight_description": "提升维度，影响口碑传播"
    },
    {
        "category": "hook_strength",
        "name": "钩子强度",
        "weight": 0.05,
        "criteria": [
            "开头吸引读者眼球",
            "结尾留有悬念或期待",
            "章节内有小高潮驱动阅读",
            "整体有追读下去的欲望"
        ],
        "weight_description": "提升维度，影响读者留存"
    }
]


class TextExtractor:
    """文本提取器 - 从小说文件中提取关键段落"""
    
    @staticmethod
    def extract_samples(text: str, num_samples: int = 5) -> List[str]:
        """提取关键文本样本"""
        # 分割章节/段落
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]
        
        if not paragraphs:
            return [text[:1000]]
        
        samples = []
        
        # 开篇样本
        if len(paragraphs) > 0:
            samples.append(paragraphs[0][:500])
        
        # 中段样本
        mid_idx = len(paragraphs) // 2
        if len(paragraphs) > mid_idx:
            samples.append(paragraphs[mid_idx][:500])
        
        # 结尾/高潮样本
        if len(paragraphs) > 1:
            samples.append(paragraphs[-1][:500])
        
        # 随机抽取其他样本
        import random
        remaining = [p for i, p in enumerate(paragraphs) if i not in [0, mid_idx, len(paragraphs)-1]]
        random.seed(42)
        samples.extend(random.sample(remaining, min(num_samples - 3, len(remaining))))
        
        return samples[:num_samples]
    
    @staticmethod
    def extract_dialogues(text: str, num: int = 3) -> List[str]:
        """提取对话样本"""
        # 简单匹配引号内的对话
        pattern = r'[""''『』][^""''『』]{10,500}[""''『』]'
        matches = re.findall(pattern, text)
        return matches[:num]
    
    @staticmethod
    def estimate_word_count(text: str) -> int:
        """估算字数"""
        # 中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words


class NovelAnalyzer:
    """小说分析器 - 基于规则的分析（无需API调用）"""
    
    def __init__(self):
        self.rubric = RUBRIC_DIMENSIONS
    
    def analyze_text(self, text: str, novel_name: str, author: str, genre: str = "玄幻") -> NovelEvaluation:
        """分析小说文本并生成评分"""
        
        # 提取文本样本
        text_samples = TextExtractor.extract_samples(text, num_samples=5)
        word_count = TextExtractor.estimate_word_count(text)
        
        # 基于文本特征进行评分
        dimensions = []
        
        for dim_config in self.rubric:
            dim_score = self._evaluate_dimension(text, text_samples, dim_config, word_count)
            dimensions.append(dim_score)
        
        # 计算总分
        total_score = sum(d.score for d in dimensions) / len(dimensions)
        weighted_score = sum(d.score * d.weight for d in dimensions) * 10  # 转换为百分制
        
        # 生成总结
        strengths, weaknesses, suggestions = self._generate_feedback(dimensions)
        
        evaluation = NovelEvaluation(
            novel_name=novel_name,
            author=author,
            genre=genre,
            total_score=total_score,
            weighted_score=weighted_score,
            dimensions=dimensions,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            text_samples=text_samples,
            evaluation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        evaluation.summary = self._generate_summary(evaluation)
        
        return evaluation
    
    def _evaluate_dimension(
        self,
        text: str,
        samples: List[str],
        dim_config: Dict,
        word_count: int
    ) -> DimensionScore:
        """评估单个维度"""
        
        base_score = 5.0  # 基础分
        criteria_met = []
        criteria_missed = []
        feedback_items = []
        
        # === 情节一致性分析 ===
        if dim_config["category"] == "plot_consistency":
            # 检测情节元素
            has_conflict = any(kw in text for kw in ['冲突', '矛盾', '危机', '危机', '争斗', '争夺'])
            has_foreshadow = any(kw in text for kw in ['伏笔', '预示', '暗示', '伏', '征兆'])
            has_climax = any(kw in text for kw in ['高潮', '爆发', '爆发', '转折', '逆转'])
            
            score = base_score
            if has_conflict: score += 0.5
            if has_foreshadow: score += 1.0
            if has_climax: score += 0.5
            if word_count > 50000: score += 1.0  # 长篇加分
            if word_count < 10000: score -= 0.5  # 短篇减分
            
            if has_foreshadow:
                criteria_met.append("伏笔设置合理并得到回收")
                feedback_items.append("伏笔设置丰富")
            else:
                criteria_missed.append("伏笔设置较少")
                feedback_items.append("建议加强伏笔铺设")
            
            if has_climax:
                criteria_met.append("冲突和高潮安排恰当")
                feedback_items.append("高潮安排合理")
            else:
                criteria_missed.append("高潮部分不够突出")
                feedback_items.append("建议增加高潮情节")
        
        # === 逻辑合理性分析 ===
        elif dim_config["category"] == "logic_rationality":
            # 检测逻辑连接词和推理词
            logic_markers = ['因为', '所以', '因此', '然而', '但是', '虽然', '尽管', '既然', '如果', '那么', '于是', '于是乎']
            logic_count = sum(text.count(m) for m in logic_markers)
            
            # 检测因果关系
            cause_effect = text.count('因为') + text.count('导致') + text.count('使得')
            
            score = base_score
            if logic_count > 20: score += 1.5
            if logic_count > 50: score += 1.0
            if cause_effect > 5: score += 1.0
            
            # 检测明显的逻辑漏洞
            plot_holes = text.count('突然') + text.count('莫名其妙') + text.count('毫无预兆')
            if plot_holes > 10: score -= 1.0
            
            if logic_count > 20:
                criteria_met.append("事件发展符合内在逻辑")
                feedback_items.append("逻辑连接词丰富，推理严密")
            else:
                criteria_missed.append("逻辑连接略显不足")
                feedback_items.append("建议增加过渡性描述")
        
        # === 角色一致性分析 ===
        elif dim_config["category"] == "character_consistency":
            # 检测角色描写
            char_descriptions = ['性格', '气质', '外貌', '特点', '特点', '特点']
            char_count = sum(text.count(d) for d in char_descriptions)
            
            # 检测心理描写
            psychology = ['想', '觉得', '认为', '心理', '内心', '思绪', '念头', '感受']
            psy_count = sum(text.count(p) for p in psychology)
            
            # 检测角色名出现频率
            import random
            char_names = self._extract_character_names(text)
            name_freq = len(char_names)
            
            score = base_score
            if psy_count > 30: score += 1.0
            if name_freq > 5: score += 1.0
            if char_count > 10: score += 0.5
            
            if psy_count > 30:
                criteria_met.append("角色行为动机合理")
                feedback_items.append("心理描写丰富，角色行为有迹可循")
            else:
                criteria_missed.append("心理描写略显不足")
                feedback_items.append("建议增加角色内心戏")
        
        # === 风格匹配度分析 ===
        elif dim_config["category"] == "style_matching":
            # 检测风格元素
            style_markers = {
                '描写': text.count('描写'),
                '叙述': text.count('叙述'),
                '对话': text.count('说') + text.count('道'),
                '感叹': text.count('！') + text.count('啊') + text.count('呀')
            }
            
            total_markers = sum(style_markers.values())
            
            score = base_score
            if style_markers['描写'] > 20: score += 1.0
            if style_markers['叙述'] > 10: score += 0.5
            if style_markers['感叹'] > 20: score += 0.5
            
            # 检测文风一致性（标点使用）
            exclamation_ratio = text.count('！') / max(len(text), 1) * 1000
            if exclamation_ratio < 2: score += 0.5  # 不过于口语化
            
            if style_markers['描写'] > 20:
                criteria_met.append("语言风格前后统一稳定")
                feedback_items.append("描写细腻，文风稳定")
            else:
                criteria_missed.append("描写略显不足")
                feedback_items.append("建议增加场景和细节描写")
        
        # === 世界观一致性分析 ===
        elif dim_config["category"] == "world_consistency":
            # 检测世界观设定词
            world_elements = ['世界', '大陆', '帝国', '宗门', '境界', '修为', '法则', '规则', '力量', '能力']
            world_count = sum(text.count(e) for e in world_elements)
            
            # 检测地理/时间设定
            geo_time = ['城', '镇', '村', '山', '河', '海', '年', '月', '日', '时']
            geo_count = sum(text.count(g) for g in geo_time)
            
            score = base_score
            if world_count > 30: score += 1.5
            if geo_count > 50: score += 1.0
            
            if world_count > 30:
                criteria_met.append("世界观设定内部自洽")
                feedback_items.append("世界观设定丰富")
            else:
                criteria_missed.append("世界观设定略显单薄")
                feedback_items.append("建议加强世界观构建")
        
        # === 叙事流畅度分析 ===
        elif dim_config["category"] == "narrative_flow":
            # 检测过渡词
            transitions = ['然后', '接着', '随后', '之后', '于是', '这时', '此时', '此刻', '接下来']
            trans_count = sum(text.count(t) for t in transitions)
            
            # 检测段落长度
            paragraphs = [p for p in text.split('\n') if p.strip()]
            avg_para_len = sum(len(p) for p in paragraphs) / max(len(paragraphs), 1)
            
            score = base_score
            if trans_count > 15: score += 1.0
            if 50 < avg_para_len < 200: score += 1.0  # 适中段落长度
            if avg_para_len > 300: score -= 0.5  # 段落过长
            
            if trans_count > 15:
                criteria_met.append("段落过渡自然流畅")
                feedback_items.append("过渡自然，节奏流畅")
            else:
                criteria_missed.append("过渡略显生硬")
                feedback_items.append("建议增加过渡性语句")
        
        # === 情感冲击力分析 ===
        elif dim_config["category"] == "emotional_impact":
            # 检测情感词
            emotion_words = ['感动', '震撼', '愤怒', '悲伤', '恐惧', '喜悦', '激动', '心疼', '热血', '泪']
            emotion_count = sum(text.count(e) for e in emotion_words)
            
            # 检测感叹句
            exclamations = text.count('！')
            
            score = base_score
            if emotion_count > 15: score += 1.5
            if exclamations > 10: score += 1.0
            if emotion_count > 30: score += 1.0
            
            if emotion_count > 15:
                criteria_met.append("情感描写真实动人")
                feedback_items.append("情感表达丰富有感染力")
            else:
                criteria_missed.append("情感描写略显平淡")
                feedback_items.append("建议增加情感爆发点")
        
        # === 钩子强度分析 ===
        elif dim_config["category"] == "hook_strength":
            # 检测悬念设置
            suspense = ['？', '？', '悬念', '疑问', '好奇', '想知道', '为什么']
            suspense_count = sum(text.count(s) for s in suspense)
            
            # 检测结尾悬念
            ending_hooks = ['未完', '待续', '敬请', '下回', '待', '请', '未知', '悬']
            ending_hook = any(text[-200:].count(e) > 0 for e in ending_hooks) if len(text) > 200 else False
            
            score = base_score
            if suspense_count > 10: score += 1.0
            if ending_hook: score += 1.5
            
            # 开篇吸引力
            first_para = text[:500] if len(text) > 500 else text
            hook_openers = ['突然', '就在', '这一', '此时', '蓦然', '忽然']
            if any(first_para.count(h) > 0 for h in hook_openers): score += 0.5
            
            if suspense_count > 10 or ending_hook:
                criteria_met.append("开头吸引读者眼球")
                feedback_items.append("悬念设置合理，吸引追读")
            else:
                criteria_missed.append("悬念设置较少")
                feedback_items.append("建议增加悬念和期待感")
        
        else:
            score = base_score
        
        # 确保分数在1-10范围内
        score = min(10.0, max(1.0, score))
        
        return DimensionScore(
            name=dim_config["name"],
            category=dim_config["category"],
            weight=dim_config["weight"],
            score=score,
            criteria_met=criteria_met,
            criteria_missed=criteria_missed,
            feedback="; ".join(feedback_items) if feedback_items else "无明显问题"
        )
    
    def _extract_character_names(self, text: str) -> List[str]:
        """提取角色名"""
        # 简单匹配模式：连续的汉字（2-4字）
        names = re.findall(r'[\u4e00-\u9fff]{2,4}(?:说|道|问|答|道|笑|道|道)', text)
        return list(set(names))
    
    def _generate_feedback(self, dimensions: List[DimensionScore]) -> tuple:
        """生成反馈"""
        sorted_dims = sorted(dimensions, key=lambda d: d.score, reverse=True)
        
        # 优势
        strengths = [
            f"【{d.name}】{d.score:.1f}分 - {d.feedback}"
            for d in sorted_dims[:3] if d.score >= 7
        ]
        
        # 劣势
        weaknesses = [
            f"【{d.name}】{d.score:.1f}分 - {d.feedback}"
            for d in sorted_dims[-3:] if d.score < 6
        ]
        
        # 建议
        suggestions = []
        for d in sorted_dims[-3:]:
            if d.criteria_missed:
                suggestions.append(f"改进{d.name}：建议{d.criteria_missed[0]}")
        
        return (
            strengths or ["无明显优势"],
            weaknesses or ["无明显劣势"],
            suggestions or ["继续保持当前水平"]
        )
    
    def _generate_summary(self, evaluation: NovelEvaluation) -> str:
        """生成评测总结"""
        score = evaluation.weighted_score
        
        if score >= 85:
            level = "⭐⭐⭐⭐⭐ 顶级神作"
            desc = "八维表现均衡优秀，是同类题材中的典范之作"
        elif score >= 75:
            level = "⭐⭐⭐⭐ 优秀作品"
            desc = "整体质量上乘，在多个维度表现突出"
        elif score >= 65:
            level = "⭐⭐⭐ 良好水准"
            desc = "整体质量良好，有部分亮点但仍有提升空间"
        elif score >= 55:
            level = "⭐⭐ 中规中矩"
            desc = "达到基本水准，在某些维度有明显短板"
        else:
            level = "⭐ 存在较大问题"
            desc = "在多个维度存在明显不足，需要系统性改进"
        
        return f"{level}\n综合评分：{score:.1f}/100\n评价：{desc}"


def evaluate_novels_from_reference(
    reference_dir: str,
    output_path: str = None
) -> List[NovelEvaluation]:
    """从reference目录评测所有小说"""
    
    analyzer = NovelAnalyzer()
    evaluations = []
    
    # 获取所有txt文件
    ref_path = Path(reference_dir)
    txt_files = list(ref_path.glob("*.txt"))
    
    print(f"发现 {len(txt_files)} 本小说待评测...\n")
    
    for i, file_path in enumerate(txt_files[:10], 1):  # 评测前10本
        try:
            print(f"[{i}/10] 正在评测: {file_path.name}...")
            
            # 读取文件 - 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
            text = None
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        text = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if text is None:
                # 最后尝试忽略错误
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            
            # 提取书名和作者
            filename = file_path.stem
            if '作者：' in filename:
                parts = filename.split('作者：')
                novel_name = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else "未知"
            elif 'by' in filename:
                parts = filename.split('by')
                novel_name = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else "未知"
            else:
                novel_name = filename
                author = "未知"
            
            # 判断类型
            genre = "玄幻"  # 默认
            genre_keywords = {
                "求生": "末日求生", "废土": "末日废土", "列车": "列车求生",
                "修仙": "修仙", "玄幻": "玄幻", "都市": "都市",
                "恐怖": "恐怖悬疑", "诡异": "玄幻", "道异": "玄幻",
                "诡秘": "西幻", "遮天": "玄幻", "凡人": "修仙",
                "第一序列": "末日", "大奉": "仙侠", "夜无疆": "玄幻",
                "深空": "科幻", "玄鉴": "修仙"
            }
            for kw, g in genre_keywords.items():
                if kw in novel_name:
                    genre = g
                    break
            
            # 估算字数
            word_count = TextExtractor.estimate_word_count(text)
            print(f"  字数估算: {word_count:,} 字")
            
            # 分析
            evaluation = analyzer.analyze_text(text, novel_name, author, genre)
            evaluations.append(evaluation)
            
            print(f"  综合评分: {evaluation.weighted_score:.1f}/100\n")
            
        except Exception as e:
            print(f"  评测失败: {e}\n")
            continue
    
    # 保存结果
    if output_path:
        save_results(evaluations, output_path)
    
    return evaluations


def save_results(evaluations: List[NovelEvaluation], output_path: str):
    """保存评测结果"""
    
    # 转换为可序列化格式
    results = {
        "evaluation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_novels": len(evaluations),
        "evaluations": []
    }
    
    for ev in evaluations:
        results["evaluations"].append({
            "novel_name": ev.novel_name,
            "author": ev.author,
            "genre": ev.genre,
            "total_score": round(ev.total_score, 2),
            "weighted_score": round(ev.weighted_score, 1),
            "summary": ev.summary,
            "dimensions": [
                {
                    "name": d.name,
                    "category": d.category,
                    "weight": d.weight,
                    "score": round(d.score, 1),
                    "weighted": round(d.score * d.weight * 10, 1),
                    "criteria_met": d.criteria_met,
                    "criteria_missed": d.criteria_missed,
                    "feedback": d.feedback
                }
                for d in ev.dimensions
            ],
            "strengths": ev.strengths,
            "weaknesses": ev.weaknesses,
            "suggestions": ev.suggestions
        })
    
    # 保存JSON
    json_path = output_path.replace('.md', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 生成Markdown报告
    generate_markdown_report(evaluations, output_path)
    
    print(f"\n结果已保存至: {json_path} 和 {output_path}")


def generate_markdown_report(evaluations: List[NovelEvaluation], output_path: str):
    """生成Markdown格式的评测报告"""
    
    lines = []
    lines.append("# 长文本八维评分评测报告\n")
    lines.append(f"**评测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**评测数量**: {len(evaluations)} 本小说\n")
    lines.append("---\n\n")
    
    # 排名表
    sorted_evs = sorted(evaluations, key=lambda x: x.weighted_score, reverse=True)
    
    lines.append("## 📊 综合评分排名\n\n")
    lines.append("| 排名 | 小说名称 | 作者 | 类型 | 综合评分 | 评级 |\n")
    lines.append("|:---:|:---|:---|:---|:---:|:---|\n")
    
    for i, ev in enumerate(sorted_evs, 1):
        level = "顶级" if ev.weighted_score >= 85 else \
                "优秀" if ev.weighted_score >= 75 else \
                "良好" if ev.weighted_score >= 65 else \
                "一般" if ev.weighted_score >= 55 else "待改进"
        lines.append(f"| {i} | {ev.novel_name} | {ev.author} | {ev.genre} | **{ev.weighted_score:.1f}** | {level} |\n")
    
    lines.append("\n---\n\n")
    
    # 每本小说的详细评分
    for i, ev in enumerate(evaluations, 1):
        lines.append(f"## {i}. {ev.novel_name}\n")
        lines.append(f"**作者**: {ev.author}  |  **类型**: {ev.genre}  |  **评测时间**: {ev.evaluation_time}\n\n")
        
        lines.append("### 📈 八维评分详情\n\n")
        lines.append("```\n")
        lines.append(f"{'维度':<12} {'权重':<8} {'评分':<8} {'加权分':<8} {'状态':<10}\n")
        lines.append("-" * 50 + "\n")
        
        for d in sorted(ev.dimensions, key=lambda x: x.weight, reverse=True):
            status = "✅ 达标" if d.score >= 7 else "⚠️ 待改进" if d.score >= 5 else "❌ 不足"
            lines.append(f"{d.name:<12} {d.weight*100:>6.1f}%  {d.score:>5.1f}   {d.score*d.weight*10:>5.1f}    {status}\n")
        
        lines.append("-" * 50 + "\n")
        total_weighted = sum(d.score * d.weight for d in ev.dimensions) * 10
        lines.append(f"{'综合评分':<12} {'100.0%':>6}  {ev.total_score:>5.2f}   {total_weighted:>5.1f}\n")
        lines.append("```\n\n")
        
        lines.append("### 📝 评测总结\n\n")
        lines.append(ev.summary + "\n\n")
        
        if ev.strengths:
            lines.append("### ✨ 优势亮点\n\n")
            for s in ev.strengths:
                lines.append(f"- {s}\n")
            lines.append("\n")
        
        if ev.weaknesses:
            lines.append("### ⚠️ 不足之处\n\n")
            for w in ev.weaknesses:
                lines.append(f"- {w}\n")
            lines.append("\n")
        
        if ev.suggestions:
            lines.append("### 💡 改进建议\n\n")
            for s in ev.suggestions:
                lines.append(f"- {s}\n")
            lines.append("\n")
        
        lines.append("---\n\n")
    
    # 维度分析总结
    lines.append("## 📊 八维维度横向对比\n\n")
    lines.append("### 各维度平均分\n\n")
    lines.append("| 维度 | 平均分 | 表现 |\n")
    lines.append("|:---|:---:|:---|\n")
    
    dim_names = {
        "plot_consistency": "情节一致性",
        "logic_rationality": "逻辑合理性",
        "character_consistency": "角色一致性",
        "style_matching": "风格匹配度",
        "world_consistency": "世界观一致性",
        "narrative_flow": "叙事流畅度",
        "emotional_impact": "情感冲击力",
        "hook_strength": "钩子强度"
    }
    
    dim_scores = {}
    for d in evaluations[0].dimensions:
        dim_scores[d.category] = []
    
    for ev in evaluations:
        for d in ev.dimensions:
            dim_scores[d.category].append(d.score)
    
    avg_scores = [(cat, sum(scores)/len(scores)) for cat, scores in dim_scores.items()]
    avg_scores.sort(key=lambda x: x[1], reverse=True)
    
    for cat, avg in avg_scores:
        bar = "█" * int(avg) + "░" * (10 - int(avg))
        level = "优秀" if avg >= 7 else "良好" if avg >= 6 else "一般" if avg >= 5 else "待改进"
        lines.append(f"| {dim_names.get(cat, cat)} | {avg:.1f}/10 {bar} | {level} |\n")
    
    lines.append("\n---\n\n")
    lines.append("*本报告由 KimiFiction 长文本八维评分系统自动生成*\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


if __name__ == "__main__":
    import sys
    
    reference_dir = r"D:\310Programm\KimiFiction\reference"
    output_dir = r"D:\310Programm\KimiFiction\training_runs"
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"novel_evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    print("=" * 60)
    print("KimiFiction 长文本八维评分评测系统")
    print("=" * 60)
    print(f"\n评测目录: {reference_dir}")
    print(f"输出路径: {output_path}\n")
    
    evaluations = evaluate_novels_from_reference(reference_dir, output_path)
    
    print("\n" + "=" * 60)
    print("评测完成！")
    print("=" * 60)
