with open(r'D:\310Programm\KimiFiction\evaluate_rules_llm.csv', encoding='utf8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[:10], 1):
    print(f"{i}: {repr(line)}")
