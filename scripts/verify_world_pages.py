"""DOM 层功能验证：统计节点数、详情面板、控制台报错"""
import json, http.client
from playwright.sync_api import sync_playwright

conn = http.client.HTTPConnection("localhost", 8000)
conn.request("POST", "/api/v1/auth/login",
             json.dumps({"username": "e2e_test_user", "password": "Test123"}),
             {"Content-Type": "application/json"})
token = json.loads(conn.getresponse().read())["access_token"]
conn.close()

checks = []
def check(name, ok, extra=""):
    checks.append((name, ok, extra))
    print(("PASS" if ok else "FAIL"), name, extra)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.add_init_script("localStorage.setItem('access_token', '" + token + "'); localStorage.setItem('user', JSON.stringify({username:'e2e_test_user'}));")
    errors = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)

    # 概览
    page.goto("http://localhost:5173/novel/1002")
    page.wait_for_timeout(3000)
    check("概览标题", page.locator("h1", has_text="玄幻长夜夺权").count() > 0)
    check("概览统计块", page.locator("a", has_text="势力").count() > 0 and page.locator("a", has_text="地点").count() > 0)
    check("tab栏存在", page.locator("text=实体图谱").count() > 0 and page.locator("text=小说地图").count() > 0 and page.locator("text=知识库").count() > 0)

    # 图谱
    page.goto("http://localhost:5173/novel/1002/graph")
    page.wait_for_timeout(3500)
    n_nodes = page.locator(".react-flow__node").count()
    check("图谱节点数", n_nodes >= 10, f"nodes={n_nodes}")
    check("图谱搜索框", page.locator("input[placeholder*='搜索名称']").count() > 0)
    if n_nodes > 0:
        page.locator(".react-flow__node").first.click()
        page.wait_for_timeout(600)
        check("图谱详情面板", page.locator("text=关联").count() > 0)
    # 搜索过滤
    page.fill("input[placeholder*='搜索名称']", "青云")
    page.wait_for_timeout(800)
    n2 = page.locator(".react-flow__node").count()
    check("图谱搜索过滤", 0 < n2 < n_nodes, f"{n2}<{n_nodes}")

    # 地图
    page.goto("http://localhost:5173/novel/1002/map")
    page.wait_for_timeout(3500)
    n_loc = page.locator(".react-flow__node").count()
    check("地图节点数", n_loc >= 6, f"nodes={n_loc}")
    check("势力图例", page.locator("text=势力版图").count() > 0)
    if n_loc > 0:
        page.locator(".react-flow__node").first.click()
        page.wait_for_timeout(600)
        check("地图详情面板", page.locator("text=关联").count() > 0)

    # 知识库
    page.goto("http://localhost:5173/novel/1002/knowledge")
    page.wait_for_timeout(2500)
    check("知识库标题", page.locator("text=世界观知识库").count() > 0)
    kb_rows = page.locator("text=青云宗").count() + page.locator("text=林晓").count()
    check("知识库列表出现角色/势力", kb_rows > 0, f"rows={kb_rows}")
    # 点选一行 → 详情
    row = page.locator("button", has_text="青云宗").first
    if row.count() > 0:
        row.click()
        page.wait_for_timeout(600)
        check("知识库详情", page.locator("text=青云宗").count() > 1)

    # 深色模式
    page.evaluate("document.documentElement.classList.add('dark')")
    page.goto("http://localhost:5173/novel/1002/graph")
    page.wait_for_timeout(3000)
    check("深色图谱节点数", page.locator(".react-flow__node").count() >= 10)

    check("无控制台报错", len(errors) == 0, f"errors={errors[:4]}")
    browser.close()

fails = [c for c in checks if not c[1]]
print("\n===== SUMMARY =====")
print(f"total={len(checks)} pass={len(checks)-len(fails)} fail={len(fails)}")
for name, ok, extra in fails:
    print("FAIL:", name, extra)
if not fails:
    print("ALL PASS")