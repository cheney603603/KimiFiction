import re

with open('D:/310Programm/KimiFiction/backend/app/workflow_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复614行
for i, line in enumerate(lines):
    if '当前题材方向为"' in line and 'genre or' in line:
        lines[i] = line.replace(
            '当前题材方向为"{genre or \'待补充\'}"，目标读者为"{audience or \'待补充\'}"',
            "当前题材方向为'{genre or \'待补充\'}'，目标读者为'{audience or \'待补充\'}'"
        )
        print(f"Fixed line {i+1}")
    if '世界设定核心为"' in line and 'world_name or' in line:
        lines[i] = line.replace(
            '世界设定核心为"{world_name or \'当前世界\'}"',
            "世界设定核心为'{world_name or \'当前世界\'}'"
        )
        print(f"Fixed line {i+1}")

with open('D:/310Programm/KimiFiction/backend/app/workflow_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Done')
