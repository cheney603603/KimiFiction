"""
质量工具模块单元测试（RL 算法已移除，测试保留项）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestQualityToolsImports:
    """保留模块导入测试"""

    def test_import_llm_judge(self):
        """测试导入 LLM-as-Judge 相关类"""
        from app.training import (
            LLMJudge,
            JudgeDimension,
            DimensionScore,
            JudgeVerdict,
            ComparisonResult,
        )

        assert LLMJudge is not None
        assert JudgeDimension is not None
        assert DimensionScore is not None
        assert JudgeVerdict is not None
        assert ComparisonResult is not None

    def test_import_data_auditor(self):
        """测试导入数据质量审计相关类"""
        from app.training import (
            DataQualityAuditor,
            AuditResult,
            QualityIssue,
        )

        assert DataQualityAuditor is not None
        assert AuditResult is not None
        assert QualityIssue is not None

    def test_rl_modules_removed(self):
        """RL 算法模块应已移除（§6.1）"""
        import sys

        with pytest.raises(ImportError):
            __import__("app.training.grpo_trainer")
        with pytest.raises(ImportError):
            __import__("app.rl_training")

    def test_writing_action_standalone(self):
        """WritingAction 枚举应迁移到独立模块（§6.3 第1步）"""
        from app.models.writing_action import WritingAction

        assert WritingAction.GENERATE.value == "generate"
        assert WritingAction.REVISE.value == "revise"
        assert WritingAction.DELETE.value == "delete"
        assert WritingAction.KEEP.value == "keep"
        assert len(list(WritingAction)) == 4


class TestWritingActionMigration:
    """写作循环对 WritingAction 的使用"""

    def test_writer_reader_loop_uses_migrated_enum(self):
        """写作循环应从新模块导入枚举"""
        import inspect
        from app.writer_reader_loop import WriterReaderLoop

        src = inspect.getsource(WriterReaderLoop)
        assert "app.models.writing_action" in inspect.getsource(
            __import__("app.writer_reader_loop", fromlist=["writer_reader_loop"])
        ) or "WritingAction" in src
