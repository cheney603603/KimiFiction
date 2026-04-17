with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', encoding='utf8') as f:
    lines = f.readlines()

# Current structure (1-indexed):
# 911: for enc in encodings: (idx 910)
# 912:     try: (idx 911)
# ...
# 922:                     continue (idx 921)
# 923:             (idx 922)
# 924:             if text is None or len(...) < 100: (idx 923)
# 925:             (idx 924) <-- empty, needs body!
# 926:             # Extract book name... (idx 925)
# 927:             filename = file_path.stem (idx 926)

# Wait - let me check the current state first
with open(r'D:\310Programm\KimiFiction\lines_908_920.txt', 'w', encoding='ascii', errors='replace') as f:
    for i in range(920, 932):
        line = lines[i]
        f.write(f'{i+1}: {line.encode("ascii", "replace").decode()}\n')
print('Done checking lines 921-932')
