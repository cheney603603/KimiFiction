import json, sys, os
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

p = r'D:\310Programm\KimiFiction\training_runs'
files = sorted([f for f in os.listdir(p) if f.startswith('llm_eval_') and f.endswith('.json')])
if not files:
    print("No results found"); exit()

with open(os.path.join(p, files[-1]), encoding='utf-8') as f:
    d = json.load(f)

evs = sorted(d['evals'], key=lambda x: x['total'], reverse=True)
print("=" * 60)
print("LLM RUBRIC RANKING")
print("=" * 60)
for i, e in enumerate(evs, 1):
    bars = ' '.join([str(int(dd['score'])) for dd in e['dims']])
    print(f"{i:>2}. {e['total']:>5.1f} {e['rank']:>2}  {e['name'][:28]:<30} | {bars}")

print()
print("DIMENSION AVERAGES:")
dims_all = defaultdict(list)
for e in evs:
    for dd in e['dims']:
        dims_all[dd['name']].append(dd['score'])
for name, scores in sorted(dims_all.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0, reverse=True):
    avg = sum(scores)/len(scores)
    bar = '#' * int(avg) + '-' * (10 - int(avg))
    print(f"  {name:<10} avg={avg:.1f}  {bar}")

print(f"\nAPI calls: {d.get('api_calls',0)} | Novels: {len(evs)} | Rules: {d.get('total_rules',0)}")
print(f"Report: {files[-1]}")
