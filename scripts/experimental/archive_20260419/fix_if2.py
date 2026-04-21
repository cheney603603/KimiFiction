with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', encoding='utf8') as f:
    lines = f.readlines()

# Line 911 (idx 910): if text is None or len([c for c in text if "一" <= c <= "鿿"]) < 100:
# Line 912 (idx 911): empty - needs to be filled
# Line 913 (idx 912): # Extract book name...

# Current: if statement with no body on next line
# Fix: replace line 912 with print + continue
# Then insert continue
# The comment line needs to stay where it is (now at 913 or shifted by 1)

# Line 912 (idx 911) currently is '\n' (empty line after if statement)
# We need to replace it with:
# '                print("Read failed...")\n'
# And insert '                continue\n' after

# But first, find out what's at idx 911
print(f'Idx 911: {repr(lines[911])}')
print(f'Idx 912: {repr(lines[912])}')
print(f'Idx 913: {repr(lines[913])}')

# Replace idx 911 (the empty body) with print statement
lines[911] = '                print("Read failed or insufficient Chinese chars")\n'
# Insert continue after it
lines.insert(912, '                continue\n')

# Now idx 914 is the comment line (previously idx 913)
print(f'After fix, idx 913: {repr(lines[913])}')
print(f'After fix, idx 914: {repr(lines[914])}')

with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'w', encoding='utf8') as f:
    f.writelines(lines)

print('Fixed!')
