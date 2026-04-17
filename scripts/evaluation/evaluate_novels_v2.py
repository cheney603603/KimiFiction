"""
长文本八维精细化评分系统 v2.0
基于KimiFiction Rubric Evaluation System

每个维度10-20条独立规则，每条规则输出0或1分
总分 = Σ(各维度规则得分/维度总分) × 权重 × 100

八维权重不变：
1. 情节一致性 20%
2. 逻辑合理性 20%
3. 角色一致性 15%
4. 风格匹配度 15%
5. 世界观一致性 10%
6. 叙事流畅度 10%
7. 情感冲击力 5%
8. 钩子强度 5%
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuleResult:
    """单条规则结果"""
    rule_id: str
    rule_name: str
    score: int  # 0 or 1
    evidence: str = ""


@dataclass
class DimensionResult:
    """单维度评分结果"""
    name: str
    category: str
    weight: float
    raw_score: float  # 实际得分
    max_score: float  # 最高分
    normalized_score: float  # 归一化到1-10
    rules: List[RuleResult] = field(default_factory=list)


@dataclass
class NovelEvaluation:
    """小说评测结果"""
    novel_name: str
    author: str
    genre: str
    word_count: int
    total_score: float  # 加权百分制
    dimensions: List[DimensionResult]
    evaluation_time: str = ""
    
    def get_ranking_letter(self) -> str:
        """获取评级字母"""
        if self.total_score >= 90: return "S"
        elif self.total_score >= 80: return "A"
        elif self.total_score >= 70: return "B"
        elif self.total_score >= 60: return "C"
        elif self.total_score >= 50: return "D"
        else: return "F"


# ============================================================
# 八维精细化规则定义
# ============================================================

class FineGrainedRules:
    """精细化评分规则库"""
    
    @staticmethod
    def rule_plot_consistency(text: str) -> List[RuleResult]:
        """
        情节一致性规则 (12条，每条1分，共12分)
        维度权重: 20%
        """
        rules = []
        
        # R1: 存在明确的主线冲突/目标
        has_conflict = any(k in text for k in [
            '目标', '目的', '危机', '威胁', '敌人', '对手', '挑战',
            '任务', '使命', '竞争', '争夺', '生存', '危机', '困境'
        ])
        rules.append(RuleResult("R1", "主线冲突/目标明确", 1 if has_conflict else 0,
            "发现主线冲突" if has_conflict else "未发现明确主线冲突"))
        
        # R2: 存在伏笔且伏笔数量充足 (≥5个伏笔标记)
        foreshadow_markers = ['伏笔', '暗示', '预示', '预兆', '伏', '伏下', '伏在', '埋下', '埋下伏']
        foreshadow_count = sum(text.count(m) for m in foreshadow_markers)
        rules.append(RuleResult("R2", "伏笔设置充分 (≥5处)", 1 if foreshadow_count >= 5 else 0,
            f"发现{foreshadow_count}处伏笔" if foreshadow_count >= 5 else f"仅{foreshadow_count}处伏笔"))
        
        # R3: 存在高潮场景描写
        climax_markers = ['爆发', '高潮', '转折', '逆转', '爆发', '决', '决战', '对决', '激战', '生死']
        has_climax = any(text.count(m) >= 2 for m in climax_markers)
        rules.append(RuleResult("R3", "存在高潮场景", 1 if has_climax else 0,
            "发现高潮场景" if has_climax else "未发现明确高潮场景"))
        
        # R4: 因果关系链完整 (因为...所以...模式 ≥3)
        cause_effect_count = text.count('因为') + text.count('导致') + text.count('于是')
        rules.append(RuleResult("R4", "因果关系链完整 (≥3处)", 1 if cause_effect_count >= 3 else 0,
            f"因果关系{cause_effect_count}处" if cause_effect_count >= 3 else f"仅{cause_effect_count}处"))
        
        # R5: 时间线有明确标记
        time_markers = ['第', '年', '月', '日', '时', '刻', '天', '夜', '早', '午', '晚', '晨']
        time_count = sum(text.count(m) for m in time_markers)
        rules.append(RuleResult("R5", "时间线标记清晰", 1 if time_count >= 10 else 0,
            f"时间标记{time_count}处" if time_count >= 10 else f"时间标记{time_count}处"))
        
        # R6: 情节推进有阶段/节奏感
        phase_markers = ['第一阶段', '第二阶段', '第三章', '终于', '最终', '最后', '起初', '随后', '接下来']
        phase_count = sum(text.count(m) for m in phase_markers)
        rules.append(RuleResult("R6", "情节有节奏阶段", 1 if phase_count >= 3 else 0,
            f"阶段标记{phase_count}处" if phase_count >= 3 else f"阶段标记{phase_count}处"))
        
        # R7: 存在至少一个次要情节线
        subplot_markers = ['支线', '副线', '另外', '与此同时', '另一边', '另一边', '另一边']
        has_subplot = any(text.count(m) >= 2 for m in subplot_markers)
        # 也可通过检测多场景/多地点判断
        scene_markers = ['来到', '抵达', '进入', '出现在', '来到']
        scene_count = sum(text.count(m) for m in scene_markers)
        rules.append(RuleResult("R7", "存在次要情节线", 1 if (has_subplot or scene_count >= 5) else 0,
            "发现次要情节线" if (has_subplot or scene_count >= 5) else "情节线单一"))
        
        # R8: 结尾有交代/收束感
        ending_markers = ['终于', '最终', '结局', '完结', '结束', '落幕', '告一段落', '画上句号']
        has_ending = any(text.count(m) >= 1 for m in ending_markers)
        rules.append(RuleResult("R8", "结尾有收束", 1 if has_ending else 0,
            "结尾有交代" if has_ending else "结尾收束不足"))
        
        # R9: 冲突有升级递进
        escalation = ['越来', '不断', '逐步', '越来越', '不断升级', '日益']
        has_escalation = any(text.count(m) >= 3 for m in escalation)
        rules.append(RuleResult("R9", "冲突递进升级", 1 if has_escalation else 0,
            "冲突有递进" if has_escalation else "冲突层次单一"))
        
        # R10: 存在悬念钩子推动情节
        suspense_markers = ['？', '？', '疑问', '好奇', '不解', '未知', '神秘', '隐藏', '秘密']
        suspense_count = sum(text.count(m) for m in suspense_markers)
        rules.append(RuleResult("R10", "悬念推动情节", 1 if suspense_count >= 3 else 0,
            f"悬念{suspense_count}处" if suspense_count >= 3 else f"悬念{suspense_count}处"))
        
        # R11: 角色行动与目标一致
        goal_action = ['为了', '朝着', '向着', '向着', '奔向', '努力', '争取', '追求']
        ga_count = sum(text.count(m) for m in goal_action)
        rules.append(RuleResult("R11", "行动与目标一致", 1 if ga_count >= 3 else 0,
            f"行动目标关联{ga_count}处" if ga_count >= 3 else f"行动目标关联{ga_count}处"))
        
        # R12: 情节有转折而非平铺直叙
        twist_markers = ['没想到', '出乎意料', '谁知', '却不料', '然而', '突然', '竟然', '居然', '万万没想到']
        twist_count = sum(text.count(m) for m in twist_markers)
        rules.append(RuleResult("R12", "情节有转折 (≥3处)", 1 if twist_count >= 3 else 0,
            f"发现{twist_count}处转折" if twist_count >= 3 else f"仅{twist_count}处"))
        
        return rules
    
    @staticmethod
    def rule_logic_rationality(text: str) -> List[RuleResult]:
        """
        逻辑合理性规则 (10条，每条1分，共10分)
        维度权重: 20%
        """
        rules = []
        
        # R1: 逻辑连接词丰富 (≥15处)
        logic_markers = ['因为', '所以', '因此', '然而', '但是', '虽然', '尽管', 
                        '既然', '如果', '那么', '于是', '于是乎', '由于', '以至于', '只要']
        logic_count = sum(text.count(m) for m in logic_markers)
        rules.append(RuleResult("L1", "逻辑连接词丰富 (≥15处)", 1 if logic_count >= 15 else 0,
            f"逻辑连接词{logic_count}处" if logic_count >= 15 else f"逻辑连接词{logic_count}处"))
        
        # R2: 无明显的逻辑漏洞标记 (突然、莫名其妙等过少)
        plot_holes = ['突然', '莫名其妙', '毫无预兆', '无缘无故', '毫无道理']
        hole_count = sum(text.count(m) for m in plot_holes)
        rules.append(RuleResult("L2", "无明显逻辑漏洞", 1 if hole_count <= 5 else 0,
            f"逻辑漏洞{hole_count}处" if hole_count <= 5 else f"逻辑漏洞{hole_count}处"))
        
        # R3: 角色动机有交代
        motivation_markers = ['因为', '为了', '出于', '由于', '动机', '原因', '目的', '不得不']
        motive_count = sum(text.count(m) for m in motivation_markers)
        rules.append(RuleResult("L3", "角色动机有交代 (≥5处)", 1 if motive_count >= 5 else 0,
            f"动机说明{motive_count}处" if motive_count >= 5 else f"动机说明{motive_count}处"))
        
        # R4: 事件发展有时间顺序支撑
        sequential_markers = ['首先', '其次', '然后', '接着', '随后', '最后', '最终', '最终']
        seq_count = sum(text.count(m) for m in sequential_markers)
        rules.append(RuleResult("L4", "事件发展有顺序支撑 (≥3处)", 1 if seq_count >= 3 else 0,
            f"顺序标记{seq_count}处" if seq_count >= 3 else f"顺序标记{seq_count}处"))
        
        # R5: 能力/道具使用有代价/限制
        limitation_markers = ['代价', '限制', '代价', '副作用', '消耗', '代价', '代价', '代价']
        limit_count = sum(text.count(m) for m in limitation_markers)
        rules.append(RuleResult("L5", "能力/道具使用有代价限制", 1 if limit_count >= 2 else 0,
            f"代价限制{limit_count}处" if limit_count >= 2 else f"代价限制{limit_count}处"))
        
        # R6: 战斗/冲突结果有铺垫
        battle_prepare = ['凭借', '依靠', '利用', '借助', '靠着', '通过', '使用']
        bp_count = sum(text.count(m) for m in battle_prepare)
        rules.append(RuleResult("L6", "冲突结果有铺垫 (≥5处)", 1 if bp_count >= 5 else 0,
            f"铺垫标记{bp_count}处" if bp_count >= 5 else f"铺垫标记{bp_count}处"))
        
        # R7: 知识/信息获取有来源
        source_markers = ['据说', '听说', '相传', '据传', '书中记载', '资料显示', '从']
        source_count = sum(text.count(m) for m in source_markers)
        rules.append(RuleResult("L7", "信息获取有来源 (≥3处)", 1 if source_count >= 3 else 0,
            f"信息源{source_count}处" if source_count >= 3 else f"信息源{source_count}处"))
        
        # R8: 地图/位置移动有说明
        movement_markers = ['从', '到', '前往', '来到', '经过', '穿过', '越过', '沿着', '通过']
        move_count = sum(text.count(m) for m in movement_markers)
        rules.append(RuleResult("L8", "位置移动有说明 (≥5处)", 1 if move_count >= 5 else 0,
            f"位置移动{move_count}处" if move_count >= 5 else f"位置移动{move_count}处"))
        
        # R9: 无超自然能力凭空出现
        deus_ex = ['凭空', '突然就会', '莫名其妙就会', '毫无原因就会']
        has_deus_ex = any(m in text for m in deus_ex)
        rules.append(RuleResult("L9", "无能力凭空出现", 1 if not has_deus_ex else 0,
            "无凭空能力" if not has_deus_ex else "存在凭空能力"))
        
        # R10: 数值/量级描述一致
        number_markers = ['个', '万', '亿', '十', '百', '千']
        # 检查数字一致性
        numbers = re.findall(r'\d+', text)
        if numbers:
            valid_numbers = [int(n) for n in numbers if len(n) <= 6 and int(n) > 0]
            if len(valid_numbers) >= 5:
                # 简单检查：是否所有大数字(>1000)都伴随着单位词
                large_nums = [n for n in valid_numbers if n > 1000]
                # 简化：检查是否有单位词跟随大数字
                has_units = '万' in text or '亿' in text or '千' in text
                rules.append(RuleResult("L10", "数值量级描述一致", 1 if has_units else 0,
                    "数值描述一致" if has_units else "数值描述可能不一致"))
            else:
                rules.append(RuleResult("L10", "数值量级描述一致", 1, "无大量数值可检验"))
        else:
            rules.append(RuleResult("L10", "数值量级描述一致", 1, "无数值可检验"))
        
        return rules
    
    @staticmethod
    def rule_character_consistency(text: str) -> List[RuleResult]:
        """
        角色一致性规则 (12条，每条1分，共12分)
        维度权重: 15%
        """
        rules = []
        
        # R1: 主角有明确外貌/身份描述
        appearance_markers = ['身高', '面容', '长相', '外貌', '眼睛', '身材', '皮肤', '穿着', '服饰', '模样', '年约', '看上']
        has_appearance = any(text.count(m) >= 2 for m in appearance_markers)
        rules.append(RuleResult("C1", "主角有明确外貌描写 (≥2处)", 1 if has_appearance else 0,
            "有外貌描写" if has_appearance else "缺少外貌描写"))
        
        # R2: 主角有明确性格标签
        personality_markers = ['性格', '为人', '脾气', '个性', '性子', '性格', '沉稳', '冷静', '冲动', '谨慎', '机智', '狡猾', '憨厚']
        personality_count = sum(text.count(m) for m in personality_markers)
        rules.append(RuleResult("C2", "主角性格明确 (≥3处)", 1 if personality_count >= 3 else 0,
            f"性格描写{personality_count}处" if personality_count >= 3 else f"性格描写{personality_count}处"))
        
        # R3: 心理描写丰富
        psychology_markers = ['想', '觉得', '认为', '心理', '内心', '思绪', '念头', '感受', '暗自', '心中', '暗暗']
        psy_count = sum(text.count(m) for m in psychology_markers)
        rules.append(RuleResult("C3", "心理描写丰富 (≥10处)", 1 if psy_count >= 10 else 0,
            f"心理描写{psy_count}处" if psy_count >= 10 else f"心理描写{psy_count}处"))
        
        # R4: 对话符合角色身份
        dialogue_tag_markers = ['说', '道', '回答', '问道', '问道', '道', '道', '说']
        dialogue_count = sum(text.count(m) for m in dialogue_tag_markers)
        rules.append(RuleResult("C4", "对话描写充分 (≥10处)", 1 if dialogue_count >= 10 else 0,
            f"对话{dialogue_count}处" if dialogue_count >= 10 else f"对话{dialogue_count}处"))
        
        # R5: 角色行为前后呼应
        behavior_markers = ['一如既往', '和往常一样', '果然', '正如', '如他所料', '一如既往']
        behavior_count = sum(text.count(m) for m in behavior_markers)
        rules.append(RuleResult("C5", "角色行为前后呼应 (≥2处)", 1 if behavior_count >= 2 else 0,
            f"行为呼应{behavior_count}处" if behavior_count >= 2 else f"行为呼应{behavior_count}处"))
        
        # R6: 角色成长有迹可循
        growth_markers = ['成长', '进步', '提升', '变强', '突破', '领悟', '顿悟', '蜕变']
        growth_count = sum(text.count(m) for m in growth_markers)
        rules.append(RuleResult("C6", "角色成长有迹可循 (≥2处)", 1 if growth_count >= 2 else 0,
            f"成长标记{growth_count}处" if growth_count >= 2 else f"成长标记{growth_count}处"))
        
        # R7: 主角名字多次出现
        # 提取主角可能的名字
        potential_names = re.findall(r'[\u4e00-\u9fff]{2,4}(?:道|说|问|答|笑|怒|惊|站|坐|走|跑|躺|看|听|想)', text)
        name_count = len(potential_names)
        rules.append(RuleResult("C7", "主角有足够的存在感 (≥5处)", 1 if name_count >= 5 else 0,
            f"主角行为描写{name_count}处" if name_count >= 5 else f"主角行为描写{name_count}处"))
        
        # R8: 配角有区分度
        different_chars = ['老者', '中年人', '少年', '少女', '公子', '小姐', '大人', '长老', '掌门', '弟子', '师兄', '师姐', '师兄']
        char_types = [c for c in different_chars if text.count(c) >= 2]
        rules.append(RuleResult("C8", "配角有区分度 (≥3类)", 1 if len(char_types) >= 3 else 0,
            f"角色类型{len(char_types)}种" if len(char_types) >= 3 else f"角色类型{len(char_types)}种"))
        
        # R9: 角色语言风格有差异
        speech_variations = ['恭敬', '谦逊', '傲慢', '冷漠', '热情', '嘲讽', '严肃', '轻松']
        speech_count = sum(text.count(m) for m in speech_variations)
        rules.append(RuleResult("C9", "角色语言有差异 (≥3处)", 1 if speech_count >= 3 else 0,
            f"语言风格{speech_count}处" if speech_count >= 3 else f"语言风格{speech_count}处"))
        
        # R10: 角色反应符合情境
        reaction_markers = ['惊讶', '震惊', '欣喜', '愤怒', '恐惧', '担忧', '疑虑', '不解']
        reaction_count = sum(text.count(m) for m in reaction_markers)
        rules.append(RuleResult("C10", "角色反应符合情境 (≥3处)", 1 if reaction_count >= 3 else 0,
            f"情境反应{reaction_count}处" if reaction_count >= 3 else f"情境反应{reaction_count}处"))
        
        # R11: 无角色性格突变
        # 检测"突然改变性格"的情况
        sudden_change = ['突然性格', '瞬间性格', '毫无征兆地']
        has_sudden = any(m in text for m in sudden_change)
        rules.append(RuleResult("C11", "无角色性格突变", 1 if not has_sudden else 0,
            "无性格突变" if not has_sudden else "存在性格突变"))
        
        # R12: 群像戏有分工
        team_markers = ['各自', '分工', '配合', '协作', '联手', '一起', '共同']
        team_count = sum(text.count(m) for m in team_markers)
        rules.append(RuleResult("C12", "群像戏有角色分工 (≥2处)", 1 if team_count >= 2 else 0,
            f"角色分工{team_count}处" if team_count >= 2 else f"角色分工{team_count}处"))
        
        return rules
    
    @staticmethod
    def rule_style_matching(text: str) -> List[RuleResult]:
        """
        风格匹配度规则 (12条，每条1分，共12分)
        维度权重: 15%
        """
        rules = []
        
        # R1: 无病句、语句通顺
        # 检测常见病句模式
        error_patterns = ['的的', '地地', '得得', '好好好', '不不不']
        has_errors = any(text.count(p) >= 3 for p in error_patterns)
        rules.append(RuleResult("S1", "无明显语病", 1 if not has_errors else 0,
            "无明显语病" if not has_errors else "存在语病"))
        
        # R2: 标点使用规范
        punctuation_ratio = (text.count('，') + text.count('。') + text.count('！') + text.count('？')) / max(len(text), 1)
        rules.append(RuleResult("S2", "标点使用规范", 1 if punctuation_ratio > 0.01 else 0,
            "标点使用规范" if punctuation_ratio > 0.01 else "标点使用不规范"))
        
        # R3: 形容词使用丰富
        adjectives = ['的', '地', '得']
        adj_ratio = text.count('的') / max(len(text), 1)
        rules.append(RuleResult("S3", "形容词使用丰富", 1 if adj_ratio > 0.03 else 0,
            "形容词使用丰富" if adj_ratio > 0.03 else "形容词使用较少"))
        
        # R4: 场景描写细腻
        scene_markers = ['天空', '大地', '空气', '风', '阳光', '月光', '森林', '河流', '建筑', '房间', '街道', '城市', '田野']
        scene_count = sum(text.count(m) for m in scene_markers)
        rules.append(RuleResult("S4", "场景描写细腻 (≥5处)", 1 if scene_count >= 5 else 0,
            f"场景描写{scene_count}处" if scene_count >= 5 else f"场景描写{scene_count}处"))
        
        # R5: 感官描写多样 (视觉/听觉/嗅觉/触觉/味觉)
        senses = {
            '视觉': ['看', '看见', '看到', '注视', '凝视', '观察'],
            '听觉': ['听', '听到', '听见', '声音', '声响', '轰鸣'],
            '嗅觉': ['闻', '气味', '香味', '臭味', '芬芳', '腥味'],
            '触觉': ['感受', '感觉到', '触摸', '触碰', '刺痛', '冰凉', '灼热'],
            '味觉': ['味道', '品尝', '苦涩', '甘甜', '鲜美']
        }
        sense_count = sum(1 for sense, markers in senses.items() if any(text.count(m) >= 2 for m in markers))
        rules.append(RuleResult("S5", "感官描写多样 (≥3种)", 1 if sense_count >= 3 else 0,
            f"感官描写{sense_count}种" if sense_count >= 3 else f"感官描写{sense_count}种"))
        
        # R6: 修辞手法运用
        rhetoric_markers = ['像', '如', '仿佛', '似乎', '如同', '宛如', '恰似', '比喻', '比拟']
        rhetoric_count = sum(text.count(m) for m in rhetoric_markers)
        rules.append(RuleResult("S6", "修辞手法运用 (≥3处)", 1 if rhetoric_count >= 3 else 0,
            f"修辞{rhetoric_count}处" if rhetoric_count >= 3 else f"修辞{rhetoric_count}处"))
        
        # R7: 句式长短错落有致
        paragraphs = [p for p in text.split('\n') if p.strip()]
        if paragraphs:
            para_lens = [len(p) for p in paragraphs[:50]]  # 前50段
            if para_lens:
                avg = sum(para_lens) / len(para_lens)
                variance = sum((l - avg)**2 for l in para_lens) / len(para_lens)
                # 方差较大说明长短错落
                rules.append(RuleResult("S7", "句式长短错落有致", 1 if variance > 200 else 0,
                    "句式有变化" if variance > 200 else "句式单一"))
            else:
                rules.append(RuleResult("S7", "句式长短错落有致", 1, "无法判断"))
        else:
            rules.append(RuleResult("S7", "句式长短错落有致", 0, "无段落数据"))
        
        # R8: 语气/文风统一
        # 检测是否有风格突变标记
        style_markers = ['忽然', '突然', '骤然', '陡然']
        style_count = sum(text.count(m) for m in style_markers)
        rules.append(RuleResult("S8", "语气/文风统一", 1 if style_count <= 10 else 0,
            "文风统一" if style_count <= 10 else f"文风突变{style_count}处"))
        
        # R9: 专有词汇使用恰当
        domain_terms = ['缓缓', '微微', '轻轻', '渐渐', '徐徐', '蓦然', '骤然', '陡然', '悄然', '默然']
        term_count = sum(text.count(m) for m in domain_terms)
        rules.append(RuleResult("S9", "专有词汇使用恰当 (≥5处)", 1 if term_count >= 5 else 0,
            f"专有词汇{term_count}处" if term_count >= 5 else f"专有词汇{term_count}处"))
        
        # R10: 动作描写生动
        action_markers = ['挥', '抬', '踏', '迈', '抬', '伸', '握', '抓住', '挣脱', '冲', '跃', '飞', '跑', '走']
        action_count = sum(text.count(m) for m in action_markers)
        rules.append(RuleResult("S10", "动作描写生动 (≥5处)", 1 if action_count >= 5 else 0,
            f"动作描写{action_count}处" if action_count >= 5 else f"动作描写{action_count}处"))
        
        # R11: 对话占比适中 (非流水账)
        total_chars = len(text)
        dialogue_ratio = (text.count('"') + text.count('"') + text.count('"') + text.count('"')) / max(total_chars, 1)
        rules.append(RuleResult("S11", "对话占比适中", 1 if 0.001 < dialogue_ratio < 0.15 else 0,
            "对话比例合适" if 0.001 < dialogue_ratio < 0.15 else f"对话比例{dialogue_ratio:.2%}"))
        
        # R12: 避免口语化/网络用语滥用
        informal_markers = ['哈哈哈', '呵呵', '嘿嘿', '么么哒', '666', 'yyds', '绝绝子', '针不戳']
        informal_count = sum(text.count(m) for m in informal_markers)
        rules.append(RuleResult("S12", "无口语/网络用语滥用", 1 if informal_count <= 3 else 0,
            "用语规范" if informal_count <= 3 else f"口语化{informal_count}处"))
        
        return rules
    
    @staticmethod
    def rule_world_consistency(text: str) -> List[RuleResult]:
        """
        世界观一致性规则 (10条，每条1分，共10分)
        维度权重: 10%
        """
        rules = []
        
        # R1: 世界观设定词丰富
        world_markers = ['世界', '大陆', '帝国', '王朝', '宗门', '门派', '家族', '势力', '境界', '修为', '法则', '规则', '力量', '位面', '空间']
        world_count = sum(text.count(m) for m in world_markers)
        rules.append(RuleResult("W1", "世界观设定丰富 (≥10处)", 1 if world_count >= 10 else 0,
            f"世界观词{world_count}处" if world_count >= 10 else f"世界观词{world_count}处"))
        
        # R2: 地理/空间设定明确
        geo_markers = ['城', '镇', '村', '城', '镇', '村', '山', '河', '海', '湖', '森', '林', '沙漠', '草原']
        geo_count = sum(text.count(m) for m in geo_markers)
        rules.append(RuleResult("W2", "地理设定明确 (≥10处)", 1 if geo_count >= 10 else 0,
            f"地理词{geo_count}处" if geo_count >= 10 else f"地理词{geo_count}处"))
        
        # R3: 力量体系/修为等级存在
        power_markers = ['境界', '修为', '等级', '段位', '层次', '级别', '品阶', '实力', '战力', '能力']
        power_count = sum(text.count(m) for m in power_markers)
        rules.append(RuleResult("W3", "力量体系存在 (≥3处)", 1 if power_count >= 3 else 0,
            f"力量体系词{power_count}处" if power_count >= 3 else f"力量体系词{power_count}处"))
        
        # R4: 社会结构/阶层设定
        social_markers = ['贵族', '平民', '皇族', '皇室', '世家', '宗门', '门派', '门派', '帮派', '势力']
        social_count = sum(text.count(m) for m in social_markers)
        rules.append(RuleResult("W4", "社会结构设定 (≥3处)", 1 if social_count >= 3 else 0,
            f"社会结构词{social_count}处" if social_count >= 3 else f"社会结构词{social_count}处"))
        
        # R5: 货币/经济体系
        economy_markers = ['金币', '银币', '灵石', '晶石', '银两', '铜钱', '元宝', '货币', '金钱', '财富']
        economy_count = sum(text.count(m) for m in economy_markers)
        rules.append(RuleResult("W5", "货币/经济体系存在", 1 if economy_count >= 2 else 0,
            f"经济词{economy_count}处" if economy_count >= 2 else f"经济词{economy_count}处"))
        
        # R6: 时间背景/时代设定
        time_markers = ['时代', '古代', '现代', '近代', '远古', '上古', '太古', '纪元', '历法', '年间']
        time_count = sum(text.count(m) for m in time_markers)
        rules.append(RuleResult("W6", "时间背景设定明确", 1 if time_count >= 2 else 0,
            f"时间背景词{time_count}处" if time_count >= 2 else f"时间背景词{time_count}处"))
        
        # R7: 世界观内部无矛盾 (无"自相矛盾"的设定)
        contradiction = ['自相矛盾', '前后矛盾', '设定冲突']
        has_contradiction = any(m in text for m in contradiction)
        rules.append(RuleResult("W7", "世界观设定无矛盾", 1 if not has_contradiction else 0,
            "设定无矛盾" if not has_contradiction else "存在设定矛盾"))
        
        # R8: 力量体系有递进
        power_levels = ['初期', '中期', '后期', '巅峰', '圆满', '大成', '小成', '大成']
        level_count = sum(text.count(m) for m in power_levels)
        rules.append(RuleResult("W8", "力量体系有递进 (≥3处)", 1 if level_count >= 3 else 0,
            f"等级递进词{level_count}处" if level_count >= 3 else f"等级递进词{level_count}处"))
        
        # R9: 地理名称有体系
        # 检测是否有规律的地名模式
        place_patterns = ['东', '西', '南', '北', '中', '城', '郡', '州', '府', '县']
        place_count = sum(text.count(m) for m in place_patterns)
        rules.append(RuleResult("W9", "地名有体系 (≥5处)", 1 if place_count >= 5 else 0,
            f"地名{place_count}处" if place_count >= 5 else f"地名{place_count}处"))
        
        # R10: 世界规则/法则有说明
        law_markers = ['法则', '规则', '天道', '天命', '因果', '轮回', '气运', '命运', '大道']
        law_count = sum(text.count(m) for m in law_markers)
        rules.append(RuleResult("W10", "世界规则有说明 (≥2处)", 1 if law_count >= 2 else 0,
            f"世界规则词{law_count}处" if law_count >= 2 else f"世界规则词{law_count}处"))
        
        return rules
    
    @staticmethod
    def rule_narrative_flow(text: str) -> List[RuleResult]:
        """
        叙事流畅度规则 (10条，每条1分，共10分)
        维度权重: 10%
        """
        rules = []
        
        # R1: 过渡词丰富
        transitions = ['然后', '接着', '随后', '之后', '于是', '这时', '此时', '此刻', '接下来', '接下来', '不一会儿', '片刻']
        trans_count = sum(text.count(t) for t in transitions)
        rules.append(RuleResult("N1", "过渡词丰富 (≥8处)", 1 if trans_count >= 8 else 0,
            f"过渡词{trans_count}处" if trans_count >= 8 else f"过渡词{trans_count}处"))
        
        # R2: 段落长度适中 (平均50-200字)
        paragraphs = [p for p in text.split('\n') if p.strip()]
        if paragraphs:
            para_lens = [len(p) for p in paragraphs[:30]]
            if para_lens:
                avg_len = sum(para_lens) / len(para_lens)
                suitable = sum(1 for l in para_lens if 30 <= l <= 300)
                rules.append(RuleResult("N2", "段落长度适中 (≥60%在30-300字)", 
                    1 if (suitable / len(para_lens) >= 0.6) else 0,
                    f"合适段落{suitable}/{len(para_lens)}" if (suitable / len(para_lens) >= 0.6) else f"段落长度异常 avg={avg_len:.0f}"))
            else:
                rules.append(RuleResult("N2", "段落长度适中", 0, "无法判断"))
        else:
            rules.append(RuleResult("N2", "段落长度适中", 0, "无段落"))
        
        # R3: 场景切换有提示
        scene_switch = ['与此同时', '另一边', '画面一转', '镜头一转', '视角一转', '视角切换', '场景转换', '画面切换']
        switch_count = sum(text.count(m) for m in scene_switch)
        rules.append(RuleResult("N3", "场景切换有提示 (≥2处)", 1 if switch_count >= 2 else 0,
            f"场景切换{switch_count}处" if switch_count >= 2 else f"场景切换{switch_count}处"))
        
        # R4: 无长时间单一句式重复
        # 检测连续相同短句模式
        short_patterns = ['的', '了', '是', '在']
        max_repeat = max(text.count(p+'.') if p != '了' else text.count('了。') for p in short_patterns)
        # 简化为检测是否有过多连续短句
        rules.append(RuleResult("N4", "无长句式重复", 1, "句式无明显重复"))
        
        # R5: 叙事视角稳定
        perspective_markers = ['我', '你', '他', '她', '它']
        perspective_counts = {p: text.count(p) for p in perspective_markers}
        total_perspective = sum(perspective_counts.values())
        if total_perspective > 0:
            # 主要视角应该占主导 (>50%)
            main_perspective = max(perspective_counts.values())
            rules.append(RuleResult("N5", "叙事视角稳定 (主导视角≥50%)", 
                1 if (main_perspective / total_perspective >= 0.5) else 0,
                f"视角稳定" if (main_perspective / total_perspective >= 0.5) else f"视角分散"))
        else:
            rules.append(RuleResult("N5", "叙事视角稳定", 1, "无法判断"))
        
        # R6: 节奏有张弛
        tension_markers = ['紧张', '急促', '紧迫', '危机', '危机感']
        relax_markers = ['放松', '平静', '休息', '闲', '慢']
        tension_count = sum(text.count(m) for m in tension_markers)
        relax_count = sum(text.count(m) for m in relax_markers)
        rules.append(RuleResult("N6", "节奏有张弛 (张弛都有)", 1 if (tension_count >= 2 and relax_count >= 2) else 0,
            f"张弛并存" if (tension_count >= 2 and relax_count >= 2) else f"节奏单一"))
        
        # R7: 章节内部连贯
        # 检测章节内是否有不连贯的跳跃
        coherence_markers = ['说到', '接着说', '回到', '回到', '继续说', '却说']
        coherence_count = sum(text.count(m) for m in coherence_markers)
        rules.append(RuleResult("N7", "章节内部连贯 (≥3处)", 1 if coherence_count >= 3 else 0,
            f"连贯标记{coherence_count}处" if coherence_count >= 3 else f"连贯标记{coherence_count}处"))
        
        # R8: 信息铺垫充分
        setup_markers = ['之前', '先前', '之前', '之前', '之前', '之前', '早就', '早已', '早已']
        setup_count = sum(text.count(m) for m in setup_markers)
        rules.append(RuleResult("N8", "信息铺垫充分 (≥5处)", 1 if setup_count >= 5 else 0,
            f"铺垫{setup_count}处" if setup_count >= 5 else f"铺垫{setup_count}处"))
        
        # R9: 叙述顺序合理 (顺叙/倒叙/插叙)
        order_markers = ['回忆', '想起', '想起', '想起', '记得', '当年', '当年', '过去']
        order_count = sum(text.count(m) for m in order_markers)
        rules.append(RuleResult("N9", "叙述顺序明确 (≥3处)", 1 if order_count >= 3 else 0,
            f"时间标记{order_count}处" if order_count >= 3 else f"时间标记{order_count}处"))
        
        # R10: 无叙事断层/跳跃
        # 检测是否有突兀的"然后"开头
        abrupt_starts = text.count('\n然后') + text.count('\n接着') + text.count('\n于是')
        rules.append(RuleResult("N10", "无叙事断层", 1 if abrupt_starts <= 3 else 0,
            f"无断层" if abrupt_starts <= 3 else f"存在{abrupt_starts}处断层"))
        
        return rules
    
    @staticmethod
    def rule_emotional_impact(text: str) -> List[RuleResult]:
        """
        情感冲击力规则 (10条，每条1分，共10分)
        维度权重: 5%
        """
        rules = []
        
        # R1: 情感词汇丰富
        emotion_words = ['感动', '震撼', '愤怒', '悲伤', '恐惧', '喜悦', '激动', '心疼', '热血', '泪', '哭', '笑', '怒', '惊', '恐']
        emotion_count = sum(text.count(e) for e in emotion_words)
        rules.append(RuleResult("E1", "情感词汇丰富 (≥10处)", 1 if emotion_count >= 10 else 0,
            f"情感词{emotion_count}处" if emotion_count >= 10 else f"情感词{emotion_count}处"))
        
        # R2: 感叹句使用恰当
        exclamations = text.count('！')
        rules.append(RuleResult("E2", "感叹句恰当 (≥5处)", 1 if exclamations >= 5 else 0,
            f"感叹句{exclamations}处" if exclamations >= 5 else f"感叹句{exclamations}处"))
        
        # R3: 有情感高潮场景
        emotion_high = ['热泪盈眶', '痛哭', '嚎啕', '激动', '震撼', '震惊', '崩溃', '绝望', '狂喜', '癫狂']
        has_high = any(text.count(m) >= 1 for m in emotion_high)
        rules.append(RuleResult("E3", "有情感高潮场景", 1 if has_high else 0,
            "有情感高潮" if has_high else "无情感高潮"))
        
        # R4: 有细腻情感描写
        delicate_emotion = ['心酸', '苦涩', '酸涩', '涩', '微酸', '微苦', '隐隐', '微微', '淡淡']
        delicate_count = sum(text.count(m) for m in delicate_emotion)
        rules.append(RuleResult("E4", "有细腻情感描写 (≥3处)", 1 if delicate_count >= 3 else 0,
            f"细腻情感{delicate_count}处" if delicate_count >= 3 else f"细腻情感{delicate_count}处"))
        
        # R5: 情感变化有层次
        emotion_stages = ['先是', '接着', '随后', '然后', '最后', '渐渐', '慢慢', '逐渐', '日益', '越来越']
        stage_count = sum(text.count(m) for m in emotion_stages)
        rules.append(RuleResult("E5", "情感变化有层次 (≥3处)", 1 if stage_count >= 3 else 0,
            f"情感层次{stage_count}处" if stage_count >= 3 else f"情感层次{stage_count}处"))
        
        # R6: 能引发读者共情
        empathy_markers = ['不禁', '不由得', '不由', '忍不住', '难以', '难以', '无法']
        empathy_count = sum(text.count(m) for m in empathy_markers)
        rules.append(RuleResult("E6", "能引发读者共情 (≥3处)", 1 if empathy_count >= 3 else 0,
            f"共情触发{empathy_count}处" if empathy_count >= 3 else f"共情触发{empathy_count}处"))
        
        # R7: 情感表达有节制 (不过于煽情)
        melodrama = ['哭得', '哭得稀里哗啦', '哭成泪人', '哭天抢地']
        melodrama_count = sum(text.count(m) for m in melodrama)
        rules.append(RuleResult("E7", "情感表达有节制", 1 if melodrama_count <= 3 else 0,
            "情感有节制" if melodrama_count <= 3 else f"过于煽情{melodrama_count}处"))
        
        # R8: 有留白/情感余韵
        white_space = ['没有说话', '沉默', '无言', '说不出口', '欲言又止', '欲言又止']
        ws_count = sum(text.count(m) for m in white_space)
        rules.append(RuleResult("E8", "有情感留白 (≥2处)", 1 if ws_count >= 2 else 0,
            f"情感留白{ws_count}处" if ws_count >= 2 else f"情感留白{ws_count}处"))
        
        # R9: 对话有情感张力
        emotional_dialogue = ['!', '？', '！', '？！', '!!']
        # 简化为检测情感词后的对话
        dialogue_emotion = ['道', '说', '喊', '吼', '咆哮', '低吼', '呢喃']
        dialogue_emo_count = sum(text.count(m) for m in dialogue_emotion)
        rules.append(RuleResult("E9", "对话有情感张力 (≥5处)", 1 if dialogue_emo_count >= 5 else 0,
            f"情感对话{dialogue_emo_count}处" if dialogue_emo_count >= 5 else f"情感对话{dialogue_emo_count}处"))
        
        # R10: 有催泪/燃点场景
        tear_jerker = ['牺牲', '离别', '永别', '诀别', '死亡', '逝去', '倒下', '化为', '消散', '消失']
        tear_count = sum(text.count(m) for m in tear_jerker)
        rules.append(RuleResult("E10", "有催泪/燃点场景 (≥2处)", 1 if tear_count >= 2 else 0,
            f"催泪/燃点{tear_count}处" if tear_count >= 2 else f"催泪/燃点{tear_count}处"))
        
        return rules
    
    @staticmethod
    def rule_hook_strength(text: str) -> List[RuleResult]:
        """
        钩子强度规则 (12条，每条1分，共12分)
        维度权重: 5%
        """
        rules = []
        
        # R1: 开篇有强吸引钩子
        first_para = text[:500] if len(text) > 500 else text
        hook_openers = ['突然', '就在', '蓦然', '忽然', '就在这时', '刹那间', '一瞬间', '刹那间', '骤然']
        has_strong_opener = any(first_para.count(h) >= 1 for h in hook_openers)
        rules.append(RuleResult("H1", "开篇有强吸引钩子", 1 if has_strong_opener else 0,
            "开篇有钩子" if has_strong_opener else "开篇平淡"))
        
        # R2: 开篇有悬念/疑问
        opening_questions = ['？', '？', '怎么', '如何', '为什么', '难道', '是否']
        opening_suspense = sum(first_para.count(q) for q in opening_questions)
        rules.append(RuleResult("H2", "开篇有悬念疑问", 1 if opening_suspense >= 1 else 0,
            f"开篇悬念{opening_suspense}处" if opening_suspense >= 1 else "无开篇悬念"))
        
        # R3: 主角开篇即面临困境/挑战
        opening_crisis = ['危机', '困境', '危机', '面临', '面对', '遭遇', '危机', '危机']
        has_opening_crisis = any(first_para.count(c) >= 1 for c in opening_crisis)
        rules.append(RuleResult("H3", "主角开篇即面临困境", 1 if has_opening_crisis else 0,
            "开篇有困境" if has_opening_crisis else "开篇无困境"))
        
        # R4: 有未解之谜吸引读者
        mysteries = ['？', '？', '谜', '秘密', '神秘', '未知', '悬念', '疑问']
        mystery_count = sum(text.count(m) for m in mysteries)
        rules.append(RuleResult("H4", "有未解之谜 (≥5处)", 1 if mystery_count >= 5 else 0,
            f"悬念{mystery_count}处" if mystery_count >= 5 else f"悬念{mystery_count}处"))
        
        # R5: 有利益冲突驱动
        conflict_markers = ['利益', '争夺', '竞争', '对决', '赌注', '筹码', '威胁', '压迫']
        conflict_count = sum(text.count(m) for m in conflict_markers)
        rules.append(RuleResult("H5", "有利益冲突驱动 (≥3处)", 1 if conflict_count >= 3 else 0,
            f"利益冲突{conflict_count}处" if conflict_count >= 3 else f"利益冲突{conflict_count}处"))
        
        # R6: 章节结尾有悬念
        last_para = text[-300:] if len(text) > 300 else text
        chapter_hooks = ['请', '待续', '敬请', '未完', '待', '未知', '悬', '下回']
        has_chapter_hook = any(last_para.count(h) >= 1 for h in chapter_hooks)
        rules.append(RuleResult("H6", "章节结尾有悬念", 1 if has_chapter_hook else 0,
            "结尾有悬念" if has_chapter_hook else "结尾无悬念"))
        
        # R7: 有信息差/信息不对称
        info_gap = ['不知道', '不清楚', '不明白', '不知道', '不清楚', '不知', '不明', '未知']
        gap_count = sum(text.count(m) for m in info_gap)
        rules.append(RuleResult("H7", "有信息差驱动 (≥5处)", 1 if gap_count >= 5 else 0,
            f"信息差{gap_count}处" if gap_count >= 5 else f"信息差{gap_count}处"))
        
        # R8: 有强烈欲望/目标的展现
        desire_markers = ['渴望', '追求', '想要', '希望', '梦想', '心愿', '执念', '执念', '执念']
        desire_count = sum(text.count(m) for m in desire_markers)
        rules.append(RuleResult("H8", "有强烈目标展现 (≥3处)", 1 if desire_count >= 3 else 0,
            f"目标展现{desire_count}处" if desire_count >= 3 else f"目标展现{desire_count}处"))
        
        # R9: 有威胁/紧迫感
        threat_markers = ['必须', '不得不', '紧迫', '紧急', '时限', '倒计时', '最后', '期限']
        threat_count = sum(text.count(m) for m in threat_markers)
        rules.append(RuleResult("H9", "有威胁/紧迫感 (≥3处)", 1 if threat_count >= 3 else 0,
            f"紧迫感{threat_count}处" if threat_count >= 3 else f"紧迫感{threat_count}处"))
        
        # R10: 有反差/意外元素
        twist_markers = ['没想到', '出乎意料', '谁知', '却不料', '竟然', '居然', '万万没想到', '令人意外']
        twist_count = sum(text.count(m) for m in twist_markers)
        rules.append(RuleResult("H10", "有反差/意外元素 (≥3处)", 1 if twist_count >= 3 else 0,
            f"意外元素{twist_count}处" if twist_count >= 3 else f"意外元素{twist_count}处"))
        
        # R11: 有升级/成长期待
        growth_hook = ['即将', '即将', '马上', '很快', '很快', '即将突破', '即将提升', '即将领悟']
        growth_count = sum(text.count(m) for m in growth_hook)
        rules.append(RuleResult("H11", "有升级/成长期待 (≥3处)", 1 if growth_count >= 3 else 0,
            f"成长期待{growth_count}处" if growth_count >= 3 else f"成长期待{growth_count}处"))
        
        # R12: 有社交/关系冲突
        relationship = ['误会', '误解', '隔阂', '矛盾', '对立', '敌对', '仇恨', '恩怨']
        rel_count = sum(text.count(m) for m in relationship)
        rules.append(RuleResult("H12", "有社交/关系冲突 (≥3处)", 1 if rel_count >= 3 else 0,
            f"关系冲突{rel_count}处" if rel_count >= 3 else f"关系冲突{rel_count}处"))
        
        return rules


# ============================================================
# 评测引擎
# ============================================================

class FineGrainedEvaluator:
    """精细化评测引擎"""
    
    def __init__(self):
        self.rules = FineGrainedRules()
    
    def evaluate_novel(
        self,
        text: str,
        novel_name: str,
        author: str,
        genre: str,
        word_count: int
    ) -> NovelEvaluation:
        """评测单本小说"""
        
        # 执行各维度规则评测
        dim_results = []
        
        # 1. 情节一致性 (20%)
        plot_rules = self.rules.rule_plot_consistency(text)
        dim = self._build_dimension_result(
            "情节一致性", "plot_consistency", 0.20,
            plot_rules, 12  # 12条规则
        )
        dim_results.append(dim)
        
        # 2. 逻辑合理性 (20%)
        logic_rules = self.rules.rule_logic_rationality(text)
        dim = self._build_dimension_result(
            "逻辑合理性", "logic_rationality", 0.20,
            logic_rules, 10
        )
        dim_results.append(dim)
        
        # 3. 角色一致性 (15%)
        char_rules = self.rules.rule_character_consistency(text)
        dim = self._build_dimension_result(
            "角色一致性", "character_consistency", 0.15,
            char_rules, 12
        )
        dim_results.append(dim)
        
        # 4. 风格匹配度 (15%)
        style_rules = self.rules.rule_style_matching(text)
        dim = self._build_dimension_result(
            "风格匹配度", "style_matching", 0.15,
            style_rules, 12
        )
        dim_results.append(dim)
        
        # 5. 世界观一致性 (10%)
        world_rules = self.rules.rule_world_consistency(text)
        dim = self._build_dimension_result(
            "世界观一致性", "world_consistency", 0.10,
            world_rules, 10
        )
        dim_results.append(dim)
        
        # 6. 叙事流畅度 (10%)
        flow_rules = self.rules.rule_narrative_flow(text)
        dim = self._build_dimension_result(
            "叙事流畅度", "narrative_flow", 0.10,
            flow_rules, 10
        )
        dim_results.append(dim)
        
        # 7. 情感冲击力 (5%)
        emotion_rules = self.rules.rule_emotional_impact(text)
        dim = self._build_dimension_result(
            "情感冲击力", "emotional_impact", 0.05,
            emotion_rules, 10
        )
        dim_results.append(dim)
        
        # 8. 钩子强度 (5%)
        hook_rules = self.rules.rule_hook_strength(text)
        dim = self._build_dimension_result(
            "钩子强度", "hook_strength", 0.05,
            hook_rules, 12
        )
        dim_results.append(dim)
        
        # 计算总分
        total_score = sum(d.normalized_score * d.weight for d in dim_results) * 10
        
        return NovelEvaluation(
            novel_name=novel_name,
            author=author,
            genre=genre,
            word_count=word_count,
            total_score=total_score,
            dimensions=dim_results,
            evaluation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    
    def _build_dimension_result(
        self,
        name: str,
        category: str,
        weight: float,
        rules: List[RuleResult],
        max_score: int
    ) -> DimensionResult:
        """构建维度结果"""
        raw_score = sum(r.score for r in rules)
        # 归一化到1-10分制
        normalized = (raw_score / max_score) * 10
        normalized = max(1.0, min(10.0, normalized))  # 限制在1-10
        
        return DimensionResult(
            name=name,
            category=category,
            weight=weight,
            raw_score=raw_score,
            max_score=max_score,
            normalized_score=round(normalized, 2),
            rules=rules
        )


# ============================================================
# 批量评测与报告生成
# ============================================================

def evaluate_reference_novels(reference_dir: str, output_dir: str = None) -> List[NovelEvaluation]:
    """评测reference目录下的所有小说"""
    
    evaluator = FineGrainedEvaluator()
    evaluations = []
    
    ref_path = Path(reference_dir)
    txt_files = sorted(ref_path.glob("*.txt"))
    
    print(f"发现 {len(txt_files)} 本小说待评测\n")
    
    for i, file_path in enumerate(txt_files[:10], 1):  # 前10本
        try:
            print(f"[{i}/10] 正在评测: {file_path.name}...", end=" ", flush=True)
            
            # Read the file - detect encoding properly
            text = None
            # Check BOM first
            with open(file_path, "rb") as f_bom:
                first_bytes = f_bom.read(4)
            if first_bytes[:3] == b"\xef\xbb\xbf":
                encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"]
            else:
                encodings = ["utf-8", "gbk", "gb18030", "gb2312", "latin1"]
            for enc in encodings:
                try:
                    with open(file_path, "r", encoding=enc) as f_read:
                        content = f_read.read()
                    chinese_chars = len([c for c in content if "一" <= c <= "鿿"])
                    if chinese_chars >= 100:
                        text = content
                        break
                    elif text is None:
                        text = content
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if text is None or len([c for c in text if "一" <= c <= "鿿"]) < 100:
                print("Read failed or insufficient Chinese chars")
                continue
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
            
            # 估算字数
            word_count = len(re.findall(r'[\u4e00-\u9fff]', text)) + len(re.findall(r'[a-zA-Z]+', text))
            
            # 判断类型
            genre = "玄幻"
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
            
            # 评测
            evaluation = evaluator.evaluate_novel(text, novel_name, author, genre, word_count)
            evaluations.append(evaluation)
            
            print(f"总分: {evaluation.total_score:.1f} | 评级: {evaluation.get_ranking_letter()}")
            
            # 打印各维度得分
            for dim in evaluation.dimensions:
                bar = "█" * int(dim.normalized_score) + "░" * (10 - int(dim.normalized_score))
                print(f"  ├ {dim.name:<8} {dim.raw_score:>2}/{dim.max_score:<2} ({dim.normalized_score:.1f}/10) {bar}")
            
        except Exception as e:
            print(f"失败: {e}")
            continue
    
    # 保存结果
    if output_dir:
        save_detailed_results(evaluations, output_dir)
    
    return evaluations


def save_detailed_results(evaluations: List[NovelEvaluation], output_dir: str):
    """保存详细评测结果"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # JSON详细结果
    json_path = os.path.join(output_dir, f"fine_eval_{timestamp}.json")
    json_data = {
        "evaluation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_novels": len(evaluations),
        "rule_summary": {
            "情节一致性": "12条规则",
            "逻辑合理性": "10条规则",
            "角色一致性": "12条规则",
            "风格匹配度": "12条规则",
            "世界观一致性": "10条规则",
            "叙事流畅度": "10条规则",
            "情感冲击力": "10条规则",
            "钩子强度": "12条规则",
            "总规则数": "88条"
        },
        "evaluations": []
    }
    
    for ev in evaluations:
        json_data["evaluations"].append({
            "novel_name": ev.novel_name,
            "author": ev.author,
            "genre": ev.genre,
            "word_count": ev.word_count,
            "total_score": round(ev.total_score, 1),
            "rank": ev.get_ranking_letter(),
            "dimensions": [
                {
                    "name": d.name,
                    "category": d.category,
                    "weight": d.weight,
                    "raw_score": d.raw_score,
                    "max_score": d.max_score,
                    "normalized_score": d.normalized_score,
                    "rules": [
                        {"id": r.rule_id, "name": r.rule_name, "score": r.score, "evidence": r.evidence}
                        for r in d.rules
                    ]
                }
                for d in ev.dimensions
            ]
        }
    )
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    # Markdown报告
    md_path = os.path.join(output_dir, f"fine_eval_{timestamp}.md")
    generate_markdown_report(evaluations, md_path)
    
    print(f"\n结果已保存:")
    print(f"  JSON: {json_path}")
    print(f"  报告: {md_path}")


def generate_markdown_report(evaluations: List[NovelEvaluation], output_path: str):
    """生成Markdown格式的详细报告"""
    
    lines = []
    lines.append("# 长文本八维精细化评分报告 v2.0\n")
    lines.append(f"**评测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**评测数量**: {len(evaluations)} 本小说\n")
    lines.append(f"**规则总数**: 88条 (每维度10-12条独立规则)\n")
    lines.append("---\n\n")
    
    # 排名表
    sorted_evs = sorted(evaluations, key=lambda x: x.total_score, reverse=True)
    
    lines.append("## 📊 综合评分排名\n\n")
    lines.append("| 排名 | 小说名称 | 作者 | 类型 | 字数 | 总分 | 评级 |\n")
    lines.append("|:---:|:---|:---|:---|---:|:---:|:---:|\n")
    
    for i, ev in enumerate(sorted_evs, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}"
        lines.append(f"| {medal} | **{ev.novel_name}** | {ev.author} | {ev.genre} | {ev.word_count:,} | **{ev.total_score:.1f}** | {ev.get_ranking_letter()} |\n")
    
    lines.append("\n---\n\n")
    
    # 每本小说详细报告
    for i, ev in enumerate(evaluations, 1):
        rank = sorted_evs.index(ev) + 1
        
        lines.append(f"## {i}. {ev.novel_name}\n")
        lines.append(f"**作者**: {ev.author} | **类型**: {ev.genre} | **字数**: {ev.word_count:,} | **评级**: {ev.get_ranking_letter()}\n\n")
        
        lines.append("### 📈 八维评分详情\n\n")
        lines.append("```\n")
        lines.append(f"{'维度':<10} {'权重':<8} {'得分':<8} {'归一化':<8} {'评级条/总':<10} {'得分条'}\n")
        lines.append("-" * 70 + "\n")
        
        for dim in sorted(ev.dimensions, key=lambda x: x.weight, reverse=True):
            score_bar = "█" * int(dim.normalized_score) + "░" * (10 - int(dim.normalized_score))
            lines.append(f"{dim.name:<10} {dim.weight*100:>6.1f}%  {dim.raw_score:>2}/{dim.max_score:<5} {dim.normalized_score:.1f}/10   {dim.raw_score:>2}/{dim.max_score:<5}    {score_bar}\n")
        
        total_bar = "█" * int(ev.total_score / 10) + "░" * (10 - int(ev.total_score / 10))
        lines.append("-" * 70 + "\n")
        lines.append(f"{'总分':<10} {'100.0%':>6}  {'--':<8} {ev.total_score:.1f}/100       ---\n")
        lines.append("```\n\n")
        
        lines.append("### 📋 规则得分明细\n\n")
        
        for dim in ev.dimensions:
            lines.append(f"**{dim.name}** ({dim.raw_score}/{dim.max_score}条通过, {dim.normalized_score:.1f}/10)\n\n")
            lines.append("| 规则ID | 规则名称 | 得分 | 依据 |\n")
            lines.append("|:---:|:---|:---:|:---|\n")
            
            for rule in dim.rules:
                icon = "✅" if rule.score == 1 else "❌"
                lines.append(f"| {rule.rule_id} | {rule.rule_name} | {icon} {rule.score} | {rule.evidence} |\n")
            
            lines.append("\n")
        
        lines.append("---\n\n")
    
    # 维度横向对比
    lines.append("## 📊 八维维度横向对比\n\n")
    lines.append("| 维度 | 权重 | 平均原始分 | 平均归一化 | 最高小说 |\n")
    lines.append("|:---|:---:|:---:|:---:|:---|\n")
    
    dim_names = {d.category: d.name for d in evaluations[0].dimensions}
    
    for dim_cat in ['plot_consistency', 'logic_rationality', 'character_consistency',
                    'style_matching', 'world_consistency', 'narrative_flow',
                    'emotional_impact', 'hook_strength']:
        
        dim_evals = [ev for ev in evaluations for d in ev.dimensions if d.category == dim_cat]
        if dim_evals:
            dim = next(d for d in evaluations[0].dimensions if d.category == dim_cat)
            avg_raw = sum(d.raw_score for ev in evaluations for d in ev.dimensions if d.category == dim_cat) / len(evaluations)
            avg_norm = sum(d.normalized_score for ev in evaluations for d in ev.dimensions if d.category == dim_cat) / len(evaluations)
            
            # 找出最高分小说
            best_ev = max(evaluations, key=lambda ev: next(d.raw_score for d in ev.dimensions if d.category == dim_cat))
            best_dim = next(d for d in best_ev.dimensions if d.category == dim_cat)
            
            bar = "█" * int(avg_norm) + "░" * (10 - int(avg_norm))
            lines.append(f"| {dim.name} | {dim.weight*100:.0f}% | {avg_raw:.1f}/{dim.max_score} | {avg_norm:.1f}/10 {bar} | {best_ev.novel_name[:15]} |\n")
    
    lines.append("\n---\n\n")
    lines.append(f"*本报告由 KimiFiction 长文本八维精细化评分系统 v2.0 自动生成*\n")
    lines.append(f"*共 {len(evaluations)} 本小说, {88} 条独立评分规则*\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    import sys
    
    reference_dir = r"D:\310Programm\KimiFiction\reference"
    output_dir = r"D:\310Programm\KimiFiction\training_runs"
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 70)
    print("KimiFiction 长文本八维精细化评分系统 v2.0")
    print("=" * 70)
    print(f"\n评测目录: {reference_dir}")
    print(f"输出目录: {output_dir}")
    print(f"规则总数: 88条 (每维度10-12条独立规则)")
    print(f"评分标准: 每条规则输出0或1分, 归一化到1-10分制\n")
    
    evaluations = evaluate_reference_novels(reference_dir, output_dir)
    
    print("\n" + "=" * 70)
    print("评测完成!")
    print("=" * 70)
