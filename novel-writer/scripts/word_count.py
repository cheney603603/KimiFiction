#!/usr/bin/env python3
"""
小说项目字数统计工具
统计 novels/ 目录下所有正文字数
"""
import os
import re
import sys
from pathlib import Path

def count_chars_in_file(filepath):
    """统计文件字数（去除标点和空格后的中文字符数 + 英文单词数/5）"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return 0
    
    # 去除 frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2]
    
    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    
    # 统计英文单词（简单估算）
    english_words = len(re.findall(r'[a-zA-Z]+', content))
    english_chars_estimate = english_words * 5  # 英文单词平均5字符
    
    return chinese_chars + english_chars_estimate


def count_file(filepath):
    """详细统计单个文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read()
    except Exception:
        return None
    
    # 去除 frontmatter
    content = raw
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2]
    
    total_chars = len(content)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    english_words = len(re.findall(r'[a-zA-Z]+', content))
    
    # 统计段落数（粗估章节数）
    paragraphs = len([p for p in content.split('\n') if p.strip()])
    
    # 估算字数（中文每字=1，英文每词≈2）
    word_count = chinese_chars + english_words * 2
    
    return {
        'total_chars': total_chars,
        'chinese_chars': chinese_chars,
        'english_words': english_words,
        'word_count': word_count,
        'paragraphs': paragraphs
    }


def scan_novel_project(novel_path):
    """扫描一个小说项目"""
    results = {
        'metadata': None,
        '设定': [],
        '大纲': [],
        '细纲': [],
        '正文': [],
        'other': []
    }
    
    for root, dirs, files in os.walk(novel_path):
        # 跳过隐藏目录和 output
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'output']
        
        for file in files:
            if file.startswith('.'):
                continue
            filepath = Path(root) / file
            rel = filepath.relative_to(novel_path)
            
            # 判断文件类型
            if file == 'metadata.json':
                results['metadata'] = str(rel)
            elif '设定' in str(rel) or '角色' in str(rel) or '世界观' in str(rel):
                results['设定'].append(str(rel))
            elif '大纲' in str(rel):
                results['大纲'].append(str(rel))
            elif '细纲' in str(rel):
                results['细纲'].append(str(rel))
            elif '正文' in str(rel):
                results['正文'].append(str(rel))
            elif file.endswith('.md'):
                results['设定'].append(str(rel))
            else:
                results['other'].append(str(rel))
    
    return results


def main():
    base_path = Path(__file__).parent.parent
    novels_dir = base_path / 'novels'
    
    if not novels_dir.exists():
        print("❌ 未找到 novels/ 目录")
        sys.exit(1)
    
    novel_dirs = [d for d in novels_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    
    if not novel_dirs:
        print("❌ novels/ 目录下没有小说项目")
        sys.exit(1)
    
    print("=" * 60)
    print("📚 小说项目字数统计报告")
    print("=" * 60)
    
    total_all = 0
    
    for novel_dir in novel_dirs:
        print(f"\n📖 {novel_dir.name}")
        print("-" * 40)
        
        project = scan_novel_project(novel_dir)
        
        stats = {'word_count': 0, 'file_count': 0, 'chinese_chars': 0, 'english_words': 0}
        
        for category, files in project.items():
            if category == 'metadata' or not files:
                continue
            cat_count = 0
            cat_words = 0
            cat_files = 0
            
            for file_rel in files:
                filepath = novel_dir / file_rel
                if filepath.exists():
                    r = count_file(filepath)
                    if r:
                        cat_count += r['word_count']
                        cat_words += r['chinese_chars'] + r['english_words']
                        cat_files += 1
            
            cat_display = {
                '设定': '📋 设定',
                '大纲': '📑 大纲',
                '细纲': '📝 细纲',
                '正文': '📖 正文',
                'other': '📦 其他'
            }
            
            icon = cat_display.get(category, '📦')
            if cat_words > 0:
                print(f"  {icon} {category}: {cat_words:,} 字 ({cat_files} 个文件)")
                stats['word_count'] += cat_count
                stats['file_count'] += cat_files
                stats['chinese_chars'] += cat_count
            else:
                print(f"  {icon} {category}: -- ({cat_files} 个文件)")
        
        # 估算总字数（正文按实际算，设定按1/3折算）
        main_words = sum(
            count_file(novel_dir / f)['word_count']
            for cat, files in project.items()
            for f in files
            if cat in ('正文', '细纲', '大纲')
            for _ in [1]  # iterator trick
            if (novel_dir / f).exists()
            and count_file(novel_dir / f)
        )
        
        # 重新精确统计
        precise_total = 0
        for root, dirs, files in os.walk(novel_dir):
            for file in files:
                if file.startswith('.'):
                    continue
                filepath = Path(root) / file
                r = count_file(filepath)
                if r:
                    precise_total += r['word_count']
        
        print(f"  ─────────────────────────")
        print(f"  📊 估算总字数: {precise_total:,} 字")
        total_all += precise_total
    
    print("\n" + "=" * 60)
    print(f"📚 所有项目总计: {total_all:,} 字")
    
    if total_all < 50000:
        print(f"📝 距离100万字还有 {1000000 - total_all:,} 字，加油！")
    else:
        print(f"✅ 已完成约 {total_all/10000:.1f} 万字！")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
