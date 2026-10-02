"""端到端验证：用 UIAI(联影网关) Key 驱动真实 LLM，走实体抽取管线，再校验前端世界页。
用法: python scripts/e2e_uiai.py  (需后端已启动 http://127.0.0.1:8080)
"""
import asyncio
import sys
import os
import json
import http.client as _http

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))


async def main():
    # 1. 解析 LLM 配置（确认走 UIAI 网关）
    from app.core.llm_config_manager import LLMConfigManager
    cfg = LLMConfigManager.get_config()
    base_url = cfg.get("base_url")
    model = cfg.get("model")
    api_key = cfg.get("api_key")
    print(f"[1] LLM 配置: base_url={base_url}")
    print(f"        model={model}  api_key 存在={bool(api_key)}")
    if "ai-infra.united-imaging.com" not in (base_url or ""):
        print("[FAIL] 未走联影 UIAI 网关 base_url!=", base_url)
        return False
    if not api_key:
        print("[FAIL] 未取到 API Key")
        return False

    # 2. 通过应用真实调用 LLM（连接测试）
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": "只回复两个字：收到"}], "max_tokens": 10},
        )
    print(f"[2] LLM 连接测试: HTTP {r.status_code}, 回复={r.json()['choices'][0]['message']['content'][:20]}")
    if r.status_code != 200:
        print(f"[FAIL] LLM 调用失败: {r.text[:200]}")
        return False

    # 3. 用一个真实小说段落走「实体抽取管线」——LLM 会识别林晓/青云宗/苏晴/青云剑冢等实体
    from app.services.entity_extraction_service import EntityExtractionService

    paragraph = (
        "林晓在青云宗山门前接受入门考核，费尽心力终于通过，成为外门弟子。"
        "同门苏晴偷偷塞给他一枚驻颜丹，说这是灵药谷药老赐下的丹药。"
        "夜里林晓回想起林家被血煞盟灭门之事，慕容战的身影挥之不去。"
        "他握紧腰间那柄得自青云剑冢的玄天剑，暗暗立誓，有朝一日要亲手报仇。"
    )
    svc = EntityExtractionService()
    res = await svc.extract_from_paragraph(
        current_paragraph=paragraph,
        paragraph_id=70001,
        existing_entities=[],  # 干净场景，便于断言新实体
        novel_context="玄幻修真小说。主角林晓，青云宗外门弟子。",
    )
    print(f"[3] 实体抽取完成: mentions={len(res.mentions)} relations={len(res.relations)}")
    for m in res.mentions:
        print(f"      - {m.canonical_name}({m.entity_type}) new={m.is_new} conf={m.confidence:.2f}")
    if not res.mentions:
        print("[FAIL] 未抽取到任何实体")
        return False

    # 4. 通过 API 写入实体与关系（复用服务层现有的 http 路径，避免跨事件循环 DB 操作）
    import http.client as _http
    conn = _http.HTTPConnection("127.0.0.1", 8080)
    body = json.dumps({"username": "e2e_test_user", "password": "Test123"})
    conn.request("POST", "/api/v1/auth/login", body, {"Content-Type": "application/json"})
    import json as _j  # noqa
    token = _j.loads(conn.getresponse().read())["access_token"]
    created = []
    for m in res.mentions:
        if not m.is_new:
            continue
        mut = {
            "novel_id": 1002,
            "canonical_name": m.canonical_name,
            "entity_type": m.entity_type,
            "aliases": m.aliases or [],
            "state_vector": m.state_changes or {},
            "narrative_summary": "由 UIAI 实体抽取管线生成（演示段落）",
        }
        conn.request("POST", "/api/v1/entities", json.dumps(mut, ensure_ascii=False).encode("utf-8"), {
            "Content-Type": "application/json", "Authorization": f"Bearer {token}",
        })
        r = conn.getresponse()
        rb = r.read()
        if r.status < 400:
            created.append(_j.loads(rb.decode("utf-8")))
        else:
            print(f"      [warn] 创建实体失败 {m.canonical_name}: HTTP {r.status} {rb[:120]}")
    for rel in res.relations:
        conn.request("POST", "/api/v1/entities/relationships", json.dumps({
            "novel_id": 1002, "source_id": rel.source_name, "target_id": rel.target_name,
            "relation_type": rel.relation_type,
        }, ensure_ascii=False).encode("utf-8"), {
            "Content-Type": "application/json", "Authorization": f"Bearer {token}",
        })
        r = conn.getresponse()
        r.read()
    conn.close()
    print(f"[4] 已通过 API 写入实体 {len(created)} 个")

    # 6. 校验 world 聚合接口能看到新实体
    conn = _http.HTTPConnection("127.0.0.1", 8080)
    body = json.dumps({"username": "e2e_test_user", "password": "Test123"})
    conn.request("POST", "/api/v1/auth/login", body, {"Content-Type": "application/json"})
    token = _j.loads(conn.getresponse().read())["access_token"]
    conn.request("GET", "/api/v1/novels/1002/world", headers={"Authorization": f"Bearer {token}"})
    wd = _j.loads(conn.getresponse().read())
    conn.close()
    print(f"[6] /world 接口: counts={wd['counts']}")
    ent_names = [e["canonical_name"] for e in wd["entities"]]
    has_lin = any(n in ent_names for n in ("林晓", "青云宗", "血煞盟", "玄天剑"))
    print(f"        实体含 林晓/青云宗/血煞盟/玄天剑 之一: {has_lin}; 实体总数={len(ent_names)}")

    print("\n===== E2E-UIAI 结果 =====")
    print("OK" if has_lin else "PARTIAL")
    return has_lin


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)