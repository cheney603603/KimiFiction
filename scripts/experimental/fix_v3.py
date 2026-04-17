with open(r'D:\310Programm\KimiFiction\evaluate_novels_v3.py', encoding='utf8') as f:
    lines = f.readlines()

fixed = False
for i, line in enumerate(lines):
    if "得分条" in line and "lines.append" in line and line.strip().endswith('"\n'):
        # This is the broken line - missing } before \n
        print(f"Found at line {i+1}: {repr(line)}")
        # Fix it - replace the line ending
        fixed_line = line.replace("{'", "{'维度':<10} {'权重':<8} {'得分':<8} {'归一化':<8} {'规则数':<10} {'得分条'}")
        if "得分条\\n\")" in line:
            lines[i] = fixed_line
            fixed = True
            print(f"Fixed: {repr(lines[i])}")

if fixed:
    with open(r'D:\310Programm\KimiFiction\evaluate_novels_v3.py', 'w', encoding='utf8') as f:
        f.writelines(lines)
    print("File updated!")
else:
    print("Pattern not found - checking...")
    for i, line in enumerate(lines):
        if "得分条" in line:
            print(f"Line {i+1}: {repr(line)}")
