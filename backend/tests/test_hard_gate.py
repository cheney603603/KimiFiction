"""章节硬门禁与文风解析单元测试（P0-9 / P0-10）"""
import pytest

from app.services.hard_gate import ChapterHardGate, count_words
from app.services.style_profile import resolve_writing_style


class TestHardGateWordCount:
    """规则1：字数达成率"""

    def test_short_draft_fails(self):
        g = ChapterHardGate(target_words=3000)
        r = g.check("这是很短的一段话。")
        assert r.passed is False
        assert any(c.rule == "字数达成率" and not c.passed for c in r.checks)

    def test_adequate_draft_passes(self):
        g = ChapterHardGate(target_words=3000)
        good = "他推开门，寒风灌了进来。" + "他看了一眼窗外，随即低头继续赶路。" * 250
        r = g.check(good)
        assert r.passed is True

    def test_count_words(self):
        assert count_words("中文abc英文") == 5  # 4 汉字 + 1 单词
        assert count_words("") == 0


class TestHardGateEnding:
    """规则2：结尾句已终止"""

    def test_comma_ending_fails(self):
        g = ChapterHardGate(target_words=3000)
        r = g.check("他推开门，寒风灌了进来。" * 300 + "未完，")
        assert not r.passed
        assert any(c.rule == "结尾句终止" and not c.passed for c in r.checks)

    def test_ellipsis_ending_fails(self):
        g = ChapterHardGate(target_words=3000)
        r = g.check("他推开门，寒风灌了进来。" * 300 + "……")
        assert not r.passed

    def test_proper_ending_passes(self):
        g = ChapterHardGate(target_words=3000)
        r = g.check("他推开门，寒风灌了进来。" * 300 + "他笑了。")
        assert any(c.rule == "结尾句终止" and c.passed for c in r.checks)

    def test_unclosed_quote_fails(self):
        g = ChapterHardGate(target_words=3000)
        r = g.check("他推开门，寒风灌了进来。" * 300 + "他问：“你还好吗")
        assert not r.passed


class TestHardGateNames:
    """规则4：出场角色名命中角色卡（宽松）"""

    def test_no_suspects_passes(self):
        g = ChapterHardGate(target_words=3000)
        good = "他推开门，寒风灌了进来。" + "他看了一眼窗外，随即低头继续赶路。" * 250
        r = g.check(good, character_names=["李云", "老管家"])
        assert r.passed is True

    def test_many_suspects_fails(self):
        g = ChapterHardGate(target_words=3000)
        good = "他推开门，寒风灌了进来。" * 250
        names = ["赵日天", "王五", "李四", "孙七", "周八", "吴九", "郑十", "钱二", "朱三"]
        fabricated = "".join(f"{n}冷笑一声。{n}站起身来。{n}别过脸去。" for n in names)
        r = g.check(good + fabricated, character_names=["李云", "老管家"])
        assert not r.passed
        assert any(c.rule == "角色名白名单" and not c.passed for c in r.checks)

    def test_common_words_not_suspects(self):
        g = ChapterHardGate(target_words=3000)
        text = "他推开门，寒风灌了进来。上面写着，元气凝成一线，愿力涌来。明白了吗？结果已经出来了。" * 120
        r = g.check(text, character_names=["李云"])
        # "上面""元气""愿力""明白""结果" 等常见词不应被误判
        assert r.passed is True

    def test_compound_surname_detected(self):
        g = ChapterHardGate(target_words=3000)
        good = "他推开门，寒风灌了进来。" * 250
        fabricated = "上官云冷笑一声。上官云站起身来。上官云别过脸去。上官云又笑了。"
        suspects = g._suspicious_names(good + fabricated, character_names=["李云"])
        assert "上官云" in suspects


class TestStyleProfile:
    """P0-10：文风解析"""

    def test_user_override_wins(self):
        assert resolve_writing_style({}, user_override="番茄大白话") == "番茄大白话"

    def test_style_prompt_priority(self):
        assert resolve_writing_style({"style_prompt": "古风典雅"}, novel_style_prompt="现代简洁") == "现代简洁"
        assert resolve_writing_style({"style_prompt": "古风典雅"}) == "古风典雅"

    def test_genre_keywords(self):
        state = {"demand_analysis": {"style_keywords": ["热血", "升级流"]}}
        assert resolve_writing_style(state) == "热血、升级流"

    def test_genre_fallback(self):
        state = {"demand_analysis": {"suggested_genre": "都市修真"}}
        assert resolve_writing_style(state) == "都市修真文风"

    def test_default(self):
        assert resolve_writing_style(None) == "叙事流畅，情节紧凑"
