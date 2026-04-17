import sys
with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', encoding='utf8') as f:
    lines = f.readlines()
for i in range(908, 918):
    line = lines[i]
    sys.stdout.reconfigure(encoding='utf-8')
    print(f'{i+1}: {line}')
