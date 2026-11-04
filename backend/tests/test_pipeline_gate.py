"""批量管线 Pro 门槛（M2）单元测试。"""
import importlib.util
import sys
from pathlib import Path

import pytest

_PIPELINE = Path(__file__).parent.parent.parent / "scripts" / "run_novel_pipeline.py"


def _load_pipeline():
    spec = importlib.util.spec_from_file_location("run_novel_pipeline", _PIPELINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_novel_pipeline"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestPipelineProGate:
    def test_free_user_blocked(self, monkeypatch):
        mod = _load_pipeline()
        monkeypatch.setattr(mod, "api", lambda method, path, **kw: {"tier": "free"})
        with pytest.raises(SystemExit):
            mod.require_pro("fake-token")

    def test_pro_user_allowed(self, monkeypatch):
        mod = _load_pipeline()
        monkeypatch.setattr(mod, "api", lambda method, path, **kw: {"tier": "pro", "batch_enabled": True})
        mod.require_pro("fake-token")  # 不抛

    def test_batch_switch_off_blocks(self, monkeypatch):
        mod = _load_pipeline()
        monkeypatch.setattr(mod, "api", lambda method, path, **kw: {"tier": "pro", "batch_enabled": False})
        with pytest.raises(SystemExit):
            mod.require_pro("fake-token")

    def test_backend_unreachable_allows(self, monkeypatch):
        """后端不可达时默认放行，避免把网络问题误判为权限问题。"""
        mod = _load_pipeline()

        def boom(method, path, **kw):
            raise Exception("connection refused")

        monkeypatch.setattr(mod, "api", boom)
        mod.require_pro("fake-token")

    def test_user_override(self, monkeypatch):
        mod = _load_pipeline()
        monkeypatch.setattr(
            sys, "argv", ["run_novel_pipeline.py", "full", "--user", "alice", "--password", "pw"]
        )
        mod.parse_user_override()
        assert mod.USER == "alice"
        assert mod.PASSWORD == "pw"
