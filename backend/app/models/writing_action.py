"""写作动作空间（独立枚举，从 RL 训练模块剥离）

RL 体系移除后保留动作枚举本身——写作循环的"生成/修订/删除/保留"仍是
循环控制的核心概念，只是不再由策略网络采样。
"""
from enum import Enum


class WritingAction(str, Enum):
    """写作动作空间"""
    GENERATE = "generate"       # 生成新内容
    REVISE = "revise"          # 修改内容
    DELETE = "delete"          # 删除内容
    KEEP = "keep"              # 保留不变
