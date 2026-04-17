"""CSV规则解析器 - 修复版"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

csv_path = r'D:\310Programm\KimiFiction\evaluate_rules_llm.csv'

with open(csv_path, 'r', encoding='utf-8') as f:
    content = f.read()

section = None
dimensions = {}
rules = []
rule_count = 0

for line in content.split('\n'):
    line = line.strip()
    if not line:
        continue

    # Section markers
    if line == '[dimensions]':
        section = 'dimensions'; continue
    elif line == '[rules]':
        section = 'rules'; continue

    # Skip comment/separator lines
    if line.startswith('#') or line.startswith('===') or line.startswith('---'):
        continue

    # Parse dimension lines
    if section == 'dimensions' and line:
        # Format: id,name,weight,"description"
        # Find the parts - first 3 are simple, 4th is quoted
        # Use csv module for proper parsing
        try:
            import csv as csvmod
            from io import StringIO
            reader = csvmod.reader(StringIO(line), quotechar='"')
            row = next(reader)
        except:
            # Fallback: split manually
            parts = line.split(',', 3)
            row = parts

        if len(row) >= 4:
            dim_id = row[0].strip()
            dim_name = row[1].strip()
            try:
                weight = float(row[2].strip())
            except ValueError:
                print(f"SKIP dim (bad weight): {line[:60]}")
                continue
            desc = row[3].strip()
            dimensions[dim_id] = {'id': dim_id, 'name': dim_name, 'weight': weight, 'description': desc}
            print(f"Dim: {dim_id} weight={weight}")

    # Parse rule lines
    elif section == 'rules' and line:
        # Format: rule_id,dimension,rule_name,description(commas OK in quotes)
        try:
            import csv as csvmod
            from io import StringIO
            reader = csvmod.reader(StringIO(line), quotechar='"')
            row = next(reader)
        except:
            parts = line.split(',', 3)
            row = parts

        if len(row) >= 4:
            rule_id = row[0].strip()
            dim_id = row[1].strip()
            rule_name = row[2].strip()
            description = row[3].strip()
            if dim_id in dimensions:
                rules.append({
                    'rule_id': rule_id, 'dimension': dim_id,
                    'rule_name': rule_name, 'description': description,
                    'weight': dimensions[dim_id]['weight']
                })
                rule_count += 1
            else:
                print(f"SKIP rule (unknown dim): {rule_id} -> {dim_id}")

print(f"\nTotal: {len(dimensions)} dimensions, {rule_count} rules")
total_w = sum(d['weight'] for d in dimensions.values())
print(f"Weight sum: {total_w:.2f}")

# Verify rules per dimension
from collections import defaultdict
by_dim = defaultdict(list)
for r in rules:
    by_dim[r['dimension']].append(r)
print("\nRules per dimension:")
for dim_id, dim_info in dimensions.items():
    cnt = len(by_dim.get(dim_id, []))
    print(f"  {dim_info['name']}: {cnt} rules")
