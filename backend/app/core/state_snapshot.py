"""
状态快照系统 - 支持完整的系统状态回滚

核心功能：
1. 每次LLM调用前自动创建快照
2. 快照包含：文件状态、数据库状态、对话上下文
3. 支持按快照回滚整个系统
"""

import json
import hashlib
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from loguru import logger


class SnapshotType(str, Enum):
    """快照类型"""
    LLM_CALL = "llm_call"           # LLM调用前
    CHAPTER_START = "chapter_start" # 章节开始
    CHAPTER_END = "chapter_end"     # 章节完成
    MANUAL = "manual"               # 手动创建
    AUTO = "auto"                   # 自动定时


@dataclass
class LLMCallRecord:
    """LLM调用记录"""
    call_id: str
    timestamp: str
    agent_name: str
    model: str
    input_messages: List[Dict[str, Any]]
    output_content: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


@dataclass
class DatabaseState:
    """数据库状态摘要"""
    novel_id: int
    chapter_count: int
    entity_count: int
    latest_chapter_number: Optional[int]
    key_tables_hash: Dict[str, str]  # 关键表的哈希摘要


@dataclass
class FileState:
    """文件状态"""
    output_dir_hash: str  # output/novel_{id}/ 目录的哈希
    key_files: Dict[str, str]  # 关键文件路径 -> 哈希


@dataclass
class Snapshot:
    """完整状态快照"""
    snapshot_id: str
    novel_id: int
    type: SnapshotType
    created_at: str
    description: str
    
    # 各层状态
    llm_call: Optional[LLMCallRecord] = None
    database_state: Optional[DatabaseState] = None
    file_state: Optional[FileState] = None
    workflow_state: Optional[Dict[str, Any]] = None
    
    # Git信息
    git_commit: Optional[str] = None
    git_dirty_files: List[str] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        if data.get("llm_call"):
            data["llm_call"] = LLMCallRecord(**data["llm_call"])
        if data.get("database_state"):
            data["database_state"] = DatabaseState(**data["database_state"])
        if data.get("file_state"):
            data["file_state"] = FileState(**data["file_state"])
        return cls(**data)


class StateSnapshotManager:
    """状态快照管理器"""
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.snapshots_dir = self.project_root / "snapshots" / f"novel_{novel_id}"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件备份目录
        self.backup_dir = self.snapshots_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # 快照索引
        self.index_file = self.snapshots_dir / "snapshot_index.json"
    
    def _generate_id(self) -> str:
        """生成唯一快照ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        random_suffix = hashlib.md5(timestamp.encode()).hexdigest()[:6]
        return f"snap_{timestamp}_{random_suffix}"
    
    def _get_output_dir(self) -> Path:
        """获取小说输出目录"""
        return self.project_root / "output" / f"novel_{self.novel_id}"
    
    def _compute_dir_hash(self, dir_path: Path) -> str:
        """计算目录内容的哈希"""
        if not dir_path.exists():
            return ""
        
        files_hash = []
        for file_path in sorted(dir_path.rglob("*")):
            if file_path.is_file():
                try:
                    content = file_path.read_bytes()
                    files_hash.append(f"{file_path.relative_to(dir_path)}:{hashlib.md5(content).hexdigest()[:8]}")
                except Exception:
                    pass
        
        return hashlib.md5("|".join(files_hash).encode()).hexdigest()[:16]
    
    def _backup_files(self, snapshot_id: str) -> Path:
        """备份当前文件状态"""
        output_dir = self._get_output_dir()
        if not output_dir.exists():
            return None
        
        backup_path = self.backup_dir / snapshot_id
        if backup_path.exists():
            shutil.rmtree(backup_path)
        
        shutil.copytree(output_dir, backup_path)
        logger.info(f"[Snapshot] 文件备份完成: {backup_path}")
        return backup_path
    
    def _get_git_info(self) -> Tuple[Optional[str], List[str]]:
        """获取Git状态"""
        try:
            # 获取当前commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            commit = result.stdout.strip()
            
            # 获取未提交文件
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            dirty_files = [line[3:] for line in result.stdout.strip().split("\n") if line]
            
            return commit, dirty_files
        except Exception as e:
            logger.warning(f"[Snapshot] Git信息获取失败: {e}")
            return None, []
    
    async def _get_database_state(self) -> DatabaseState:
        """获取数据库状态摘要"""
        from app.core.database import get_session
        from app.models.chapter import Chapter
        from app.models.entity import Entity
        from sqlalchemy import select, func
        
        async with get_session() as db:
            # 章节数
            result = await db.execute(
                select(func.count()).where(Chapter.novel_id == self.novel_id)
            )
            chapter_count = result.scalar()
            
            # 实体数
            result = await db.execute(
                select(func.count()).where(Entity.novel_id == self.novel_id)
            )
            entity_count = result.scalar()
            
            # 最新章节
            result = await db.execute(
                select(Chapter.chapter_number)
                .where(Chapter.novel_id == self.novel_id)
                .order_by(Chapter.chapter_number.desc())
                .limit(1)
            )
            latest_chapter = result.scalar()
            
            # 关键表哈希（简化版）
            key_tables_hash = {
                "chapters": hashlib.md5(str(chapter_count).encode()).hexdigest()[:8],
                "entities": hashlib.md5(str(entity_count).encode()).hexdigest()[:8],
            }
            
            return DatabaseState(
                novel_id=self.novel_id,
                chapter_count=chapter_count,
                entity_count=entity_count,
                latest_chapter_number=latest_chapter,
                key_tables_hash=key_tables_hash
            )
    
    async def create_snapshot(
        self,
        snapshot_type: SnapshotType,
        description: str,
        llm_call: Optional[LLMCallRecord] = None,
        workflow_state: Optional[Dict[str, Any]] = None
    ) -> Snapshot:
        """创建新快照"""
        snapshot_id = self._generate_id()
        
        logger.info(f"[Snapshot] 创建快照: {snapshot_id} - {description}")
        
        # 备份文件
        backup_path = self._backup_files(snapshot_id)
        
        # 获取Git信息
        git_commit, git_dirty = self._get_git_info()
        
        # 获取数据库状态
        db_state = await self._get_database_state()
        
        # 计算文件状态
        output_dir = self._get_output_dir()
        file_state = FileState(
            output_dir_hash=self._compute_dir_hash(output_dir),
            key_files={}
        )
        
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            novel_id=self.novel_id,
            type=snapshot_type,
            created_at=datetime.now().isoformat(),
            description=description,
            llm_call=llm_call,
            database_state=db_state,
            file_state=file_state,
            workflow_state=workflow_state,
            git_commit=git_commit,
            git_dirty_files=git_dirty
        )
        
        # 保存快照
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 更新索引
        await self._update_index(snapshot)
        
        logger.info(f"[Snapshot] 快照创建完成: {snapshot_id}")
        return snapshot
    
    async def _update_index(self, snapshot: Snapshot):
        """更新快照索引"""
        index = await self._load_index()
        
        index["snapshots"] = index.get("snapshots", [])
        index["snapshots"].append({
            "snapshot_id": snapshot.snapshot_id,
            "type": snapshot.type,
            "created_at": snapshot.created_at,
            "description": snapshot.description,
            "has_llm_call": snapshot.llm_call is not None
        })
        
        # 按时间排序
        index["snapshots"].sort(key=lambda x: x["created_at"], reverse=True)
        
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    async def _load_index(self) -> Dict[str, Any]:
        """加载快照索引"""
        if not self.index_file.exists():
            return {"snapshots": []}
        
        with open(self.index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    async def list_snapshots(
        self,
        snapshot_type: Optional[SnapshotType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出快照列表"""
        index = await self._load_index()
        snapshots = index.get("snapshots", [])
        
        if snapshot_type:
            snapshots = [s for s in snapshots if s["type"] == snapshot_type]
        
        return snapshots[:limit]
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """获取完整快照"""
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return None
        
        with open(snapshot_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Snapshot.from_dict(data)
    
    async def rollback_to_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """
        回滚到指定快照
        
        回滚内容包括：
        1. 文件状态（从备份恢复）
        2. 数据库状态（删除快照后的数据）
        3. 工作流状态（恢复上下文）
        
        Returns:
            {"success": bool, "message": str, "details": {...}}
        """
        logger.warning(f"[Snapshot] 开始回滚到: {snapshot_id}")
        
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            return {
                "success": False,
                "message": f"快照不存在: {snapshot_id}",
                "details": {}
            }
        
        details = {
            "snapshot_id": snapshot_id,
            "snapshot_time": snapshot.created_at,
            "files_restored": False,
            "database_rolled_back": False,
            "workflow_state_restored": False
        }
        
        try:
            # 1. 恢复文件
            backup_path = self.backup_dir / snapshot_id
            output_dir = self._get_output_dir()
            
            if backup_path.exists() and output_dir.exists():
                # 备份当前状态（以防万一）
                current_backup = self.backup_dir / f"before_rollback_{self._generate_id()}"
                shutil.copytree(output_dir, current_backup)
                details["pre_rollback_backup"] = str(current_backup)
                
                # 恢复快照文件
                shutil.rmtree(output_dir)
                shutil.copytree(backup_path, output_dir)
                details["files_restored"] = True
                logger.info(f"[Snapshot] 文件恢复完成")
            
            # 2. 回滚数据库
            db_result = await self._rollback_database(snapshot)
            details["database_rolled_back"] = db_result["success"]
            details["database_details"] = db_result
            
            # 3. 记录回滚操作
            await self._record_rollback(snapshot_id, details)
            
            return {
                "success": True,
                "message": f"成功回滚到快照 {snapshot_id} ({snapshot.created_at})",
                "details": details
            }
            
        except Exception as e:
            logger.error(f"[Snapshot] 回滚失败: {e}")
            return {
                "success": False,
                "message": f"回滚失败: {str(e)}",
                "details": details
            }
    
    async def _rollback_database(self, snapshot: Snapshot) -> Dict[str, Any]:
        """回滚数据库到快照状态"""
        from app.core.database import get_session
        from app.models.chapter import Chapter
        from app.models.entity import Entity, EntityRelationship
        from app.models.memory_node import MemoryNode
        from sqlalchemy import delete
        
        result = {"success": False, "deleted_chapters": 0, "deleted_entities": 0}
        
        try:
            async with get_session() as db:
                # 获取快照时的章节号
                target_chapter = snapshot.database_state.latest_chapter_number
                
                if target_chapter is not None:
                    # 删除快照后的章节
                    chapter_result = await db.execute(
                        delete(Chapter).where(
                            (Chapter.novel_id == self.novel_id) &
                            (Chapter.chapter_number > target_chapter)
                        )
                    )
                    result["deleted_chapters"] = chapter_result.rowcount
                    
                    # 删除相关记忆节点
                    await db.execute(
                        delete(MemoryNode).where(
                            (MemoryNode.novel_id == self.novel_id) &
                            (MemoryNode.chapter_number > target_chapter)
                        )
                    )
                
                # 注意：实体状态不删除，因为需要保留历史
                # 但可以通过重新运行实体抽取来更新
                
                await db.commit()
                result["success"] = True
                
        except Exception as e:
            logger.error(f"[Snapshot] 数据库回滚失败: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _record_rollback(self, target_snapshot_id: str, details: Dict):
        """记录回滚操作"""
        rollback_record = {
            "timestamp": datetime.now().isoformat(),
            "target_snapshot_id": target_snapshot_id,
            "details": details
        }
        
        rollback_file = self.snapshots_dir / "rollback_history.json"
        history = []
        
        if rollback_file.exists():
            with open(rollback_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        
        history.append(rollback_record)
        
        with open(rollback_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        try:
            # 删除快照文件
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            if snapshot_file.exists():
                snapshot_file.unlink()
            
            # 删除备份
            backup_path = self.backup_dir / snapshot_id
            if backup_path.exists():
                shutil.rmtree(backup_path)
            
            # 更新索引
            index = await self._load_index()
            index["snapshots"] = [s for s in index["snapshots"] if s["snapshot_id"] != snapshot_id]
            
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[Snapshot] 快照删除: {snapshot_id}")
            return True
            
        except Exception as e:
            logger.error(f"[Snapshot] 删除失败: {e}")
            return False


# 全局快照管理器缓存
_snapshot_managers: Dict[int, StateSnapshotManager] = {}


def get_snapshot_manager(novel_id: int) -> StateSnapshotManager:
    """获取小说对应的快照管理器"""
    if novel_id not in _snapshot_managers:
        _snapshot_managers[novel_id] = StateSnapshotManager(novel_id)
    return _snapshot_managers[novel_id]
