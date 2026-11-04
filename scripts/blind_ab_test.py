"""
盲读 A/B 验收生成脚本（docs/NOVEL_QUALITY_UPGRADE_PLAN.md §8）

用法（A/B 各用一个后端实例，实例的 WRITING_PIPELINE_V2 分别置 false/true）：
  # 终端 1：WRITING_PIPELINE_V2=false 的 8080 实例
  python scripts/blind_ab_test.py --variant A --backend http://127.0.0.1:8080 --user <你的账号> --out blind_ab
  # 终端 2：WRITING_PIPELINE_V2=true 的 8081 实例
  python scripts/blind_ab_test.py --variant B --backend http://127.0.0.1:8081 --user <你的账号> --out blind_ab

产出 blind_ab/ ：
  A_ch1.md~A_ch5.md / B_ch1.md~B_ch5.md   生成正文（同一组 5 个固定细纲）
  protocol.md                              盲读协议 + 随机编号打分表

固定 5 个细纲覆盖：冲突 / 过渡 / 情绪 / 信息 / 群像 各一（§8.1）。
可用 --novel <id> 复用已存在小说（续跑指定细纲）。
"""
import sys
import os
import json
import time
import random
import argparse
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_STYLE = (
    "番茄小说文风：全大白话、短句、快节奏；每章都要有装逼打脸/人前显圣的爽点；"
    "开头第一句进冲突，结尾留钩子；禁止堆砌环境描写与修饰词"
)

# ── 5 个固定章节细纲（§8.1 覆盖 5 类）─────────────────
FIXED_OUTLINES = [
    {  # 冲突章：正面交锋 + 身份揭穿
        "chapter_number": 1,
        "title": "城门对峙",
        "summary": "主角李云在城门口与追杀他的仇家正面相遇，双方交锋中他的隐藏身份被当众揭穿，冲突全面爆发。",
        "key_events": [
            "李云进城时被守门将领认出通缉令上的画像",
            "仇家率众合围，李云以一敌多压制全场",
            "众人逼问身份，李云自曝前世霸主的过往",
            "李云的旧部突然现身，冲突进入更高层次",
        ],
        "scenes": ["城门口盘查", "合围爆发", "身份揭穿与旧部现身"],
        "word_count_target": 3000,
    },
    {  # 过渡章：无大高潮，蓄力铺垫
        "chapter_number": 2,
        "title": "夜路",
        "summary": "风波暂平，李云带着伤连夜赶路，途中整理思绪、安排下一步，与同行者交换情报，为后续布局做铺垫。",
        "key_events": [
            "李云离开城门后独自走夜路疗伤",
            "回忆此前的线索，推断出追杀者的幕后主使",
            "与老管家会合，敲定下一步计划",
            "在驿站意外听闻关于旧部的最新消息",
        ],
        "scenes": ["疗伤与回忆", "与老管家会合", "驿站听闻消息"],
        "word_count_target": 3000,
    },
    {  # 情绪章：内心戏/回忆/情感波折
        "chapter_number": 3,
        "title": "故人",
        "summary": "李云偶遇前世故人的遗孤，尘封多年的情感被重新翻开；他在这份牵绊里动摇，也借此想清楚了自己真正要守护的东西。",
        "key_events": [
            "李云在市集偶遇故人遗孤，认出对方身上的信物",
            "独自回忆与故人并肩作战的往事",
            "决定出手护住遗孤，暴露行踪也在所不惜",
            "深夜独坐，厘清自己重生归来的真正目的",
        ],
        "scenes": ["市集偶遇", "回忆往事", "深夜自省"],
        "word_count_target": 3000,
    },
    {  # 信息章：世界观/设定交代
        "chapter_number": 4,
        "title": "势力图谱",
        "summary": "李云通过商会账簿与暗桩情报，系统梳理当前世界的势力版图与力量体系，确认了各方底牌，锁定下一步目标。",
        "key_events": [
            "从商会账簿中读到近年各势力此消彼长的线索",
            "暗桩递来关于仙道门阀与武道世家的详尽情报",
            "李云对照前世记忆，标注出几个关键人物的真实境界",
            "确认幕后主使所在的势力，定下渗透计划",
        ],
        "scenes": ["账簿推演", "暗桩情报", "定下目标"],
        "word_count_target": 3000,
    },
    {  # 群像章：多角色互动
        "chapter_number": 5,
        "title": "围炉",
        "summary": "李云召集核心同伴围炉议事，众人各抒己见、吵成一团又互相补台，在多线碰撞中定下了共同的行动方案。",
        "key_events": [
            "老管家、旧部、新收的弟子等人齐聚一堂",
            "众人对下一步行动各有主张，争执不下",
            "李云拍板折中方案，逐一分派任务",
            "散场后各自行动，为后续章节埋线",
        ],
        "scenes": ["围炉夜话", "争执与拍板", "分派任务"],
        "word_count_target": 3000,
    },
]


def api(base, method, path, payload=None, token=None, timeout=3700):
    req = urllib.request.Request(f"{base}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def extract_status(prog):
    if not isinstance(prog, dict):
        return None
    steps = prog.get("steps")
    if isinstance(steps, dict):
        first = next(iter(steps.values()), None)
        if isinstance(first, dict) and first.get("status"):
            return first.get("status")
    return prog.get("status") or prog.get("state")


def poll_chapter(base, token, novel_id, chapter_number, task_id, max_wait=60 * 60):
    """轮询直到章节入库或任务失败。"""
    waited = 0
    wait = 15
    while waited < max_wait:
        try:
            ch = api(base, "GET", f"/chapters/novel/{novel_id}/chapter/{chapter_number}", token=token)
            if ch and (ch.get("content") or ch.get("chapter_number")):
                return ch
        except Exception:
            pass
        try:
            prog = api(base, "GET", f"/workflow/task-progress/{task_id}", token=token)
        except Exception:
            prog = {}
        if extract_status(prog) in ("failed", "error"):
            return None
        time.sleep(wait)
        waited += wait
    return None


def generate_one(base, token, novel_id, outline, style, out_path):
    n = outline["chapter_number"]
    print(f"\n=== [ch{n}] {outline['title']} ===")
    payload = {
        "chapter_number": n,
        "auto_mode": False,
        "timeout": 3600,
        "writing_style": style,
        "env_description_level": "minimal",
        "dialogue_ratio": 0.5,
    }
    for attempt in range(1, 4):
        try:
            resp = api(base, "POST", f"/workflow/chapter/{novel_id}", payload, token=token)
        except Exception as e:
            print(f"    write 请求失败: {e}")
            resp = {}
        task_id = (resp or {}).get("task_id")
        if not task_id:
            print(f"    write 启动失败: {str(resp)[:200]}")
            time.sleep(10)
            continue
        ch = poll_chapter(base, token, novel_id, n, task_id)
        if ch and ch.get("content"):
            content = ch["content"]
            Path(out_path).write_text(
                f"# 第{n}章 {outline['title']}\n\n{content}\n",
                encoding="utf-8",
            )
            print(f"    => 完成 字数≈{len(content)} -> {out_path}")
            return True
        print(f"    => 第{attempt}次未入库，重试...")
        time.sleep(30)
    return False


def main():
    parser = argparse.ArgumentParser(description="盲读 A/B 验收生成")
    parser.add_argument("--variant", required=True, choices=["A", "B"])
    parser.add_argument("--backend", default="http://127.0.0.1:8080")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", default="Test123")
    parser.add_argument("--out", default="blind_ab")
    parser.add_argument("--novel", type=int, default=None)
    parser.add_argument("--style", default=DEFAULT_STYLE)
    args = parser.parse_args()

    base = args.backend.rstrip("/") + "/api/v1"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    token = api(base, "POST", "/auth/login",
                {"username": args.user, "password": args.password})["access_token"]
    print(f"[auth] 已登录 {args.user}，variant={args.variant}，backend={args.backend}")

    # 1. 确定 novel_id
    novel_id = args.novel
    if novel_id is None:
        print("\n>>> 创建验收小说（不跑设计阶段，仅建书）")
        info = api(base, "POST", "/workflow/start",
                   {"title": f"盲读A/B-{args.variant}", "preferred_genre": "都市修真"}, token=token)
        novel_id = info.get("novel_id")
        assert novel_id, json.dumps(info, ensure_ascii=False)[:300]
        print(f">>> novel_id = {novel_id}")

    # 2. 写入 5 个固定细纲
    print("\n>>> 写入固定细纲")
    api(base, "PUT", f"/workflow/chapter-outlines/{novel_id}",
        {"chapter_outlines": FIXED_OUTLINES}, token=token)

    # 3. 逐章生成
    results = []
    for outline in FIXED_OUTLINES:
        n = outline["chapter_number"]
        out_path = out_dir / f"{args.variant}_ch{n}.md"
        ok = generate_one(base, token, novel_id, outline, args.style, out_path)
        results.append((n, ok))

    # 4. 盲读协议与打分表
    random.seed(20261104)
    shuffled = list(range(1, 6))
    random.shuffle(shuffled)
    mapping = {i + 1: shuffled[i] for i in range(5)}
    protocol = f"""# 盲读 A/B 验收（质量升级方案 §8）

- 日期：{time.strftime('%Y-%m-%d %H:%M')}
- variant A：WRITING_PIPELINE_V2=false（现状）；variant B：WRITING_PIPELINE_V2=true（改造后）
- 细纲固定：冲突 / 过渡 / 情绪 / 信息 / 群像 各 1 章
- 评审 {len([r for r in results if r[1]])} 章 A/B 配对

## 随机编号对照（评审时只看编号，不看 A/B 标签）

| 编号 | 章节 | 实际文件 |
|---|---|---|
"""
    for num, ch in mapping.items():
        protocol += f"| {num} | 第{ch}章 | {args.variant}_ch{ch}.md |\n"
    protocol += """
## 评分表（每位评审独立填写）

对每个编号回答：
1. 更像人写的：____（编号）
2. 自然度（1-5）：____
3. 细节感（1-5）：____
4. 可读性（1-5）：____
5. 是否像 AI 写的：是 / 否

## 通过标准（§8.2）
- B 的自然度中位数 ≥ 3.5
- B 被判为"AI 写"的比例 ≤ 50%
- 评审 ≥ 2 人，分歧 > 1 分时加第三人
"""
    (out_dir / "protocol.md").write_text(protocol, encoding="utf-8")

    print("\n>>> 完成摘要:", json.dumps(
        {"variant": args.variant, "novel_id": novel_id,
         "results": results, "out": str(out_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
