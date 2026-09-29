"""截图验证新页面（概览/图谱/地图/知识库）"""
import json, http.client, time
from playwright.sync_api import sync_playwright

OUT = "E:/tmp-cc/share" if False else "logs/screens"
import os
os.makedirs(OUT, exist_ok=True)

# login
conn = http.client.HTTPConnection("localhost", 8000)
conn.request("POST", "/api/v1/auth/login",
             json.dumps({"username": "e2e_test_user", "password": "Test123"}),
             {"Content-Type": "application/json"})
token = json.loads(conn.getresponse().read())["access_token"]
conn.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.add_init_script(f"localStorage.setItem('access_token', '{token}'); localStorage.setItem('user', JSON.stringify({{'username':'e2e_test_user','nickname':'E2E测试'}}));")

    def shot(name, wait=2500):
        page.wait_for_timeout(wait)
        page.screenshot(path=f"{OUT}/{name}.png", full_page=False)
        print("saved", name)

    page.goto("http://localhost:5173/novel/1002")
    shot("1-overview", 2500)

    page.goto("http://localhost:5173/novel/1002/graph")
    shot("2-graph", 3200)
    # 点击第一个节点 → 详情面板
    nodes = page.locator(".react-flow__node")
    if nodes.count() > 0:
        nodes.first.click()
        shot("3-graph-selected", 800)
    # 悬停高亮
    if nodes.count() > 0:
        nodes.nth(min(2, nodes.count() - 1)).hover()
        shot("4-graph-hover", 800)

    page.goto("http://localhost:5173/novel/1002/map")
    shot("5-map", 3200)
    if page.locator(".react-flow__node").count() > 0:
        page.locator(".react-flow__node").first.click()
        shot("6-map-selected", 800)

    page.goto("http://localhost:5173/novel/1002/knowledge")
    shot("7-knowledge", 2500)
    # 点选一条
    rows = page.locator("button", has_text="青云山")
    if rows.count() > 0:
        rows.first.click()
        shot("8-knowledge-selected", 800)

    # 深色模式验证
    page.evaluate("document.documentElement.classList.add('dark')")
    page.goto("http://localhost:5173/novel/1002/graph")
    shot("9-graph-dark", 3200)
    page.goto("http://localhost:5173/novel/1002/knowledge")
    shot("10-knowledge-dark", 2500)

    browser.close()
print("DONE", OUT, os.listdir(OUT))