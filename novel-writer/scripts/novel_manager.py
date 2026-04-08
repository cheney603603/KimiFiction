#!/usr/bin/env python3
"""
小说项目管理脚本
提供命令行界面管理小说项目
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class NovelManager:
    """小说项目管理器"""
    
    # 标准目录结构
    DIR_STRUCTURE = {
        "demand": "00_作品设定.json",
        "world": "01_世界观设定.json",
        "characters": "02_角色设定.json",
        "plot": "03_故事线设定.json",
        "outline": "04_分卷大纲",
        "chapter_outlines": "05_章节细纲",
        "chapters": "06_正文",
        "history": ".novel_history/revisions",
    }
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.project_id = self.project_path.name
    
    @classmethod
    def create_project(cls, title: str, base_path: str = None) -> "NovelManager":
        """创建新项目"""
        if base_path is None:
            base_path = os.path.join(os.getcwd(), "novels")
        
        # 生成项目ID
        import hashlib
        import time
        raw = f"{title}_{time.time()}"
        hash_id = hashlib.md5(raw.encode()).hexdigest()[:8]
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:20]
        project_id = f"{safe_title}_{hash_id}"
        
        project_path = Path(base_path) / project_id
        project_path.mkdir(parents=True, exist_ok=True)
        
        # 创建目录结构
        cls._create_structure(project_path)
        
        # 初始化元数据
        metadata = {
            "title": title,
            "project_id": project_id,
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "status": "planning",
        }
        
        with open(project_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 项目创建成功: {project_id}")
        print(f"   路径: {project_path}")
        
        return cls(str(project_path))
    
    @classmethod
    def _create_structure(cls, project_path: Path) -> None:
        """创建目录结构"""
        project_path.mkdir(parents=True, exist_ok=True)
        
        # 创建所有子目录
        (project_path / ".novel_history" / "revisions").mkdir(parents=True, exist_ok=True)
        
        for key, value in cls.DIR_STRUCTURE.items():
            if "/" in value:
                dir_path = project_path / value.split("/")[0]
                dir_path.mkdir(parents=True, exist_ok=True)
            elif "." not in value:
                dir_path = project_path / value
                dir_path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_project(cls, project_path: str) -> "NovelManager":
        """加载项目"""
        path = Path(project_path)
        if not path.exists():
            raise FileNotFoundError(f"项目不存在: {project_path}")
        
        metadata_file = path / "metadata.json"
        if not metadata_file.exists():
            raise ValueError(f"不是有效的项目目录: {project_path}")
        
        return cls(str(path))
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取项目元数据"""
        with open(self.project_path / "metadata.json", "r", encoding="utf-8") as f:
            return json.load(f)
    
    def update_metadata(self, data: Dict[str, Any]) -> None:
        """更新项目元数据"""
        metadata = self.get_metadata()
        metadata.update(data)
        metadata["updated_at"] = datetime.now().isoformat()
        
        with open(self.project_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def get_status(self) -> Dict[str, Any]:
        """获取项目状态"""
        metadata = self.get_metadata()
        
        # 统计文件数
        outline_count = len(list((self.project_path / "05_章节细纲").rglob("*.json"))) if (self.project_path / "05_章节细纲").exists() else 0
        chapter_count = len(list((self.project_path / "06_正文").rglob("*.md"))) if (self.project_path / "06_正文").exists() else 0
        
        # 计算字数
        total_words = 0
        for chapter_file in (self.project_path / "06_正文").rglob("*.md"):
            try:
                with open(chapter_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 移除YAML头
                    if content.startswith("---"):
                        content = content.split("---", 2)[-1]
                    # 统计中文
                    chinese = len([c for c in content if '\u4e00' <= c <= '\u9fff'])
                    total_words += chinese
            except:
                pass
        
        return {
            "project_id": self.project_id,
            "title": metadata.get("title", ""),
            "status": metadata.get("status", "unknown"),
            "created_at": metadata.get("created_at", ""),
            "updated_at": metadata.get("updated_at", ""),
            "outline_count": outline_count,
            "chapter_count": chapter_count,
            "total_words": total_words,
            "progress": self._calculate_progress(metadata),
        }
    
    def _calculate_progress(self, metadata: Dict) -> float:
        """计算进度百分比"""
        status = metadata.get("status", "planning")
        phases = ["planning", "designing", "writing", "reviewing", "completed"]
        
        if status in phases:
            idx = phases.index(status)
            return int((idx / (len(phases) - 1)) * 100)
        return 0
    
    # ===== 文件操作 =====
    
    def save_setting(self, setting_type: str, data: Dict[str, Any]) -> None:
        """保存设定文件"""
        filename = self.DIR_STRUCTURE.get(setting_type)
        if not filename:
            raise ValueError(f"未知设定类型: {setting_type}")
        
        filepath = self.project_path / filename
        
        # 确保目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 添加元数据
        data["saved_at"] = datetime.now().isoformat()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存: {filename}")
    
    def load_setting(self, setting_type: str) -> Dict[str, Any]:
        """加载设定文件"""
        filename = self.DIR_STRUCTURE.get(setting_type)
        if not filename:
            raise ValueError(f"未知设定类型: {setting_type}")
        
        filepath = self.project_path / filename
        
        if not filepath.exists():
            return {}
        
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def save_chapter_outline(self, volume: int, chapter: int, outline: Dict) -> None:
        """保存章节细纲"""
        # 确保目录存在
        dir_path = self.project_path / f"05_章节细纲/第{volume}卷"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        filename = dir_path / f"第{chapter:03d}章.json"
        
        outline["volume"] = volume
        outline["chapter"] = chapter
        outline["saved_at"] = datetime.now().isoformat()
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存细纲: 第{volume}卷 第{chapter}章")
    
    def save_chapter(self, volume: int, chapter: int, title: str, content: str) -> None:
        """保存章节正文"""
        # 确保目录存在
        dir_path = self.project_path / f"06_正文/第{volume}卷"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        safe_title = "".join(c if c not in '<>:"|?*' else "_" for c in title)[:30]
        filename = dir_path / f"第{chapter:03d}章_{safe_title}.md"
        
        # 构建内容
        full_content = f"""---
title: {title}
volume: {volume}
chapter: {chapter}
generated_at: {datetime.now().isoformat()}
---

# {title}

{content}
"""
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        print(f"✅ 已保存正文: {filename}")
    
    # ===== 导出功能 =====
    
    def export_chapters(self, volume: int = None) -> str:
        """导出章节"""
        chapters = []
        
        if volume:
            pattern = f"06_正文/第{volume}卷/*.md"
        else:
            pattern = "06_正文/**/*.md"
        
        for chapter_file in self.project_path.glob(pattern):
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read()
                
                # 解析YAML头
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        meta = {}
                        for line in parts[1].strip().split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                meta[key.strip()] = value.strip()
                        
                        title = meta.get("title", chapter_file.stem)
                        chapters.append({
                            "title": title,
                            "content": parts[2].strip(),
                        })
                        continue
            
            chapters.append({
                "title": chapter_file.stem,
                "content": content,
            })
        
        # 合并
        output = []
        for ch in sorted(chapters, key=lambda x: x.get("title", "")):
            output.append(f"\n\n{'='*40}\n")
            output.append(f"{ch['title']}\n")
            output.append(f"{'='*40}\n\n")
            output.append(ch["content"])
        
        return "".join(output)
    
    def create_backup(self, reason: str = "manual") -> str:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}_{reason}"
        backup_path = self.project_path / f".novel_history/backups/{backup_name}"
        
        backup_path.mkdir(parents=True, exist_ok=True)
        
        import shutil
        for item in ["metadata.json", "00_作品设定.json", "01_世界观设定.json", 
                     "02_角色设定.json", "03_故事线设定.json"]:
            src = self.project_path / item
            if src.exists():
                shutil.copy2(src, backup_path / item)
        
        # 复制大纲和正文目录
        for item in ["04_分卷大纲", "05_章节细纲", "06_正文"]:
            src = self.project_path / item
            if src.exists():
                shutil.copytree(src, backup_path / item, dirs_exist_ok=True)
        
        print(f"✅ 备份已创建: {backup_name}")
        return str(backup_path)
    
    # ===== 列表功能 =====
    
    def list_outlines(self, volume: int = None) -> list:
        """列出章节细纲"""
        if volume:
            pattern = f"05_章节细纲/第{volume}卷/*.json"
        else:
            pattern = "05_章节细纲/**/*.json"
        
        outlines = []
        for file in self.project_path.glob(pattern):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                outlines.append({
                    "volume": data.get("volume", 0),
                    "chapter": data.get("chapter", 0),
                    "title": data.get("title", ""),
                    "file": str(file.relative_to(self.project_path)),
                })
        
        return sorted(outlines, key=lambda x: (x["volume"], x["chapter"]))
    
    def list_chapters(self, volume: int = None) -> list:
        """列出正文章节"""
        if volume:
            pattern = f"06_正文/第{volume}卷/*.md"
        else:
            pattern = "06_正文/**/*.md"
        
        chapters = []
        for file in self.project_path.glob(pattern):
            chapters.append({
                "title": file.stem.split("_", 1)[-1] if "_" in file.stem else file.stem,
                "file": str(file.relative_to(self.project_path)),
                "size": file.stat().st_size,
            })
        
        return sorted(chapters, key=lambda x: x["title"])


def main():
    parser = argparse.ArgumentParser(description="小说项目管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 创建项目
    create_parser = subparsers.add_parser("create", help="创建新项目")
    create_parser.add_argument("title", help="小说标题")
    create_parser.add_argument("--path", help="项目路径", default=None)
    
    # 加载项目
    load_parser = subparsers.add_parser("load", help="加载项目")
    load_parser.add_argument("path", help="项目路径")
    
    # 状态
    status_parser = subparsers.add_parser("status", help="查看项目状态")
    status_parser.add_argument("path", help="项目路径")
    
    # 备份
    backup_parser = subparsers.add_parser("backup", help="创建备份")
    backup_parser.add_argument("path", help="项目路径")
    backup_parser.add_argument("--reason", help="备份原因", default="manual")
    
    # 导出
    export_parser = subparsers.add_parser("export", help="导出章节")
    export_parser.add_argument("path", help="项目路径")
    export_parser.add_argument("--volume", type=int, help="指定卷号")
    export_parser.add_argument("--output", help="输出文件")
    
    args = parser.parse_args()
    
    if args.command == "create":
        manager = NovelManager.create_project(args.title, args.path)
        print(json.dumps(manager.get_status(), indent=2, ensure_ascii=False))
    
    elif args.command == "load":
        manager = NovelManager.load_project(args.path)
        print(json.dumps(manager.get_status(), indent=2, ensure_ascii=False))
    
    elif args.command == "status":
        manager = NovelManager.load_project(args.path)
        status = manager.get_status()
        print(f"\n📚 {status['title']}")
        print(f"   状态: {status['status']}")
        print(f"   进度: {status['progress']}%")
        print(f"   字数: {status['total_words']:,}")
        print(f"   章节: {status['chapter_count']}")
        print(f"   细纲: {status['outline_count']}")
    
    elif args.command == "backup":
        manager = NovelManager.load_project(args.path)
        manager.create_backup(args.reason)
    
    elif args.command == "export":
        manager = NovelManager.load_project(args.path)
        content = manager.export_chapters(args.volume)
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ 已导出到: {args.output}")
        else:
            print(content)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
