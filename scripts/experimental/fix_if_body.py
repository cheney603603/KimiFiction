with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', encoding='utf8') as f:
    lines = f.readlines()

# Current state:
# 911 (idx 910): '            for enc in encodings:\n'
# 912 (idx 911): '                    continue\n'
# 913 (idx 912): '            \n'
# 914 (idx 913): '            if text is None or len(...) < 100:\n'
# 915 (idx 914): '            \n'  <-- THIS is the problem, empty body
# 916 (idx 915): '            # Extract book name...\n'
# 917 (idx 916): '            filename = file_path.stem\n'

# The if at idx 913 needs a body
# Replace idx 914 (empty line) with print + continue
lines[914] = '                print("Read failed or insufficient Chinese chars")\n'
# Insert continue after
lines.insert(915, '                continue\n')

# Verify
for i in range(910, 922):
    print(f'{i+1}: {repr(lines[i])}')

with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'w', encoding='utf8') as f:
    f.writelines(lines)

print('Fixed!')
