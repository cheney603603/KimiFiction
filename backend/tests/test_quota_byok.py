"""BYOK 配置解析 / Key 加密 / 额度墙 单元测试（M1）。"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.user_context import UserContext, capture, restore, apply
from app.core.llm_config_manager import LLMConfigManager
from app.services.quota_service import (
    QuotaService, QuotaExceeded, _month_str,
)


# ─────────────────────────────────────────────
# 1. Key 加密（secret_box）
# ─────────────────────────────────────────────
class TestSecretBox:
    def test_roundtrip(self, monkeypatch):
        monkeypatch.setenv("APP_KEY_ENCRYPT_SECRET", "test-secret")
        from app.core.secret_box import encrypt_secret, decrypt_secret
        enc = encrypt_secret("sk-abc123")
        assert enc != "sk-abc123"
        assert decrypt_secret(enc) == "sk-abc123"

    def test_refuses_without_env(self, monkeypatch):
        monkeypatch.delenv("APP_KEY_ENCRYPT_SECRET", raising=False)
        from app.core.secret_box import encrypt_secret
        with pytest.raises(RuntimeError):
            encrypt_secret("sk-abc")

    def test_decrypt_fails_when_env_changed(self, monkeypatch):
        monkeypatch.setenv("APP_KEY_ENCRYPT_SECRET", "key-A")
        from app.core.secret_box import encrypt_secret
        enc = encrypt_secret("sk-abc")
        monkeypatch.setenv("APP_KEY_ENCRYPT_SECRET", "key-B")
        from app.core.secret_box import decrypt_secret
        with pytest.raises(Exception):
            decrypt_secret(enc)


# ─────────────────────────────────────────────
# 2. 用户上下文 + LLM 配置解析优先级
# ─────────────────────────────────────────────
class TestUserConfigResolution:
    def test_user_snapshot_overrides_env(self, monkeypatch):
        # 隔离模块级全局配置，避免被其他测试的 set_config 污染
        from app.core.llm_config_manager import _global_config
        saved_global = dict(_global_config)
        _global_config.clear()
        try:
            monkeypatch.setenv("DEEPSEEK_API_KEY", "ENV_KEY")
            monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://env.example.com/v1")
            with UserContext(1, {
                "provider": "deepseek",
                "api_key": "USER_KEY",
                "base_url": "https://user.example.com/v1",
                "model": "user-model",
            }):
                cfg = LLMConfigManager.get_config()
                assert cfg["api_key"] == "USER_KEY"
                assert cfg["base_url"] == "https://user.example.com/v1"
                assert cfg["model"] == "user-model"
            # 退出上下文回落环境变量
            cfg2 = LLMConfigManager.get_config()
            assert cfg2["api_key"] == "ENV_KEY"
        finally:
            _global_config.clear()
            _global_config.update(saved_global)

    def test_capture_restore_apply(self):
        with UserContext(7, {"api_key": "K1"}):
            ctx = capture()
        assert ctx["user_id"] == 7
        assert ctx["llm_config_snapshot"]["api_key"] == "K1"

        with restore(ctx):
            assert LLMConfigManager.get_config().get("api_key") == "K1"

        # apply 用于 Starlette BackgroundTask（无上下文管理器）
        apply({"user_id": 8, "llm_config_snapshot": {"api_key": "K2"}})
        assert LLMConfigManager.get_config().get("api_key") == "K2"


class _Result:
    """模拟 SQLAlchemy 查询结果：一次 execute 同时服务 user 与 novel 计数。"""
    def __init__(self, user, count=0):
        self.user = user
        self.count = count

    def scalar_one_or_none(self):
        return self.user

    def scalar(self):
        return self.count


def _fake_db(user, count=0):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(user, count))
    return db


def _fake_user(**overrides):
    base = dict(
        id=1, tier="free", novel_quota=1, monthly_chapter_quota=20,
        quota_month=None, monthly_chapters_used=0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ─────────────────────────────────────────────
# 3. 额度墙
# ─────────────────────────────────────────────
class TestQuotaService:
    @pytest.mark.asyncio
    async def test_free_exceeds_chapter_quota(self):
        user = _fake_user(quota_month=_month_str(), monthly_chapters_used=20)
        svc = QuotaService(_fake_db(user))
        with pytest.raises(QuotaExceeded):
            await svc.assert_can_generate_chapter(1)

    @pytest.mark.asyncio
    async def test_free_within_quota_ok(self):
        svc = QuotaService(_fake_db(_fake_user(monthly_chapters_used=5)))
        await svc.assert_can_generate_chapter(1)  # 不抛

    @pytest.mark.asyncio
    async def test_pro_unlimited(self):
        user = _fake_user(tier="pro", monthly_chapters_used=99)
        svc = QuotaService(_fake_db(user))
        await svc.assert_can_generate_chapter(1)  # 不抛

    @pytest.mark.asyncio
    async def test_record_increments_and_initializes_month(self):
        user = _fake_user()
        svc = QuotaService(_fake_db(user))
        await svc.record_chapter_generated(1)
        assert user.quota_month == _month_str()
        assert user.monthly_chapters_used == 1

    @pytest.mark.asyncio
    async def test_record_ignored_for_pro(self):
        user = _fake_user(tier="pro")
        svc = QuotaService(_fake_db(user))
        await svc.record_chapter_generated(1)
        assert user.monthly_chapters_used == 0

    @pytest.mark.asyncio
    async def test_lazy_month_reset(self):
        user = _fake_user(quota_month="2000-01", monthly_chapters_used=20)
        svc = QuotaService(_fake_db(user))
        await svc.assert_can_generate_chapter(1)  # 跨月 → 自动归零，不抛
        assert user.quota_month == _month_str()
        assert user.monthly_chapters_used == 0

    @pytest.mark.asyncio
    async def test_free_exceeds_novel_quota(self):
        svc = QuotaService(_fake_db(_fake_user(), count=1))
        with pytest.raises(QuotaExceeded):
            await svc.assert_can_create_novel(1)

    @pytest.mark.asyncio
    async def test_status_shape(self):
        svc = QuotaService(_fake_db(
            _fake_user(quota_month=_month_str(), monthly_chapters_used=3), count=1
        ))
        st = await svc.get_status(1)
        assert st["tier"] == "free"
        assert st["novels_used"] == 1
        assert st["chapters_used"] == 3
        assert st["is_unlimited"] is False


# ─────────────────────────────────────────────
# 4. 用户 LLM 配置快照（解密）
# ─────────────────────────────────────────────
class TestLLMUserConfigSnapshot:
    @pytest.mark.asyncio
    async def test_get_snapshot_decrypts(self, monkeypatch):
        monkeypatch.setenv("APP_KEY_ENCRYPT_SECRET", "test-secret")
        from app.core.secret_box import encrypt_secret
        from app.services.llm_user_service import LLMUserConfigService

        row = SimpleNamespace(
            provider="deepseek",
            api_key_enc=encrypt_secret("sk-123"),
            base_url="https://user.example.com/v1",
            model="user-model",
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_Result(row, 0))
        snap = await LLMUserConfigService(db).get_snapshot(1)
        assert snap["api_key"] == "sk-123"
        assert snap["base_url"] == "https://user.example.com/v1"
