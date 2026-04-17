# -*- coding: utf-8 -*-
import os, re, sys, json, yaml
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Fix stdout encoding for Chinese output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RULES_FILE = os.path.join(os.path.dirname(__file__), "evaluate_rules_v2.yaml")
REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "reference")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "training_runs")

# ============================================================
# Data classes
# ============================================================
class RuleDef:
    def __init__(self, d):
        self.rule_id = d["rule_id"]
        self.name = d["name"]
        self.category = d["category"]
        self.dimension = d["dimension"]
        self.keywords = d.get("keywords", [])
        self.threshold = d.get("threshold", 1)
        self.max_score = d.get("max_score", 10)
        self.mode = d.get("evidence_mode", "count")
        self.description = d.get("description", "")

class RuleResult:
    def __init__(self, rule_id, name, score, count, threshold, evidence):
        self.rule_id = rule_id
        self.name = name
        self.score = score
        self.count = count
        self.threshold = threshold
        self.evidence = evidence

class DimResult:
    def __init__(self, name, cat, weight, raw, max_s, norm, rules):
        self.name = name
        self.category = cat
        self.weight = weight
        self.raw_score = raw
        self.max_score = max_s
        self.normalized = norm
        self.rules = rules

class NovelEval:
    def __init__(self, name, author, genre, wc, score, rank, dims, time):
        self.novel_name = name
        self.author = author
        self.genre = genre
        self.word_count = wc
        self.total_score = score
        self.rank = rank
        self.dimensions = dims
        self.evaluation_time = time

    def to_dict(self):
        return {
            "novel_name": self.novel_name, "author": self.author, "genre": self.genre,
            "word_count": self.word_count, "total_score": round(self.total_score, 1),
            "rank": self.rank, "evaluation_time": self.evaluation_time,
            "dimensions": [
                {"name": d.name, "category": d.category, "weight": d.weight,
                 "raw_score": d.raw_score, "max_score": d.max_score,
                 "normalized_score": d.normalized,
                 "rules": [{"id": r.rule_id, "name": r.name, "score": r.score,
                            "count": r.count, "threshold": r.threshold, "evidence": r.evidence}
                           for r in d.rules]}
                for d in self.dimensions]
        }

# ============================================================
# Rule Loader
# ============================================================
class RuleLoader:
    def __init__(self, rules_file):
        self.file = rules_file
        self.dims = {}
        self.rules = []
        self.by_cat = defaultdict(list)
        self._load()

    def _load(self):
        with open(self.file, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        for d in cfg.get("dimensions", []):
            self.dims[d["id"]] = d
        for r in cfg.get("rules", []):
            rule = RuleDef(r)
            self.rules.append(rule)
            self.by_cat[rule.category].append(rule)
        total = sum(d["weight"] for d in self.dims.values())
        print(f"  Loaded {len(self.rules)} rules, {len(self.dims)} dimensions, weight_sum={total:.2f}")

    def get(self, cat):
        return self.by_cat.get(cat, [])

# ============================================================
# Text Analyzer
# ============================================================
class Analyzer:
    def __init__(self, text):
        self.text = text
        self.tlen = len(text)
        self.cn = len(re.findall(r'[\u4e00-\u9fff]', text))
        self.parag = [p.strip() for p in text.split('\n') if p.strip()]
        self.plens = [len(p) for p in self.parag[:50]]
        self.open = text[:500] if len(text) >= 500 else text
        self.end = text[-300:] if len(text) >= 300 else text

    def count(self, kws, rng="full"):
        t = self.open if rng=="open" else (self.end if rng=="end" else self.text)
        return sum(t.count(k) for k in kws)

    def ratio(self, kws):
        c = self.count(kws)
        return (c / max(self.tlen, 1)) * 100

    def pvar(self):
        if not self.plens: return 0
        avg = sum(self.plens) / len(self.plens)
        return sum((l - avg)**2 for l in self.plens) / len(self.plens)

    def plrat(self):
        if not self.plens: return 0
        ok = sum(1 for l in self.plens if 30 <= l <= 300)
        return (ok / len(self.plens)) * 100

    def persp(self):
        cts = {'he': self.text.count('他'), 'she': self.text.count('她'),
               'it': self.text.count('它')}
        tot = sum(cts.values())
        if tot == 0: return 0, '?'
        m = max(cts.values())
        mp = max(cts, key=cts.get)
        mp = {'he': 'he', 'she': 'she', 'it': 'it'}[mp]
        return (m/tot)*100, mp

    def senses(self):
        n = 0
        if self.count(['看','看见','看到','注视']) >= 2: n += 1
        if self.count(['听','听到','听见','声音']) >= 2: n += 1
        if self.count(['闻','气味','香味']) >= 1: n += 1
        if self.count(['感受','触摸','刺痛']) >= 2: n += 1
        if self.count(['味道','品尝','苦涩']) >= 1: n += 1
        return n

    def dqratio(self):
        q = self.text.count('"') + self.text.count('"') + self.text.count('"')
        return q / max(self.tlen, 1)

# ============================================================
# Rule Executor
# ============================================================
class Executor:
    def __init__(self, rule, ana):
        self.rule = rule
        self.ana = ana

    def run(self):
        r = self.rule
        kws = r.keywords
        thr = r.threshold
        mode = r.mode
        c = 0; ev = ""; ok = False

        if mode == "count":
            c = self.ana.count(kws); ok = c >= thr; ev = f"{c}"
        elif mode == "count_inverse":
            c = self.ana.count(kws); ok = c <= thr; ev = f"{c}"
        elif mode == "ratio":
            if kws == ['\uff0e'] or kws == ['.']:
                c = self.ana.count(['\uff0e']); ratio = (c/max(self.ana.tlen,1))*100
            else:
                c = self.ana.count(kws); ratio = self.ana.ratio(kws)
            ok = ratio >= thr; ev = f"{ratio:.2f}%"
        elif mode == "variance":
            c = int(self.ana.pvar()); ok = self.ana.pvar() >= thr; ev = f"var={c}"
        elif mode == "para_length":
            c = int(self.ana.plrat()); ok = c >= thr
            avg = sum(self.ana.plens)/max(len(self.ana.plens),1)
            ev = f"avg={avg:.0f}"
        elif mode == "perspective":
            ratio, mp = self.ana.persp(); c = int(ratio); ok = ratio >= thr; ev = f"{mp}({ratio:.0f}%)"
        elif mode == "tension":
            t = self.ana.count(['紧张','急促','紧迫','危机'])
            rl = self.ana.count(['放松','平静','休息','闲','慢'])
            ok = t >= 2 and rl >= 2; c = t + rl; ev = f"T{t}/R{rl}"
        elif mode == "sense_count":
            c = self.ana.senses(); ok = c >= thr; ev = f"{c} senses"
        elif mode == "dialogue_ratio":
            ratio = self.ana.dqratio(); c = int(ratio*100); ok = 0.001 < ratio < 0.15; ev = f"{ratio*100:.2f}%"
        elif mode == "repeat_check":
            c = 0; ok = True; ev = "OK"
        elif mode == "opening":
            c = self.ana.count(kws, "open"); ok = c >= thr; ev = f"open={c}"
        elif mode == "ending":
            c = self.ana.count(kws, "end"); ok = c >= thr; ev = f"end={c}"
        else:
            c = self.ana.count(kws); ok = c >= thr; ev = f"{c}"

        return RuleResult(r.rule_id, r.name, 1 if ok else 0, c, thr, ev)

# ============================================================
# Evaluation Engine
# ============================================================
class Engine:
    def __init__(self, rules_file):
        self.loader = RuleLoader(rules_file)

    def eval_novel(self, text, name, author, genre, wc):
        ana = Analyzer(text)
        dim_results = []

        for dim_id, dim_meta in self.loader.dims.items():
            rules = self.loader.get(dim_id)
            if not rules: continue
            rres = []; raw = 0
            for rule in rules:
                res = Executor(rule, ana).run()
                rres.append(res); raw += res.score
            maxs = len(rules)
            norm = max(1.0, min(10.0, (raw/maxs)*10))
            dim_results.append(DimResult(
                dim_meta["name"], dim_id, dim_meta["weight"],
                raw, maxs, round(norm, 1), rres
            ))

        total = sum(d.normalized * d.weight for d in dim_results) * 10
        rank = "S" if total >= 90 else "A" if total >= 80 else "B" if total >= 70 else "C" if total >= 60 else "D" if total >= 50 else "F"
        return NovelEval(name, author, genre, wc, round(total, 1), rank, dim_results,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ============================================================
# File reading
# ============================================================
def read_novel(fp):
    for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'latin1']:
        try:
            with open(fp, 'r', encoding=enc) as f:
                c = f.read()
            cn = len(re.findall(r'[\u4e00-\u9fff]', c))
            if cn >= 100 or len(c) >= 5000:
                return c, enc
        except:
            continue
    return None, ""

def meta_from_filename(fname):
    stem = Path(fname).stem
    if '作者：' in stem:
        p = stem.split('作者：')
        return p[0].strip(), p[1].strip() if len(p) > 1 else "?"
    elif 'by' in stem:
        p = stem.split('by')
        return p[0].strip(), p[1].strip() if len(p) > 1 else "?"
    return stem, "?"

# ============================================================
# Markdown Report
# ============================================================
def gen_md(evals, dims_meta, out_path):
    lines = []
    # Chinese header labels stored as ASCII-safe dict
    HL = {
        'title': '# KimiFiction Long Text 8-Dimension Evaluation Report v2.0\n',
        'time': '**Evaluation Time**: ',
        'count': '**Novels Evaluated**: ',
        'rules_file': '**Rules File**: `evaluate_rules_v2.yaml` (editable)\n',
        'sep': '---\n\n',
        'ranking': '## Ranking\n\n',
        'th': '| Rank | Novel | Author | Genre | Words | Score | Rank |\n',
        'th2': '|:---:|:---|:---|:---|---:|:---:|:---:|\n',
        'detail': '## Detail: ',
        'eight_dim': '### Eight-Dimension Scores\n\n',
        'eight_hdr': '```\n',
        'eight_row': '{:<10} {:>6}  {:>5}  {:>6}  {:>5}    {:10}\n',
        'eight_sep': '-' * 70 + '\n',
        'eight_total': 'TOTAL        100.0%     --   {score}/100\n',
        'eight_end': '```\n\n',
        'rules_hdr': '### Rule Details\n\n',
        'rules_th': '| ID | Name | Pass | Count | Thresh | Evidence |\n',
        'rules_th2': '|:---:|:---|:---:|:---:|:---:|:---|\n',
        'cross': '## Cross-Novel Dimension Comparison\n\n',
        'cross_th': '| Dimension | Weight | Avg Score | Best Novel |\n',
        'cross_th2': '|:---|:---:|:---:|:---|\n',
        'footer': '*Generated by KimiFiction 8-Dimension Evaluation System v2.0*\n',
    }

    lines.append(HL['title'])
    lines.append(HL['time'] + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n')
    lines.append(HL['count'] + str(len(evals)) + ' novels\n')
    lines.append(HL['rules_file'])
    lines.append(HL['sep'])

    # Ranking
    sorted_evs = sorted(evals, key=lambda x: x.total_score, reverse=True)
    medals = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
    lines.append(HL['ranking'])
    lines.append(HL['th']); lines.append(HL['th2'])
    for i, ev in enumerate(sorted_evs):
        lines.append(f"| {i+1} | **{ev.novel_name}** | {ev.author} | {ev.genre} | {ev.word_count:,} | **{ev.total_score:.1f}** | {ev.rank} |\n")

    lines.append(HL['sep'])

    # Detail per novel
    for ev in evals:
        rank_in_list = sorted_evs.index(ev) + 1
        lines.append(f"## {rank_in_list}. {ev.novel_name}\n")
        lines.append(f"**Author**: {ev.author} | **Genre**: {ev.genre} | **Words**: {ev.word_count:,} | **Rank**: {ev.rank}\n\n")
        lines.append(HL['eight_dim'])
        lines.append(HL['eight_hdr'])
        # Header row
        lines.append(HL['eight_row'].format(
            'Dim', 'Wght%', 'Score', 'Norm', 'Rules', 'Bar'))
        lines.append(HL['eight_sep'])
        for d in sorted(ev.dimensions, key=lambda x: x.weight, reverse=True):
            bar = '\u2588' * int(d.normalized) + '\u2591' * (10 - int(d.normalized))
            lines.append(HL['eight_row'].format(
                d.name, f"{d.weight*100:.0f}%",
                f"{d.raw_score:.0f}/{d.max_score}",
                f"{d.normalized}/10",
                f"{d.raw_score:.0f}/{d.max_score}",
                bar))
        lines.append(HL['eight_sep'])
        lines.append(HL['eight_total'].format(score=ev.total_score))
        lines.append(HL['eight_end'])

        # Rule details
        lines.append(HL['rules_hdr'])
        for d in ev.dimensions:
            failed = sum(1 for r in d.rules if r.score == 0)
            hdr = f"**{d.name}** ({d.raw_score:.0f}/{d.max_score} passed, {d.normalized}/10)"
            if failed > 0:
                hdr += f" [WARNING: {failed} rules failed]"
            lines.append(hdr + '\n\n')
            lines.append(HL['rules_th']); lines.append(HL['rules_th2'])
            for r in d.rules:
                icon = 'PASS' if r.score == 1 else 'FAIL'
                lines.append(f"| {r.rule_id} | {r.name} | {icon} | {r.count} | >= {r.threshold} | {r.evidence} |\n")
            lines.append('\n')
        lines.append(HL['sep'])

    # Cross-novel comparison
    lines.append(HL['cross'])
    lines.append(HL['cross_th']); lines.append(HL['cross_th2'])
    for dim_id, dim_meta in dims_meta.items():
        evs_for_dim = [ev for ev in evals for d in ev.dimensions if d.category == dim_id]
        if evs_for_dim:
            avg = sum(d.normalized for ev in evals for d in ev.dimensions if d.category == dim_id) / len(evs_for_dim)
            best = max(evals, key=lambda ev: next((d.raw_score for d in ev.dimensions if d.category == dim_id), 0))
            bar = '\u2588' * int(avg) + '\u2591' * (10 - int(avg))
            lines.append(f"| {dim_meta['name']} | {dim_meta['weight']*100:.0f}% | {avg:.1f}/10 {bar} | {best.novel_name[:15]} |\n")

    lines.append(HL['sep'])
    lines.append(HL['footer'])

    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--file", type=str)
    parser.add_argument("--rules", action="store_true", help="validate rules only")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dir", type=str)
    parser.add_argument("--output", type=str)
    parser.add_argument("--rules-file", type=str)
    args = parser.parse_args()

    ref_dir = args.dir or REFERENCE_DIR
    out_dir = args.output or OUTPUT_DIR
    rules_file = args.rules_file or RULES_FILE
    limit = None if args.all else args.limit
    single = args.file

    print("=" * 70)
    print("KimiFiction 8-Dimension Fine-Grained Scoring System v2.0")
    print("=" * 70)
    print(f"  Rules file: {rules_file}")
    print(f"  Source dir: {ref_dir}")
    print(f"  Output dir: {out_dir}")
    print()

    engine = Engine(rules_file)

    if args.rules:
        print("\nRules config validated OK")
        return

    ref_path = Path(ref_dir)
    if single:
        files = [ref_path / single]
    else:
        files = sorted(ref_path.glob("*.txt"))
        if limit:
            files = files[:limit]

    print(f"\nFound {len(files)} novels to evaluate\n")

    os.makedirs(out_dir, exist_ok=True)
    evals = []

    for i, fp in enumerate(files, 1):
        try:
            print(f"[{i}/{len(files)}] {fp.name}...", end=" ", flush=True)
            content, enc = read_novel(fp)
            if content is None:
                print("Read failed"); continue

            name, author = meta_from_filename(fp.name)
            wc = len(re.findall(r'[\u4e00-\u9fff]', content)) + len(re.findall(r'[a-zA-Z]+', content))

            genre = "Fantasy"
            gm = {"\u6c38\u751f": "Apocalypse", "\u5e9f\u571f": "Apocalypse",
                  "\u5218\u8f66": "Train Survival", "\u4ed9\u4fee": "Xianxia",
                  "\u7384\u5e7b": "Fantasy", "\u90fd\u5e02": "Urban",
                  "\u4ed9\u4fa0": "Xianxia", "\u5927\u5c0b": "Xianxia",
                  "\u5929\u6cb3": "Fantasy", "\u5c71\u6cb3\u796d": "Fantasy",
                  "\u65e0\u5883": "Train Survival"}
            for kw, g in gm.items():
                if kw in name:
                    genre = g; break

            ev = engine.eval_novel(content, name, author, genre, wc)
            evals.append(ev)

            print(f"Score: {ev.total_score:.1f} | Rank: {ev.rank}")
            for d in ev.dimensions:
                bar = '#' * int(d.normalized) + '-' * (10 - int(d.normalized))
                fail = sum(1 for r in d.rules if r.score == 0)
                warn = f" [!{fail}]" if fail > 0 else ""
                print(f"  | {d.name:<10} {d.raw_score:.0f}/{d.max_score} ({d.normalized}/10) {bar}{warn}")

        except Exception as e:
            print(f"Error: {e}")

    if evals:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        jp = os.path.join(out_dir, f"fine_eval_{ts}.json")
        mp = os.path.join(out_dir, f"fine_eval_{ts}.md")

        jdata = {
            "evaluation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_novels": len(evals),
            "rules_file": rules_file,
            "dimensions": [{"id": k, "name": v["name"], "weight": v["weight"]}
                           for k, v in engine.loader.dims.items()],
            "total_rules": len(engine.loader.rules),
            "evaluations": [e.to_dict() for e in evals],
        }
        with open(jp, 'w', encoding='utf-8') as f:
            json.dump(jdata, f, ensure_ascii=False, indent=2)

        gen_md(evals, engine.loader.dims, mp)

        print(f"\nSaved:")
        print(f"  JSON: {jp}")
        print(f"  MD: {mp}")

if __name__ == "__main__":
    main()
