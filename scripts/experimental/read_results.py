import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'D:\310Programm\KimiFiction\training_runs\fine_eval_20260416_182440.json', encoding='utf8') as f:
    data = json.load(f)

evals = data['evaluations']
sorted_evs = sorted(evals, key=lambda x: x['total_score'], reverse=True)

print('='*60)
print('FINAL RANKING (27 Novels)')
print('='*60)
for i, ev in enumerate(sorted_evs, 1):
    stars = '*' if ev['rank']=='S' else ''
    print(f'{i:>2}. {ev["total_score"]:>5.1f} {ev["rank"]:>2}{stars} {ev["novel_name"][:35]}')

# Dimension analysis
print()
print('DIMENSION ANALYSIS:')
dims = {}
for ev in evals:
    for d in ev['dimensions']:
        cat = d['category']
        if cat not in dims:
            dims[cat] = {'name': d['name'], 'scores': [], 'weight': d['weight']}
        dims[cat]['scores'].append(d['normalized_score'])

for cat, info in dims.items():
    avg = sum(info['scores']) / len(info['scores'])
    best = max(info['scores'])
    worst = min(info['scores'])
    best_ev = [e for e in evals for d in e['dimensions'] if d['category']==cat and d['normalized_score']==best][0]
    worst_ev = [e for e in evals for d in e['dimensions'] if d['category']==cat and d['normalized_score']==worst][0]
    print(f'  {info["name"]:<10} avg={avg:.1f} best={best:.1f}({best_ev["novel_name"][:15]}) worst={worst:.1f}({worst_ev["novel_name"][:15]})')
