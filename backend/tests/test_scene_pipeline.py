"""写作管线 V2 组件测试（P1：分场景 / 反模板化 / 诊断指标）"""
import pytest

from app.services.scene_pipeline import ChapterTypePool, ScenePipeline
from app.services.writing_diagnostics import compute_diagnostics


class TestChapterTypePool:
    """反模板化：章节类型池"""

    def test_avoids_three_in_a_row(self):
        assert ChapterTypePool.pick(["conflict", "conflict"]) == "transition"
        assert ChapterTypePool.pick(["emotion", "emotion"]) == "conflict"

    def test_empty_recent(self):
        t = ChapterTypePool.pick([])
        assert t in ChapterTypePool.TYPES

    def test_all_types_valid(self):
        assert set(ChapterTypePool.TYPES) == {"conflict", "transition", "emotion", "information", "ensemble"}
        assert "conflict" in ChapterTypePool.LABELS


class TestSceneStitch:
    """规则化场景缝合"""

    @pytest.fixture
    def pipe(self):
        return ScenePipeline(novel_id=1, chapter_number=1)

    def test_join_scenes(self, pipe):
        text = pipe._stitch(["第一场景内容。", "第二场景内容。"])
        assert "第一场景内容。" in text
        assert "第二场景内容。" in text
        assert "\n\n" in text

    def test_trim_parenthetical_notes(self, pipe):
        text = pipe._stitch(["（切换视角）第一场景内容。", "（切回主角）第二场景内容。"])
        assert "（切换视角）" not in text
        assert "（切回主角）" not in text

    def test_empty(self, pipe):
        assert pipe._stitch([]) == ""
        assert pipe._stitch(["", "  "]) == ""


class TestWritingDiagnostics:
    """三尺度诊断指标（仅诊断，不入 reward）"""

    def test_burstiness_low_flags_machine_rhythm(self):
        text = "他笑了。她笑了。大家笑了。他走了。她走了。大家都走了。"
        diag = compute_diagnostics(text)
        assert "burstiness" in diag
        assert diag["burstiness"] < 0.45
        assert diag["burstiness_flag"] is True

    def test_ai_phrases_detected(self):
        text = "他微微点头，若有所思。仿佛空气凝固，气氛变得紧张。他淡淡说了一句。"
        diag = compute_diagnostics(text)
        assert diag["ai_phrase_hits_per_1000"] > 0
        assert diag["ai_phrase_flag"] is True
        assert len(diag["ai_phrases"]) > 0

    def test_opening_similarity(self):
        opening_a = "他推开门，寒风灌了进来。他看了一眼窗外，随即低头继续赶路。" * 10
        opening_b = "他推开门，寒风灌了进来。他看了一眼窗外，随即低头继续赶路。" * 10
        opening_c = "天边泛起鱼肚白。鸟鸣声里，少年翻了个身。" * 10
        diag = compute_diagnostics(opening_a, prev_openings=[opening_b, opening_c])
        assert diag["opening_similarity"] > 0.3
        assert diag["opening_similarity_flag"] is True

    def test_no_prev_openings(self):
        diag = compute_diagnostics("他推开门，寒风灌了进来。" * 50)
        assert diag["opening_similarity"] is None
        assert diag["emotion_curve_corr"] is None

    def test_diagnostics_are_not_scores(self):
        """强制约束：诊断指标不应出现在任何评分字段中（R1）。"""
        diag = compute_diagnostics("他推开门，寒风灌了进来。" * 50)
        assert "score" not in diag
        assert "reward" not in diag
