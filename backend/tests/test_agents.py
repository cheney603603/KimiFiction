"""
Agent 模块单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAgentFactory:
    """AgentFactory 测试"""
    
    def test_import_agent_factory(self):
        """测试导入 AgentFactory"""
        from app.agents import AgentFactory
        assert AgentFactory is not None
    
    def test_list_agents(self):
        """测试列出所有 Agent"""
        from app.agents import AgentFactory
        
        agents = AgentFactory.list_agents()
        assert isinstance(agents, list)
        assert len(agents) > 0
        
        # 检查关键 Agent 存在
        assert "world_builder" in agents
        assert "character_designer" in agents
        assert "plot_designer" in agents
        assert "outline_generator" in agents
    
    def test_get_agent_info(self):
        """测试获取 Agent 信息"""
        from app.agents import AgentFactory
        
        info = AgentFactory.get_agent_info("world_builder")
        assert isinstance(info, dict)
        assert "name" in info
        assert "description" in info
        assert info["unified"] == True
    
    def test_create_unified_agent(self):
        """测试创建统一 Agent"""
        from app.agents import AgentFactory
        
        agent = AgentFactory.create("world_builder")
        assert agent is not None
        assert agent.name == "WorldBuilder"
    
    def test_create_legacy_agent(self):
        """测试创建 Legacy Agent"""
        from app.agents import AgentFactory
        
        agent = AgentFactory.create("analyzer")
        assert agent is not None
    
    def test_create_unknown_agent_raises(self):
        """测试创建未知 Agent 抛出异常"""
        from app.agents import AgentFactory
        
        with pytest.raises(ValueError) as exc_info:
            AgentFactory.create("unknown_agent")
        
        assert "未知的Agent类型" in str(exc_info.value)


class TestUnifiedAgent:
    """UnifiedAgent 测试"""
    
    def test_import_unified_agents(self):
        """测试导入统一 Agent"""
        from app.agents import (
            UnifiedAgent,
            UnifiedWorldBuilderAgent,
            UnifiedCharacterDesignerAgent,
            UnifiedPlotDesignerAgent,
            UnifiedOutlineGeneratorAgent,
        )
        
        assert UnifiedAgent is not None
        assert UnifiedWorldBuilderAgent is not None
        assert UnifiedCharacterDesignerAgent is not None
    
    def test_world_builder_template(self):
        """测试 WorldBuilder 模板生成"""
        from app.agents import UnifiedWorldBuilderAgent
        
        agent = UnifiedWorldBuilderAgent()
        template = agent.get_template({"genre": "玄幻"})
        
        assert "世界观" in template
        assert "JSON" in template
    
    def test_character_designer_template(self):
        """测试 CharacterDesigner 模板生成"""
        from app.agents import UnifiedCharacterDesignerAgent
        
        agent = UnifiedCharacterDesignerAgent()
        template = agent.get_template({"genre": "玄幻", "num_characters": 5})
        
        assert "角色" in template
        assert "主角" in template
        assert "JSON" in template
    
    def test_outline_generator_template(self):
        """测试 OutlineGenerator 模板生成"""
        from app.agents import UnifiedOutlineGeneratorAgent
        
        agent = UnifiedOutlineGeneratorAgent()
        template = agent.get_template({"total_volumes": 3, "chapters_per_volume": 100})
        
        assert "大纲" in template
        assert "卷" in template
