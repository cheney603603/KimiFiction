"""
JSON 解析工具
提供健壮的 JSON 解析功能，处理各种 LLM 输出格式
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger


def extract_json_from_response(response: str) -> Tuple[Optional[Union[Dict, List]], str]:
    """
    从 LLM 响应中提取 JSON 数据
    
    Args:
        response: LLM 返回的原始响应
        
    Returns:
        (解析后的JSON对象/数组或None, 状态信息)
    """
    if not response:
        return None, "响应为空"
    
    # 如果是 bytes，尝试解码
    if isinstance(response, bytes):
        try:
            response = response.decode('utf-8')
        except:
            return None, "无法解码响应"
    
    cleaned = _normalize_response_text(str(response).strip())
    
    if not cleaned:
        return None, "响应为空字符串"
    
    json_text = None
    
    # 方式1: 提取 ```json 代码块
    if "```json" in cleaned:
        parts = cleaned.split("```json")
        if len(parts) > 1:
            json_text = parts[1].split("```")[0].strip()
    
    # 方式2: 提取 ``` 代码块
    elif "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 2:
            json_text = parts[1].strip()
    
    # 方式3: 尝试直接解析
    if json_text is None:
        json_text = cleaned
    
    # 尝试解析提取的文本
    result, error = _try_parse_json(json_text)
    if result is not None:
        return result, "成功"
    
    # 方式4: 优先按边界提取最外层 JSON，避免正则先命中内层对象
    boundary_candidate = _extract_outer_json_candidate(cleaned)
    if boundary_candidate:
        result, _ = _try_parse_json(boundary_candidate)
        if result is not None:
            return result, "通过边界提取"

    # 方式5: 使用正则表达式查找 JSON 对象
    json_pattern = r'\{(?:[^{}]|\{[^{}]*\})*\}'
    matches = re.findall(json_pattern, cleaned)
    
    for match in matches:
        result, _ = _try_parse_json(match)
        if result is not None:
            return result, "通过正则提取"
    
    # 方式6: 查找数组格式
    array_pattern = r'\[[\s\S]*\]'
    array_matches = re.findall(array_pattern, cleaned)
    
    for match in array_matches:
        result, _ = _try_parse_json(match)
        if result is not None:
            return result, "通过数组正则提取"
    
    # 所有方式都失败
    preview = cleaned[:300] if len(cleaned) > 300 else cleaned
    return None, f"解析失败，响应预览: {preview}"


def _try_parse_json(text: str) -> Tuple[Optional[Union[Dict, List]], str]:
    """尝试解析 JSON，返回结果和错误信息"""
    if not text:
        return None, "文本为空"
    
    try:
        result = json.loads(text)
        return result, "成功"
    except json.JSONDecodeError as e:
        return None, f"JSONDecodeError: {e}"
    except Exception as e:
        return None, f"解析错误: {e}"


def _normalize_response_text(text: str) -> str:
    """清理 chat2api/模型常见包装文本，尽量把 JSON 块前移。"""
    cleaned = text.strip()

    cleaned = re.sub(r'^\s*(JSON|json)\s*[\r\n]+', '', cleaned)
    cleaned = re.sub(r'^\s*(复制|Copy)\s*[\r\n]+', '', cleaned)

    first_object = cleaned.find('{')
    first_array = cleaned.find('[')
    candidates = [idx for idx in (first_object, first_array) if idx != -1]
    if candidates:
        first_json_idx = min(candidates)
        cleaned = cleaned[first_json_idx:]

    return cleaned.strip()


def _extract_outer_json_candidate(text: str) -> Optional[str]:
    """提取最大的外层 JSON 对象或数组。"""
    object_start = text.find('{')
    object_end = text.rfind('}')
    array_start = text.find('[')
    array_end = text.rfind(']')

    candidates: List[str] = []

    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append(text[object_start:object_end + 1])

    if array_start != -1 and array_end != -1 and array_end > array_start:
        candidates.append(text[array_start:array_end + 1])

    if not candidates:
        return None

    return max(candidates, key=len)


def parse_json_response(response: str, required_fields: list = None) -> Tuple[bool, Any, str]:
    """
    解析 LLM 的 JSON 响应
    
    Args:
        response: LLM 返回的原始响应
        required_fields: 可选的必需字段列表，用于验证
        
    Returns:
        (是否成功, 解析结果或None, 错误信息)
    """
    result, message = extract_json_from_response(response)
    
    if result is None:
        return False, None, message
    
    # 如果是列表，不验证字段
    if isinstance(result, list):
        return True, result, "成功"
    
    # 验证必需字段（仅对字典有效）
    if required_fields and isinstance(result, dict):
        missing = [f for f in required_fields if f not in result]
        if missing:
            return False, None, f"缺少必需字段: {missing}"
    
    return True, result, "成功"


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全的 JSON 解析，失败时返回默认值
    
    Args:
        text: 要解析的文本
        default: 解析失败时返回的默认值
        
    Returns:
        解析结果或默认值
    """
    if not text:
        return default
    
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def json_to_markdown(data: Any, indent: int = 0) -> str:
    """
    将 JSON 字典或列表转换为可读的 Markdown 格式
    
    Args:
        data: JSON 数据
        indent: 缩进级别
        
    Returns:
        Markdown 格式的字符串
    """
    lines = []
    prefix = "  " * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}- **{key}:**")
                lines.append(json_to_markdown(value, indent + 1))
            else:
                lines.append(f"{prefix}- **{key}:** {value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(json_to_markdown(item, indent))
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{data}")
    
    return "\n".join(lines)
