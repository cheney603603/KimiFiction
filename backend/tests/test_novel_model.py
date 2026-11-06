"""小说级模型覆盖（三层回落：小说 > 用户BYOK > 全局）单元测试。"""
from types import SimpleNamespace

from app.core import user_context
from app.core.llm_config_manager import LLMConfigManager
from app.services.novel_model_service import build_novel_override


def test_build_novel_override_only_set_fields():
    row = SimpleNamespace(model_provider="deepseek", model_name="deepseek-chat", model_base_url=None)
    assert build_novel_override(row) == {"provider": "deepseek", "model": "deepseek-chat"}

    row2 = SimpleNamespace(model_provider=None, model_name=None, model_base_url=None)
    assert build_novel_override(row2) is None


def test_three_tier_novel_overrides_config():
    user_context.set_novel_config_snapshot(
        {"provider": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com"}
    )
    try:
        cfg = LLMConfigManager.get_config()
        assert cfg["provider"] == "deepseek"
        assert cfg["model"] == "deepseek-chat"
        assert cfg["base_url"] == "https://api.deepseek.com"
    finally:
        user_context.set_novel_config_snapshot(None)


def test_three_tier_no_override_falls_back():
    cfg = LLMConfigManager.get_config()
    # 无覆盖时回落全局/默认（provider 至少存在）
    assert cfg.get("provider")
