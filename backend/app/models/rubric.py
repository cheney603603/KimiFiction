"""
Rubric Evaluation Data Models
结构化Rubric评测系统的数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.core.database import Base


class EvaluationType(str, Enum):
    """评测类型"""
    PRE_TRAINING = "pre_training"      # 训练前评测
    POST_TRAINING = "post_training"    # 训练后评测
    MID_TRAINING = "mid_training"      # 训练中评测
    BASELINE = "baseline"              # 基线评测


class DimensionCategory(str, Enum):
    """评分维度类别"""
    PLOT_CONSISTENCY = "plot_consistency"      # 情节一致性
    STYLE_MATCHING = "style_matching"          # 风格匹配度
    LOGIC_RATIONALITY = "logic_rationality"    # 逻辑合理性
    CHARACTER_CONSISTENCY = "character_consistency"  # 角色一致性
    WORLD_CONSISTENCY = "world_consistency"    # 世界观一致性
    NARRATIVE_FLOW = "narrative_flow"          # 叙事流畅度
    EMOTIONAL_IMPACT = "emotional_impact"      # 情感冲击力
    HOOK_STRENGTH = "hook_strength"            # 钩子强度


class RubricTemplate(Base):
    """Rubric模板 - 定义评测标准"""
    __tablename__ = "rubric_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    genre = Column(String(50), nullable=True, comment="适用类型(玄幻/科幻等)")
    
    # 模板配置
    dimensions_config = Column(JSON, nullable=False, comment="维度配置[{""dimension"": "", ""weight"": 0.3}]")
    total_weight = Column(Float, default=1.0, comment="总权重")
    
    # 规则库引用
    rule_library_refs = Column(JSON, default=list, comment="引用的规则库ID列表")
    character_library_refs = Column(JSON, default=list, comment="引用的角色库ID列表")
    plot_library_refs = Column(JSON, default=list, comment="引用的情节库ID列表")
    
    # 元数据
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    evaluations = relationship("RubricEvaluation", back_populates="template")


class RubricDimension(Base):
    """Rubric评分维度 - 具体评分项"""
    __tablename__ = "rubric_dimensions"
    
    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("rubric_evaluations.id"), nullable=False)
    
    # 维度信息
    category = Column(SQLEnum(DimensionCategory), nullable=False, comment="维度类别")
    name = Column(String(100), nullable=False, comment="维度名称")
    weight = Column(Float, default=1.0, comment="权重")
    
    # 评分标准(1-10分)
    score = Column(Float, nullable=False, comment="得分(1-10)")
    
    # 评分依据
    criteria_met = Column(JSON, default=list, comment="满足的标准项")
    criteria_missed = Column(JSON, default=list, comment="未满足的标准项")
    
    # 详细反馈
    feedback = Column(Text, nullable=True, comment="维度反馈")
    evidence = Column(Text, nullable=True, comment="评分证据/引用文本")
    
    # 知识库引用
    kb_references = Column(JSON, default=list, comment="知识库引用[{""type"": "", ""id"": "", ""relevance"": 0.8}]")
    
    # 元数据
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    evaluation = relationship("RubricEvaluation", back_populates="dimensions")


class RubricEvaluation(Base):
    """Rubric评测记录 - 完整评测结果"""
    __tablename__ = "rubric_evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True, index=True)
    chapter_number = Column(Integer, nullable=False, comment="章节号")
    
    # 评测类型
    eval_type = Column(SQLEnum(EvaluationType), nullable=False, comment="评测类型")
    template_id = Column(Integer, ForeignKey("rubric_templates.id"), nullable=True)
    
    # 评测主体
    evaluator_type = Column(String(50), default="reader_agent", comment="评测者类型(reader_agent/human/mixed)")
    evaluator_id = Column(String(100), nullable=True, comment="评测者ID(人工评测时)")
    
    # 总体评分
    total_score = Column(Float, nullable=False, comment="总分(1-10)")
    weighted_score = Column(Float, nullable=False, comment="加权总分")
    
    # 各维度评分(冗余存储，方便查询)
    dimension_scores = Column(JSON, nullable=False, comment="维度得分汇总")
    
    # 详细反馈
    summary_feedback = Column(Text, nullable=True, comment="总体反馈")
    strengths = Column(JSON, default=list, comment="优点列表")
    weaknesses = Column(JSON, default=list, comment="缺点列表")
    improvement_suggestions = Column(JSON, default=list, comment="改进建议")
    
    # 一致性检查
    consistency_issues = Column(JSON, default=list, comment="一致性问题[{""type"": "", ""severity"": "", ""description"": "", ""suggestion"": ""}]")
    
    # 人工介入
    human_override = Column(Boolean, default=False, comment="人工覆盖")
    human_score = Column(Float, nullable=True, comment="人工评分")
    human_feedback = Column(Text, nullable=True, comment="人工反馈")
    
    # 元数据
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    novel = relationship("Novel", back_populates="rubric_evaluations")
    chapter = relationship("Chapter", back_populates="rubric_evaluations")
    template = relationship("RubricTemplate", back_populates="evaluations")
    dimensions = relationship("RubricDimension", back_populates="evaluation", cascade="all, delete-orphan")


class TrainingEpisode(Base):
    """训练回合 - RL训练数据"""
    __tablename__ = "training_episodes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, comment="章节号")
    
    # 回合信息
    episode_number = Column(Integer, nullable=False, comment="回合序号")
    round_number = Column(Integer, nullable=False, comment="当前轮次")
    max_rounds = Column(Integer, default=5, comment="最大轮次")
    
    # 状态
    state_draft = Column(Text, nullable=False, comment="当前草稿状态")
    state_version = Column(Integer, default=0, comment="草稿版本")
    
    # 动作
    action_taken = Column(String(50), nullable=False, comment="采取的动作")
    action_probs = Column(JSON, nullable=False, comment="动作概率分布")
    
    # 奖励
    reward = Column(Float, nullable=False, comment="即时奖励")
    cumulative_reward = Column(Float, default=0.0, comment="累积奖励")
    
    # Reader评分详情
    reader_score = Column(Float, nullable=True, comment="读者评分")
    hook_score = Column(Float, nullable=True, comment="钩子评分")
    immersion_score = Column(Float, nullable=True, comment="沉浸感评分")
    
    # Rubric评测详情
    rubric_evaluation_id = Column(Integer, ForeignKey("rubric_evaluations.id"), nullable=True)
    rubric_score = Column(Float, nullable=True, comment="Rubric总分")
    
    # 策略信息
    policy_version = Column(Integer, default=0, comment="策略版本")
    value_estimate = Column(Float, nullable=True, comment="价值估计")
    advantage = Column(Float, nullable=True, comment="优势函数值")
    
    # 元数据
    is_terminal = Column(Boolean, default=False, comment="是否终止状态")
    termination_reason = Column(String(100), nullable=True, comment="终止原因")
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    novel = relationship("Novel", back_populates="training_episodes")
    rubric_evaluation = relationship("RubricEvaluation")


class TrainingBatch(Base):
    """训练批次 - 聚合多个回合"""
    __tablename__ = "training_batches"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 批次信息
    batch_name = Column(String(100), nullable=False, comment="批次名称")
    batch_type = Column(String(50), default="ppo", comment="批次类型(ppo/dpo/sft)")
    
    # 统计信息
    episode_count = Column(Integer, default=0, comment="回合数")
    total_words = Column(Integer, default=0, comment="总字数")
    avg_reward = Column(Float, default=0.0, comment="平均奖励")
    best_reward = Column(Float, default=0.0, comment="最佳奖励")
    worst_reward = Column(Float, default=0.0, comment="最差奖励")
    
    # 训练前后对比
    pre_training_eval_id = Column(Integer, ForeignKey("rubric_evaluations.id"), nullable=True)
    post_training_eval_id = Column(Integer, ForeignKey("rubric_evaluations.id"), nullable=True)
    improvement_score = Column(Float, nullable=True, comment="改进分数")
    
    # 状态
    status = Column(String(50), default="collecting", comment="状态(collecting/training/completed)")
    
    # 文件路径
    data_file_path = Column(String(500), nullable=True, comment="数据文件路径")
    report_file_path = Column(String(500), nullable=True, comment="报告文件路径")
    
    # 元数据
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    pre_training_eval = relationship("RubricEvaluation", foreign_keys=[pre_training_eval_id])
    post_training_eval = relationship("RubricEvaluation", foreign_keys=[post_training_eval_id])


class ComparisonReport(Base):
    """对比报告 - 训练前后对比"""
    __tablename__ = "comparison_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 报告信息
    report_name = Column(String(200), nullable=False, comment="报告名称")
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=True, index=True)
    
    # 对比对象
    baseline_batch_id = Column(Integer, ForeignKey("training_batches.id"), nullable=True, comment="基线批次")
    comparison_batch_id = Column(Integer, ForeignKey("training_batches.id"), nullable=True, comment="对比批次")
    
    # 对比结果
    overall_improvement = Column(Float, nullable=True, comment="总体改进率")
    dimension_improvements = Column(JSON, nullable=True, comment="各维度改进率")
    
    # 详细分析
    key_improvements = Column(JSON, default=list, comment="关键改进点")
    persistent_issues = Column(JSON, default=list, comment="持续存在的问题")
    regression_areas = Column(JSON, default=list, comment="退步领域")
    
    # 报告文件
    report_path = Column(String(500), nullable=True, comment="报告文件路径")
    charts_path = Column(String(500), nullable=True, comment="图表文件路径")
    
    # 元数据
    is_auto_generated = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    novel = relationship("Novel", back_populates="comparison_reports")
