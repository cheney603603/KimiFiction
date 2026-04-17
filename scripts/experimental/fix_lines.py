with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 1002-1011 (1-indexed) need to be replaced
# They are currently at index 1001-1010 (0-indexed)
correct_lines = [
    '                    "rules": [\n',
    '                        {"id": r.rule_id, "name": r.rule_name, "score": r.score, "evidence": r.evidence}\n',
    '                        for r in d.rules\n',
    '                    ]\n',
    '                }\n',
    '                for d in ev.dimensions\n',
    '            ]\n',
    '        }\n',
    '        })\n',
    '    \n',
]

lines[1001:1011] = correct_lines

with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed lines 1002-1011')

# Verify
with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'r', encoding='utf-8') as f:
    lines2 = f.readlines()
for i in range(999, 1015):
    print(f'{i+1}: {repr(lines2[i])}')
