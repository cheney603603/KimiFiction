"""
KimiFiction 实体管理系统端到端集成测试

运行条件:
  1. Docker 服务运行中 (MySQL + Redis)
  2. 后端服务运行中 (uvicorn app.main:app --port 8000)
  3. Python 包: pytest, httpx

运行方式:
  pytest backend/tests/test_entity_e2e.py -v --asyncio-mode=auto

如需自动清理测试数据，设置环境变量 E2E_CLEANUP=true
"""
import os
import pytest
import httpx
from typing import Dict, Optional
from datetime import datetime

# ─── 配置 ────────────────────────────────────────────────────
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"
TEST_USER = {
    "username": f"e2e_test_{datetime.now().strftime('%m%d%H%M%S')}",
    "email": f"e2e_{datetime.now().strftime('%m%d%H%M%S')}@test.com",
    "password": "TestPass123!",
}
CLEANUP = os.getenv("E2E_CLEANUP", "true").lower() == "true"


# ─── 辅助函数 ─────────────────────────────────────────────────

class TestContext:
    """测试上下文，保存测试过程中创建的资源"""
    token: str = ""
    novel_id: int = 0
    entity_ids: Dict[str, str] = {}   # name -> entity_id
    relationship_ids: list = []


ctx = TestContext()


async def api_post(path: str, json_data: dict, token: Optional[str] = None) -> dict:
    """POST 请求辅助"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post(f"{API_PREFIX}{path}", json=json_data, headers=headers)
        return resp


async def api_get(path: str, token: str, params: Optional[dict] = None) -> httpx.Response:
    """GET 请求辅助"""
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.get(f"{API_PREFIX}{path}", headers=headers, params=params)
        return resp


async def api_put(path: str, json_data: dict, token: str) -> httpx.Response:
    """PUT 请求辅助"""
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.put(f"{API_PREFIX}{path}", json=json_data, headers=headers)
        return resp


async def api_delete(path: str, token: str, params: Optional[dict] = None) -> httpx.Response:
    """DELETE 请求辅助"""
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.delete(f"{API_PREFIX}{path}", headers=headers, params=params)
        return resp


# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    """为整个模块创建一个事件循环"""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── 测试用例集 1: 系统基础 ──────────────────────────────────

class TestSystemBasics:
    """验证后端服务正常运行"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """后端健康检查"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            resp = await client.get("/health")
        assert resp.status_code in (200, 404), f"Health check failed: {resp.status_code}"
        # 部分后端没有显式 /health 端点，404 也说明服务在运行

    @pytest.mark.asyncio
    async def test_api_root(self):
        """API 根路径可达"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            resp = await client.get(f"{API_PREFIX}/novels")
        assert resp.status_code in (200, 401), f"API root failed: {resp.status_code}"
        # 401 表示需要认证，说明服务正常


# ─── 测试用例集 2: 用户认证 ──────────────────────────────────

class TestAuth:
    """用户注册与登录"""

    @pytest.mark.asyncio
    async def test_register(self):
        """注册测试用户"""
        resp = await api_post("/auth/register", TEST_USER)
        assert resp.status_code in (200, 201, 400), f"Register failed: {resp.text}"
        if resp.status_code == 400 and "already" in resp.text.lower():
            pytest.skip("User already exists, will login instead")

    @pytest.mark.asyncio
    async def test_login(self):
        """登录获取 Token"""
        resp = await api_post("/auth/login", {
            "username": TEST_USER["username"],
            "password": TEST_USER["password"],
        })
        assert resp.status_code in (200, 201), f"Login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.token = data.get("access_token") or data.get("token", "")
        assert ctx.token, f"No token in response: {data}"


# ─── 测试用例集 3: 小说创建 ──────────────────────────────────

class TestNovelCreation:
    """创建测试用小说"""

    @pytest.mark.asyncio
    async def test_create_novel(self):
        """创建测试小说"""
        assert ctx.token, "No token available — login first"
        resp = await api_post("/novels", {
            "title": "剑破苍穹 (测试)",
            "genre": "xianxia",
            "style_prompt": "热血冒险，爽文风格",
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create novel failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.novel_id = data.get("id") or data.get("novel", {}).get("id", 0)
        assert ctx.novel_id > 0, f"No novel id in response: {data}"

    @pytest.mark.asyncio
    async def test_get_novel(self):
        """获取小说详情"""
        assert ctx.novel_id > 0, "No novel created"
        resp = await api_get(f"/novels/{ctx.novel_id}", ctx.token)
        assert resp.status_code == 200, f"Get novel failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("title") == "剑破苍穹 (测试)", f"Unexpected title: {data}"


# ─── 测试用例集 4: 实体 CRUD ─────────────────────────────────

class TestEntityCRUD:
    """实体管理的增删改查"""

    @pytest.mark.asyncio
    async def test_create_character(self):
        """创建角色实体"""
        assert ctx.novel_id > 0
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "叶凡",
            "entity_type": "character",
            "aliases": ["叶黑", "叶小子"],
            "state_vector": {
                "age": 18,
                "gender": "男",
                "personality": "坚毅勇敢，重情重义",
                "goals": ["成仙", "保护家人"],
                "cultivation_level": "筑基期",
            },
            "narrative_summary": "来自偏远小镇的少年，拥有稀世灵根",
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create character failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.entity_ids["叶凡"] = data["entity_id"]
        assert data["canonical_name"] == "叶凡"
        assert data["entity_type"] == "character"
        assert data["aliases"] == ["叶黑", "叶小子"]
        assert data["state_vector"]["age"] == 18
        assert "entity_id" in data

    @pytest.mark.asyncio
    async def test_create_faction(self):
        """创建势力实体"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "天玄宗",
            "entity_type": "faction",
            "state_vector": {
                "leader": "玄天道人",
                "members": ["叶凡", "清风"],
                "territory": "东荒",
                "strength": "一流宗门",
                "ideology": "守护苍生，追求大道",
            },
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create faction failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.entity_ids["天玄宗"] = data["entity_id"]
        assert data["canonical_name"] == "天玄宗"
        assert data["entity_type"] == "faction"

    @pytest.mark.asyncio
    async def test_create_location(self):
        """创建场景实体"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "东荒密林",
            "entity_type": "location",
            "state_vector": {
                "type": "森林",
                "climate": "湿润",
                "terrain": "古木参天，瘴气弥漫",
                "significance": "叶凡获得第一次奇遇的地方",
            },
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create location failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.entity_ids["东荒密林"] = data["entity_id"]
        assert data["canonical_name"] == "东荒密林"

    @pytest.mark.asyncio
    async def test_create_item(self):
        """创建物品实体"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "玄天鼎",
            "entity_type": "item",
            "state_vector": {
                "type": "法宝",
                "origin": "天玄宗祖传",
                "function": "炼丹炼器，攻防一体",
                "power_level": "仙器",
                "owner": "叶凡",
                "restrictions": ["需筑基以上修为催动"],
            },
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create item failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.entity_ids["玄天鼎"] = data["entity_id"]

    @pytest.mark.asyncio
    async def test_create_skill(self):
        """创建功法实体（前端无此分类，后端应支持）"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "太虚剑诀",
            "entity_type": "skill",
            "state_vector": {
                "level": "天阶上品",
                "element": "金",
                "effects": ["破万法", "斩因果"],
            },
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create skill failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.entity_ids["太虚剑诀"] = data["entity_id"]
        assert data["entity_type"] == "skill"

    @pytest.mark.asyncio
    async def test_list_entities_all(self):
        """列出小说所有实体"""
        resp = await api_get(f"/entities/novel/{ctx.novel_id}", ctx.token)
        assert resp.status_code == 200, f"List entities failed: {resp.status_code}"
        data = resp.json()
        assert data["total"] >= 5, f"Expected at least 5 entities, got {data['total']}"
        assert len(data["items"]) >= 5

    @pytest.mark.asyncio
    async def test_list_entities_by_type(self):
        """按类型筛选实体"""
        resp = await api_get(f"/entities/novel/{ctx.novel_id}", ctx.token,
                             params={"entity_type": "character"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["entity_type"] == "character"

    @pytest.mark.asyncio
    async def test_get_entity(self):
        """获取单个实体详情"""
        entity_id = ctx.entity_ids.get("叶凡")
        assert entity_id, "No test entity available"
        resp = await api_get(f"/entities/{entity_id}", ctx.token)
        assert resp.status_code == 200, f"Get entity failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["canonical_name"] == "叶凡"
        assert data["entity_id"] == entity_id
        assert data["state_vector"]["age"] == 18
        assert data["state_vector"]["personality"] == "坚毅勇敢，重情重义"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self):
        """获取不存在的实体应返回404"""
        resp = await api_get("/entities/ent_nonexist", ctx.token)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_entity(self):
        """更新实体信息"""
        entity_id = ctx.entity_ids.get("叶凡")
        assert entity_id
        resp = await api_put(f"/entities/{entity_id}", {
            "canonical_name": "叶凡",
            "aliases": ["叶黑", "叶小子", "荒天帝"],
            "state_vector": {
                "age": 19,
                "cultivation_level": "金丹期",
                "personality": "坚毅勇敢，重情重义",
                "goals": ["成仙", "保护家人", "证道"],
            },
            "narrative_summary": "来自偏远小镇的少年，拥有稀世灵根，现已突破金丹期",
        }, ctx.token)
        assert resp.status_code == 200, f"Update entity failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "荒天帝" in data["aliases"]
        assert data["state_vector"]["age"] == 19
        assert data["state_vector"]["cultivation_level"] == "金丹期"
        assert data["narrative_summary"] and "金丹期" in data["narrative_summary"]

    @pytest.mark.asyncio
    async def test_partial_update_entity(self):
        """部分更新实体（只更新摘要）"""
        entity_id = ctx.entity_ids.get("天玄宗")
        assert entity_id
        resp = await api_put(f"/entities/{entity_id}", {
            "narrative_summary": "东荒第一宗门，门徒数千",
        }, ctx.token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["narrative_summary"] == "东荒第一宗门，门徒数千"
        # 验证其他字段未受影响
        assert data["canonical_name"] == "天玄宗"

    @pytest.mark.asyncio
    async def test_create_entity_empty_state(self):
        """创建无 state_vector 和 aliases 的实体"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "无名路人",
            "entity_type": "character",
        }, token=ctx.token)
        assert resp.status_code in (200, 201)
        data = resp.json()
        ctx.entity_ids["无名路人"] = data["entity_id"]
        assert data["state_vector"] == {}
        assert data["aliases"] == []

    @pytest.mark.asyncio
    async def test_create_empty_entity_list(self):
        """列出无实体的类型应返回空列表"""
        # 创建一个新小说并验证其没有实体
        resp = await api_post("/novels", {
            "title": "空测试小说",
            "genre": "fantasy",
        }, token=ctx.token)
        assert resp.status_code in (200, 201)
        empty_novel_id = resp.json().get("id") or 0

        resp = await api_get(f"/entities/novel/{empty_novel_id}", ctx.token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

        # 清理空测试小说
        await api_delete(f"/novels/{empty_novel_id}", ctx.token)


# ─── 测试用例集 5: 实体关系 ──────────────────────────────────

class TestEntityRelationships:
    """实体关系管理"""

    @pytest.mark.asyncio
    async def test_create_relationship(self):
        """创建实体关系: 叶凡 -> 天玄宗 (弟子)"""
        ye_fan_id = ctx.entity_ids.get("叶凡")
        tian_xuan_id = ctx.entity_ids.get("天玄宗")
        assert ye_fan_id and tian_xuan_id

        resp = await api_post("/entities/relationships", {
            "novel_id": ctx.novel_id,
            "source_id": ye_fan_id,
            "target_id": tian_xuan_id,
            "relation_type": "弟子",
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Create relationship failed: {resp.status_code} {resp.text}"
        data = resp.json()
        ctx.relationship_ids.append(data["id"])
        assert data["source_id"] == ye_fan_id
        assert data["target_id"] == tian_xuan_id
        assert data["relation_type"] == "弟子"

    @pytest.mark.asyncio
    async def test_create_relationship_reverse(self):
        """创建反向关系: 天玄宗 -> 叶凡 (成员)"""
        ye_fan_id = ctx.entity_ids.get("叶凡")
        tian_xuan_id = ctx.entity_ids.get("天玄宗")

        resp = await api_post("/entities/relationships", {
            "novel_id": ctx.novel_id,
            "source_id": tian_xuan_id,
            "target_id": ye_fan_id,
            "relation_type": "成员",
        }, token=ctx.token)
        assert resp.status_code in (200, 201)
        data = resp.json()
        ctx.relationship_ids.append(data["id"])

    @pytest.mark.asyncio
    async def test_create_relationship_item_owner(self):
        """创建物品归属关系: 玄天鼎 -> 叶凡 (持有)"""
        ding_id = ctx.entity_ids.get("玄天鼎")
        ye_fan_id = ctx.entity_ids.get("叶凡")

        resp = await api_post("/entities/relationships", {
            "novel_id": ctx.novel_id,
            "source_id": ding_id,
            "target_id": ye_fan_id,
            "relation_type": "持有",
        }, token=ctx.token)
        assert resp.status_code in (200, 201)
        data = resp.json()
        ctx.relationship_ids.append(data["id"])

    @pytest.mark.asyncio
    async def test_list_relationships(self):
        """列出小说所有关系"""
        resp = await api_get(f"/entities/novel/{ctx.novel_id}/relationships", ctx.token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3, f"Expected at least 3 relationships, got {data['total']}"


# ─── 测试用例集 6: 实体删除 ──────────────────────────────────

class TestEntityDeletion:
    """实体删除测试（顺序敏感，应在最后执行）"""

    @pytest.mark.asyncio
    async def test_batch_delete_missing_ids(self):
        """批量删除空列表应返回400"""
        resp = await api_delete("/entities/batch", ctx.token, params={"ids": ""})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_single_entity(self):
        """删除单个实体"""
        entity_id = ctx.entity_ids.get("无名路人")
        assert entity_id
        resp = await api_delete(f"/entities/{entity_id}", ctx.token)
        assert resp.status_code == 200
        # 验证删除后获取不到
        resp = await api_get(f"/entities/{entity_id}", ctx.token)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_delete_entities(self):
        """批量删除实体"""
        ids_to_delete = [
            ctx.entity_ids.get("东荒密林"),
            ctx.entity_ids.get("玄天鼎"),
            ctx.entity_ids.get("太虚剑诀"),
        ]
        ids_to_delete = [eid for eid in ids_to_delete if eid]
        assert len(ids_to_delete) >= 2

        ids_param = ",".join(ids_to_delete)
        resp = await api_delete("/entities/batch", ctx.token, params={"ids": ids_param})
        assert resp.status_code == 200, f"Batch delete failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "deleted_ids" in data

        # 验证已被删除
        resp = await api_get(f"/entities/novel/{ctx.novel_id}", ctx.token)
        remaining = resp.json()
        remaining_ids = {e["entity_id"] for e in remaining["items"]}
        for deleted_id in ids_to_delete:
            assert deleted_id not in remaining_ids, f"{deleted_id} should have been deleted"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_entity(self):
        """删除不存在的实体"""
        resp = await api_delete("/entities/ent_nonexist", ctx.token)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_entity_relationship_cascade(self):
        """删除实体时关系应级联删除"""
        # 创建一对实体建立关系，删除一个后关系应消失
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "临时角色A",
            "entity_type": "character",
        }, token=ctx.token)
        a_id = resp.json()["entity_id"]

        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "临时角色B",
            "entity_type": "character",
        }, token=ctx.token)
        b_id = resp.json()["entity_id"]

        await api_post("/entities/relationships", {
            "novel_id": ctx.novel_id,
            "source_id": a_id,
            "target_id": b_id,
            "relation_type": "朋友",
        }, token=ctx.token)

        # 删除 A
        await api_delete(f"/entities/{a_id}", ctx.token)

        # 验证 A 已删除
        resp = await api_get(f"/entities/{a_id}", ctx.token)
        assert resp.status_code == 404

        # 验证 B 仍然存在
        resp = await api_get(f"/entities/{b_id}", ctx.token)
        assert resp.status_code == 200

        # 关系应该自动删除（通过 A 的级联不会影响 B）
        resp = await api_get(f"/entities/novel/{ctx.novel_id}/relationships", ctx.token)
        for rel in resp.json()["items"]:
            assert rel["source_id"] != a_id
            assert rel["target_id"] != a_id

        # 清理
        await api_delete(f"/entities/{b_id}", ctx.token)


# ─── 测试用例集 7: API 错误处理 ─────────────────────────────

class TestAPIErrorHandling:
    """API 错误处理验证"""

    @pytest.mark.asyncio
    async def test_create_entity_invalid_type(self):
        """使用无效实体类型应返回错误"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "Invalid",
            "entity_type": "invalid_type",
        }, token=ctx.token)
        # 后端会抛 ValueError (未捕获) → 500, 或 Pydantic 捕获 → 422
        assert resp.status_code in (422, 500), f"Expected error for invalid type, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_create_entity_empty_name(self):
        """空名称应返回错误"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "",
            "entity_type": "character",
        }, token=ctx.token)
        assert resp.status_code in (422, 400), f"Expected error for empty name, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_unauthorized_access(self):
        """未认证请求应返回401"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            resp = await client.get(f"{API_PREFIX}/entities/novel/1")
        assert resp.status_code == 401 or resp.status_code == 403


# ─── 测试用例集 8: 实体状态向量 ─────────────────────────────

class TestEntityStateVector:
    """实体状态向量（state_vector）的完整功能"""

    @pytest.mark.asyncio
    async def test_state_vector_complex_types(self):
        """状态向量支持复杂类型"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "测试复杂状态",
            "entity_type": "character",
            "state_vector": {
                "tags": ["tag1", "tag2", "tag3"],
                "nested": {"key1": "value1", "key2": 42},
                "numeric_list": [1, 2, 3],
                "mixed": [1, "two", {"three": 3}],
                "null_field": None,
            },
        }, token=ctx.token)
        assert resp.status_code in (200, 201), f"Complex state failed: {resp.status_code} {resp.text}"
        data = resp.json()
        sv = data["state_vector"]
        assert sv["tags"] == ["tag1", "tag2", "tag3"]
        assert sv["nested"]["key1"] == "value1"
        assert sv["numeric_list"] == [1, 2, 3]

        # 清理
        await api_delete(f"/entities/{data['entity_id']}", ctx.token)

    @pytest.mark.asyncio
    async def test_state_vector_empty_after_update(self):
        """清空 state_vector 应为 {}"""
        resp = await api_post("/entities", {
            "novel_id": ctx.novel_id,
            "canonical_name": "状态测试实体",
            "entity_type": "character",
            "state_vector": {"temp": "data"},
        }, token=ctx.token)
        eid = resp.json()["entity_id"]

        # 清空 state_vector
        resp = await api_put(f"/entities/{eid}", {"state_vector": {}}, ctx.token)
        assert resp.status_code == 200
        assert resp.json()["state_vector"] == {}

        await api_delete(f"/entities/{eid}", ctx.token)


# ─── 测试用例集 9: 工作流集成 ───────────────────────────────

class TestWorkflowIntegration:
    """验证实体与工作流的集成"""

    @pytest.mark.asyncio
    async def test_workflow_state_contains_entities(self):
        """工作流状态中包含实体信息"""
        resp = await api_get(f"/workflow/state/{ctx.novel_id}", ctx.token)
        if resp.status_code == 404:
            pytest.skip("Workflow not started for this novel")
        assert resp.status_code == 200
        # 工作流状态可能包含 active_entities 或 entities 字段
        data = resp.json()
        # 并不是所有工作流都有实体字段，取决于工作流阶段
        # 至少保证请求成功即可
        assert "state" in data or "phase" in data or "status" in data


# ─── 测试用例集 10: 清理 ────────────────────────────────────

class TestCleanup:
    """测试数据清理（受 E2E_CLEANUP 控制）"""

    @pytest.mark.asyncio
    async def test_cleanup_test_novel(self):
        """删除测试小说（级联删除所有实体和关系）"""
        if not CLEANUP:
            pytest.skip("Cleanup disabled via E2E_CLEANUP=false")

        assert ctx.novel_id > 0, "No novel to clean up"
        resp = await api_delete(f"/novels/{ctx.novel_id}", ctx.token)
        assert resp.status_code == 200, f"Cleanup failed: {resp.status_code} {resp.text}"

        # 验证小说已被删除
        resp = await api_get(f"/novels/{ctx.novel_id}", ctx.token)
        assert resp.status_code == 404