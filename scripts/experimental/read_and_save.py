with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', encoding='utf8') as f:
    lines = f.readlines()

with open(r'D:\310Programm\KimiFiction\lines_908_920.txt', 'w', encoding='ascii', errors='replace') as f:
    for i in range(908, 920):
        line = lines[i]
        f.write(f'{i+1}: {line.encode("ascii", "replace").decode()}\n')
print('Done')
