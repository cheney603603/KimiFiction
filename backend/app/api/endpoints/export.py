"""
数据导出API
提供小说数据的导出功能
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import require_auth, get_current_user
from app.services.export_service import ExportService

router = APIRouter()


@router.get("/novel/{novel_id}/txt")
async def export_txt(
    novel_id: int,
    include_toc: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """导出小说为TXT格式"""
    service = ExportService(db)
    
    try:
        content = await service.export_to_txt(novel_id, include_toc)
        
        # 获取小说标题作为文件名
        from app.services.novel_service import NovelService
        novel_service = NovelService(db)
        novel = await novel_service.get_novel(novel_id)
        filename = f"{novel.title if novel else 'novel'}.txt"
        
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/novel/{novel_id}/markdown")
async def export_markdown(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """导出小说为Markdown格式"""
    service = ExportService(db)
    
    try:
        content = await service.export_to_markdown(novel_id)
        
        from app.services.novel_service import NovelService
        novel_service = NovelService(db)
        novel = await novel_service.get_novel(novel_id)
        filename = f"{novel.title if novel else 'novel'}.md"
        
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/novel/{novel_id}/json")
async def export_json(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """导出小说为JSON格式（完整数据）"""
    service = ExportService(db)
    
    try:
        data = await service.export_to_json(novel_id)
        
        from app.services.novel_service import NovelService
        novel_service = NovelService(db)
        novel = await novel_service.get_novel(novel_id)
        filename = f"{novel.title if novel else 'novel'}.json"
        
        import json
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/novel/{novel_id}/characters")
async def export_characters(
    novel_id: int,
    format: str = "markdown",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """导出角色设定"""
    service = ExportService(db)
    
    try:
        content = await service.export_characters(novel_id, format)
        
        from app.services.novel_service import NovelService
        novel_service = NovelService(db)
        novel = await novel_service.get_novel(novel_id)
        
        if format == "json":
            filename = f"{novel.title if novel else 'novel'}_characters.json"
            media_type = "application/json; charset=utf-8"
        else:
            filename = f"{novel.title if novel else 'novel'}_characters.md"
            media_type = "text/markdown; charset=utf-8"
        
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/novel/{novel_id}/outline")
async def export_outline(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """导出大纲"""
    service = ExportService(db)
    
    try:
        content = await service.export_outline(novel_id)
        
        from app.services.novel_service import NovelService
        novel_service = NovelService(db)
        novel = await novel_service.get_novel(novel_id)
        filename = f"{novel.title if novel else 'novel'}_outline.md"
        
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/novel/{novel_id}/epub")
async def export_epub(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """导出小说为EPUB格式（电子书）"""
    service = ExportService(db)
    
    try:
        # 获取小说标题作为文件名
        from app.services.novel_service import NovelService
        novel_service = NovelService(db)
        novel = await novel_service.get_novel(novel_id)
        
        # 导出EPUB
        epub_path = await service.export_to_epub(novel_id)
        
        filename = f"{novel.title if novel else 'novel'}.epub"
        
        return FileResponse(
            epub_path,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"EPUB导出失败: {str(e)}")


@router.get("/reference/{filename}")
async def get_reference_file(
    filename: str,
    current_user = Depends(get_current_user)
):
    """读取 reference 目录下的参考小说文件"""
    from pathlib import Path
    from fastapi.responses import FileResponse

    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_dir = backend_dir.parent
    ref_file = project_dir / "reference" / filename

    if not ref_file.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    return FileResponse(
        ref_file,
        media_type="text/plain; charset=utf-8",
        filename=filename,
    )
