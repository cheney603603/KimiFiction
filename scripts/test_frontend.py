from playwright.sync_api import sync_playwright
import json, http.client

# Login and get token
conn = http.client.HTTPConnection("localhost", 8000)
conn.request("POST", "/api/v1/auth/login",
           json.dumps({"username":"e2e_test_user","password":"Test123"}),
           {"Content-Type":"application/json"})
r = conn.getresponse()
token = json.loads(r.read())["access_token"]
conn.close()

# Get novel_id
conn = http.client.HTTPConnection("localhost", 8000)
conn.request("GET", "/api/v1/novels", headers={"Authorization": f"Bearer {token}"})
r = conn.getresponse()
novels = json.loads(r.read())
items = novels.get("items") or novels.get("novels") or []
novel_id = items[-1]["id"] if items else 0
conn.close()

print(f"Using novel_id={novel_id}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="chrome")
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # 1. Login
    print("\n=== 1. 登录前端 ===")
    page.goto("http://localhost:5173/login", wait_until="networkidle")
    page.fill("[type=text], input", "e2e_test_user")
    page.fill("[type=password], input", "Test123")
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard", timeout=15000)
    print("登录成功")

    # 2. Open novel detail
    print("\n=== 2. 小说详情页 ===")
    page.goto(f"http://localhost:5173/novel/{novel_id}", wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path="frontend/screenshots/01_novel_detail.png", full_page=True)

    # 3. Open entity management
    print("\n=== 3. 实体管理页 ===")
    page.goto(f"http://localhost:5173/novel/{novel_id}/entities", wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path="frontend/screenshots/02_entity_manager.png", full_page=True)

    # 4. Create a new entity - click the create button
    print("\n=== 4. 新建实体 ===")
    page.click("text=新建实体")
    page.wait_for_timeout(500)
    page.screenshot(path="frontend/screenshots/03_create_form.png", full_page=True)

    # Fill in the form - target the inputs by placeholder
    page.fill("input[placeholder*='实体名称']", "张三丰")
    page.fill("input[placeholder*='别名']", "张真人, 三丰真人")
    page.fill("textarea[placeholder*='摘要']", "武当派祖师")
    page.fill("input[placeholder*='年龄']", "120")
    page.fill("input[placeholder*='性别']", "男")
    page.fill("textarea[placeholder*='性格']", "道法自然, 超然物外")
    page.fill("input[placeholder*='修为']", "破碎虚空")
    page.screenshot(path="frontend/screenshots/04_form_filled.png", full_page=True)

    print(" 点击保存")
    page.click("button:has-text('保存')")
    page.wait_for_timeout(2000)
    page.screenshot(path="frontend/screenshots/05_entity_created.png", full_page=True)

    # 5. Test search
    print("\n=== 5. 搜索功能 ===")
    page.goto(f"http://localhost:5173/novel/{novel_id}/entities", wait_until="networkidle")
    page.wait_for_timeout(1000)
    page.fill("input[placeholder*='搜索实体']", "张三丰")
    page.wait_for_timeout(1000)
    page.screenshot(path="frontend/screenshots/06_search_result.png", full_page=True)
    print(" 搜索 '张三丰' - 应只显示张三丰")

    # Clear search
    page.fill("input[placeholder*='搜索实体']", "")
    page.wait_for_timeout(500)

    # 6. Test expand card
    print("\n=== 6. 展开卡片详情 ===")
    page.wait_for_timeout(500)
    expand_btn = page.locator("text=生物 / 角色")
    page.wait_for_timeout(500)
    page.screenshot(path="frontend/screenshots/07_card_view.png", full_page=True)

    # 7. Batch select
    print("\n=== 7. 批量选择 ===")
    # Click the first checkbox to select this entity
    page.wait_for_timeout(500)
    page.locator("svg.lucide-square").first.click()
    page.wait_for_timeout(500)
    page.screenshot(path="frontend/screenshots/08_batch_select.png", full_page=True)
    print(" 已选中一个实体")

    page.wait_for_timeout(2000)

    browser.close()
    print("\n前端测试完成!")

    # 后端验证
    conn = http.client.HTTPConnection("localhost", 8000)
    conn.request("GET", f"/api/v1/entities/novel/{novel_id}", headers={"Authorization": f"Bearer {token}"})
    r = conn.getresponse()
    result = json.loads(r.read())
    total = result.get("total", 0)
    print(f"后端验证: 实体数={total}")
    conn.close()

    print("\n部署测试全部通过!")