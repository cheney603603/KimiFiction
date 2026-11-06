"""
章节硬门禁（确定性规则，§5.2）
================================

不使用 LLM 分；任一规则不通过即触发定向重写（≤1 次）；仍不过则标记 flagged 待人工。

规则（按顺序判定）：
1. 字数达成率 ≥ 85%（相对目标字数）
2. 结尾句已终止（不以逗号/顿号/"……"截断，无未闭合引号）
3. 场景数 = 期望场景数，各场景字数偏差 ≤ 30%（仅提供 scene 边界时启用）
4. 出场角色名全部命中角色卡（防臆造人物，宽松阈值避免误杀）
5. 境界/力量等级引用与世界观设定表一致（宽松阈值）
6. 伏笔台账无超期未回收项（P2 上线后启用，台账为空时恒通过）
7. 番茄审核红线：无低俗/种马后宫类触发词（确定性高置信词表，命中即失败）

强制约束（§5.3 / R1）：本模块只做判定与告警，绝不参与 reward 加权。
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


def count_words(text: str) -> int:
    """中文字符数 + 英文单词数。"""
    if not text:
        return 0
    chinese = len(re.findall(r'[一-鿿]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english


@dataclass
class RuleCheck:
    rule: str
    passed: bool
    detail: str = ""


@dataclass
class GateResult:
    passed: bool
    failures: List[RuleCheck] = field(default_factory=list)
    checks: List[RuleCheck] = field(default_factory=list)
    word_count: int = 0
    target_words: int = 0

    def failure_summary(self) -> str:
        return "; ".join(f"{c.rule}: {c.detail}" for c in self.failures)


# 单字姓氏（用于臆造人名探测锚点；复合姓氏另行处理）
_SINGLE_SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜" \
                   "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐" \
                   "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄" \
                   "和林萧叶江吴秦楚"

# 复合姓氏（2 字，先匹配）
_COMPOUND_SURNAMES = [
    "司马", "欧阳", "上官", "诸葛", "司徒", "夏侯", "尉迟", "公孙", "独孤",
    "慕容", "南宫", "端木", "东方", "皇甫", "令狐", "呼延", "拓跋", "宇文",
    "百里", "第五", "完颜",
]

# 姓名锚点正则：复合姓氏优先（最长匹配），其次单字姓氏
_ANCHOR_RE = re.compile(
    r"(?:" + "|".join(sorted(_COMPOUND_SURNAMES, key=len, reverse=True)) + r"|[" + _SINGLE_SURNAMES + r"])"
)


# 番茄审核红线（deai-promax novel-rules：低俗/种马后宫/性暗示高置信词表，确定性判定）
_REDLINE_HARD = (
    "种马", "后宫", "三妻四妾", "脚踏三条船", "脚踏四条船", "床笫之欢",
    "上床", "翘臀", "胸脯", "玉体", "少儿不宜",
)


class ChapterHardGate:
    """章节确定性硬门禁。"""

    def __init__(
        self,
        target_words: int = 3000,
        word_ratio_threshold: float = 0.85,
        name_suspect_threshold: int = 8,
        name_min_freq: int = 3,
    ):
        self.target_words = target_words
        self.word_ratio_threshold = word_ratio_threshold
        self.name_suspect_threshold = name_suspect_threshold
        self.name_min_freq = name_min_freq

    def check(
        self,
        content: str,
        *,
        character_names: Optional[Sequence[str]] = None,
        power_levels: Optional[Sequence[str]] = None,
        expected_scenes: int = 0,
        scene_ends: Optional[Sequence[int]] = None,
        overdue_foreshadowing: Optional[Sequence[str]] = None,
    ) -> GateResult:
        """执行硬门禁判定。

        Args:
            content: 章节正文
            character_names: 角色卡姓名列表（规则4）
            power_levels: 世界观力量等级白名单（规则5）
            expected_scenes: 期望场景数，>0 且提供 scene_ends 时启用规则3
            scene_ends: 各场景结束位置（字符索引，升序）
            overdue_foreshadowing: 超期未回收伏笔（规则6，P2）
        """
        checks: List[RuleCheck] = []
        failures: List[RuleCheck] = []
        wc = count_words(content)

        def record(rule: str, passed: bool, detail: str = "") -> None:
            c = RuleCheck(rule=rule, passed=passed, detail=detail)
            checks.append(c)
            if not passed:
                failures.append(c)

        # 规则1：字数达成率
        need = int(self.target_words * self.word_ratio_threshold)
        record("字数达成率", wc >= need, f"{wc}/{need}")

        # 规则2：结尾句已终止
        record("结尾句终止", self._ending_terminated(content), self._ending_detail(content))

        # 规则3：场景数 + 各场景字数偏差
        if expected_scenes > 0 and scene_ends:
            scene_counts = self._scene_word_counts(content, scene_ends)
            record(
                "场景数",
                len(scene_counts) == expected_scenes,
                f"{len(scene_counts)}/{expected_scenes}",
            )
            if scene_counts:
                avg = sum(scene_counts) / len(scene_counts)
                worst = max((abs(c - avg) / avg) for c in scene_counts) if avg else 1.0
                record(
                    "场景字数均衡",
                    worst <= 0.30,
                    f"最大偏差 {worst:.0%}",
                )

        # 规则4：出场角色名命中角色卡（宽松）
        if character_names:
            suspects = self._suspicious_names(content, character_names)
            record(
                "角色名白名单",
                len(suspects) < self.name_suspect_threshold,
                f"疑似未登记人名 {len(suspects)} 个: {suspects[:5]}",
            )

        # 规则5：力量等级白名单（宽松）
        if power_levels:
            suspects = self._suspicious_levels(content, power_levels)
            record(
                "力量等级白名单",
                len(suspects) < 2,
                f"疑似越界等级 {len(suspects)} 个: {suspects[:5]}",
            )

        # 规则6：伏笔台账（P2）
        if overdue_foreshadowing:
            record(
                "伏笔超期",
                len(overdue_foreshadowing) == 0,
                f"{len(overdue_foreshadowing)} 项超期: {overdue_foreshadowing[:3]}",
            )

        # 规则7：番茄审核红线（低俗/种马后宫高置信词，命中即失败）
        redline = [w for w in _REDLINE_HARD if w in content]
        record(
            "番茄红线",
            len(redline) == 0,
            f"疑似低俗词 {len(redline)} 个: {redline[:5]}",
        )

        return GateResult(
            passed=not failures,
            failures=failures,
            checks=checks,
            word_count=wc,
            target_words=self.target_words,
        )

    # ── 规则实现 ─────────────────────────────

    def _ending_terminated(self, content: str) -> bool:
        text = content.rstrip()
        if not text:
            return False
        last = text[-1]
        # 不以逗号/顿号/分号/冒号/省略号结尾
        if last in "，、；：…":
            return False
        # 不以未闭合的引号结尾
        if last in "“„『「":
            return False
        # 未闭合引号检查：左引号多于右引号视为未闭合
        if text.count("“") > text.count("”"):
            return False
        return True

    def _ending_detail(self, content: str) -> str:
        text = content.rstrip()
        if not text:
            return "正文为空"
        last = text[-1]
        if last in "，、；：…":
            return f"以 '{last}' 截断"
        if last in "“„『「":
            return "结尾为未闭合引号"
        return "正常终止"

    def _scene_word_counts(self, content: str, scene_ends: Sequence[int]) -> List[int]:
        boundaries = [0] + [min(max(int(e), 0), len(content)) for e in scene_ends] + [len(content)]
        boundaries = sorted(set(boundaries))
        counts = []
        for i in range(len(boundaries) - 1):
            seg = content[boundaries[i]: boundaries[i + 1]]
            counts.append(count_words(seg))
        # 最后一个边界可能等于结尾，避免出现 0 字数场景
        return counts

    def _suspicious_names(self, content: str, character_names: Sequence[str]) -> List[str]:
        """探测疑似臆造人名（宽松启发式）。

        策略：以常见姓氏为锚点，取其后 1-2 字构成 2/3 字候选名；
        候选名重复出现（≥2 次）、不在角色卡、非常见词 → 记为可疑。
        放宽策略：仅当可疑名数量达阈值才判不通过，降低误杀。
        """
        names = {n for n in character_names if n}
        if not names:
            return []
        from collections import Counter

        freq: Counter = Counter()
        length = len(content)
        for m in _ANCHOR_RE.finditer(content):
            anchor = m.group()
            body_start = m.start() + len(anchor)
            # 姓名主体：单字姓 +1~2 字，复合姓 +1~2 字
            for extra in (1, 2):
                j = body_start + extra
                if j > length:
                    continue
                candidate = content[m.start():j]
                if not re.fullmatch(r'[一-鿿]+', candidate):
                    continue
                if candidate in names or candidate in _COMMON_WORDS:
                    continue
                if candidate[-1] in _FUNCTION_WORDS:
                    continue
                freq[candidate] += 1

        # 放宽：同一候选名须出现 ≥name_min_freq 次才计为可疑，降低世界设定术语误杀
        suspects = [n for n, f in freq.items() if f >= self.name_min_freq]
        return sorted(set(suspects))

    def _suspicious_levels(self, content: str, power_levels: Sequence[str]) -> List[str]:
        """探测疑似越界力量等级：以 境/期/阶/层/重天/段 结尾但不在白名单。"""
        levels = {lv for lv in power_levels if lv}
        if not levels:
            return []
        tokens = re.findall(r'[一-鿿]{1,4}(?:境|期|阶|层|重天|段|品)', content)
        from collections import Counter
        counter = Counter(tokens)
        suspects = []
        for token, freq in counter.items():
            if token in levels:
                continue
            if token in _COMMON_WORDS:
                continue
            if freq >= 2:
                suspects.append(token)
        return suspects


# 常见叙述词，避免被姓名/等级探测误伤
_COMMON_WORDS = frozenset({
    "境界", "阶段", "层次", "表示", "明白", "结果", "任何", "一定", "已经",
    "发现", "感觉", "知道", "时候", "地方", "事情", "东西", "现在", "然后",
    "所以", "但是", "而且", "于是", "如果", "可以", "可能", "这样", "这个",
    "那个", "什么", "怎么", "为什么", "自己", "我们", "你们", "他们", "大家",
    "许多", "如此", "一般", "十分", "突然", "终于", "接着", "立刻", "瞬间",
    "一时", "一直", "一直", "一瞬", "浑身", "心头", "脑中", "心底", "目光",
    # 常见修炼/世界观术语（避免被姓名启发式误判为臆造人名）
    "元气", "元力", "愿力", "灵力", "法力", "真气", "修为", "灵石", "灵识",
    "上品", "中品", "下品", "一品", "二品", "三品", "上面", "上写",
})

# 常见虚词结尾（作姓名尾字极罕见），用于姓名启发式过滤
_FUNCTION_WORDS = frozenset(
    "的了在着过把被就都还很能会想要让给对跟从到去来说得这那之与及了"
)
