"""语言质检门禁 + 番茄红线确定性规则的单元测试。"""
from app.services.hard_gate import ChapterHardGate
from app.services.language_quality_gate import scan_language


def test_language_gate_detects_ai_cliches():
    text = (
        "他不由得愣住了。霎时间，整个房间的气氛瞬间凝滞。\n"
        "看到他眼底闪过一丝波澜，她心中五味杂陈。良久，他才缓缓开口。\n"
        "值得注意的是，这不仅仅是一个选择，更是命运的转折点。"
    )
    res = scan_language(text)
    assert res.passed is False
    rules = {f.rule for f in res.failures}
    assert "不由得" in rules
    assert "霎时间" in rules
    assert "良久" in rules
    assert "眼底闪过一丝波澜" in rules
    assert "心中五味杂陈" in rules
    assert any(r.startswith("模型路标") for r in rules)
    assert res.ai_score > 0


def test_language_gate_detects_pivot_and_dash():
    text = "他看重的不是结果，而是过程。她静静地站着——什么也没说。"
    res = scan_language(text)
    assert res.passed is False
    rules = {f.rule for f in res.failures}
    assert "翻案句" in rules
    assert "破折号滥用" in rules


def test_language_gate_clean_text_passes():
    text = (
        "他站在门口，看见桌上那张借条。老板说是他的，他没否认。\n"
        "他把借条折了两次，塞回口袋，转身出了门。"
    )
    res = scan_language(text)
    assert res.failures == []


def test_hard_gate_redline_detects_lowbrow():
    g = ChapterHardGate(target_words=50).check(
        "他坐拥后宫三千，夜夜三妻四妾。", character_names=[]
    )
    redline_failures = [c for c in g.failures if c.rule == "番茄红线"]
    assert redline_failures
    assert "后宫" in redline_failures[0].detail


def test_hard_gate_redline_clean_text():
    g = ChapterHardGate(target_words=30).check(
        "他站在门口，看着桌上那张借条。", character_names=[]
    )
    redline_failures = [c for c in g.failures if c.rule == "番茄红线"]
    assert redline_failures == []
