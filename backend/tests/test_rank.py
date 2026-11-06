"""番茄榜单服务 + 用量按模型聚合的单元测试（不触网，全用夹具数据）。"""
from types import SimpleNamespace

import pytest

from app.services.fanqie_rank_service import FanqieRankService, decode_text
from app.services.llm_usage_service import _by_model


# ─────────────────────────────────────────
# decode_text：PUA 私用区字符解码
# ─────────────────────────────────────────

def test_decode_text_pua_with_mapping():
    mapping = {"": "东", "": "方", "": "仙"}
    assert decode_text("仙侠", mapping) == "东方仙侠"


def test_decode_text_unknown_pua_kept():
    # 未知码位保持原样（decode_ok 会标 false，由 book/info 回查兜底）
    assert decode_text("仙侠", {}) == "仙侠"


def test_decode_text_plain_passthrough():
    assert decode_text("凡人修仙传", {"": "凡"}) == "凡人修仙传"


# ─────────────────────────────────────────
# fetch_rank：分页 + book/info 明文回查 + 字段变换
# ─────────────────────────────────────────

RANK_PAGE = {
    "data": {
        "book_list": [
            {
                "bookId": "1001",
                "bookName": "侠",  # 榜单接口为 PUA 混淆名
                "author": "张三",
                "currentPos": 3,
                "rankPosDiff": 5,
                "wordNumber": 845950,
                "read_count": 689484,
                "creationStatus": 1,
                "lastChapterTitle": "第392章 结尾",
            }
        ]
    }
}

BOOK_INFO = {
    "data": {
        "bookName": "东方仙侠录",  # book/info 返回明文
        "author": "作者真名",
        "wordNumber": 900000,
        "creationStatus": 0,
    }
}


@pytest.fixture
def fake_http_json(monkeypatch):
    """把 _http_json 换成夹具数据源，避免真实网络请求。"""

    async def fake(client, path, params):
        if path == "/api/rank/category/list":
            return RANK_PAGE
        if path == "/api/book/info":
            return BOOK_INFO
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr("app.services.fanqie_rank_service._http_json", fake)
    return fake


@pytest.mark.asyncio
async def test_fetch_rank_uses_clean_book_info(fake_http_json):
    svc = FanqieRankService(None)
    books = await svc.fetch_rank("male", "1140", "read", top=5)
    assert len(books) == 5  # 单页夹具数据不足 top 时会翻页补齐
    b = books[0]
    # 书名/作者取自 book/info 明文（而非 PUA 混淆名）
    assert b["book_name"] == "东方仙侠录"
    assert b["author"] == "作者真名"
    # 榜单列表字段优先（wordNumber / creationStatus 与 info 一致时取榜单）
    assert b["word_count"] == 845950
    assert b["status"] == "连载"  # 榜单 creationStatus 1
    assert b["rank"] == 3
    assert b["rank_change"] == 5
    assert b["decode_ok"] is True


@pytest.mark.asyncio
async def test_fetch_rank_falls_back_to_rank_fields(monkeypatch):
    # 无 book/info 时回落榜单字段 + 种子解码
    async def fake(client, path, params):
        if path == "/api/rank/category/list":
            return RANK_PAGE
        raise AssertionError(f"unexpected path: {path}")

    # 固定解码映射，避免依赖真实种子表内容
    def fake_mapping():
        return {"": "东", "": "方", "": "仙"}

    monkeypatch.setattr("app.services.fanqie_rank_service._http_json", fake)
    monkeypatch.setattr("app.services.fanqie_rank_service._load_mapping", fake_mapping)
    svc = FanqieRankService(None)
    books = await svc.fetch_rank("male", "1140", "read", top=5)
    b = books[0]
    assert b["book_name"] == "东方仙侠"  # 映射  → 东方仙
    assert b["author"] == "张三"
    assert b["word_count"] == 845950
    assert b["status"] == "连载"
    assert b["last_chapter"] == "第392章 结尾"


# ─────────────────────────────────────────
# categories：37 品类男/女分组
# ─────────────────────────────────────────

CATEGORY_PAGE = {
    "data": {
        "list": [
            {"id": 1140, "name": "东方仙侠", "group": ["male"]},
            {"id": 1139, "name": "古风世情", "group": ["female"]},
        ]
    }
}


@pytest.mark.asyncio
async def test_categories_gender_groups(monkeypatch):
    async def fake(client, path, params):
        assert path == "/api/config/list"
        return CATEGORY_PAGE

    monkeypatch.setattr("app.services.fanqie_rank_service._http_json", fake)
    svc = FanqieRankService(None)
    items = await svc.categories()
    assert {"id": "1140", "name": "东方仙侠", "gender": "male"} in items
    assert {"id": "1139", "name": "古风世情", "gender": "female"} in items


# ─────────────────────────────────────────
# 用量按模型聚合
# ─────────────────────────────────────────

def _row(model="deepseek-flash", tokens_in=100, tokens_out=50, retry=0, status="ok"):
    return SimpleNamespace(model=model, tokens_in=tokens_in,
                           tokens_out=tokens_out, retry_count=retry, status=status)


def test_by_model_aggregation():
    rows = [
        _row("deepseek-flash", 100, 50, retry=1),
        _row("deepseek-flash", 200, 60, retry=0),
        _row("gpt-4o", 300, 70, retry=2, status="error"),
    ]
    by_model = _by_model(rows)
    assert by_model["deepseek-flash"] == {"calls": 2, "tokens_in": 300, "tokens_out": 110,
                                          "retries": 1, "errors": 0}
    assert by_model["gpt-4o"] == {"calls": 1, "tokens_in": 300, "tokens_out": 70,
                                  "retries": 2, "errors": 1}


def test_by_model_unknown_model_bucket():
    by_model = _by_model([_row(model=None)])
    assert "未知" in by_model


@pytest.mark.asyncio
async def test_models_summary_totals():
    from app.services.llm_usage_service import LLMUsageService

    class FakeScalars:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return FakeScalars(self._rows)

    class FakeDB:
        def __init__(self, rows):
            self._rows = rows

        async def execute(self, *a, **k):
            return FakeResult(self._rows)

    db = FakeDB([_row(), _row(retry=2, status="error"), _row(tokens_in=0)])
    summary = await LLMUsageService(db).models_summary()
    assert summary["total_calls"] == 3
    assert summary["total_tokens_in"] == 200
    assert summary["total_tokens_out"] == 150
    assert summary["total_tokens"] == 350
    assert summary["total_retries"] == 2
    assert summary["total_errors"] == 1
