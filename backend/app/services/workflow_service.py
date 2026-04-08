"""
工作流服务层
管理多智能体工作流的状态和协调
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.schemas.workflow import (
    WorkflowStartRequest,
    GenreAnalysisRequest,
    UserInputRequest,
    AgentMessage,
)
from app.services.novel_service import NovelService
from app.core.redis_client import SessionManager


class WorkflowService:
    """工作流服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.novel_service = NovelService(db)
        self._websockets: Dict[int, List] = {}  # novel_id -> websocket列表
    
    async def start_workflow(self, request: WorkflowStartRequest) -> Dict:
        """启动新小说工作流"""
        from app.schemas.novel import NovelCreate
        
        # 1. 创建小说项目
        novel_data = NovelCreate(
            title=request.title,
            genre=request.preferred_genre,
        )
        novel = await self.novel_service.create_novel(novel_data)
        
        # 2. 初始化工作流状态
        state = {
            "novel_id": novel.id,
            "current_state": "awaiting_genre",
            "messages": [],
            "waiting_for_user": True,
            "progress": {
                "genre_confirmed": False,
                "plot_discussed": False,
                "characters_designed": False,
                "outline_generated": False,
                "writing_started": False,
            },
            "can_proceed": False,
        }
        
        # 3. 保存到Redis
        await SessionManager.save_state(f"novel_{novel.id}", state)
        
        # 4. 如果有初始想法，直接分析
        if request.initial_idea:
            analysis = await self.analyze_genre(
                GenreAnalysisRequest(user_input=request.initial_idea)
            )
            state["messages"].append(AgentMessage(
                role="agent",
                content=f"我分析了您的需求：\n建议类型：{analysis.suggested_genre}\n理由：{analysis.reasoning}",
                message_type="suggestion",
                metadata={"analysis": analysis.model_dump()}
            ).model_dump())
            await SessionManager.save_state(f"novel_{novel.id}", state)
        
        logger.info(f"启动工作流: 小说ID {novel.id}")
        return state
    
    async def get_state(self, novel_id: int) -> Optional[Dict]:
        """获取工作流状态"""
        return await SessionManager.get_state(f"novel_{novel_id}")
    
    async def analyze_genre(self, request: GenreAnalysisRequest) -> Any:
        """分析小说类型（调用LLM）"""
        # TODO: 集成实际的LLM调用
        # 临时返回模拟结果
        from app.schemas.workflow import GenreAnalysisResponse
        
        return GenreAnalysisResponse(
            suggested_genre="玄幻",
            sub_genres=["东方玄幻", "修仙"],
            style_keywords=["热血", "升级流", "废柴逆袭"],
            tropes=["退婚流", "金手指", "宗门斗争"],
            target_audience="青少年男性",
            similar_works=["斗破苍穹", "凡人修仙传"],
            reasoning="根据您的描述，这是一个典型的东方玄幻升级流故事"
        )
    
    async def process_user_input(self, novel_id: int, request: UserInputRequest) -> Dict:
        """处理用户输入"""
        state = await self.get_state(novel_id)
        
        # 如果工作流不存在，自动初始化
        if not state:
            # 获取小说信息
            novel = await self.novel_service.get_novel(novel_id)
            if not novel:
                raise ValueError(f"小说不存在: {novel_id}")
            
            # 初始化工作流状态
            state = {
                "novel_id": novel_id,
                "current_state": "awaiting_genre",
                "messages": [],
                "waiting_for_user": True,
                "progress": {
                    "genre_confirmed": False,
                    "plot_discussed": False,
                    "characters_designed": False,
                    "outline_generated": False,
                    "writing_started": False,
                },
                "can_proceed": False,
            }
            await SessionManager.save_state(f"novel_{novel_id}", state)
            logger.info(f"自动初始化工作流: 小说ID {novel_id}")
        
        # 添加用户消息
        state["messages"].append(AgentMessage(
            role="user",
            content=request.message
        ).model_dump())
        
        current_state = state["current_state"]
        
        # 根据当前状态处理
        ai_response = None
        
        if current_state == "awaiting_genre":
            # 确认类型，进入剧情讨论
            if "确认" in request.message or "同意" in request.message:
                state["current_state"] = "discussing_plot"
                state["progress"]["genre_confirmed"] = True
                ai_response = "太好了！类型已确认。现在让我们来讨论一下主线剧情。您希望故事的主要冲突是什么？"
            else:
                ai_response = f"收到您的想法：{request.message}。请确认这个类型设定，或告诉我您希望调整的地方。"
        
        elif current_state == "discussing_plot":
            # 剧情讨论中
            if "开始设计角色" in request.message:
                state["current_state"] = "designing_chars"
                state["progress"]["plot_discussed"] = True
                ai_response = "剧情讨论完成！现在让我为您设计主要角色。"
            else:
                ai_response = f"了解了，{request.message}。还有其他想法吗？说完后可以输入'开始设计角色'继续。"
        
        elif current_state == "designing_chars":
            if "生成大纲" in request.message:
                state["current_state"] = "generating_outline"
                state["progress"]["characters_designed"] = True
                ai_response = "好的，现在开始生成大纲..."
            else:
                ai_response = "正在为您设计角色...有什么特殊要求吗？输入'生成大纲'继续。"
        
        elif current_state == "generating_outline":
            if "开始写作" in request.message:
                state["current_state"] = "writing_chapter"
                state["progress"]["outline_generated"] = True
                state["progress"]["writing_started"] = True
                ai_response = "大纲已完成！开始撰写第一章..."
            else:
                ai_response = "正在生成大纲，请稍候...输入'开始写作'启动撰写。"
        
        # 添加AI回复到消息列表
        if ai_response:
            state["messages"].append(AgentMessage(
                role="agent",
                content=ai_response,
                message_type="response"
            ).model_dump())
        
        # 保存状态
        await SessionManager.save_state(f"novel_{novel_id}", state)
        
        # 通知WebSocket客户端
        await self._notify_clients(novel_id, state)
        
        return state
    
    async def generate_characters(self, novel_id: int) -> Dict:
        """生成角色设计"""
        # TODO: 调用角色设计Agent
        state = await self.get_state(novel_id)
        if state:
            state["messages"].append(AgentMessage(
                role="agent",
                content="角色设计完成！已创建主角、反派和重要配角。",
                message_type="suggestion"
            ).model_dump())
            await SessionManager.save_state(f"novel_{novel_id}", state)
        return state or {}
    
    async def generate_outline(self, novel_id: int) -> Dict:
        """生成大纲"""
        # TODO: 调用大纲生成Agent
        state = await self.get_state(novel_id)
        if state:
            state["messages"].append(AgentMessage(
                role="agent",
                content="大纲生成完成！已创建三卷大纲，每卷约100章。",
                message_type="suggestion"
            ).model_dump())
            await SessionManager.save_state(f"novel_{novel_id}", state)
        return state or {}
    
    async def start_writing(self, novel_id: int, auto_mode: bool = False, target_chapters: Optional[int] = None) -> Dict:
        """开始自动撰写"""
        state = await self.get_state(novel_id)
        if not state:
            raise ValueError("工作流不存在")
        
        state["current_state"] = "writing_chapter"
        state["auto_mode"] = auto_mode
        if target_chapters:
            state["target_chapters"] = target_chapters
        
        state["messages"].append(AgentMessage(
            role="agent",
            content=f"开始{'自动' if auto_mode else '手动'}撰写模式！",
            message_type="system"
        ).model_dump())
        
        await SessionManager.save_state(f"novel_{novel_id}", state)
        
        # TODO: 启动后台任务开始生成
        
        return state
    
    async def pause_workflow(self, novel_id: int) -> Dict:
        """暂停工作流"""
        state = await self.get_state(novel_id)
        if state:
            state["current_state"] = "paused"
            await SessionManager.save_state(f"novel_{novel_id}", state)
        return state or {}
    
    async def resume_workflow(self, novel_id: int) -> Dict:
        """恢复工作流"""
        state = await self.get_state(novel_id)
        if state:
            # 恢复到之前的状态
            state["current_state"] = state.get("previous_state", "writing_chapter")
            await SessionManager.save_state(f"novel_{novel_id}", state)
        return state or {}
    
    async def register_websocket(self, novel_id: int, websocket):
        """注册WebSocket连接"""
        if novel_id not in self._websockets:
            self._websockets[novel_id] = []
        self._websockets[novel_id].append(websocket)
    
    async def unregister_websocket(self, novel_id: int, websocket):
        """注销WebSocket连接"""
        if novel_id in self._websockets:
            if websocket in self._websockets[novel_id]:
                self._websockets[novel_id].remove(websocket)
    
    async def _notify_clients(self, novel_id: int, state: Dict):
        """通知所有连接的客户端"""
        if novel_id in self._websockets:
            disconnected = []
            for ws in self._websockets[novel_id]:
                try:
                    await ws.send_json({
                        "type": "state_update",
                        "data": state
                    })
                except Exception:
                    disconnected.append(ws)
            
            # 清理断开的连接
            for ws in disconnected:
                self._websockets[novel_id].remove(ws)
