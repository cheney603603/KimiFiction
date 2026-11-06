"""
热点/文风采集器骨架（opencli 驱动真实 Chrome）。

用途：浏览番茄小说 / 起点中文网等站点，抓取热榜标题或正文段落，作为
热点关键词与文风样本的原始输入（落库后进入 style_profile / 热榜表）。

用法：
  python scripts/collect_web_style.py --url https://www.qidian.com/rank
  python scripts/collect_web_style.py --url <正文页> --mode prose --out samples/prose_1.txt

依赖：本机已安装并登录 opencli（opencli browser <session> 可用）。
会话：自动从 `opencli doctor` 探测已连接的 Chrome profile；也可 --session 指定。

注意：
- 目标站（番茄/起点）在公司网络下可能被防火墙重置（实测 ERR_CONNECTION_RESET），
  脚本会识别 chrome-error:// 页面并给出明确诊断，不静默失败。
- 只采集公开榜单/公开样章，遵守站点 robots/ToS；不触碰盗版聚合站。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


def _find_opencli() -> str:
    import shutil
    for name in ("opencli", "opencli.cmd", "opencli.exe"):
        p = shutil.which(name)
        if p:
            return p
    for cand in (
        r"C:\Program Files\nodejs\opencli.cmd",
        r"$HOME\AppData\Roaming\npm\opencli.cmd",
    ):
        if Path(cand.replace("$HOME", str(Path.home()))).exists():
            return cand.replace("$HOME", str(Path.home()))
    print("[collect] 未找到 opencli 可执行文件，请确认已全局安装 opencli")
    sys.exit(2)


_OPENCLI = None


def _run(args: list) -> str:
    global _OPENCLI
    if _OPENCLI is None:
        _OPENCLI = _find_opencli()
    proc = subprocess.run([_OPENCLI, *args], capture_output=True)
    raw = proc.stdout
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _find_session() -> str:
    out = _run(["doctor"])
    m = re.search(r"•\s*([0-9a-zA-Z]{6,16}): connected", out)
    if m:
        return m.group(1)
    print("[collect] 未发现已连接的 opencli Chrome profile，请先运行 opencli doctor 确认")
    sys.exit(2)


def collect(url: str, session: str, mode: str, out_path: str | None,
            use_browser: bool = False, proxy: str | None = None) -> str:
    # 通道一：Python OpenSSL 直连（本机已实测可达 fanqie API / qidian / baidu；
    #           curl(schannel) 与 Chrome 直连被网络指纹拦截，Python 不受影响）
    if not use_browser:
        import urllib.request
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                "Accept": "text/html,application/json,*/*",
                "Referer": "https://fanqienovel.com/",
            })
            opener = urllib.request.build_opener()
            if proxy:
                proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                opener = urllib.request.build_opener(proxy_handler)
            with opener.open(req, timeout=20) as resp:
                raw = resp.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            if out_path:
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                Path(out_path).write_text(text, encoding="utf-8")
                print(f"[collect] Python 直连成功，已保存 {len(text)} 字符 -> {out_path}")
            else:
                print(f"[collect] Python 直连成功，{len(text)} 字符（前 300 字预览）：\n{text[:300]}")
            return text
        except Exception as e:
            print(f"[collect] Python 直连失败（{type(e).__name__}），尝试 opencli 浏览器通道…")

    # 通道二：opencli 驱动真实 Chrome（页面需要 JS 渲染 / 反爬挑战页时使用）
    _run(["browser", session, "open", url])
    state = _run(["browser", session, "state"])

    if "chrome-error://" in state or "ERR_CONNECTION" in state:
        title = re.search(r"title: (.+)", state)
        print(f"[collect] 目标站不可达（网络策略拦截）：{title.group(1) if title else url}")
        print("[collect] 诊断：ERR_CONNECTION_RESET —— 当前网络（企业防火墙/代理）重置了到该域名的连接。")
        print("[collect] 处置：部署到能访问目标站的网络运行，或改用半自动（用户粘贴样本）模式。")
        return ""

    if mode == "prose":
        # 正文页：拉取页面主文本（opencli browser extract 会返回可读文本）
        out = _run(["browser", session, "extract"])
    else:
        # 榜单页：拉取页面结构（标题/链接）
        out = state

    # 精简：去掉交互元素索引噪音，保留文本
    text = re.sub(r"\s*\[\d+\]\s*", "", out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(text, encoding="utf-8")
        print(f"[collect] 已保存 {len(text)} 字符 -> {out_path}")
    else:
        print(text[:3000])
    return text


def main():
    parser = argparse.ArgumentParser(description="热点/文风采集器骨架（opencli）")
    parser.add_argument("--url", required=True, help="目标 URL（榜单页或正文页）")
    parser.add_argument("--mode", choices=["rank", "prose"], default="rank")
    parser.add_argument("--session", default=None, help="opencli 浏览器会话（默认自动探测）")
    parser.add_argument("--out", default=None, help="保存到文件")
    parser.add_argument("--browser", action="store_true", help="强制走 opencli 浏览器通道（默认 Python 直连优先）")
    parser.add_argument("--proxy", default=None, help="HTTP/SOCKS5 代理，如 http://127.0.0.1:7897")
    args = parser.parse_args()

    session = args.session or _find_session()
    print(f"[collect] session={session} url={args.url} mode={args.mode}")
    collect(args.url, session, args.mode, args.out, use_browser=args.browser, proxy=args.proxy)


if __name__ == "__main__":
    main()
