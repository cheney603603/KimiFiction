"""
数据导出服务
提供小说数据的导出功能（TXT、Markdown、EPUB等格式）
"""
import json
import zipfile
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.novel import Novel
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.outline import Outline


class ExportService:
    """导出服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def export_to_txt(self, novel_id: int, include_toc: bool = True) -> str:
        """
        导出为TXT格式
        
        Args:
            novel_id: 小说ID
            include_toc: 是否包含目录
            
        Returns:
            TXT内容
        """
        # 获取小说信息
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        
        if not novel:
            raise ValueError("小说不存在")
        
        # 获取所有章节
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number.asc())
        )
        chapters = chapters_result.scalars().all()
        
        lines = []
        
        # 标题
        lines.append(f"《{novel.title}》")
        lines.append("")
        
        if novel.genre:
            lines.append(f"类型：{novel.genre}")
        
        lines.append(f"总章节数：{len(chapters)}")
        lines.append(f"总字数：{novel.total_words}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("")
        
        # 目录
        if include_toc and chapters:
            lines.append("目录")
            lines.append("")
            for ch in chapters:
                lines.append(f"第{ch.chapter_number}章 {ch.title}")
            lines.append("")
            lines.append("=" * 50)
            lines.append("")
        
        # 章节内容
        for ch in chapters:
            lines.append(f"第{ch.chapter_number}章 {ch.title}")
            lines.append("")
            lines.append(ch.content)
            lines.append("")
            lines.append("=" * 50)
            lines.append("")
        
        return "\n".join(lines)
    
    async def export_to_markdown(self, novel_id: int) -> str:
        """
        导出为Markdown格式
        
        Args:
            novel_id: 小说ID
            
        Returns:
            Markdown内容
        """
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        
        if not novel:
            raise ValueError("小说不存在")
        
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number.asc())
        )
        chapters = chapters_result.scalars().all()
        
        lines = []
        
        # 标题和元数据
        lines.append(f"# {novel.title}")
        lines.append("")
        
        if novel.genre:
            lines.append(f"**类型：** {novel.genre}")
        
        lines.append(f"**总章节数：** {len(chapters)}")
        lines.append(f"**总字数：** {novel.total_words:,}")
        lines.append(f"**导出时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 目录
        lines.append("## 目录")
        lines.append("")
        for ch in chapters:
            lines.append(f"- [第{ch.chapter_number}章 {ch.title}](#chapter-{ch.chapter_number})")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 章节内容
        for ch in chapters:
            lines.append(f"<a id='chapter-{ch.chapter_number}'></a>")
            lines.append(f"## 第{ch.chapter_number}章 {ch.title}")
            lines.append("")
            
            # 将内容转换为Markdown段落
            paragraphs = ch.content.split('\n')
            for p in paragraphs:
                if p.strip():
                    lines.append(p)
                    lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    async def export_to_json(self, novel_id: int) -> dict:
        """
        导出为JSON格式（包含完整数据）
        
        Args:
            novel_id: 小说ID
            
        Returns:
            JSON数据
        """
        # 获取小说
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        
        if not novel:
            raise ValueError("小说不存在")
        
        # 获取章节
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number.asc())
        )
        chapters = chapters_result.scalars().all()
        
        # 获取角色
        characters_result = await self.db.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        characters = characters_result.scalars().all()
        
        # 获取大纲
        outlines_result = await self.db.execute(
            select(Outline)
            .where(Outline.novel_id == novel_id)
            .order_by(Outline.volume_number.asc())
        )
        outlines = outlines_result.scalars().all()
        
        return {
            "novel": {
                "id": novel.id,
                "title": novel.title,
                "genre": novel.genre,
                "style_prompt": novel.style_prompt,
                "total_chapters": novel.total_chapters,
                "total_words": novel.total_words,
                "status": novel.status.value,
                "created_at": novel.created_at.isoformat() if novel.created_at else None,
            },
            "chapters": [
                {
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "content": ch.content,
                    "summary": ch.summary,
                    "word_count": ch.word_count,
                }
                for ch in chapters
            ],
            "characters": [
                {
                    "name": char.name,
                    "role_type": char.role_type.value,
                    "profile": char.profile,
                    "first_appearance": char.first_appearance,
                }
                for char in characters
            ],
            "outlines": [
                {
                    "volume_number": o.volume_number,
                    "volume_title": o.volume_title,
                    "arcs": o.arcs,
                }
                for o in outlines
            ],
            "export_info": {
                "format": "json",
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
            }
        }
    
    async def export_characters(self, novel_id: int, format: str = "markdown") -> str:
        """
        导出角色设定
        
        Args:
            novel_id: 小说ID
            format: 导出格式（markdown/json）
            
        Returns:
            导出内容
        """
        characters_result = await self.db.execute(
            select(Character)
            .where(Character.novel_id == novel_id)
            .order_by(Character.role_type.asc(), Character.first_appearance.asc())
        )
        characters = characters_result.scalars().all()
        
        if format == "json":
            return json.dumps(
                [char.to_dict() for char in characters],
                ensure_ascii=False,
                indent=2
            )
        
        # Markdown格式
        lines = []
        lines.append("# 角色设定")
        lines.append("")
        
        role_type_names = {
            "protagonist": "主角",
            "antagonist": "反派",
            "supporting": "配角",
            "minor": "龙套",
        }
        
        for char in characters:
            lines.append(f"## {char.name}")
            lines.append("")
            lines.append(f"**类型：** {role_type_names.get(char.role_type.value, char.role_type.value)}")
            lines.append(f"**首次出场：** 第{char.first_appearance}章")
            lines.append(f"**出场次数：** {char.appearance_count}")
            lines.append("")
            
            if char.profile:
                lines.append("### 人设信息")
                lines.append("")
                for key, value in char.profile.items():
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value)
                    lines.append(f"- **{key}：** {value}")
                lines.append("")
            
            if char.current_status:
                lines.append("### 当前状态")
                lines.append("")
                lines.append(char.current_status)
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    async def export_outline(self, novel_id: int) -> str:
        """
        导出大纲
        
        Args:
            novel_id: 小说ID
            
        Returns:
            Markdown内容
        """
        outlines_result = await self.db.execute(
            select(Outline)
            .where(Outline.novel_id == novel_id)
            .order_by(Outline.volume_number.asc())
        )
        outlines = outlines_result.scalars().all()
        
        lines = []
        lines.append("# 剧情大纲")
        lines.append("")
        
        for outline in outlines:
            lines.append(f"## 第{outline.volume_number}卷：{outline.volume_title}")
            lines.append("")
            
            if outline.summary:
                lines.append(outline.summary)
                lines.append("")
            
            if outline.arcs:
                lines.append("### 剧情弧")
                lines.append("")
                for arc in outline.arcs:
                    lines.append(f"#### {arc.get('title', '未命名')}")
                    lines.append("")
                    lines.append(f"**章节范围：** 第{arc.get('start_chapter', '?')}-{arc.get('end_chapter', '?')}章")
                    lines.append("")
                    if arc.get('description'):
                        lines.append(arc['description'])
                        lines.append("")
                    if arc.get('key_events'):
                        lines.append("**关键事件：**")
                        for event in arc['key_events']:
                            lines.append(f"- {event}")
                        lines.append("")
                    lines.append("")
            
            if outline.key_points:
                lines.append("### 关键节点")
                lines.append("")
                lines.append(outline.key_points)
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)

    async def export_to_epub(self, novel_id: int, output_path: str = None) -> str:
        """
        导出为EPUB格式
        
        Args:
            novel_id: 小说ID
            output_path: 输出文件路径（可选，默认Temp目录）
            
        Returns:
            EPUB文件路径
        """
        import tempfile
        import shutil
        
        # 获取小说和章节数据
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        
        if not novel:
            raise ValueError("小说不存在")
        
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number.asc())
        )
        chapters = chapters_result.scalars().all()
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        epub_dir = Path(temp_dir) / "epub"
        epub_dir.mkdir()
        
        (epub_dir / "META-INF").mkdir()
        (epub_dir / "OEBPS").mkdir()
        
        # 清理小说标题中的非法字符
        safe_title = re.sub(r'[<>:"/\\|?*]', '', novel.title)
        
        # 1. 创建 container.xml
        container_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""
        (epub_dir / "META-INF" / "container.xml").write_text(container_xml, encoding="utf-8")
        
        # 2. 创建 NCX 目录文件
        ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="novel_{novel_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle>
        <text>{safe_title}</text>
    </docTitle>
    <navMap>
"""
        
        chapter_items = []
        for i, ch in enumerate(chapters):
            ncx_content += f"""        <navPoint id="navPoint-{i+1}" playOrder="{i+1}">
            <navLabel>
                <text>第{ch.chapter_number}章 {ch.title}</text>
            </navLabel>
            <content src="chapter_{ch.chapter_number}.xhtml"/>
        </navPoint>
"""
            chapter_items.append(f'<item id="chapter_{ch.chapter_number}" href="chapter_{ch.chapter_number}.xhtml" media-type="application/xhtml+xml"/>')
        
        ncx_content += """    </navMap>
</ncx>"""
        
        # 3. 创建 content.opf
        opf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{safe_title}</dc:title>
        <dc:language>zh-CN</dc:language>
        <dc:creator>KimiFiction</dc:creator>
        <dc:identifier id="bookid" opf:scheme="UUID">novel_{novel_id}</dc:identifier>
        <dc:description>由KimiFiction生成的小说</dc:description>
        <meta name="generator" content="KimiFiction"/>
    </metadata>
    <manifest>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
        <item id="nav" href="toc.xhtml" media-type="application/xhtml+xml"/>
"""
        opf_content += "\n".join(f"        {item}" for item in chapter_items)
        opf_content += """
    </metadata>
    <spine toc="ncx">
"""
        
        for i, ch in enumerate(chapters):
            opf_content += f'        <itemref idref="chapter_{ch.chapter_number}"/>\n'
        
        opf_content += """    </spine>
</package>"""
        
        (epub_dir / "OEBPS" / "content.opf").write_text(opf_content, encoding="utf-8")
        (epub_dir / "OEBPS" / "toc.ncx").write_text(ncx_content, encoding="utf-8")
        
        # 4. 创建导航文件 (toc.xhtml)
        toc_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>目录</title>
    <style>
        body {{ font-family: "SimSun", serif; margin: 5%; }}
        h1 {{ text-align: center; margin-bottom: 1em; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ margin: 0.5em 0; }}
        a {{ text-decoration: none; color: #333; }}
    </style>
</head>
<body>
    <h1>目录</h1>
    <ul>
"""
        for ch in chapters:
            toc_xhtml += f'        <li><a href="chapter_{ch.chapter_number}.xhtml">第{ch.chapter_number}章 {ch.title}</a></li>\n'
        
        toc_xhtml += """    </ul>
</body>
</html>"""
        (epub_dir / "OEBPS" / "toc.xhtml").write_text(toc_xhtml, encoding="utf-8")
        
        # 5. 创建各章节HTML
        for ch in chapters:
            chapter_html = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>第{ch.chapter_number}章 {ch.title}</title>
    <style>
        body {{ font-family: "SimSun", serif; margin: 5%; line-height: 1.6; }}
        h2 {{ text-align: center; margin-bottom: 1em; }}
        p {{ text-indent: 2em; margin: 0.5em 0; }}
    </style>
</head>
<body>
    <h2>第{ch.chapter_number}章 {ch.title}</h2>
"""
            
            # 将内容转换为HTML段落
            paragraphs = ch.content.split('\n')
            for p in paragraphs:
                if p.strip():
                    # 转义HTML特殊字符
                    p = p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    chapter_html += f"    <p>{p}</p>\n"
            
            chapter_html += """</body>
</html>"""
            (epub_dir / "OEBPS" / f"chapter_{ch.chapter_number}.xhtml").write_text(chapter_html, encoding="utf-8")
        
        # 6. 打包成EPUB
        if output_path is None:
            output_path = Path(tempfile.gettempdir()) / f"{safe_title}.epub"
        
        output_path = Path(output_path)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            # 添加container.xml
            epub_zip.write(epub_dir / "META-INF" / "container.xml", "META-INF/container.xml")
            
            # 添加OEBPS内容
            for file_path in (epub_dir / "OEBPS").rglob("*"):
                if file_path.is_file():
                    arcname = "OEBPS/" + file_path.name
                    epub_zip.write(file_path, arcname)
        
        # 清理临时目录
        shutil.rmtree(temp_dir)
        
        logger.info(f"EPUB导出完成: {output_path}")
        return str(output_path)
