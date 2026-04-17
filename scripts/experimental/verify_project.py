#!/usr/bin/env python3
"""
项目验证脚本

检查所有关键模块是否能正常导入
"""
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def check_import(module_name: str, description: str) -> bool:
    """检查模块是否能正常导入"""
    try:
        __import__(module_name)
        print(f"[OK] {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"[FAIL] {description}: {module_name} - {e}")
        return False
    except Exception as e:
        print(f"[WARN] {description}: {module_name} - {e}")
        return False

def main():
    print("=" * 60)
    print("NovelGen Project Verification")
    print("=" * 60)
    
    results = []
    
    # 1. 核心模块
    print("\n[核心模块]")
    results.append(check_import("app.core.config", "配置管理"))
    results.append(check_import("app.core.local_llm", "本地LLM"))
    results.append(check_import("app.core.database", "数据库"))
    results.append(check_import("app.core.redis_client", "Redis客户端"))
    results.append(check_import("app.core.vector_store", "向量存储"))
    
    # 2. 智能体模块
    print("\n[智能体模块]")
    results.append(check_import("app.agents.base", "智能体基类"))
    results.append(check_import("app.agents.writer", "Writer Agent"))
    results.append(check_import("app.agents.reader", "Reader Agent"))
    
    # 3. RAG和上下文
    print("\n[RAG和上下文]")
    results.append(check_import("app.rag_system", "层次化RAG"))
    results.append(check_import("app.context_manager", "上下文管理"))
    results.append(check_import("app.services.embedding_service", "Embedding服务"))
    
    # 4. RL训练模块
    print("\n[RL训练模块]")
    results.append(check_import("app.training.grpo_trainer", "GRPO训练器"))
    results.append(check_import("app.training.lora_trainer", "LoRA训练器"))
    results.append(check_import("app.training.imitation_learning", "模仿学习"))
    results.append(check_import("app.training.tpo_service", "TPO服务"))
    
    # 5. Writer-Reader RL
    print("\n[Writer-Reader RL]")
    results.append(check_import("app.writer_reader_rl", "Writer-Reader对抗"))
    
    # 6. LangGraph
    print("\n[LangGraph]")
    results.append(check_import("app.agent_graph.state", "状态定义"))
    try:
        check_import("app.agent_graph.graph", "工作流图")
    except:
        pass
    
    # 7. API端点
    print("\n[API端点]")
    results.append(check_import("app.api.endpoints.training", "训练API"))
    results.append(check_import("app.api.routes", "路由配置"))
    
    # 8. 评测系统
    print("\n[评测系统]")
    results.append(check_import("app.services.rubric_evaluation_service", "Rubric评测"))
    results.append(check_import("app.services.training_data_collector", "训练数据采集"))
    
    # 总结
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"验证结果: {passed}/{total} 通过")
    
    if passed == total:
        print("[OK] All modules verified!")
        return 0
    else:
        print(f"[WARN] {total - passed} modules have issues")
        print("\n可能的解决方案:")
        print("1. 安装依赖: pip install -r backend/requirements.txt")
        print("2. 检查模型文件: models/Qwen3.5-2B-Q4_K_M.gguf")
        print("3. 检查数据库和Redis连接配置")
        return 1

if __name__ == "__main__":
    sys.exit(main())
