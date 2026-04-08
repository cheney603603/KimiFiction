"""
剧情讨论智能体
与用户进行多轮对话，确定主线剧情
"""
from typing import Any, Dict, List
from app.agents.base import BaseAgent


class PlotDiscussorAgent(BaseAgent):
    """
    剧情讨论智能体
    
    与用户进行交互式对话，确定：
    - 主线剧情
    - 核心冲突
    - 世界观设定
    - 关键转折点
    - 结局走向
    """
    
    SYSTEM_PROMPT = """你是一位资深的小说编辑和剧情策划专家。
你的任务是通过与用户的对话，帮助确定小说的核心剧情。

在对话中，你需要：
1. 提出关键问题以了解用户的想法
2. 根据用户的回答给出建议
3. 逐步完善剧情框架
4. 记录重要的设定和决策

你应该：
- 保持专业但友好的语气
- 在关键决策点给出明确建议
- 帮助用户发现潜在的剧情问题
- 鼓励用户发挥创意

当前对话阶段：{stage}"""
    
    def __init__(self):
        super().__init__("PlotDiscussor", self.SYSTEM_PROMPT.format(stage="初始"))
        self.conversation_history: List[Dict[str, str]] = []
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理剧情讨论
        
        Args:
            context: 包含 user_input, genre, stage 等
            
        Returns:
            智能体响应和当前状态
        """
        user_input = context.get("user_input", "")
        genre = context.get("genre", "未知类型")
        stage = context.get("stage", "initial")
        history = context.get("history", [])
        
        self.log_action("处理剧情讨论", {"stage": stage, "input": user_input[:50]})
        
        # 构建对话历史
        history_text = "\n".join([
            f"{'用户' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
            for msg in history[-5:]  # 只保留最近5轮
        ])
        
        prompt = f"""小说类型：{genre}
当前阶段：{stage}

对话历史：
{history_text}

用户最新输入：
{user_input}

请回复用户，继续剧情讨论。如果需要，可以：
1. 提出后续问题
2. 总结已确定的剧情点
3. 给出建议或警告
4. 推进到下一阶段

请直接回复用户（不要加"AI:"前缀）："""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                output_format="text",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            
            # 判断是否可以进入下一阶段
            can_proceed = self._check_can_proceed(stage, history + [
                {"role": "user", "content": user_input},
                {"role": "agent", "content": response}
            ])
            
            self.log_action("剧情讨论完成", {"can_proceed": can_proceed})
            
            return {
                "success": True,
                "response": response,
                "can_proceed": can_proceed,
                "next_stage": self._get_next_stage(stage) if can_proceed else stage,
                "_react_trace": react_result["trace"],
            }
            
        except Exception as e:
            self.log_action("讨论失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def _check_can_proceed(self, stage: str, history: List[Dict]) -> bool:
        """检查是否可以进入下一阶段"""
        # 简单的启发式判断
        user_messages = [h for h in history if h.get("role") == "user"]
        
        if stage == "initial" and len(user_messages) >= 2:
            return True
        if stage == "conflict" and len(user_messages) >= 4:
            return True
        if stage == "worldbuilding" and len(user_messages) >= 6:
            return True
        
        return False
    
    def _get_next_stage(self, current_stage: str) -> str:
        """获取下一阶段"""
        stages = ["initial", "conflict", "worldbuilding", "characters", "complete"]
        try:
            idx = stages.index(current_stage)
            return stages[min(idx + 1, len(stages) - 1)]
        except ValueError:
            return "initial"
