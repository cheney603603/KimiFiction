with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', encoding='utf8') as f:
    lines = f.readlines()

for i in range(909, 920):
    print(f'{i+1}: {repr(lines[i])}')
