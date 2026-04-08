"""
结构化文件管理器
统一管理小说项目的文件存取
"""
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterator
from datetime import datetime
from dataclasses import dataclass, asdict
from loguru import logger

from app.core.config import settings


@dataclass
class FileMetadata:
    """文件元数据"""
    path: str
    created_at: datetime
    modified_at: datetime
    size: int
    version: int = 1


@dataclass
class NovelProject:
    """小说项目"""
    project_id: str
    title: str
    created_at: datetime
    metadata: Dict[str, Any]
    root_path: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "root_path": self.root_path,
        }


class NovelFileManager:
    """
    小说项目文件管理器
    
    负责：
    1. 规范化小说项目目录结构
    2. 读写结构化文件（JSON/YAML）
    3. 版本管理和历史记录
    4. 文件操作事务性保证
    """
    
    # 标准目录结构
    DIR_STRUCTURE = {
        "metadata": "metadata.json",
        "demand_analysis": "00_作品设定.json",
        "world_setting": "01_世界观设定.json",
        "characters": "02_角色设定.json",
        "plot_setting": "03_故事线设定.json",
        "outline": "04_分卷大纲",
        "chapter_outlines": "05_章节细纲",
        "chapters": "06_正文",
        "history": ".novel_history",
    }
    
    def __init__(self, project_path: str):
        """
        初始化文件管理器
        
        Args:
            project_path: 项目根目录路径
        """
        self.project_path = Path(project_path)
        self.project_id = self.project_path.name
        self._ensure_structure()
    
    @classmethod
    def create_project(cls, title: str, base_path: Optional[str] = None) -> "NovelFileManager":
        """
        创建新小说项目
        
        Args:
            title: 小说标题
            base_path: 基础路径，默认使用配置中的小说目录
        """
        if base_path is None:
            base_path = settings.NOVEL_PROJECTS_PATH or os.path.join(os.getcwd(), "novels")
        
        # 创建项目目录
        project_id = cls._generate_project_id(title)
        project_path = Path(base_path) / project_id
        
        if project_path.exists():
            raise ValueError(f"项目已存在: {project_id}")
        
        project_path.mkdir(parents=True, exist_ok=True)
        
        # 创建标准目录结构
        manager = cls(str(project_path))
        manager._ensure_structure()
        
        # 初始化元数据
        manager.save_metadata({
            "title": title,
            "project_id": project_id,
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
        })
        
        logger.info(f"创建小说项目: {project_id} at {project_path}")
        return manager
    
    @classmethod
    def load_project(cls, project_id: str, base_path: Optional[str] = None) -> "NovelFileManager":
        """加载已有项目"""
        if base_path is None:
            base_path = settings.NOVEL_PROJECTS_PATH or os.path.join(os.getcwd(), "novels")
        
        project_path = Path(base_path) / project_id
        
        if not project_path.exists():
            raise FileNotFoundError(f"项目不存在: {project_id}")
        
        return cls(str(project_path))
    
    @staticmethod
    def _generate_project_id(title: str) -> str:
        """生成项目ID"""
        import hashlib
        import time
        
        # 使用标题+时间戳生成唯一ID
        raw = f"{title}_{time.time()}"
        hash_id = hashlib.md5(raw.encode()).hexdigest()[:8]
        
        # 清理标题用于目录名
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        safe_title = safe_title[:20].strip()
        
        return f"{safe_title}_{hash_id}"
    
    def _ensure_structure(self) -> None:
        """确保目录结构存在"""
        self.project_path.mkdir(parents=True, exist_ok=True)
        
        # 创建标准子目录
        for key, value in self.DIR_STRUCTURE.items():
            if "/" in value:
                # 子目录
                dir_path = self.project_path / value.split("/")[0]
                dir_path.mkdir(parents=True, exist_ok=True)
            elif "." in value:
                # 文件，不需要创建
                pass
            else:
                # 目录
                dir_path = self.project_path / value
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # 创建历史目录
        history_path = self.project_path / ".novel_history" / "revisions"
        history_path.mkdir(parents=True, exist_ok=True)
    
    # ===== 元数据操作 =====
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取项目元数据"""
        return self._read_json("metadata.json")
    
    def save_metadata(self, metadata: Dict[str, Any]) -> None:
        """保存项目元数据"""
        self._write_json("metadata.json", metadata)
    
    def get_project_info(self) -> NovelProject:
        """获取项目信息"""
        metadata = self.get_metadata()
        return NovelProject(
            project_id=self.project_id,
            title=metadata.get("title", ""),
            created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
            metadata=metadata,
            root_path=str(self.project_path),
        )
    
    # ===== 结构化文件操作 =====
    
    def save_demand_analysis(self, data: Dict[str, Any]) -> None:
        """保存需求分析结果"""
        self._write_json(self.DIR_STRUCTURE["demand_analysis"], {
            **data,
            "saved_at": datetime.now().isoformat(),
        })
    
    def get_demand_analysis(self) -> Dict[str, Any]:
        """获取需求分析结果"""
        return self._read_json(self.DIR_STRUCTURE["demand_analysis"])
    
    def save_world_setting(self, data: Dict[str, Any]) -> None:
        """保存世界观设定"""
        self._write_json(self.DIR_STRUCTURE["world_setting"], {
            **data,
            "saved_at": datetime.now().isoformat(),
        })
    
    def get_world_setting(self) -> Dict[str, Any]:
        """获取世界观设定"""
        return self._read_json(self.DIR_STRUCTURE["world_setting"])
    
    def save_characters(self, characters: List[Dict[str, Any]]) -> None:
        """保存角色设定"""
        self._write_json(self.DIR_STRUCTURE["characters"], {
            "characters": characters,
            "count": len(characters),
            "saved_at": datetime.now().isoformat(),
        })
    
    def get_characters(self) -> List[Dict[str, Any]]:
        """获取角色设定"""
        data = self._read_json(self.DIR_STRUCTURE["characters"])
        return data.get("characters", [])
    
    def save_plot_setting(self, data: Dict[str, Any]) -> None:
        """保存故事线设定（冲突、伏笔等）"""
        self._write_json(self.DIR_STRUCTURE["plot_setting"], {
            **data,
            "saved_at": datetime.now().isoformat(),
        })
    
    def get_plot_setting(self) -> Dict[str, Any]:
        """获取故事线设定"""
        return self._read_json(self.DIR_STRUCTURE["plot_setting"])
    
    # ===== 大纲操作 =====
    
    def save_outline(self, outline: Dict[str, Any]) -> None:
        """保存分卷大纲"""
        # 保存整体大纲
        self._write_json("04_分卷大纲/大纲总览.json", {
            **outline,
            "saved_at": datetime.now().isoformat(),
        })
        
        # 保存各卷单独文件
        for volume in outline.get("volumes", []):
            volume_num = volume.get("volume_number", 1)
            volume_title = volume.get("title", f"第{volume_num}卷")
            safe_title = self._sanitize_filename(volume_title)
            filename = f"04_分卷大纲/第{volume_num}卷_{safe_title}.json"
            self._write_json(filename, {
                **volume,
                "saved_at": datetime.now().isoformat(),
            })
    
    def get_outline(self) -> Dict[str, Any]:
        """获取分卷大纲"""
        return self._read_json("04_分卷大纲/大纲总览.json")
    
    def get_volume_outline(self, volume_number: int) -> Dict[str, Any]:
        """获取指定卷的大纲"""
        # 尝试从总览获取
        outline = self.get_outline()
        for vol in outline.get("volumes", []):
            if vol.get("volume_number") == volume_number:
                return vol
        
        # 尝试直接读取文件
        filename = f"04_分卷大纲/第{volume_number}卷.json"
        return self._read_json(filename)
    
    # ===== 章节细纲操作 =====
    
    def save_chapter_outline(
        self,
        volume_number: int,
        chapter_number: int,
        outline: Dict[str, Any]
    ) -> None:
        """保存章节细纲"""
        safe_title = self._sanitize_filename(outline.get("title", ""))
        filename = f"05_章节细纲/第{volume_number}卷/第{chapter_number:03d}章_{safe_title}.json"
        
        self._write_json(filename, {
            **outline,
            "volume_number": volume_number,
            "chapter_number": chapter_number,
            "saved_at": datetime.now().isoformat(),
        })
    
    def get_chapter_outline(
        self,
        volume_number: int,
        chapter_number: int
    ) -> Optional[Dict[str, Any]]:
        """获取章节细纲"""
        # 尝试多个可能的文件名
        for pattern in [
            f"05_章节细纲/第{volume_number}卷/第{chapter_number:03d}章_*.json",
        ]:
            matches = list(self.project_path.glob(pattern))
            if matches:
                return self._read_json(str(matches[0].relative_to(self.project_path)))
        
        return None
    
    def get_all_chapter_outlines(self, volume_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有章节细纲"""
        if volume_number:
            pattern = f"05_章节细纲/第{volume_number}卷/*.json"
        else:
            pattern = "05_章节细纲/**/*.json"
        
        outlines = []
        for filepath in self.project_path.glob(pattern):
            try:
                data = self._read_json(str(filepath.relative_to(self.project_path)))
                outlines.append(data)
            except Exception as e:
                logger.warning(f"读取细纲失败: {filepath}, error={e}")
        
        # 按章节号排序
        outlines.sort(key=lambda x: x.get("chapter_number", 0))
        return outlines
    
    # ===== 正文操作 =====
    
    def save_chapter(
        self,
        volume_number: int,
        chapter_number: int,
        content: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        保存章节正文
        
        Args:
            volume_number: 卷号
            chapter_number: 章节号
            content: 正文内容
            title: 章节标题
            metadata: 额外元数据
            
        Returns:
            文件路径
        """
        # 确定文件名
        if not title:
            title = f"第{chapter_number}章"
        
        safe_title = self._sanitize_filename(title)
        filename = f"06_正文/第{volume_number}卷/第{chapter_number:03d}章_{safe_title}.md"
        
        # 构建文件内容（包含元数据头）
        full_content = self._build_chapter_content(
            volume_number,
            chapter_number,
            title,
            content,
            metadata
        )
        
        self._write_text(filename, full_content)
        
        return filename
    
    def _build_chapter_content(
        self,
        volume_number: int,
        chapter_number: int,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """构建章节文件内容"""
        lines = [
            "---",
            f"title: {title}",
            f"volume: {volume_number}",
            f"chapter: {chapter_number}",
            f"generated_at: {datetime.now().isoformat()}",
        ]
        
        if metadata:
            for key, value in metadata.items():
                lines.append(f"{key}: {value}")
        
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(content)
        
        return "\n".join(lines)
    
    def get_chapter(
        self,
        volume_number: int,
        chapter_number: int
    ) -> Optional[Dict[str, Any]]:
        """获取章节正文"""
        # 查找文件
        for filepath in self.project_path.glob(f"06_正文/第{volume_number}卷/第{chapter_number:03d}章_*.md"):
            content = self._read_text(str(filepath.relative_to(self.project_path)))
            return self._parse_chapter_content(content, str(filepath.name))
        
        return None
    
    def _parse_chapter_content(self, content: str, filename: str) -> Dict[str, Any]:
        """解析章节文件内容"""
        result = {
            "filename": filename,
            "title": filename,
            "content": content,
            "metadata": {},
        }
        
        # 解析YAML头部
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                import yaml
                try:
                    metadata = yaml.safe_load(parts[1])
                    if metadata:
                        result["metadata"] = metadata
                        result["title"] = metadata.get("title", result["title"])
                        result["volume"] = metadata.get("volume")
                        result["chapter"] = metadata.get("chapter")
                    result["content"] = parts[2].strip()
                    # 移除标题行
                    lines = result["content"].split("\n")
                    if lines and lines[0].startswith("# "):
                        result["content"] = "\n".join(lines[2:])
                except:
                    pass
        
        return result
    
    def get_all_chapters(self, volume_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有章节"""
        if volume_number:
            pattern = f"06_正文/第{volume_number}卷/*.md"
        else:
            pattern = "06_正文/**/*.md"
        
        chapters = []
        for filepath in self.project_path.glob(pattern):
            try:
                content = self._read_text(str(filepath.relative_to(self.project_path)))
                chapter = self._parse_chapter_content(content, str(filepath.name))
                chapters.append(chapter)
            except Exception as e:
                logger.warning(f"读取章节失败: {filepath}, error={e}")
        
        chapters.sort(key=lambda x: (
            x.get("metadata", {}).get("volume", 0),
            x.get("metadata", {}).get("chapter", 0)
        ))
        return chapters
    
    # ===== 历史版本 =====
    
    def save_revision(
        self,
        file_path: str,
        revision_type: str = "auto"
    ) -> str:
        """
        保存文件的历史版本
        
        Args:
            file_path: 原文件路径（相对于项目根目录）
            revision_type: 修订类型 ("auto" | "manual" | "feedback")
            
        Returns:
            历史文件路径
        """
        if not self.project_path.joinpath(file_path).exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 创建历史文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_filename = f"{Path(file_path).stem}_{timestamp}_{revision_type}{Path(file_path).suffix}"
        history_path = f".novel_history/revisions/{history_filename}"
        
        # 复制文件
        src = self.project_path / file_path
        dst = self.project_path / history_path
        shutil.copy2(src, dst)
        
        logger.info(f"保存历史版本: {file_path} -> {history_path}")
        return history_path
    
    def get_revisions(self, file_path: str) -> List[Dict[str, Any]]:
        """获取文件的所有历史版本"""
        stem = Path(file_path).stem
        pattern = f".novel_history/revisions/{stem}_*.{Path(file_path).suffix[1:]}"
        
        revisions = []
        for filepath in self.project_path.glob(pattern):
            stat = filepath.stat()
            revisions.append({
                "path": str(filepath.relative_to(self.project_path)),
                "filename": filepath.name,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "size": stat.st_size,
            })
        
        revisions.sort(key=lambda x: x["created_at"], reverse=True)
        return revisions
    
    def restore_revision(self, history_path: str, target_path: Optional[str] = None) -> None:
        """恢复历史版本"""
        if target_path is None:
            # 从历史路径推断原路径
            filename = Path(history_path).name
            parts = filename.rsplit("_", 3)
            if len(parts) >= 4:
                target_path = parts[0] + Path(history_path).suffix
        
        src = self.project_path / history_path
        dst = self.project_path / (target_path or history_path)
        
        shutil.copy2(src, dst)
        logger.info(f"恢复历史版本: {history_path} -> {target_path}")
    
    # ===== 导出功能 =====
    
    def export_all_chapters(
        self,
        volume_number: Optional[int] = None,
        format: str = "markdown"
    ) -> str:
        """
        导出所有章节
        
        Args:
            volume_number: 指定卷号，None表示全部
            format: 输出格式 ("markdown" | "text")
            
        Returns:
            导出文件内容
        """
        chapters = self.get_all_chapters(volume_number)
        
        if format == "markdown":
            return self._export_markdown(chapters)
        else:
            return self._export_text(chapters)
    
    def _export_markdown(self, chapters: List[Dict[str, Any]]) -> str:
        """导出为Markdown"""
        parts = []
        
        for chapter in chapters:
            metadata = chapter.get("metadata", {})
            title = metadata.get("title", chapter.get("title", ""))
            volume = metadata.get("volume", "")
            
            if volume:
                parts.append(f"\n\n# 第{volume}卷\n")
            
            parts.append(f"\n## {title}\n")
            parts.append(chapter.get("content", ""))
        
        return "\n".join(parts)
    
    def _export_text(self, chapters: List[Dict[str, Any]]) -> str:
        """导出为纯文本"""
        parts = []
        
        for chapter in chapters:
            metadata = chapter.get("metadata", {})
            title = metadata.get("title", chapter.get("title", ""))
            volume = metadata.get("volume", "")
            
            if volume:
                parts.append(f"\n\n{'='*40}\n第{volume}卷\n{'='*40}\n")
            
            parts.append(f"\n{title}\n{'-'*len(title)}\n")
            parts.append(chapter.get("content", ""))
        
        return "\n".join(parts)
    
    # ===== 内部工具方法 =====
    
    def _read_json(self, relative_path: str) -> Dict[str, Any]:
        """读取JSON文件"""
        filepath = self.project_path / relative_path
        if not filepath.exists():
            return {}
        
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _write_json(self, relative_path: str, data: Dict[str, Any]) -> None:
        """写入JSON文件"""
        filepath = self.project_path / relative_path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _read_text(self, relative_path: str) -> str:
        """读取文本文件"""
        filepath = self.project_path / relative_path
        if not filepath.exists():
            return ""
        
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    
    def _write_text(self, relative_path: str, content: str) -> None:
        """写入文本文件"""
        filepath = self.project_path / relative_path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名"""
        # 移除或替换非法字符
        import re
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = name[:50]  # 限制长度
        return name.strip()


# ===== 项目列表管理 =====

class ProjectRegistry:
    """项目注册表"""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or settings.NOVEL_PROJECTS_PATH or os.path.join(os.getcwd(), "novels"))
    
    def list_projects(self) -> List[NovelProject]:
        """列出所有项目"""
        projects = []
        
        if not self.base_path.exists():
            return projects
        
        for item in self.base_path.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                try:
                    manager = NovelFileManager(str(item))
                    projects.append(manager.get_project_info())
                except Exception as e:
                    logger.warning(f"加载项目失败: {item}, error={e}")
        
        projects.sort(key=lambda x: x.created_at, reverse=True)
        return projects
    
    def get_project(self, project_id: str) -> NovelFileManager:
        """获取项目管理器"""
        return NovelFileManager.load_project(project_id, str(self.base_path))
    
    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        project_path = self.base_path / project_id
        
        if project_path.exists():
            shutil.rmtree(project_path)
            logger.info(f"删除项目: {project_id}")
            return True
        
        return False
