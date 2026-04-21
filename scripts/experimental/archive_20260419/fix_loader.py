import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\310Programm\KimiFiction\evaluate_novels_llm.py', encoding='utf-8') as f:
    content = f.read()

# Find the _load method and replace it
old_load = '''    def _load(self):
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        section = None
        for line in content.split('\\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line == '[dimensions]':
                section = 'dimensions'; continue
            elif line == '[rules]':
                section = 'rules'; continue

            if section == 'dimensions' and line:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    self.dimensions[parts[0]] = {
                        'id': parts[0], 'name': parts[1],
                        'weight': float(parts[2]), 'description': parts[3],
                    }
            elif section == 'rules' and line:
                # CSV: rule_id,dimension,rule_name,description(可能含逗号)
                parts = line.split(',')
                if len(parts) >= 4:
                    rule = RuleDefinition(
                        rule_id=parts[0].strip(),
                        dimension=parts[1].strip(),
                        rule_name=parts[2].strip(),
                        description=','.join(parts[3:]).strip(),
                        dimension_weight=self.dimensions.get(parts[1].strip(), {}).get('weight', 0.1),
                    )
                    self.rules.append(rule)
                    self.rules_by_dim[rule.dimension].append(rule)

        total_weight = sum(d['weight'] for d in self.dimensions.values())
        print(f"  Loaded {len(self.rules)} rules, {len(self.dimensions)} dims, weight_sum={total_weight:.2f}")'''

new_load = '''    def _load(self):
        import csv as csvmod
        from io import StringIO

        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        section = None
        for line in content.split('\\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('===') or line.startswith('---'):
                continue
            if line == '[dimensions]':
                section = 'dimensions'; continue
            elif line == '[rules]':
                section = 'rules'; continue

            if section == 'dimensions' and line:
                # Use csv reader for proper quoted field parsing
                reader = csvmod.reader(StringIO(line), quotechar='"')
                try:
                    parts = next(reader)
                except:
                    continue
                if len(parts) >= 4:
                    try:
                        self.dimensions[parts[0]] = {
                            'id': parts[0], 'name': parts[1],
                            'weight': float(parts[2]), 'description': parts[3],
                        }
                    except ValueError:
                        pass  # Skip header line if it slips through

            elif section == 'rules' and line:
                reader = csvmod.reader(StringIO(line), quotechar='"')
                try:
                    parts = next(reader)
                except:
                    continue
                if len(parts) >= 4:
                    dim_id = parts[1].strip()
                    dim_w = self.dimensions.get(dim_id, {}).get('weight', 0.1)
                    rule = RuleDefinition(
                        rule_id=parts[0].strip(),
                        dimension=dim_id,
                        rule_name=parts[2].strip(),
                        description=parts[3].strip() if len(parts) > 3 else '',
                        dimension_weight=dim_w,
                    )
                    self.rules.append(rule)
                    self.rules_by_dim[rule.dimension].append(rule)

        total_weight = sum(d['weight'] for d in self.dimensions.values())
        print(f"  Loaded {len(self.rules)} rules, {len(self.dimensions)} dims, weight_sum={total_weight:.2f}")'''

if old_load in content:
    content = content.replace(old_load, new_load)
    with open(r'D:\310Programm\KimiFiction\evaluate_novels_llm.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed!')
else:
    print('Pattern not found - checking...')
    idx = content.find('def _load(self)')
    print(repr(content[idx:idx+500]))
