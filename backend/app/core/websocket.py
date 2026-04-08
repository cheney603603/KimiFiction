"""
WebSocket连接管理模块
管理小说工作流的实时通信
"""
from typing import Dict, List, Set
from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # novel_id -> Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # WebSocket -> novel_id (反向索引)
        self.ws_to_novel: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, novel_id: int):
        """建立WebSocket连接"""
        await websocket.accept()
        
        if novel_id not in self.active_connections:
            self.active_connections[novel_id] = set()
        
        self.active_connections[novel_id].add(websocket)
        self.ws_to_novel[websocket] = novel_id
        
        logger.info(f"WebSocket连接建立: novel_id={novel_id}, 总连接数={len(self.active_connections[novel_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        novel_id = self.ws_to_novel.get(websocket)
        
        if novel_id and novel_id in self.active_connections:
            self.active_connections[novel_id].discard(websocket)
            
            # 清理空集合
            if not self.active_connections[novel_id]:
                del self.active_connections[novel_id]
        
        if websocket in self.ws_to_novel:
            del self.ws_to_novel[websocket]
        
        if novel_id:
            logger.info(f"WebSocket连接断开: novel_id={novel_id}")
    
    async def send_to_novel(self, novel_id: int, message: dict):
        """向特定小说的所有连接发送消息"""
        if novel_id not in self.active_connections:
            return
        
        disconnected = []
        for websocket in self.active_connections[novel_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"发送WebSocket消息失败: {e}")
                disconnected.append(websocket)
        
        # 清理断开的连接
        for ws in disconnected:
            self.disconnect(ws)
    
    async def send_to_client(self, websocket: WebSocket, message: dict):
        """向单个客户端发送消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        for novel_id in list(self.active_connections.keys()):
            await self.send_to_novel(novel_id, message)
    
    def get_connection_count(self, novel_id: int = None) -> int:
        """获取连接数"""
        if novel_id:
            return len(self.active_connections.get(novel_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())


# 全局连接管理器实例
websocket_manager = ConnectionManager()


class WebSocketNotifier:
    """WebSocket通知器 - 用于业务层调用"""
    
    @staticmethod
    async def notify_state_update(novel_id: int, state: dict):
        """通知状态更新"""
        await websocket_manager.send_to_novel(novel_id, {
            "type": "state_update",
            "data": state,
            "timestamp": __import__('time').time()
        })
    
    @staticmethod
    async def notify_chapter_generated(novel_id: int, chapter: dict):
        """通知章节生成完成"""
        await websocket_manager.send_to_novel(novel_id, {
            "type": "chapter_generated",
            "data": chapter,
            "timestamp": __import__('time').time()
        })
    
    @staticmethod
    async def notify_progress(novel_id: int, progress: dict):
        """通知进度更新"""
        await websocket_manager.send_to_novel(novel_id, {
            "type": "progress",
            "data": progress,
            "timestamp": __import__('time').time()
        })
    
    @staticmethod
    async def notify_error(novel_id: int, error: str):
        """通知错误"""
        await websocket_manager.send_to_novel(novel_id, {
            "type": "error",
            "message": error,
            "timestamp": __import__('time').time()
        })
    
    @staticmethod
    async def notify_agent_message(novel_id: int, message: dict):
        """通知智能体消息"""
        await websocket_manager.send_to_novel(novel_id, {
            "type": "agent_message",
            "data": message,
            "timestamp": __import__('time').time()
        })
