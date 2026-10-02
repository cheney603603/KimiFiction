"""
为指定小说灌入演示世界观数据（角色/势力/地点/物品/技能/关系/记忆）
用于在浏览器里可视化实体图谱、小说地图、知识库。
用法: python scripts/seed_demo_world.py <novel_id> [username] [password]
"""
import sys
import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"

def api(method, path, payload=None, token=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(req, data) as r:
        return json.loads(r.read().decode())

def main():
    novel_id = int(sys.argv[1])
    username = sys.argv[2] if len(sys.argv) > 2 else "e2e_test_user"
    password = sys.argv[3] if len(sys.argv) > 3 else "Test123"

    token = api("POST", "/auth/login", {"username": username, "password": password})["access_token"]

    def create_entity(name, etype, state=None, summary=None, aliases=None):
        return api("POST", "/entities", {
            "novel_id": novel_id, "canonical_name": name, "entity_type": etype,
            "aliases": aliases or [], "state_vector": state or {}, "narrative_summary": summary,
        }, token)

    def create_character(name, role_type, profile):
        return api("POST", "/characters", {"novel_id": novel_id, "name": name, "role_type": role_type, "profile": profile}, token)

    def create_rel(a, b, rel):
        api("POST", "/entities/relationships", {"novel_id": novel_id, "source_id": a, "target_id": b, "relation_type": rel}, token)

    # 角色
    lin_xiao = create_character("林晓", "protagonist", {
        "age": 22, "gender": "男", "personality": "冷静坚韧，重情重义",
        "background": "青云宗外门弟子，因家族被灭而踏上复仇之路。", "goals": ["查明真相", "振兴家族"],
        "skills": ["御剑术"], "fears": ["再次失去重要之人"], "relationships": {"苏晴": "青梅竹马", "青云宗": "门下弟子"},
    })
    su_qing = create_character("苏晴", "supporting", {
        "age": 20, "gender": "女", "personality": "温柔善良，医术精湛",
        "background": "灵药谷弟子，与林晓从小相识。", "skills": ["炼丹术"], "relationships": {"林晓": "青梅竹马"},
    })
    create_character("慕容战", "antagonist", {
        "age": 45, "gender": "男", "personality": "野心勃勃，心狠手辣",
        "background": "血煞盟盟主，林家灭门案的幕后黑手。", "relationships": {"林晓": "仇敌"},
    })

    # 势力
    qingyun = create_entity("青云宗", "faction", {
        "leader": "青玄真人", "members": ["林晓", "青玄真人"], "territory": "青云山, 青云剑冢",
        "ideology": "以剑证道，守护人间正道", "enemies": ["血煞盟"], "allies": ["灵药谷"],
    }, "正道剑修大宗，底蕴深厚。")
    lingyao = create_entity("灵药谷", "faction", {
        "leader": "药老", "members": ["苏晴"], "territory": "灵药谷", "allies": ["青云宗"],
    }, "以医入道的药修圣地。")
    xuesha = create_entity("血煞盟", "faction", {
        "leader": "慕容战", "territory": "血煞峰", "enemies": ["青云宗"],
    }, "魔道势力，手段残忍。")

    # 地点
    dict1 = create_entity("青云山", "location", {
        "type": "山脉", "terrain": "崇山峻岭，灵气充沛", "atmosphere": "仙气缥缈",
        "significance": "青云宗主峰，宗门核心所在", "connected_locations": "青云剑冢, 灵药谷", "inhabitants": "青云宗弟子",
    }, "青云宗宗门所在。")
    dict2 = create_entity("青云剑冢", "location", {
        "type": "秘境", "terrain": "万剑插地", "significance": "历代剑修的传承之地", "connected_locations": "青云山",
    }, "林晓在此获得机缘。")
    dict3 = create_entity("血煞峰", "location", {
        "type": "山峰", "atmosphere": "阴风阵阵", "significance": "血煞盟总部", "connected_locations": "青云山",
    }, "魔道总部。")

    # 物品与技能
    create_entity("玄天剑", "item", {"type": "神兵", "owner": "林晓", "power_level": "地级", "origin": "青云剑冢"}, "上古神兵，威力无穷。")
    create_entity("驻颜丹", "item", {"type": "丹药", "owner": "苏晴", "function": "永葆青春"}, "灵药谷炼制的珍稀丹药。")
    create_entity("御剑术", "skill", {"type": "剑法", "level": "玄阶", "attributes": "速度", "origin": "青云宗"}, "青云宗入门剑法。")
    create_entity("炼丹术", "skill", {"type": "丹道", "level": "地阶", "origin": "灵药谷"}, "灵药谷传承丹术。")

    # 关系：势力↔势力、角色归属、总部控制
    create_rel(qingyun["entity_id"], lingyao["entity_id"], "盟友")
    create_rel(qingyun["entity_id"], xuesha["entity_id"], "敌对")
    create_rel(qingyun["entity_id"], dict1["entity_id"], "驻地")
    create_rel(xuesha["entity_id"], dict3["entity_id"], "驻地")
    create_rel(lingyao["entity_id"], dict2["entity_id"], "管辖")

    # 记忆节点（后端记忆创建接口存在序列化缺陷，失败不影响演示数据）
    try:
        api("POST", "/memory/nodes", {
            "novel_id": novel_id, "node_type": "plot_point", "title": "青云剑冢机缘",
            "content": "林晓在青云剑冢获得玄天剑认可，实力大增。",
            "chapter_range": "3-6",
            "related_characters": ["林晓"], "related_locations": ["青云剑冢"],
        }, token)
        api("POST", "/memory/nodes", {
            "novel_id": novel_id, "node_type": "mystery", "title": "林家灭门真相",
            "content": "林家灭门与血煞盟有关，慕容战疑似幕后主使。",
            "chapter_range": "1-30",
            "related_characters": ["林晓", "慕容战"], "related_locations": ["青云山"],
        }, token)
        print("   记忆 ×2")
    except Exception as exc:
        print(f"   [!] 记忆节点创建失败（后端已知问题）：{exc}")

    print(f"[OK] 已为小说 {novel_id} 灌入演示世界观数据")
    print(f"     角色 x3 / 势力 x3 / 地点 x3 / 物品 x2 / 技能 x2 / 关系 x5")

if __name__ == "__main__":
    main()