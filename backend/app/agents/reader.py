"""
读者体验智能体
从读者视角评估章节可读性、情绪钩子和追读欲望

包含两层评估体系：
1. ReaderAgent     - 基于 LLM 的定性反馈（困惑点、修改建议等）
2. ProgrammaticRubricEvaluator - 程序化 8 维评分（更稳定、可计算）
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base import BaseAgent


class ReaderAgent(BaseAgent):
    """模拟目标读者反馈的Agent。"""

    SYSTEM_PROMPT = """你是一位真实且挑剔的网络小说读者。

你的职责是：
1. 从读者体验角度评价章节是否抓人
2. 指出让人困惑、出戏、节奏拖沓的地方
3. 评估情绪起伏、代入感、追读欲望
4. 给作者留下具体可执行的改进建议

输出必须是合法JSON。"""

    def __init__(self):
        super().__init__("Reader", self.SYSTEM_PROMPT)

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        chapter_number = context.get("chapter_number", 0)
        chapter_content = context.get("chapter_content", "")
        outline = context.get("outline", {})
        target_reader = context.get("target_reader", "大众网文读者")

        prompt = f"""请从"{target_reader}"的视角评价下面这一章。

章节号：第{chapter_number}章
章节细纲摘要：{outline.get("summary", "")}

章节正文：
{chapter_content[:6000]}

请输出JSON：
{{
  "reader_score": 0.0,
  "immersion_score": 0.0,
  "hook_score": 0.0,
  "confusing_points": ["困惑点1"],
  "boring_points": ["节奏问题1"],
  "most_engaging_moments": ["高光点1"],
  "reader_expectations": ["读者接下来想看什么"],
  "revision_suggestions": ["建议1"],
  "would_continue_reading": true
}}"""

        react_result = await self.run_react_loop(
            prompt,
            context=context,
            temperature=0.5,
            output_format="json",
        )
        response = react_result["final_text"] or react_result["raw_response"]
        result, parse_message = self._extract_json_with_message(response)
        if result is None:
            return {
                "success": False,
                "error": f"JSON解析失败: {parse_message}",
                "raw_response": response[:1000],
            }

        return {
            "success": True,
            "chapter_number": chapter_number,
            "reader_feedback": result,
            "_react_trace": react_result["trace"],
        }

    def _extract_json_with_message(self, response: str):
        from app.core.json_utils import extract_json_from_response
        return extract_json_from_response(response)


# =============================================================================
# 程序化 8 维 Rubric 评分器（改进：逐维打分，比一次性输出更稳定）
# =============================================================================

# 8 维定义（与 rubric.py 中的 DimensionCategory 一致）
RUBRIC_DIMENSIONS = [
    "plot_consistency",       # 情节一致性：伏笔是否回收、逻辑是否自洽
    "style_matching",         # 风格匹配度：与前文风格是否一致
    "logic_rationality",      # 逻辑合理性：事件因果是否成立
    "character_consistency",   # 角色一致性：性格、说话方式是否前后一致
    "world_consistency",      # 世界观一致性：设定是否被违反
    "narrative_flow",         # 叙事流畅度：段落衔接、节奏把控
    "emotional_impact",       # 情感冲击力：读者能否共鸣、高潮是否有力
    "hook_strength",          # 钩子强度：开头结尾是否有吸引力
]

# 各维度权重（与 RewardFunction 保持一致）
DIMENSION_WEIGHTS = {
    "plot_consistency":      0.18,
    "style_matching":       0.10,
    "logic_rationality":    0.15,
    "character_consistency": 0.12,
    "world_consistency":    0.10,
    "narrative_flow":       0.12,
    "emotional_impact":     0.13,
    "hook_strength":        0.10,
}


class ProgrammaticRubricEvaluator:
    """
    程序化 8 维 Rubric 评分器

    核心改进：
    - 逐维打分（每维独立 prompt + few-shot 示例），比一次性输出更稳定
    - 引入可计算指标（无需 LLM），降低延迟和方差
    - 最终分数 = LLM打分(60%) + 可计算指标(40%)

    使用方式：
        evaluator = ProgrammaticRubricEvaluator(reader_agent)
        scores = await evaluator.evaluate(content, outline, characters)
        total = evaluator.compute_weighted_score(scores)
    """

    # 逐维打分的 few-shot 示例（每维 2 个正例 + 1 个负例）
    DIMENSION_PROMPTS: Dict[str, str] = {
        "plot_consistency": """你是一位网络小说编辑，专门评估情节一致性。

评估标准（1-10分）：
- 9-10：所有伏笔均回收，逻辑链条完整，无前后矛盾
- 7-8：伏笔大部分回收，偶有小漏洞但不影响阅读
- 5-6：明显漏洞或矛盾1-2处，读者会感到困惑
- 3-4：多处情节矛盾，因果关系混乱
- 1-2：情节完全无法自洽，逻辑崩塌

示例：
章节片段："主角前世是剑修，三十岁突破化神失败陨落，转世后记忆模糊，但剑意犹存。"
评估：这一段情节一致，主角的过去→陨落→转世→残留记忆，逻辑链条清晰。（评分：9/10）

章节片段："主角擅长用刀，但后文提到'剑意凛然'，再后文又说'刀光一闪'杀敌。"
评估：武器设定前后矛盾，读者会困惑主角到底用什么武器。（评分：4/10）

现在评估以下章节的情节一致性：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "style_matching": """你是一位网络小说编辑，专门评估风格一致性。

评估标准（1-10分）：
- 9-10：语言风格、句式长短、用词习惯完全一致
- 7-8：整体一致，个别段落略有差异
- 5-6：风格跳跃明显，如前半文言后半口语
- 3-4：多次风格突变，阅读割裂感强
- 1-2：全篇风格混乱，无法形成阅读惯性

示例：
章节片段（轻松幽默风格）："主角挠了挠头，心想这系统怕不是个傻子。"
评估：风格一致，对话口语化，轻松幽默基调保持。（评分：9/10）

章节片段："他深吸一口气，眸中精光一闪。与此同时，系统提示音响起：'叮~恭喜宿主获得……'"
评估：前半古典叙事，后半突然冒出"叮~"，风格突变。（评分：4/10）

现在评估以下章节的风格一致性：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "logic_rationality": """你是一位网络小说编辑，专门评估逻辑合理性。

评估标准（1-10分）：
- 9-10：所有行为有合理动机，能力使用符合设定，无"机械降神"
- 7-8：基本合理，个别细节模糊但可接受
- 5-6：明显动机不足或能力越级使用，读者会质疑
- 3-4：主角行为无逻辑，如突然无敌或突然失忆
- 1-2：完全违背基本常理，如"被封印却能用全力"

示例：
章节片段："敌人是元婴期修士，主角金丹期，功法被压制。两人激战三百回合，主角最终以伤换伤，一剑刺穿敌人丹田。"
评估：金丹对元婴越级挑战，虽然胜利但代价惨重，以伤换伤符合逻辑。（评分：8/10）

章节片段："主角被封印了全身修为，只能等死。但下一秒，他突然爆发全部实力，一招秒杀了所有敌人。"
评估："被封印"和"爆发全部实力"直接矛盾，完全不合逻辑。（评分：2/10）

现在评估以下章节的逻辑合理性：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "character_consistency": """你是一位网络小说编辑，专门评估角色一致性。

评估标准（1-10分）：
- 9-10：人物性格、语言风格、行为逻辑完全一致
- 7-8：整体一致，个别细节有小偏差
- 5-6：人物性格飘移，如冷酷角色突然话多
- 3-4：人物设定前后矛盾，如前后性格完全相反
- 1-2：人物行为完全随机，不可预测

示例：
章节片段（高冷性格）："他没有说话，只是淡淡看了对方一眼。'你确定？'声音平静如水。"
评估：高冷性格保持一致，言简意赅，没有突然变话痨。（评分：9/10）

章节片段（高冷性格）："他挠了挠头，'嘿嘿，这次运气不错嘛！下次再来啊！'一边说一边跳了起来。"
评估：高冷角色突然变得极其热情活泼，与设定完全不符。（评分：3/10）

现在评估以下章节的角色一致性（重点关注：{character_names}）：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "world_consistency": """你是一位网络小说编辑，专门评估世界观一致性。

评估标准（1-10分）：
- 9-10：力量体系、社会规则、地理设定完全遵守
- 7-8：基本遵守，个别细节模糊
- 5-6：明显违反设定1-2处，如越级使用禁术
- 3-4：多处违反设定，如突然出现不符合世界的新元素
- 1-2：设定完全崩塌

示例：
章节片段（玄幻世界，设定元婴期才能御剑飞行）："主角踏剑而起，飞行百里，终于在一处山谷降落。"
评估：前提是主角已突破元婴，符合设定。（评分：9/10）

章节片段（设定凡人无法感知灵气）："一个凡人老农看到天上的灵气波动，心中大惊。"
评估：凡人不应能感知灵气，违反设定。（评分：4/10）

现在评估以下章节的世界观一致性（设定：{world_setting_summary}）：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "narrative_flow": """你是一位网络小说编辑，专门评估叙事流畅度。

评估标准（1-10分）：
- 9-10：场景转换自然，节奏张弛有度，无断层感
- 7-8：整体流畅，偶有节奏拖沓或转换生硬
- 5-6：节奏忽快忽慢，如高潮后突然进入大段说明
- 3-4：叙事跳跃，读者需要反复回读
- 1-2：段落零散，章节完全无法连贯阅读

示例：
章节片段："大战之后，众人返回营地。篝火旁，伤兵们沉默不语。（节奏放缓）'明天继续。'主角说罢，独自走向山顶，望着远方出神。（情绪铺垫）忽然，天边传来一声尖锐的啸叫。（节奏突然拉起）"
评估：节奏控制良好，张弛有度，从战斗→休整→情绪→新悬念，过渡自然。（评分：9/10）

章节片段："战斗结束。A打败了B。（突然跳到）三个月后，C来到了D城。（又跳到）E是D城的城主。"
评估：时间跳跃过于频繁，缺乏过渡，节奏完全失控。（评分：3/10）

现在评估以下章节的叙事流畅度：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "emotional_impact": """你是一位网络小说编辑，专门评估情感冲击力。

评估标准（1-10分）：
- 9-10：读者能够强烈共情，高潮段落令人热血沸腾或潸然泪下
- 7-8：能引起一定情感波动，高潮段落有一定感染力
- 5-6：情感表达平淡，读者反应冷淡
- 3-4：完全无法引起情感共鸣，文字缺乏感染力
- 1-2：情感表达失败，甚至令人尴尬

示例：
章节片段："他跪在母亲的坟前，肩膀微微颤抖。风卷起枯叶，从他苍老的手中滑落。"吾欲归来，母已不在。"一滴泪落在墓碑上。"
评估：细节描写（枯叶、苍老的手）与情感（悲伤、思乡）完美融合，感染力强。（评分：9/10）

章节片段："他很难过。母亲死了。他哭了一场。然后他决定继续努力修炼。"
评估：情感表达过于直白平淡，没有通过细节和氛围营造感染力。（评分：4/10）

现在评估以下章节的情感冲击力：
{chapter_content[:2000]}

只输出一个1-10的数字分数：""",

        "hook_strength": """你是一位网络小说编辑，专门评估开头结尾钩子强度。

评估标准（1-10分）：
- 9-10：开头立刻抓住注意力，结尾留下强悬念，读者非追不可
- 7-8：开头有吸引力，结尾悬念足够
- 5-6：开头平淡或结尾悬念不足
- 3-4：开头冗长无趣，结尾无悬念或悬念被剧透
- 1-2：完全无法吸引读者继续阅读

示例：
章节片段（结尾）：
"就在他即将触碰到那枚玉简的瞬间——身后，一道冰冷的声音响起：'你真的以为，我会让你带走它吗？'他猛然回头，看到了一张熟悉到让他窒息的脸。"
评估：结尾有强悬念，"熟悉的脸"制造紧张感，读者必须追下一章。（评分：9/10）

章节片段（结尾）：
"战斗结束了，主角取得了胜利，大家都非常高兴。"
评估：结尾直接给出完整结果，毫无悬念，读者没有继续阅读的动力。（评分：3/10）

现在评估以下章节的钩子强度（只看开头和结尾各300字）：
开头：
{chapter_content[:300]}
结尾：
{chapter_content[-300:]}

只输出一个1-10的数字分数：""",
    }

    def __init__(self, reader_agent: Optional[ReaderAgent] = None, llm_weight: float = 0.6):
        """
        Args:
            reader_agent: 用于 LLM 打分的 ReaderAgent（可选）
            llm_weight: LLM 评分在最终分数中的权重（默认 60%）
        """
        self.reader_agent = reader_agent
        self.llm_weight = llm_weight
        self.auto_weight = 1.0 - llm_weight

    async def evaluate(
        self,
        content: str,
        outline: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        world_setting: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行 8 维程序化评分

        流程：
        1. 并行计算可自动指标（hook_detection, coherence_proxy, pacing）
        2. 并行逐维 LLM 评分（每维独立 prompt + few-shot）
        3. 混合加权得到最终分数
        """
        import asyncio

        # ── Step 1: 可计算指标（无需 LLM，毫秒级）──────────────────────
        auto_metrics = self._compute_auto_metrics(content)

        # ── Step 2: 8 维逐维 LLM 评分 ────────────────────────────────
        llm_scores = await self._score_dimensions_with_llm(
            content, outline, characters, world_setting
        )

        # ── Step 3: 混合加权 ─────────────────────────────────────────
        final_scores = {}
        for dim in RUBRIC_DIMENSIONS:
            llm_val = llm_scores.get(dim, 5.0)    # 默认 5/10
            auto_val = self._map_auto_to_dim(auto_metrics, dim)
            # 混合：LLM(60%) + 可计算(40%)
            final_scores[dim] = self.llm_weight * llm_val + self.auto_weight * auto_val

        # ── Step 4: 计算汇总分数 ─────────────────────────────────────
        total_score = self.compute_weighted_score(final_scores)
        reader_proxy = self._compute_reader_proxy(content)

        return {
            # 8 维分数（归一化到 0-1）
            "dimension_scores": {k: round(v / 10.0, 3) for k, v in final_scores.items()},
            # 各维度原始 LLM 分数
            "llm_scores": {k: round(v, 1) for k, v in llm_scores.items()},
            # 可计算指标
            "auto_metrics": auto_metrics,
            # 综合分（0-1）
            "total_score": round(total_score / 10.0, 3),
            # 读者代理分（可计算，无 LLM）
            "reader_proxy": reader_proxy,
            # 通过阈值判断
            "passed": total_score >= 7.8 and final_scores.get("hook_strength", 0) >= 7.0,
        }

    def _compute_auto_metrics(self, content: str) -> Dict[str, float]:
        """
        计算可自动获得的指标（无需 LLM，毫秒级）
        所有值归一化到 0-10 范围
        """
        if not content:
            return self._default_auto_metrics()

        chinese_chars = re.findall(r'[\u4e00-\u9fff]', content)
        total_chars = len(content)
        chinese_len = len(chinese_chars)

        metrics = {}

        # 1. 钩子检测（结尾悬念句数量）
        hook_patterns = [
            r'突然', r'就在.+时', r'就在这时', r'然而', r'可是',
            r'却不知道', r'他不知道', r'就在这时', r'下一刻',
            r'话音未落', r'说时迟', r'谁知', r'岂料', r'但见',
        ]
        hook_count = sum(
            len(re.findall(p, content)) for p in hook_patterns
        )
        metrics["hook_count"] = min(hook_count / 3.0, 10.0)  # 3个悬念句=10分

        # 2. 段落连贯性代理（句子长度变化度）
        sentences = re.split(r'[。！？；\n]', content)
        non_empty = [s.strip() for s in sentences if len(s.strip()) > 5]
        if len(non_empty) >= 3:
            lengths = [len(s) for s in non_empty]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            # 方差适中（约50-200）得分最高，过高过低都扣分
            ideal_variance = 100
            variance_score = 10.0 - abs(variance - ideal_variance) / 50.0
            metrics["coherence_proxy"] = max(1.0, min(10.0, variance_score))
        else:
            metrics["coherence_proxy"] = 5.0

        # 3. 对话比例
        dialogue_pattern = r'[""\'""].{5,200}?[""\'""]'
        dialogues = re.findall(dialogue_pattern, content)
        dialogue_chars = sum(len(d) for d in dialogues)
        if chinese_len > 0:
            dialogue_ratio = dialogue_chars / chinese_len
            # 理想比例 0.2-0.5
            if 0.2 <= dialogue_ratio <= 0.5:
                metrics["dialogue_ratio"] = 10.0
            elif dialogue_ratio < 0.1:
                metrics["dialogue_ratio"] = dialogue_ratio / 0.1 * 5.0
            elif dialogue_ratio > 0.6:
                metrics["dialogue_ratio"] = max(1.0, 10.0 - (dialogue_ratio - 0.6) / 0.4 * 9.0)
            else:
                metrics["dialogue_ratio"] = 7.0
        else:
            metrics["dialogue_ratio"] = 5.0

        # 4. 字数合理性（目标 3000±600）
        word_count = chinese_len
        if 2400 <= word_count <= 3600:
            metrics["word_count_reasonableness"] = 10.0
        elif word_count < 2400:
            metrics["word_count_reasonableness"] = max(1.0, word_count / 2400 * 8.0)
        else:
            metrics["word_count_reasonableness"] = max(1.0, 10.0 - (word_count - 3600) / 2000 * 8.0)

        # 5. 结尾悬念指数（结尾100字中的疑问句/感叹句/省略号）
        ending = content[-200:] if len(content) > 200 else content
        suspense_markers = (
            ending.count("？") + ending.count("!") + ending.count("…") +
            ending.count("......") + len(re.findall(r'却不知道|却见|却听', ending))
        )
        metrics["ending_suspense"] = min(suspense_markers / 2.0, 10.0)

        return metrics

    def _map_auto_to_dim(self, auto_metrics: Dict[str, float], dim: str) -> float:
        """将可计算指标映射到对应维度"""
        mapping = {
            "hook_strength":     auto_metrics.get("hook_count", 5.0) * 0.5
                                + auto_metrics.get("ending_suspense", 5.0) * 0.5,
            "narrative_flow":    auto_metrics.get("coherence_proxy", 5.0),
            "style_matching":    auto_metrics.get("coherence_proxy", 5.0),
            "logic_rationality": auto_metrics.get("coherence_proxy", 5.0),
            "plot_consistency":  auto_metrics.get("coherence_proxy", 5.0),
            "character_consistency": 7.0,    # 程序无法判断，保持中性
            "world_consistency": auto_metrics.get("coherence_proxy", 5.0),
            "emotional_impact": auto_metrics.get("coherence_proxy", 5.0),
        }
        return mapping.get(dim, 7.0)

    async def _score_dimensions_with_llm(
        self,
        content: str,
        outline: Optional[Dict[str, Any]],
        characters: Optional[List[Dict[str, Any]]],
        world_setting: Optional[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        并行对 8 维逐维打分
        每维使用独立的 few-shot prompt，只输出一个数字
        """
        if self.reader_agent is None:
            # 无 LLM，全部返回中性分数
            return {dim: 7.0 for dim in RUBRIC_DIMENSIONS}

        import asyncio

        tasks = []
        for dim in RUBRIC_DIMENSIONS:
            task = self._score_single_dimension(
                dim, content, outline, characters, world_setting
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = {}
        for dim, result in zip(RUBRIC_DIMENSIONS, results):
            if isinstance(result, Exception):
                scores[dim] = 7.0  # 降级
            else:
                scores[dim] = result

        return scores

    async def _score_single_dimension(
        self,
        dim: str,
        content: str,
        outline: Optional[Dict[str, Any]],
        characters: Optional[List[Dict[str, Any]]],
        world_setting: Optional[Dict[str, Any]],
    ) -> float:
        """对单一维度打分"""
        prompt_template = self.DIMENSION_PROMPTS.get(dim, "")
        if not prompt_template:
            return 7.0

        # 填充上下文变量
        character_names = (
            ", ".join(c.get("name", "?") for c in characters[:3])
            if characters else "无特定角色"
        )
        world_summary = (
            world_setting.get("overview", "无世界观设定")[:200]
            if world_setting else "无世界观设定"
        )

        prompt = prompt_template.format(
            chapter_content=content,
            character_names=character_names,
            world_setting_summary=world_summary,
        )

        try:
            react_result = await self.reader_agent.run_react_loop(
                prompt,
                context={},
                temperature=0.1,    # 低温度保证稳定性
                output_format="text",
            )
            response = react_result["final_text"] or react_result["raw_response"]

            # 提取数字分数
            score = self._extract_score(response)
            return max(1.0, min(10.0, score))

        except Exception:
            return 7.0

    @staticmethod
    def _extract_score(response: str) -> float:
        """从 LLM 输出中提取数字分数"""
        # 尝试提取第一个数字
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', response.strip())
        for num_str in numbers:
            val = float(num_str)
            if 1.0 <= val <= 10.0:
                return val
        return 7.0  # 降级

    def compute_weighted_score(self, dimension_scores: Dict[str, float]) -> float:
        """计算 8 维加权总分（满分 10）"""
        total = 0.0
        for dim, score in dimension_scores.items():
            weight = DIMENSION_WEIGHTS.get(dim, 0.0)
            total += score * weight
        return total

    def _compute_reader_proxy(self, content: str) -> float:
        """
        计算读者代理分数（完全可计算，不依赖 LLM）
        用于快速筛选，无需调用 LLM 的场景
        """
        auto = self._compute_auto_metrics(content)
        # 综合：钩子(40%) + 连贯性(30%) + 字数合理(30%)
        return (
            auto.get("hook_count", 0) / 10.0 * 0.4
            + auto.get("coherence_proxy", 5) / 10.0 * 0.3
            + auto.get("word_count_reasonableness", 5) / 10.0 * 0.3
        )

    @staticmethod
    def _default_auto_metrics() -> Dict[str, float]:
        return {
            "hook_count": 5.0,
            "coherence_proxy": 7.0,
            "dialogue_ratio": 7.0,
            "word_count_reasonableness": 7.0,
            "ending_suspense": 5.0,
        }
