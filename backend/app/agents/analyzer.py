"""
类型分析智能体
分析用户输入，提取小说类型、风格、偏好等信息
"""
import json
from typing import Any, Dict
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


class GenreAnalyzerAgent(BaseAgent):
    """
    类型分析智能体
    
    分析用户的初始需求描述，提取：
    - 建议的小说类型
    - 子类型/标签
    - 风格关键词
    - 常见套路
    - 目标读者群
    - 相似作品推荐
    """
    
    SYSTEM_PROMPT = """你是一位专业的小说类型分析专家。
你的任务是根据用户的描述，分析并推荐最适合的小说类型和风格。

你需要输出JSON格式的分析结果，包含以下字段：
- suggested_genre: 建议的主类型（如：玄幻、科幻、都市、言情等）
- sub_genres: 子类型列表
- style_keywords: 风格关键词（如：热血、轻松、黑暗、治愈等）
- tropes: 可能包含的套路/梗
- target_audience: 目标读者群
- similar_works: 相似作品推荐（2-3部）
- reasoning: 推荐理由

请确保输出是合法的JSON格式。"""
    
    def __init__(self):
        super().__init__("GenreAnalyzer", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析用户需求

        Args:
            context: 包含 user_input, messages 的上下文

        Returns:
            类型分析结果
        """
        user_input = context.get("user_input", "")
        messages = context.get("messages", [])

        # 如果没有user_input，尝试从messages中获取
        if not user_input and messages:
            # 获取最后一条用户消息
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_input = msg.get("content", "")
                    break

        # 如果还是没有，提示用户输入
        if not user_input:
            self.log_action("缺少输入", {"context_keys": list(context.keys())})
            return {
                "success": False,
                "error": "缺少用户输入，请提供小说创作需求描述"
            }

        self.log_action("开始类型分析", {"input_length": len(user_input)})

        # 构建包含对话历史的prompt
        prompt = f"""请分析以下小说创作需求："""

        # 如果有对话历史，添加历史上下文
        if messages:
            history_text = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in messages[-5:]  # 只取最近5条消息
            ])
            prompt += f"""

之前的对话历史：
{history_text}
"""

        prompt += f"""

用户最新的描述：
{user_input}

请提供详细的类型分析，输出JSON格式。"""

        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]

            # 检查响应是否为空
            if not response or not response.strip():
                self.log_action("收到空响应", {"input_length": len(user_input)})
                return {
                    "success": False,
                    "error": "收到空响应，请检查Chat2API服务状态"
                }

            # 记录原始响应长度
            self.log_action("收到LLM响应", {"response_length": len(response)})

            # 使用通用JSON解析工具
            result, parse_message = extract_json_from_response(response)
            
            if result is None:
                self.log_action("JSON解析失败", {
                    "parse_message": parse_message,
                    "response_length": len(response),
                    "response_preview": response[:300]
                })
                return {
                    "success": False,
                    "error": f"JSON解析失败: {parse_message}",
                    "raw_response": response[:1000]
                }

            self.log_action("类型分析完成", {
                "genre": result.get("suggested_genre"),
                "sub_genres": result.get("sub_genres", [])
            })

            return {
                "success": True,
                "analysis": result,
                "_react_trace": react_result["trace"],
            }

        except Exception as e:
            self.log_action("分析失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
