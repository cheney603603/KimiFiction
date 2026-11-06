"""番茄小说公开榜单服务：Python 直连平台公开接口 + PUA 字体混淆解码 + 快照入库。

参考：用户技能 fanqie-rank（.workbuddy/skills/fanqie-rank）的接口契约——
  榜单 `GET /api/rank/category/list`：app_id=2503&rank_list_type=3&offset&limit&category_id&gender&rankMold&rank_version=
  品类 `GET /api/config/list`：config_key=serial_rank_category_list_common
  gender=1 男 / 2 女，必须与品类分组一致；rankMold=1 新书 / 2 阅读。
  category_id=0 恒为空（平台无全站总榜）。
仅使用公开榜单与书籍详情接口，不抓章节正文；遵守合理频率。
"""
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hot_topic import HotTopic

BASE = "https://fanqienovel.com"
APP_ID = 2503
RANK_LIST_TYPE = 3
MOLD = {"read": 2, "new": 1}
GENDER = {"male": 1, "female": 2}
STATUS_TEXT = {0: "完结", 1: "连载"}
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SEED_PATH = Path(__file__).resolve().parent.parent / "assets" / "fanqie_decode_seed.json"
PAGE_LIMIT = 20
SLEEP = 0.3


def _load_mapping() -> Dict[str, str]:
    """PUA 私用区字符 → 真实字符 映射（种子表 + 可选的学习缓存）。"""
    mapping: Dict[str, str] = {}
    if SEED_PATH.exists():
        try:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            for k, v in (seed.get("chars") or {}).items():
                if k.startswith("U+"):
                    mapping[chr(int(k[2:], 16))] = v
        except Exception:
            pass
    cache_path = Path(os.path.expanduser("~/.cache/fanqie-rank/decode-map.json"))
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            learned = {chr(int(k[2:], 16)): v
                       for k, v in (cache.get("chars") or {}).items() if k.startswith("U+")}
            mapping.update(learned)
        except Exception:
            pass
    return mapping


def _is_pua(ch: str) -> bool:
    return 0xE000 <= ord(ch) <= 0xF8FF


def decode_text(text: str, mapping: Dict[str, str]) -> str:
    if not text:
        return ""
    return "".join(mapping.get(ch, ch) if _is_pua(ch) else ch for ch in text)


async def _http_json(client: httpx.AsyncClient, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = await client.get(f"{BASE}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as e:
            last = e
            import asyncio
            await asyncio.sleep(1.0 * (attempt + 1))
    raise last  # type: ignore[misc]


class FanqieRankService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._mapping: Optional[Dict[str, str]] = None
        self._detail: Dict[str, Dict[str, Any]] = {}

    @property
    def mapping(self) -> Dict[str, str]:
        if self._mapping is None:
            self._mapping = _load_mapping()
        return self._mapping

    async def categories(self) -> List[Dict[str, str]]:
        """37 个品类（男频/女频分组）。"""
        async with httpx.AsyncClient(timeout=20, verify=False,
                                     headers={"User-Agent": UA, "Referer": f"{BASE}/rank"}) as client:
            data = await _http_json(client, "/api/config/list", {
                "config_key": "serial_rank_category_list_common",
            })
        items = (data.get("data") or {}).get("list") or []
        out = []
        for it in items:
            groups = it.get("group") or []
            gender = "male" if "male" in groups else ("female" if "female" in groups else "?")
            name = decode_text(str(it.get("name", "")), self.mapping)
            out.append({"id": str(it.get("id")), "name": name, "gender": gender})
        return out

    async def fetch_rank(self, gender: str, genre_id: str, rank_type: str,
                         top: int = 20) -> List[Dict[str, Any]]:
        """实时抓取榜单（不落库），书名/作者经 PUA 解码，未知码位回查 book/info 补全。"""
        mold = MOLD.get(rank_type, 2)
        g = GENDER.get(gender, 1)
        books: List[Dict[str, Any]] = []
        offset = 0
        async with httpx.AsyncClient(timeout=20, verify=False,
                                     headers={"User-Agent": UA, "Referer": f"{BASE}/rank"}) as client:
            while len(books) < top:
                want = min(PAGE_LIMIT, top - len(books))
                data = await _http_json(client, "/api/rank/category/list", {
                    "app_id": APP_ID, "rank_list_type": RANK_LIST_TYPE,
                    "offset": offset, "limit": want, "category_id": genre_id,
                    "rank_version": "", "gender": g, "rankMold": mold,
                })
                page = (data.get("data") or {}).get("book_list") or []
                if not page:
                    break
                books.extend(page)
                offset += len(page)
                if len(books) < top:
                    import asyncio
                    await asyncio.sleep(SLEEP)

        # 榜单名的 PUA 混淆按请求可能轮换，静态种子可能把个别字解错；
        # 对 top 内每本书回查 book/info（该接口返回明文）保证书名/作者准确。
        for b in books[:top]:
            bid = str(b.get("bookId", ""))
            try:
                info = await _http_json(client, "/api/book/info", {"bookId": bid})
                self._detail[bid] = info.get("data") or {}
            except Exception:
                pass
            import asyncio
            await asyncio.sleep(SLEEP)

        out = []
        for idx, b in enumerate(books[:top], start=1):
            bid = str(b.get("bookId", ""))
            info = self._detail.get(bid) or {}
            creation = b.get("creationStatus") if b.get("creationStatus") is not None else info.get("creationStatus")
            # book/info 返回明文，直接使用（无回查结果时回落榜单字段 + 种子解码）
            name = decode_text(str(info.get("bookName") or b.get("bookName") or ""), self.mapping)
            author = decode_text(str(info.get("author") or info.get("authorName") or b.get("author") or ""), self.mapping)
            last_ch = decode_text(str(info.get("lastChapterTitle") or b.get("lastChapterTitle") or ""), self.mapping)
            unknown = any(_is_pua(ch) for ch in name + author)
            out.append({
                "rank": b.get("currentPos") or idx,
                "rank_change": int(b.get("rankPosDiff") or 0),
                "book_id": bid,
                "book_name": name,
                "author": author,
                "word_count": int(b.get("wordNumber") or info.get("wordNumber") or 0),
                "read_count": int(b.get("read_count") or b.get("readCount") or info.get("readCount") or 0),
                "status": STATUS_TEXT.get(int(creation or -1), "未知") if str(creation).isdigit() else "未知",
                "last_chapter": last_ch,
                "decode_ok": not unknown,
            })
        return out

    async def get_or_fetch(self, gender: str, genre_id: str, genre: str, rank_type: str,
                           top: int = 20, refresh: bool = False) -> List[Dict[str, Any]]:
        """先读当日快照，无则实时抓取并入库（refresh=1 强制重抓）。"""
        if not refresh:
            rows = (await self.db.execute(
                select(HotTopic)
                .where(HotTopic.snapshot_date == date.today(),
                       HotTopic.gender == gender,
                       HotTopic.genre_id == genre_id,
                       HotTopic.rank_type == rank_type)
                .order_by(HotTopic.rank)
            )).scalars().all()
            if rows:
                return [{
                    "rank": r.rank, "rank_change": r.rank_change or 0,
                    "book_id": r.book_id, "book_name": r.book_name,
                    "author": r.author or "", "word_count": r.word_count,
                    "read_count": r.read_count, "status": r.status or "",
                    "last_chapter": r.last_chapter or "", "decode_ok": True,
                } for r in rows]

        books = await self.fetch_rank(gender, genre_id, rank_type, top)
        await self.db.execute(
            delete(HotTopic).where(HotTopic.snapshot_date == date.today(),
                                   HotTopic.gender == gender,
                                   HotTopic.genre_id == genre_id,
                                   HotTopic.rank_type == rank_type)
        )
        for b in books:
            self.db.add(HotTopic(
                snapshot_date=date.today(), gender=gender, genre=genre,
                genre_id=genre_id, rank_type=rank_type,
                rank=b["rank"], rank_change=b.get("rank_change", 0),
                book_id=b["book_id"], book_name=b["book_name"],
                author=b["author"], word_count=b["word_count"],
                read_count=b["read_count"], status=b["status"],
                last_chapter=b["last_chapter"],
            ))
        await self.db.flush()
        return books
