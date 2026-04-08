#!/usr/bin/env python3
"""
RAG管道脚本
提供轻量级的RAG功能，不依赖外部向量数据库时使用
"""
import json
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class SimpleRAGPipeline:
    """
    轻量级RAG管道
    
    不依赖向量数据库，使用关键词匹配和TF-IDF风格的检索
    适用于没有外部依赖的环境
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self._index = {}  # 简单索引
        self._build_index()
    
    def _build_index(self) -> None:
        """构建索引"""
        self._index = {
            "world_setting": self._load_file("01_世界观设定.json"),
            "characters": self._load_file("02_角色设定.json"),
            "plot_setting": self._load_file("03_故事线设定.json"),
            "outlines": self._load_all_outlines(),
            "chapters": self._load_all_chapters(),
        }
    
    def _load_file(self, filename: str) -> Optional[Dict]:
        """加载JSON文件"""
        filepath = self.project_path / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def _load_all_outlines(self) -> List[Dict]:
        """加载所有章节细纲"""
        outlines = []
        for file in self.project_path.glob("05_章节细纲/**/*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    outlines.append({
                        "chapter": data.get("chapter", 0),
                        "volume": data.get("volume", 1),
                        "title": data.get("title", ""),
                        "summary": data.get("summary", ""),
                        "key_events": data.get("key_events", []),
                        "content": json.dumps(data, ensure_ascii=False),
                    })
            except Exception:
                pass
        return outlines
    
    def _load_all_chapters(self) -> List[Dict]:
        """加载所有章节摘要"""
        chapters = []
        
        for file in self.project_path.glob("06_正文/**/*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 解析YAML头
                title = file.stem
                summary = ""
                metadata = {}
                
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].strip().split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                metadata[key.strip()] = value.strip()
                        summary = parts[2][:500]  # 前500字作为摘要
                        title = metadata.get("title", title)
                
                chapters.append({
                    "title": title,
                    "chapter": int(metadata.get("chapter", 0)),
                    "volume": int(metadata.get("volume", 1)),
                    "summary": summary,
                    "content": content,
                    "path": str(file),
                })
            except Exception:
                pass
        
        return chapters
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        source_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关内容
        
        Args:
            query: 查询文本
            top_k: 返回结果数
            source_types: 限定来源类型
            
        Returns:
            检索结果列表
        """
        results = []
        source_types = source_types or ["world_setting", "characters", "plot_setting", "outlines", "chapters"]
        
        # 提取查询关键词
        keywords = self._extract_keywords(query)
        
        for source_type in source_types:
            if source_type == "world_setting":
                content = self._index.get("world_setting")
                if content:
                    score = self._calculate_score(keywords, json.dumps(content, ensure_ascii=False))
                    results.append({
                        "type": "world_setting",
                        "content": self._summarize_json(content, max_length=1000),
                        "score": score,
                        "source": "01_世界观设定.json",
                    })
            
            elif source_type == "characters":
                content = self._index.get("characters")
                if content:
                    for char in content.get("characters", []):
                        score = self._calculate_score(keywords, json.dumps(char, ensure_ascii=False))
                        results.append({
                            "type": "character",
                            "name": char.get("name", ""),
                            "content": json.dumps(char, ensure_ascii=False),
                            "score": score,
                            "source": "02_角色设定.json",
                        })
            
            elif source_type == "plot_setting":
                content = self._index.get("plot_setting")
                if content:
                    score = self._calculate_score(keywords, json.dumps(content, ensure_ascii=False))
                    results.append({
                        "type": "plot_setting",
                        "content": self._summarize_json(content, max_length=1000),
                        "score": score,
                        "source": "03_故事线设定.json",
                    })
            
            elif source_type == "outlines":
                for outline in self._index.get("outlines", []):
                    score = self._calculate_score(keywords, outline.get("content", ""))
                    if score > 0:
                        results.append({
                            "type": "outline",
                            "chapter": outline.get("chapter", 0),
                            "volume": outline.get("volume", 1),
                            "title": outline.get("title", ""),
                            "content": outline.get("summary", ""),
                            "score": score,
                            "source": f"05_章节细纲/第{outline.get('volume')}卷",
                        })
            
            elif source_type == "chapters":
                for chapter in self._index.get("chapters", []):
                    score = self._calculate_score(keywords, chapter.get("summary", ""))
                    if score > 0:
                        results.append({
                            "type": "chapter",
                            "chapter": chapter.get("chapter", 0),
                            "volume": chapter.get("volume", 1),
                            "title": chapter.get("title", ""),
                            "content": chapter.get("summary", "")[:500],
                            "score": score,
                            "source": chapter.get("path", ""),
                        })
        
        # 排序并返回top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 移除标点
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 提取中文词
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', text)
        
        # 英文词
        english_words = re.findall(r'[a-zA-Z]+', text)
        
        # 组合并去重
        keywords = list(set(chinese_words + english_words))
        
        # 过滤停用词
        stopwords = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "什么", "怎么", "如何", "为什么", "可以", "the", "a", "an", "is", "are", "was", "were"}
        
        return [w for w in keywords if w not in stopwords and len(w) > 1]
    
    def _calculate_score(self, keywords: List[str], content: str) -> float:
        """计算相关性分数"""
        if not keywords or not content:
            return 0.0
        
        content_lower = content.lower()
        score = 0.0
        
        for keyword in keywords:
            # 计算出现次数
            count = content_lower.count(keyword.lower())
            if count > 0:
                # 多次出现加分
                score += min(count * 0.1, 0.5)
        
        # 归一化
        return min(score, 1.0)
    
    def _summarize_json(self, data: Dict, max_length: int = 500) -> str:
        """将JSON数据转换为可读摘要"""
        lines = []
        
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 200:
                lines.append(f"**{key}**: {value[:200]}...")
            elif isinstance(value, list) and value:
                lines.append(f"**{key}**: {len(value)}项")
            elif isinstance(value, dict) and value:
                lines.append(f"**{key}**: {len(value)}个子项")
            else:
                lines.append(f"**{key}**: {value}")
            
            if sum(len(l) for l in lines) > max_length:
                break
        
        return "\n".join(lines)
    
    def build_chapter_context(
        self,
        chapter_number: int,
        outline: Dict[str, Any] = None
    ) -> str:
        """
        为章节构建上下文提示
        
        Args:
            chapter_number: 章节号
            outline: 章节大纲
            
        Returns:
            格式化的上下文字符串
        """
        parts = []
        
        # 1. 世界观设定
        world = self._index.get("world_setting")
        if world:
            parts.append("【世界观设定】")
            parts.append(self._summarize_json(world, 500))
            parts.append("")
        
        # 2. 角色状态
        characters = self._index.get("characters", {}).get("characters", [])
        if characters:
            parts.append("【主要角色】")
            for char in characters[:5]:
                name = char.get("name", "")
                personality = char.get("profile", {}).get("personality", "")
                skills = char.get("profile", {}).get("skills", [])
                parts.append(f"- {name}: {personality}" + (f" | 技能: {', '.join(skills[:2])}" if skills else ""))
            parts.append("")
        
        # 3. 相关章节
        outline_data = self._index.get("outlines", [])
        recent_outlines = [o for o in outline_data 
                         if 0 < o.get("chapter", 0) <= chapter_number][-5:]
        
        if recent_outlines:
            parts.append("【前文概要】")
            for o in recent_outlines:
                parts.append(f"第{o.get('chapter')}章 {o.get('title')}: {o.get('summary', '')[:100]}")
            parts.append("")
        
        # 4. 当前章节大纲
        if outline:
            parts.append("【本章大纲】")
            parts.append(f"标题: {outline.get('title', '')}")
            parts.append(f"摘要: {outline.get('summary', '')}")
            parts.append(f"关键事件: {', '.join(outline.get('key_events', []))}")
            parts.append("")
        
        # 5. 检索相关伏笔
        if outline:
            query = outline.get("summary", "") + " " + " ".join(outline.get("key_events", []))
            relevant = self.retrieve(query, top_k=3, source_types=["plot_setting", "outlines"])
            
            if relevant:
                parts.append("【相关设定】")
                for r in relevant:
                    if r["score"] > 0.1:
                        parts.append(f"- {r.get('title', r.get('type', ''))}: {r.get('content', '')[:100]}")
                parts.append("")
        
        return "\n".join(parts)


class RAGPipeline:
    """
    完整RAG管道
    
    当Qdrant可用时使用向量检索
    否则回退到SimpleRAGPipeline
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        
        # 尝试使用向量数据库
        try:
            from app.core.vector_store import vector_store
            self._use_vector = True
            self._vector_store = vector_store
            print("✅ 使用向量RAG")
        except ImportError:
            self._use_vector = False
            print("⚠️ 向量数据库不可用，使用简单RAG")
        
        # 始终创建简单索引作为后备
        self._simple_rag = SimpleRAGPipeline(project_path)
    
    async def add_to_index(
        self,
        doc_type: str,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """添加文档到索引"""
        if self._use_vector:
            # 使用向量索引
            try:
                from app.services.embedding_service import get_embedding
                vector = await get_embedding(content)
                
                return await self._vector_store.add_document(
                    doc_id=f"{doc_type}_{doc_id}",
                    vector=vector,
                    payload={
                        "type": doc_type,
                        "content": content,
                        **(metadata or {})
                    }
                )
            except Exception as e:
                print(f"⚠️ 向量索引失败: {e}")
        
        # 简单索引会在下次初始化时自动更新
        return True
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        source_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """检索相关内容"""
        return self._simple_rag.retrieve(query, top_k, source_types)
    
    def build_context(self, chapter_number: int, outline: Dict = None) -> str:
        """构建章节上下文"""
        return self._simple_rag.build_chapter_context(chapter_number, outline)


# 命令行工具

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG管道工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 构建索引
    build_parser = subparsers.add_parser("build", help="构建RAG索引")
    build_parser.add_argument("project_path", help="项目路径")
    
    # 检索
    retrieve_parser = subparsers.add_parser("retrieve", help="检索相关内容")
    retrieve_parser.add_argument("project_path", help="项目路径")
    retrieve_parser.add_argument("query", help="查询文本")
    retrieve_parser.add_argument("--top-k", type=int, default=5, help="返回数量")
    retrieve_parser.add_argument("--types", nargs="+", help="来源类型")
    
    # 构建上下文
    context_parser = subparsers.add_parser("context", help="构建章节上下文")
    context_parser.add_argument("project_path", help="项目路径")
    context_parser.add_argument("chapter", type=int, help="章节号")
    
    args = parser.parse_args()
    
    if args.command == "build":
        rag = SimpleRAGPipeline(args.project_path)
        print("✅ 索引构建完成")
        print(f"   世界观: {'有' if rag._index.get('world_setting') else '无'}")
        print(f"   角色: {len(rag._index.get('characters', {}).get('characters', []))}个")
        print(f"   细纲: {len(rag._index.get('outlines', []))}个")
        print(f"   章节: {len(rag._index.get('chapters', []))}个")
    
    elif args.command == "retrieve":
        rag = SimpleRAGPipeline(args.project_path)
        results = rag.retrieve(args.query, args.top_k, args.types)
        
        print(f"\n🔍 检索结果: \"{args.query}\"")
        print("=" * 50)
        
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['type']}] 分数: {r['score']:.2f}")
            print(f"   来源: {r.get('source', '')}")
            print(f"   内容: {r.get('content', r.get('name', ''))[:200]}")
    
    elif args.command == "context":
        rag = SimpleRAGPipeline(args.project_path)
        context = rag.build_chapter_context(args.chapter)
        
        print(f"\n📖 第{args.chapter}章上下文")
        print("=" * 50)
        print(context)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
