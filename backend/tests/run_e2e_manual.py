"""
实体管理系统端到端测试（快速验证用）
直接运行: python backend/tests/run_e2e_manual.py
要求: 后端在 localhost:8000 运行
"""
import sys, json, asyncio
import httpx

BASE = "http://localhost:8000/api/v1"
PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  -> {detail}")

async def call(method, path, json_data=None, params=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:
        if method == "POST":
            return await c.post(path, json=json_data, headers=headers)
        elif method == "PUT":
            return await c.put(path, json=json_data, headers=headers)
        elif method == "DELETE":
            return await c.delete(path, headers=headers, params=params)
        else:
            return await c.get(path, headers=headers, params=params)

async def main():
    global PASS, FAIL

    # 1. Health
    print("\n=== 1. 系统基础 ===")
    r = await call("GET", "http://localhost:8000/health")
    check("Health Check", r.status_code == 200, str(r.status_code))

    # 2. Login
    print("\n=== 2. 用户认证 ===")
    r = await call("POST", "/auth/login", {"username": "e2e_test_user", "password": "Test123"})
    check("Login", r.status_code in (200, 201), f"status={r.status_code}")
    token = r.json().get("access_token") or ""
    check("Token received", len(token) > 20, f"len={len(token)}")

    # 3. Novel
    print("\n=== 3. 小说创建 ===")
    r = await call("POST", "/novels", {"title": "E2E测试小说", "genre": "xianxia"}, token=token)
    novel_id = r.json().get("id") or 0
    check("Create Novel", r.status_code in (200, 201) and novel_id > 0, str(r.status_code))

    # 4. Entity CRUD
    print("\n=== 4. 实体 CRUD ===")
    entities = {}
    for name, etype, extra in [
        ("叶凡", "character", {"aliases": ["叶黑"], "state_vector": {"age": 18, "goals": ["成仙"]}}),
        ("天玄宗", "faction", {}),
        ("东荒密林", "location", {}),
        ("玄天鼎", "item", {}),
        ("太虚剑诀", "skill", {}),
    ]:
        body = {"novel_id": novel_id, "canonical_name": name, "entity_type": etype}
        body.update(extra)
        r = await call("POST", "/entities", body, token=token)
        entities[name] = r.json().get("entity_id", "")
        check(f"Create {name} ({etype})", r.status_code in (200, 201), str(r.status_code))

    # List
    r = await call("GET", f"/entities/novel/{novel_id}", token=token)
    check("List all", r.json()["total"] >= 5, f"total={r.json()['total']}")

    r = await call("GET", f"/entities/novel/{novel_id}", params={"entity_type": "character"}, token=token)
    check("Filter by character", r.json()["total"] >= 1, str(r.json()["total"]))

    r = await call("GET", f"/entities/novel/{novel_id}", params={"entity_type": "skill"}, token=token)
    check("Filter by skill", r.json()["total"] >= 1, str(r.json()["total"]))

    # Get detail
    r = await call("GET", f"/entities/{entities['叶凡']}", token=token)
    check("Get detail", r.status_code == 200 and r.json()["canonical_name"] == "叶凡", str(r.status_code))
    check("  state_vector.age", r.json().get("state_vector", {}).get("age") == 18, str(r.json()))

    # 404
    r = await call("GET", "/entities/ent_nonexist", token=token)
    check("Get 404", r.status_code == 404, str(r.status_code))

    # Update
    r = await call("PUT", f"/entities/{entities['叶凡']}", {
        "aliases": ["叶黑", "荒天帝"],
        "state_vector": {"age": 19, "cultivation_level": "金丹期"},
    }, token=token)
    check("Update entity", r.status_code == 200, str(r.status_code))
    check("  aliases updated", "荒天帝" in str(r.json().get("aliases", [])), str(r.json().get("aliases")))
    check("  state_vector.age", r.json().get("state_vector", {}).get("age") == 19, str(r.json().get("state_vector")))

    # Partial update
    r = await call("PUT", f"/entities/{entities['天玄宗']}", {"narrative_summary": "东荒第一宗门"}, token=token)
    check("Partial update", r.status_code == 200, str(r.status_code))
    check("  name unchanged", r.json()["canonical_name"] == "天玄宗", str(r.json()))

    # Create minimal entity
    r = await call("POST", "/entities", {"novel_id": novel_id, "canonical_name": "路人", "entity_type": "character"}, token=token)
    tmp_id = r.json().get("entity_id", "")
    check("Create minimal", r.status_code in (200, 201) and r.json().get("state_vector") == {}, str(r.status_code))

    # 5. Relationships
    print("\n=== 5. 实体关系 ===")
    r = await call("POST", "/entities/relationships", {
        "novel_id": novel_id, "source_id": entities["叶凡"], "target_id": entities["天玄宗"], "relation_type": "弟子"
    }, token=token)
    check("Create relationship", r.status_code in (200, 201), str(r.status_code))

    r = await call("GET", f"/entities/novel/{novel_id}/relationships", token=token)
    check("List relationships", r.status_code == 200 and r.json()["total"] >= 1, f"total={r.json()['total']}")

    # 6. Deletion
    print("\n=== 6. 删除 ===")
    r = await call("DELETE", "/entities/batch", params={"ids": ""}, token=token)
    check("Batch delete empty -> 400", r.status_code == 400, str(r.status_code))

    r = await call("DELETE", f"/entities/{tmp_id}", token=token)
    check("Delete single", r.status_code == 200, str(r.status_code))
    r = await call("GET", f"/entities/{tmp_id}", token=token)
    check("  verify 404", r.status_code == 404, str(r.status_code))

    ids = ",".join([entities["东荒密林"], entities["玄天鼎"], entities["太虚剑诀"]])
    r = await call("DELETE", "/entities/batch", params={"ids": ids}, token=token)
    check("Batch delete multiple", r.status_code == 200, str(r.status_code))
    check("  deleted_ids count", len(r.json().get("deleted_ids", [])) >= 2, str(r.json()))

    r = await call("DELETE", "/entities/ent_nonexist", token=token)
    check("Delete 404", r.status_code == 404, str(r.status_code))

    # Cascade
    r = await call("POST", "/entities", {"novel_id": novel_id, "canonical_name": "CascadeA", "entity_type": "character"}, token=token)
    ca = r.json()["entity_id"]
    r = await call("POST", "/entities", {"novel_id": novel_id, "canonical_name": "CascadeB", "entity_type": "character"}, token=token)
    cb = r.json()["entity_id"]
    await call("POST", "/entities/relationships", {"novel_id": novel_id, "source_id": ca, "target_id": cb, "relation_type": "朋友"}, token=token)
    await call("DELETE", f"/entities/{ca}", token=token)
    r = await call("GET", f"/entities/{ca}", token=token)
    check("Cascade: source gone", r.status_code == 404, str(r.status_code))
    r = await call("GET", f"/entities/{cb}", token=token)
    check("Cascade: target alive", r.status_code == 200, str(r.status_code))
    await call("DELETE", f"/entities/{cb}", token=token)

    # 7. Error handling
    print("\n=== 7. 错误处理 ===")
    r = await call("POST", "/entities", {"novel_id": novel_id, "canonical_name": "X", "entity_type": "invalid"}, token=token)
    check("Invalid type", r.status_code in (422, 500), str(r.status_code))
    r = await call("POST", "/entities", {"novel_id": novel_id, "canonical_name": "", "entity_type": "character"}, token=token)
    check("Empty name", r.status_code in (422, 400), str(r.status_code))

    # 8. State vector
    print("\n=== 8. 状态向量 ===")
    r = await call("POST", "/entities", {
        "novel_id": novel_id, "canonical_name": "SVT1", "entity_type": "character",
        "state_vector": {"tags": ["a", "b"], "nested": {"k": "v"}},
    }, token=token)
    sv_id = r.json().get("entity_id", "")
    check("Complex state", r.status_code in (200, 201), str(r.status_code))
    check("  tags array", r.json()["state_vector"]["tags"] == ["a", "b"], str(r.json()["state_vector"]))
    await call("DELETE", f"/entities/{sv_id}", token=token)

    r = await call("POST", "/entities", {"novel_id": novel_id, "canonical_name": "SVT2", "entity_type": "character", "state_vector": {"x": "y"}}, token=token)
    sv2_id = r.json()["entity_id"]
    r = await call("PUT", f"/entities/{sv2_id}", {"state_vector": {}}, token=token)
    check("Clear state -> {}", r.status_code == 200 and r.json()["state_vector"] == {}, str(r.json()["state_vector"]))
    await call("DELETE", f"/entities/{sv2_id}", token=token)

    # Summary
    total = PASS + FAIL
    print(f"\n{'='*50}")
    print(f"结果: {PASS}/{total} passed")
    if FAIL > 0:
        print(f"      {FAIL} FAILED ❌")
        sys.exit(1)
    else:
        print("全部通过!")
    print(f"{'='*50}")

asyncio.run(main())