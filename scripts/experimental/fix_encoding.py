with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Chinese char range check
lo = '\u4e00'
hi = '\u9fff'

# New block
new_block = []
new_block.append('            # Read the file - detect encoding properly\n')
new_block.append('            text = None\n')
new_block.append('            # Check BOM first\n')
new_block.append('            with open(file_path, "rb") as f_bom:\n')
new_block.append('                first_bytes = f_bom.read(4)\n')
new_block.append('            if first_bytes[:3] == b"\\xef\\xbb\\xbf":\n')
new_block.append('                encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"]\n')
new_block.append('            else:\n')
new_block.append('                encodings = ["utf-8", "gbk", "gb18030", "gb2312", "latin1"]\n')
new_block.append('            for enc in encodings:\n')
new_block.append('                try:\n')
new_block.append('                    with open(file_path, "r", encoding=enc) as f_read:\n')
new_block.append('                        content = f_read.read()\n')
new_block.append(f'                    chinese_chars = len([c for c in content if "{lo}" <= c <= "{hi}"])\n')
new_block.append('                    if chinese_chars >= 100:\n')
new_block.append('                        text = content\n')
new_block.append('                        break\n')
new_block.append('                    elif text is None:\n')
new_block.append('                        text = content\n')
new_block.append('                except (UnicodeDecodeError, UnicodeError):\n')
new_block.append('                    continue\n')
new_block.append('            \n')
new_block.append(f'            if text is None or len([c for c in text if "{lo}" <= c <= "{hi}"]) < 100:\n')

# Replace lines 889-906 (indices 888-905)
lines[888:906] = new_block

with open(r'D:\310Programm\KimiFiction\evaluate_novels_v2.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed encoding detection')
