"""
按系统全流程小说生成驱动脚本
用法:
  python scripts/run_novel_pipeline.py design --title "修真大佬重返都市" --genre "都市修真" --idea "<初始创意>"
  python scripts/run_novel_pipeline.py chapters --novel <id> --from 1 --count 5
  python scripts/run_novel_pipeline.py full --title "..." --genre "..." --idea "..." --until 100 [--watch] [--webhook URL]
  python scripts/run_novel_pipeline.py status --novel <id>

full: 设计阶段 → 批量写章节 一键贯通；已存在小说时自动续写未写章节。
      --watch 失败自动重试直到写满；--webhook URL 完成后 POST 通知。

批量管线（full / chapters）为 Pro 功能（M2 额度墙）：默认账号 e2e_test_user 需为 pro；
--user <username> [--password <pw>] 指定其他用户（BYOK：后端按该用户的 Key 计费）。
"""
import sys
import os
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8080/api/v1"
USER = "e2e_test_user"
PASSWORD = "Test123"

PHASES = ["demand_analysis", "world_building", "character_design",
          "plot_design", "outline_draft", "outline_detail"]


def api(method, path, payload=None, token=None, timeout=3700):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def login():
    return api("POST", "/auth/login", {"username": USER, "password": PASSWORD})["access_token"]


def parse_user_override():
    """解析 --user [--password] 参数覆盖默认账号（批量管线 Pro 门槛依赖账号 tier）。"""
    global USER, PASSWORD
    sargs = sys.argv
    if "--user" in sargs:
        USER = sargs[sargs.index("--user") + 1]
    if "--password" in sargs:
        PASSWORD = sargs[sargs.index("--password") + 1]


def require_pro(token):
    """批量管线是 Pro 功能：free 用户或批量总开关关闭时拒绝运行。"""
    try:
        st = api("GET", "/quota/status", token=token)
    except Exception as e:
        print(f"[gate] 查询额度失败，默认放行（后端不可达? {e}）")
        return
    tier = (st or {}).get("tier", "free")
    batch_enabled = (st or {}).get("batch_enabled", True)
    if not batch_enabled:
        print("\n[gate] 批量管线总开关已关闭（PRO_BATCH_ENABLED=false），拒绝运行。")
        sys.exit(1)
    if tier != "pro":
        print(
            f"\n[gate] 批量管线是 Pro 功能，当前用户为 {tier} 层。\n"
            f"       请用 --user <pro用户> 运行，或联系管理员开通 Pro（POST /api/v1/quota/tier）。"
        )
        sys.exit(1)
    print(f"[gate] 用户 tier={tier}，批量管线放行。")


def _extract_status(prog):
    """任务进度可能把总体状态放在 steps.<step_id>.status 里，统一提取。"""
    if not isinstance(prog, dict):
        return None
    steps = prog.get("steps")
    if isinstance(steps, dict):
        first = next(iter(steps.values()), None)
        if isinstance(first, dict) and first.get("status"):
            return first.get("status")
    return prog.get("status") or prog.get("state")


def poll_task(token, task_id, wait=8, max_wait=40 * 60):
    waited = 0
    while waited < max_wait:
        try:
            prog = api("GET", f"/workflow/task-progress/{task_id}", token=token)
        except Exception:
            prog = {}
        status = _extract_status(prog) or "running"
        print(f"    [poll] {waited // 60}m{waited % 60:02d}s status={status}")
        if status in ("completed", "success", "done", "failed", "error"):
            return prog
        if isinstance(prog, dict):
            if prog.get("error") or prog.get("fail_reason"):
                print("    [poll] error:", prog.get("error") or prog.get("fail_reason"))
                return prog
        time.sleep(wait)
        waited += wait
    return {"status": "timeout"}


def run_phase(token, novel_id, phase, input_data=None, attempts=10):
    for attempt in range(1, attempts + 1):
        print(f"\n=== [phase] {phase} (尝试 {attempt}/{attempts}) ===")
        payload = {"phase": phase, "timeout": 3600}
        if input_data:
            payload["input_data"] = input_data
        try:
            resp = api("POST", f"/workflow/phase/{novel_id}", payload, token=token)
        except Exception as e:
            print(f"    启动失败: {e}")
            resp = {}
        task_id = (resp or {}).get("task_id")
        if not task_id:
            print("    启动失败:", str(resp)[:300])
            time.sleep(15)
            continue
        prog = poll_task(token, task_id, wait=10, max_wait=65 * 60)
        status = _extract_status(prog) or "running"
        ok = status in ("completed", "success", "done")
        print(f"    => {phase}: {status}")
        # 读取阶段结果
        try:
            result = api("GET", f"/workflow/phase-result/{novel_id}/{phase}", token=token)
            _summarize_phase(phase, result)
            with open(f"logs/phase_{phase}.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"    (phase-result 读取失败: {e})")
        if ok:
            return True
        # 失败后等待流量缓解再重试
        delay = [0, 20, 40, 60, 120, 180, 300, 300, 300, 300][min(attempt, 10) - 1]
        if attempt < attempts:
            print(f"    等待 {delay}s 后重试...")
            time.sleep(delay)
    return False


def _summarize_phase(phase, result):
    def s(value, n=400):
        if value is None:
            return ""
        if isinstance(value, str):
            return str(value)[:n]
        return json.dumps(value, ensure_ascii=False)[:n]

    if isinstance(result, dict):
        data = result.get("data", result)
        print(f"    [result] keys={list(result.keys())[:10]}")
        if phase == "world_building" and isinstance(data, dict):
            print("      地域/地图:", s(data.get("geography", data.get("regions", ""))))
            print("      力量体系:", s(data.get("power_systems", data.get("power_system", ""))))
        elif phase == "character_design":
            chars = data if isinstance(data, list) else data.get("characters", data.get("list", [])) if isinstance(data, dict) else []
            if isinstance(chars, list):
                print(f"      角色数: {len(chars)}")
                for c in chars[:6]:
                    if isinstance(c, dict):
                        print("        -", c.get("name"), c.get("role_type", c.get("role", "")))
                    else:
                        print("        -", c)
            else:
                print("      ", s(data))
        elif phase == "outline_draft":
            print("      ", s(data))
        else:
            print("      ", s(data))
    else:
        print("    [result] ", s(result))


def write_chapter(token, novel_id, chapter_number, poll_max=1500, attempts=10):
    for attempt in range(1, attempts + 1):
        print(f"\n=== [chapter {chapter_number}] (尝试 {attempt}/{attempts}) ===")
        payload = {
            "chapter_number": chapter_number,
            "auto_mode": False,
            "timeout": 3600,
            "writing_style": "番茄小说文风：全大白话、短句、快节奏；每章都要有装逼打脸/人前显圣的爽点；开头第一句进冲突，结尾留钩子；禁止堆砌环境描写与修饰词",
            "env_description_level": "minimal",
            "dialogue_ratio": 0.5,
        }
        try:
            resp = api("POST", f"/workflow/chapter/{novel_id}", payload, token=token)
        except Exception as e:
            print("    write 请求失败:", e)
            resp = {}
        task_id = (resp or {}).get("task_id")
        if not task_id:
            print("    write reply:", json.dumps(resp, ensure_ascii=False)[:400])
            time.sleep(15)
            continue
        # 章节写完后 tracker 状态可能不翻转，改为「任务态 + 章节是否已入库」双判定
        status, ch = await_chapter(token, novel_id, chapter_number, task_id, poll_max)
        ok = status in ("completed", "success", "done") or ch is not None
        print(f"    => ch{chapter_number}: status={status} 入库={bool(ch)}")
        if ok and ch is not None:
            content = ch.get("content", "")
            print(f"    ch{chapter_number} title={ch.get('title')} 字数≈{len(content)}")
            with open(f"logs/ch{chapter_number:03d}.txt", "w", encoding="utf-8") as f:
                f.write(f"# {ch.get('title')}\n\n{content}")
            return True
        if ok and ch is None:
            ok = False
        delay = [0, 20, 40, 60, 120, 180, 300, 300, 300, 300][min(attempt, 10) - 1]
        if attempt < attempts:
            print(f"    等待 {delay}s 后重试...")
            time.sleep(delay)
    return False


def await_chapter(token, novel_id, chapter_number, task_id, max_wait):
    """轮询任务直到完成或章节入库；返回 (status, chapter_dict_or_None)"""
    waited = 0
    wait = 12
    status = "running"
    while waited < max_wait:
        try:
            prog = api("GET", f"/workflow/task-progress/{task_id}", token=token)
        except Exception:
            prog = {}
        status = _extract_status(prog) or "running"
        # 章节入库即视为完成
        try:
            ch = api("GET", f"/chapters/novel/{novel_id}/chapter/{chapter_number}", token=token)
            if ch and (ch.get("content") or ch.get("chapter_number")):
                return ("completed", ch)
        except Exception:
            pass
        if status in ("failed", "error"):
            return (status, None)
        time.sleep(wait)
        waited += wait
    return ("timeout", None)


def cmd_design(argv):
    sargs = sys.argv
    # 支持 --novel <id> --from-phase <phase> 续跑
    novel_id = None
    start_phase = 0
    if "--novel" in sargs:
        novel_id = int(sargs[sargs.index("--novel") + 1])
    if "--from-phase" in sargs:
        ph = sargs[sargs.index("--from-phase") + 1]
        if ph in PHASES:
            start_phase = PHASES.index(ph)
    token = login()
    if novel_id is None:
        title = "修真大佬重返都市"
        genre = "都市修真"
        idea = (
            "主角是重生回到高考后的都市废柴高中生，前世在修真界修行数百年成为返虚境霸主，"
            "师门被灭后孤苦伶仃。他带着连通两界的空间项链回到现实，修为尽失但悟性与眼光仍在，"
            "并无瓶颈只需积累灵力。现实世界存在武道与仙道传承，灵气逐渐复苏，元婴为现实天花板。"
            "他目标是陪伴家人妹妹，找到回修真界的路，并通过与异界落魄少年的师徒契约拯救当年师门。"
            "主角是社恐高冷型，心机深沉，不想惹麻烦却麻烦不断；围绕青梅竹马、校花学妹、宗族圣女、"
            "富二代世交等关系展开打脸爽点。世界势力复杂且有底线，不是无脑反派。"
        )
        print("创建小说:", title)
        info = api("POST", "/workflow/start",
                   {"title": title, "preferred_genre": genre, "initial_idea": idea}, token=token)
        novel_id = info.get("novel_id")
        print("novel_id:", novel_id)
        assert novel_id, json.dumps(info, ensure_ascii=False)[:300]
        with open("logs/novel_meta.json", "w", encoding="utf-8") as f:
            json.dump({"novel_id": novel_id, "title": title}, f, ensure_ascii=False, indent=2)
    else:
        with open("logs/novel_meta.json", "w", encoding="utf-8") as f:
            json.dump({"novel_id": novel_id, "title": "修真大佬重返都市(续)"}, f, ensure_ascii=False, indent=2)
    for phase in PHASES[start_phase:]:
        ok = run_phase(token, novel_id, phase)
        if not ok:
            print(f"   [中断] 阶段 {phase} 未成功，停止后续阶段")
            break
    print("\n设计阶段完成。novel_id=", novel_id)


def cmd_chapters(argv):
    token = login()
    require_pro(token)  # 批量管线为 Pro 功能
    meta = json.load(open("logs/novel_meta.json", encoding="utf-8")) if __import__("os").path.exists("logs/novel_meta.json") else {}
    novel_id = meta.get("novel_id")
    # parse
    sargs = sys.argv
    novel_id = novel_id or int(sargs[sargs.index("chapters") + 1])
    start_n = 1
    count = 5
    until = None
    if "--from" in sargs:
        start_n = int(sargs[sargs.index("--from") + 1])
    if "--count" in sargs:
        count = int(sargs[sargs.index("--count") + 1])
    if "--until" in sargs:
        until = int(sargs[sargs.index("--until") + 1])
    end = until if until is not None else start_n + count - 1
    failed = 0
    for n in range(start_n, end + 1):
        ok = write_chapter(token, novel_id, n)
        if ok:
            failed = 0
        else:
            failed += 1
            print(f"   [失败记录] 第{n}章失败，已连续失败 {failed} 次")
            time.sleep(90)
        # 每 5 章输出一次进度
        if n % 5 == 0 or n == end:
            done = n - start_n + 1
            print(f"   >>> 进度: {done}/{end - start_n + 1} 章（累计失败 {failed}）")
        # 若连续失败 3 次，等待 10 分钟缓解网关压力后再继续
        if failed >= 3:
            print("   连续失败过多，休息 120s 缓解网关压力...")
            time.sleep(600)
            failed = 0
    print(f"\n章节批量完成：共尝试 {end - start_n + 1} 章")


def cmd_status(argv):
    token = login()
    meta = json.load(open("logs/novel_meta.json", encoding="utf-8"))
    novel_id = meta["novel_id"]
    prog = api("GET", f"/workflow/progress/{novel_id}", token=token)
    print(json.dumps(prog, ensure_ascii=False, indent=2))


def _notify(webhook, payload):
    if not webhook:
        return
    try:
        req = urllib.request.Request(webhook, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, json.dumps(payload, ensure_ascii=False).encode("utf-8"), timeout=15) as r:
            print("   [通知] webhook:", r.status)
    except Exception as e:
        print(f"   [通知] webhook 发送失败: {e}")


def cmd_full(argv):
    """设计阶段 → 批量写章节 一键贯通（P2 pipeline 原生化）。

    已存在小说（--novel 或 logs/novel_meta.json）时自动续写未写章节；
    --watch 失败自动重试直到写满；--webhook URL 完成后 POST 通知。
    """
    sargs = sys.argv
    novel_id = None
    from_n = None
    until = None
    count = 5
    watch = "--watch" in sargs
    webhook = None
    if "--webhook" in sargs:
        webhook = sargs[sargs.index("--webhook") + 1]
    if "--novel" in sargs:
        novel_id = int(sargs[sargs.index("--novel") + 1])
    if "--from" in sargs:
        from_n = int(sargs[sargs.index("--from") + 1])
    if "--until" in sargs:
        until = int(sargs[sargs.index("--until") + 1])
    if "--count" in sargs:
        count = int(sargs[sargs.index("--count") + 1])

    token = login()
    require_pro(token)  # 批量管线为 Pro 功能

    # 1. 确定 novel_id（已有小说则续跑，否则先跑设计阶段）
    if novel_id is None and os.path.exists("logs/novel_meta.json"):
        meta = json.load(open("logs/novel_meta.json", encoding="utf-8"))
        novel_id = meta.get("novel_id")
    if novel_id is None:
        print("\n>>> 无已有小说，先执行设计阶段（6 阶段）")
        cmd_design(sargs)
        meta = json.load(open("logs/novel_meta.json", encoding="utf-8"))
        novel_id = meta["novel_id"]
    else:
        os.makedirs("logs", exist_ok=True)
        with open("logs/novel_meta.json", "w", encoding="utf-8") as f:
            json.dump({"novel_id": novel_id, "title": "续跑"}, f, ensure_ascii=False, indent=2)
    print(f">>> novel_id = {novel_id}")

    # 2. 确定起始章节（未指定则从已写章节的下一个续写）
    if from_n is None:
        try:
            chapters = api("GET", f"/chapters/novel/{novel_id}", token=token)
            items = chapters.get("items", []) if isinstance(chapters, dict) else []
            nums = [int(c.get("chapter_number", 0)) for c in items if isinstance(c, dict)]
            from_n = (max(nums) + 1) if nums else 1
            print(f">>> 已写 {len(nums)} 章，从第 {from_n} 章续写")
        except Exception as e:
            print(f"    (查询已写章节失败，从第 1 章开始: {e})")
            from_n = 1
    end = until if until is not None else from_n + count - 1
    print(f">>> 目标：第 {from_n} ~ {end} 章，watch={watch}")

    # 3. 批量写章节（失败重试；watch 模式持续到写满）
    n = from_n
    failed = 0
    written = 0
    while n <= end:
        ok = write_chapter(token, novel_id, n)
        if ok:
            failed = 0
            written += 1
            n += 1
            if n % 5 == 0 or n > end:
                print(f"   >>> 进度: 已完成 {n - from_n}/{end - from_n + 1} 章")
        else:
            failed += 1
            print(f"   [失败] 第{n}章，连续失败 {failed} 次")
            if failed >= 3:
                print("   连续失败过多，休息 120s 缓解网关压力...")
                time.sleep(600)
                failed = 0
            if not watch and failed >= 2:
                print("   （非 watch 模式，暂停。可加 --watch 自动续跑）")
                break
            time.sleep(90)

    summary = {
        "novel_id": novel_id,
        "requested": (from_n, end),
        "written": written,
        "status": "completed" if n > end else "paused",
    }
    print("\n>>> 完成摘要:", json.dumps(summary, ensure_ascii=False, indent=2))
    _notify(webhook, summary)


if __name__ == "__main__":
    parse_user_override()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "design"
    if cmd == "design":
        cmd_design(sys.argv)
    elif cmd == "chapters":
        cmd_chapters(sys.argv)
    elif cmd == "full":
        cmd_full(sys.argv)
    elif cmd == "status":
        cmd_status(sys.argv)
    else:
        print(__doc__)