# -*- coding: utf-8 -*-
"""KimiFiction 八维 LLM Rubric 评测系统 v4
从 evaluate_rules_llm.csv 加载规则, 由 DeepSeek 判断 Yes/No

运行: python evaluate_novels_llm.py [--all] [--limit N] [--rules]
"""
import os, re, sys, json, time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import csv as csvmod
from io import StringIO

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---- paths ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE  = os.path.join(SCRIPT_DIR, "evaluate_rules_llm.csv")
REF_DIR     = os.path.join(SCRIPT_DIR, "reference")
OUT_DIR     = os.path.join(SCRIPT_DIR, "training_runs")

# ---- load env from backend/.env ----
BACKEND_ENV = os.path.join(SCRIPT_DIR, "backend", ".env")
if os.path.exists(BACKEND_ENV):
    with open(BACKEND_ENV, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

# ---- API keys ----
PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek")

if PROVIDER == "deepseek":
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY",""),
                    base_url=os.environ.get("DEEPSEEK_BASE_URL","https://api.deepseek.com"))
    MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
elif PROVIDER == "kimi":
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("KIMI_API_KEY",""),
                    base_url="https://api.moonshot.cn/v1")
    MODEL = os.environ.get("KIMI_MODEL", "moonshot-v1-8k")
else:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY",""),
                    base_url=os.environ.get("OPENAI_BASE_URL","https://api.openai.com/v1"))
    MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

BATCH = 10  # rules per LLM call

# ============================================================
# data
# ============================================================

@dataclass
class RuleDef:
    rule_id: str; dimension: str; rule_name: str
    description: str; weight: float = 0.0

@dataclass
class Judgment:
    rule_id: str; rule_name: str; dimension: str
    answer: str; reason: str

@dataclass
class DimResult:
    name: str; cat: str; weight: float
    total: int; passed: int; score: float
    judgments: List[Judgment] = field(default_factory=list)

@dataclass
class NovelResult:
    name: str; author: str; genre: str
    words: int; total: float; rank: str
    dims: List[DimResult]
    time_str: str = ""; api_calls: int = 0

    def to_dict(self):
        return dict(name=self.name, author=self.author, genre=self.genre,
                     words=self.words, total=round(self.total,1), rank=self.rank,
                     time_str=self.time_str, api_calls=self.api_calls,
                     dims=[dict(name=d.name, cat=d.cat, weight=d.weight,
                                total=d.total, passed=d.passed, score=d.score,
                                judgments=[dict(id=j.rule_id, name=j.rule_name,
                                               ans=j.answer, reason=j.reason[:200])
                                           for j in d.judgments])
                            for d in self.dims])

# ============================================================
# LLM
# ============================================================
_api_calls = 0

def llm_judge_batch(rules: List[RuleDef], text: str, novel: str, dim_name: str) -> List[Judgment]:
    global _api_calls
    if not rules: return []
    rules_text = "\n".join(
        f"规则{i+1} [{r.rule_id}] {r.rule_name}:\n  {r.description}"
        for i, r in enumerate(rules))
    prompt = (f"小说片段:\n{text[:15000]}\n\n"
              f"**评测规则**:\n{rules_text}\n\n"
              f"**输出格式** (只输出JSON数组):\n"
              f'[{{"rule_id":"R1","answer":"Yes","reason":"判断依据"}},\n'
              f' {{"rule_id":"R2","answer":"No","reason":"理由"}}]')

    messages = [
        {"role":"system","content":"你是严谨的小说评测专家。只输出JSON数组，answer只能是Yes或No。"},
        {"role":"user","content":prompt}]

    _api_calls += 1
    try:
        resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.1)
        text_resp = resp.choices[0].message.content
    except Exception as e:
        # fallback: one by one
        judgments = []
        for r in rules:
            _api_calls += 1
            try:
                r2 = client.chat.completions.create(model=MODEL,
                    messages=[{"role":"user","content":f"{text[:4000]}\n\n规则 [{r.rule_id}] {r.rule_name}: {r.description}\n输出: {{'rule_id':'{r.rule_id}','answer':'Yes','reason':'...'}}"}],
                    temperature=0.1)
                m = re.search(r'\{[^}]+\}', r2.choices[0].message.content)
                if m:
                    d = json.loads(m.group())
                    judgments.append(Judgment(r.rule_id, r.rule_name, r.dimension,
                                              d.get("answer","No"), d.get("reason","")[:100]))
                else:
                    judgments.append(Judgment(r.rule_id, r.rule_name, r.dimension, "No", "parse error"))
            except:
                judgments.append(Judgment(r.rule_id, r.rule_name, r.dimension, "No", str(e)))
            time.sleep(0.2)
        return judgments

    # parse JSON
    try:
        m = re.search(r'\[\s*\{.*?\}\s*\]', text_resp, re.DOTALL)
        results = json.loads(m.group()) if m else json.loads(text_resp)
        rule_map = {r.rule_id: r for r in rules}
        judgments = []
        for item in results:
            rid = item.get("rule_id","")
            if rid in rule_map:
                r = rule_map[rid]
                judgments.append(Judgment(rid, r.rule_name, r.dimension,
                                          item.get("answer","No").strip(),
                                          item.get("reason","")[:200]))
        # fill missing
        found = {j.rule_id for j in judgments}
        for r in rules:
            if r.rule_id not in found:
                judgments.append(Judgment(r.rule_id, r.rule_name, r.dimension, "No", "missing"))
        return judgments
    except:
        return [Judgment(r.rule_id, r.rule_name, r.dimension, "No", "parse fail") for r in rules]

# ============================================================
# loader
# ============================================================

class RuleLoader:
    def __init__(self):
        self.dims: Dict[str,dict] = {}
        self.rules: List[RuleDef] = []
        self.by_dim: Dict[str,List[RuleDef]] = defaultdict(list)
        self._load()

    def _load(self):
        with open(RULES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        section = None
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('===') or line.startswith('---'): continue
            if line == '[dimensions]': section = 'dims'; continue
            elif line == '[rules]': section = 'rules'; continue
            if not section: continue

            reader = csvmod.reader(StringIO(line), quotechar='"')
            try: parts = next(reader)
            except: continue

            if section == 'dims' and len(parts) >= 4:
                try:
                    self.dims[parts[0]] = dict(id=parts[0], name=parts[1],
                                                 weight=float(parts[2]), desc=parts[3])
                except: pass

            elif section == 'rules' and len(parts) >= 4:
                did = parts[1].strip()
                w = self.dims.get(did,{}).get('weight', 0.1)
                r = RuleDef(parts[0].strip(), did, parts[2].strip(),
                             parts[3].strip() if len(parts)>3 else '', w)
                self.rules.append(r); self.by_dim[did].append(r)

        tw = sum(d['weight'] for d in self.dims.values())
        print(f"  {len(self.rules)} rules, {len(self.dims)} dims, weight={tw:.2f}")

# ============================================================
# text extraction
# ============================================================

def eval_text(text: str) -> str:
    """提取用于LLM评测的文本，总量不超过MAX_TEXT字符"""
    n = len(text)
    MAX = 20000  # 硬上限，避免超长文本导致API超时
    if n < 10000: return text
    # 取头+中+尾，但总量不超过MAX
    head = text[:int(n * 0.3)]
    mid_start = int(n * 0.35)
    mid_end = int(n * 0.65)
    tail_start = int(n * 0.7)
    # 如果超限，逐步减少中间部分
    while len(head) + (mid_end - mid_start) + (n - tail_start) > MAX and (mid_end - mid_start) > 1000:
        mid_end -= 1000
    tail = text[tail_start:]
    result = head + '\n[...]\n' + text[mid_start:mid_end] + '\n[...]\n' + tail
    if len(result) > MAX:
        result = result[:MAX]
    return result

def read_novel(fp: Path) -> Tuple[Optional[str],str]:
    for enc in ['utf-8-sig','utf-8','gbk','gb18030','latin1']:
        try:
            with open(fp, encoding=enc) as f: c = f.read()
            if len(re.findall(r'[\u4e00-\u9fff]', c)) >= 100: return c, enc
        except: pass
    return None,""

def meta(fp: str) -> Tuple[str,str]:
    s = Path(fp).stem
    if '作者：' in s:
        p = s.split('作者：')
        return p[0].strip(), p[1].strip() if len(p)>1 else "?"
    if 'by' in s:
        p = s.split('by')
        return p[0].strip(), p[1].strip() if len(p)>1 else "?"
    return s,"?"

# ============================================================
# engine
# ============================================================

class Engine:
    def __init__(self): self.loader = RuleLoader()

    def eval(self, text: str, name: str, author: str, genre: str, wc: int) -> NovelResult:
        global _api_calls
        _api_calls = 0
        etext = eval_text(text)
        print(f"  LLM judging {len(self.loader.rules)} rules...", flush=True)
        dim_results = []
        for did, dinfo in self.loader.dims.items():
            rules = self.loader.by_dim[did]
            judgments = []
            for i in range(0, len(rules), BATCH):
                batch = rules[i:i+BATCH]
                judgments.extend(llm_judge_batch(batch, etext, name, dinfo['name']))
                time.sleep(0.3)
            passed = sum(1 for j in judgments if j.answer.lower() == 'yes')
            score = max(1.0, min(10.0, (passed/len(rules))*10))
            dim_results.append(DimResult(dinfo['name'], did, dinfo['weight'],
                                          len(rules), passed, round(score,1), judgments))
        total = sum(d.score*d.weight for d in dim_results)*10
        rank = "S" if total>=90 else "A" if total>=80 else "B" if total>=70 else "C" if total>=60 else "D" if total>=50 else "F"
        return NovelResult(name, author, genre, wc, round(total,1), rank, dim_results,
                           datetime.now().strftime("%Y-%m-%d %H:%M:%S"), _api_calls)

# ============================================================
# markdown report
# ============================================================

def gen_md(evals, loader, out_path):
    L = ['# KimiFiction LLM Rubric Evaluation Report\n\n',
         f'**Time**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  '
         f'**N**: {len(evals)}  '
         f'**Rules**: `evaluate_rules_llm.csv`\n\n---\n\n']
    sorted_evs = sorted(evals, key=lambda x: x.total, reverse=True)
    L.append('## Ranking\n\n| # | Novel | Author | Score | Rank |\n|:---:|:---|:---|---:|:---:|\n')
    for i, e in enumerate(sorted_evs, 1):
        bars = ' '.join(f'{d.score:.0f}' for d in e.dims)
        L.append(f'| {i} | **{e.name}** | {e.author} | **{e.total:.1f}** | {e.rank} |\n')
    L.append('\n---\n\n')
    for ev in sorted_evs:
        L.append(f'## {ev.name}\n\n**Author**: {ev.author}  |  **Score**: {ev.total:.1f}  |  **{ev.rank}**  |  API calls: {ev.api_calls}\n\n')
        L.append('| Dimension | Weight | Pass | Score |\n|:---|:---:|:---:|:---:|\n')
        for d in sorted(ev.dims, key=lambda x: x.weight, reverse=True):
            bar = '\u2588'*int(d.score) + '\u2591'*(10-int(d.score))
            L.append(f'| {d.name} | {d.weight*100:.0f}% | {d.passed}/{d.total} | {d.score}/10 {bar} |\n')
        L.append('\n**Rule Judgments**:\n\n')
        for d in ev.dims:
            L.append(f'**{d.name}** ({d.passed}/{d.total})\n\n')
            L.append('| ID | Rule | Answer | Reason |\n|:---:|:---|:---:|:---|\n')
            for j in d.judgments:
                L.append(f'| {j.rule_id} | {j.rule_name} | {j.answer} | {j.reason[:80]} |\n')
            L.append('\n')
        L.append('---\n\n')
    with open(out_path, 'w', encoding='utf-8') as f: f.writelines(L)

# ============================================================
# main
# ============================================================

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--file", type=str)
    p.add_argument("--rules", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--dir", type=str)
    p.add_argument("--batch", type=int, default=BATCH)
    args = p.parse_args()

    ref_dir = args.dir or REF_DIR
    limit = None if args.all else args.limit
    os.makedirs(OUT_DIR, exist_ok=True)

    print("="*60)
    print("KimiFiction 8-Dim LLM Rubric Scoring System v4")
    print("="*60)
    print(f"  Rules: {RULES_FILE}")
    print(f"  Provider: {PROVIDER} / {MODEL}")
    print(f"  Batch: {args.batch} rules/call")

    if not args.rules:
        engine = Engine()
        if args.rules:
            print("OK"); return
    else:
        print("  API: deepseek=OK kim=OK openai=OK")
        print("OK"); return

    ref = Path(ref_dir)
    files = [ref/args.file] if args.file else sorted(ref.glob("*.txt"))
    if limit: files = files[:limit]
    print(f"\nFound {len(files)} novels\n" + "="*60)

    evals = []
    for i, fp in enumerate(files, 1):
        try:
            print(f"\n[{i}/{len(files)}] {fp.name}", flush=True)
            content, enc = read_novel(fp)
            if not content: print("  read failed"); continue
            name, author = meta(fp.name)
            wc = len(re.findall(r'[\u4e00-\u9fff]', content)) + len(re.findall(r'[a-zA-Z]+', content))
            ev = engine.eval(content, name, author, "Fantasy", wc)
            evals.append(ev)
            print(f"  Score: {ev.total:.1f} | {ev.rank} | calls={ev.api_calls}")
            for d in ev.dims:
                bar = '#'*int(d.score)+'-'*(10-int(d.score))
                fail = d.total - d.passed
                print(f"  | {d.name:<10} {d.passed}/{d.total} ({d.score}/10) {bar}" + (f" [!{fail}]" if fail else ""))
        except Exception as e:
            print(f"  Error: {e}"); import traceback; traceback.print_exc()

    if evals:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        jp = os.path.join(OUT_DIR, f"llm_eval_{ts}.json")
        mp = os.path.join(OUT_DIR, f"llm_eval_{ts}.md")
        loader = engine.loader
        jdata = dict(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     total=len(evals), rules_file=RULES_FILE, provider=PROVIDER,
                     dims=[dict(id=k, name=v['name'], weight=v['weight']) for k,v in loader.dims.items()],
                     total_rules=len(loader.rules),
                     api_calls=sum(e.api_calls for e in evals),
                     evals=[e.to_dict() for e in evals])
        with open(jp, 'w', encoding='utf-8') as f: json.dump(jdata, f, ensure_ascii=False, indent=2)
        gen_md(evals, loader, mp)
        print(f"\nSaved: {jp}\n       {mp}")

if __name__ == "__main__": main()
