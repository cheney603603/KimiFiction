#!/usr/bin/env python3
"""
小说章节合并工具
将多章正文合并为一个大文件，便于整体阅读或导出
"""
import os
import re
import sys
from pathlib import Path
from datetime import datetime


def extract_frontmatter(content):
    """提取frontmatter"""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
    return '', content


def extract_chapter_title(filepath):
    """从文件路径提取章节标题"""
    filename = filepath.stem  # 去掉扩展名
    # 去掉序号前缀如 "第001章_"
    match = re.match(r'第?\d+章[_\s]*(.*)', filename)
    if match:
        return match.group(1).strip() if match.group(1) else filename
    return filename


def merge_volume(volume_path, output_path=None):
    """合并单卷的所有章节"""
    chapters = []
    
    for root, dirs, files in os.walk(volume_path):
        dirs.sort()
        for file in sorted(files):
            if not file.endswith('.md') or file.startswith('.'):
                continue
            filepath = Path(root) / file
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取frontmatter
            fm, body = extract_frontmatter(content)
            body = body.strip()
            
            if body:
                title = extract_chapter_title(filepath)
                chapters.append((title, body, fm))
    
    if not chapters:
        print(f"⚠️  未找到任何章节文件: {volume_path}")
        return None
    
    # 构建合并文档
    volume_name = volume_path.name
    output = []
    output.append(f"# {volume_name}\n")
    output.append(f"> 合并时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.append(f"> 章节数: {len(chapters)}\n")
    output.append("\n---\n")
    
    for i, (title, body, fm) in enumerate(chapters, 1):
        output.append(f"\n\n## 第{i}章 {title}\n")
        if fm:
            output.append(f"<!-- {fm.strip()} -->\n")
        output.append(body)
    
    result = '\n'.join(output)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"✅ 已合并 {len(chapters)} 章 -> {output_path}")
        return output_path
    
    return result


def merge_project(novel_path, output_path=None):
    """合并整个项目的所有正文"""
    # 查找所有正文目录
    zhengwen_dirs = []
    for root, dirs, files in os.walk(novel_path):
        for d in dirs:
            if '正文' in d:
                zhengwen_dirs.append(Path(root) / d)
    
    if not zhengwen_dirs:
        print(f"⚠️  未找到正文目录: {novel_path}")
        return None
    
    output = []
    novel_name = novel_path.name
    
    output.append(f"# {novel_name} 全文\n")
    output.append(f"> 合并时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.append(f"> 合并卷数: {len(zhengwen_dirs)}\n")
    output.append("\n---\n")
    
    total_chapters = 0
    
    for vol_dir in sorted(zhengwen_dirs):
        print(f"📖 处理卷: {vol_dir.name}...")
        chapters = []
        
        for root, dirs, files in os.walk(vol_dir):
            dirs.sort()
            for file in sorted(files):
                if not file.endswith('.md') or file.startswith('.'):
                    continue
                filepath = Path(root) / file
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                fm, body = extract_frontmatter(content)
                body = body.strip()
                
                if body:
                    title = extract_chapter_title(filepath)
                    chapters.append((title, body, fm))
        
        if chapters:
            total_chapters += len(chapters)
            output.append(f"\n\n# {vol_dir.name}\n")
            output.append(f"共 {len(chapters)} 章\n")
            output.append("\n---\n")
            
            for i, (title, body, fm) in enumerate(chapters, 1):
                output.append(f"\n\n## 第{i}章 {title}\n")
                if fm:
                    output.append(f"<!-- {fm.strip()} -->\n")
                output.append(body)
    
    output.append(f"\n\n---\n")
    output.append(f"> ✅ 全文合并完成！共 {total_chapters} 章\n")
    
    result = '\n'.join(output)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"\n✅ 已合并全部 {total_chapters} 章 -> {output_path}")
        return output_path
    
    return result


def main():
    base_path = Path(__file__).parent.parent
    novels_dir = base_path / 'novels'
    
    if not novels_dir.exists():
        print("❌ 未找到 novels/ 目录，请先创建小说项目")
        sys.exit(1)
    
    import argparse
    parser = argparse.ArgumentParser(description='合并小说章节')
    parser.add_argument('--novel', type=str, help='小说项目名（不填则列出所有项目）')
    parser.add_argument('--volume', type=str, help='指定卷名（需配合--novel）')
    parser.add_argument('--output', type=str, help='输出文件路径')
    args = parser.parse_args()
    
    if args.novel:
        novel_path = novels_dir / args.novel
        if not novel_path.exists():
            print(f"❌ 未找到项目: {args.novel}")
            sys.exit(1)
        
        if args.volume:
            vol_path = novel_path / '06_正文' / args.volume
            if not vol_path.exists():
                # 尝试模糊匹配
                zhengwen = novel_path / '06_正文'
                if zhengwen.exists():
                    for d in zhengwen.iterdir():
                        if args.volume in d.name:
                            vol_path = d
                            break
            
            output_path = args.output or f"{novel_path}/{novel_path.name}_{vol_path.name}_合并版.md"
            merge_volume(vol_path, output_path)
        else:
            output_path = args.output or f"{novel_path}/{novel_path.name}_全文合并版.md"
            merge_project(novel_path, output_path)
    else:
        # 列出所有项目
        print("📚 可用小说项目:")
        print("-" * 40)
        for d in sorted(novels_dir.iterdir()):
            if d.is_dir() and not d.name.startswith('.'):
                # 统计正文章数
                chapter_count = 0
                for root, dirs, files in os.walk(d):
                    chapter_count += sum(1 for f in files if f.endswith('.md') and '正文' in root)
                print(f"  📖 {d.name} ({chapter_count} 章)")
        
        print("\n用法:")
        print("  python merge_chapters.py --novel 项目名 --volume 卷名  # 合并单卷")
        print("  python merge_chapters.py --novel 项目名               # 合并全部正文")


if __name__ == "__main__":
    main()
