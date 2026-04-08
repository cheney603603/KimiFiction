#!/usr/bin/env python3
"""
工作流执行器
提供命令行界面执行小说创作工作流
"""
import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from enum import Enum

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 导入后端模块
try:
    from app.workflow_engine import WorkflowEngine, WorkflowPhase, get_workflow_engine
    from app.context_manager import LightweightContextManager
    from app.file_manager import NovelFileManager
    from app.agents.analyzer import GenreAnalyzerAgent
    from app.agents.world_builder import WorldBuilderAgent
    from app.agents.character_designer import CharacterDesignerAgent
    from app.agents.plot_designer import PlotDesignerAgent
    from app.agents.outline_generator import OutlineGeneratorAgent
    from app.agents.writer import ChapterWriterAgent
    from app.agents.reviewer import ReviewerAgent
    from app.agents.memory_manager import MemoryManagerAgent
    
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 后端模块不可用: {e}")
    print("   将使用独立模式运行...")
    BACKEND_AVAILABLE = False


class WorkflowRunner:
    """
    工作流执行器
    
    提供交互式和脚本式两种工作流执行方式
    """
    
    PHASE_NAMES = {
        WorkflowPhase.DEMAND_ANALYSIS: "需求分析",
        WorkflowPhase.WORLD_BUILDING: "世界观构建",
        WorkflowPhase.CHARACTER_DESIGN: "角色设计",
        WorkflowPhase.PLOT_DESIGN: "冲突伏笔设计",
        WorkflowPhase.OUTLINE_DRAFT: "剧情大纲",
        WorkflowPhase.OUTLINE_DETAIL: "章节细纲",
        WorkflowPhase.CHAPTER_WRITING: "章节写作",
        WorkflowPhase.CHAPTER_REVIEW: "章节审核",
        WorkflowPhase.CHAPTER_REVISION: "章节修改",
        WorkflowPhase.FRAMEWORK_ADJUSTMENT: "框架调整",
        WorkflowPhase.WAITING_CONFIRM: "等待确认",
        WorkflowPhase.PAUSED: "已暂停",
        WorkflowPhase.COMPLETED: "已完成",
        WorkflowPhase.ERROR: "错误",
    } if BACKEND_AVAILABLE else {}
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.project_id = self.project_path.name
        self.engine = None
        self.file_manager = None
        self._agents = {}
        self._callbacks = []
        
        # 初始化
        self._init()
    
    def _init(self):
        """初始化组件"""
        if BACKEND_AVAILABLE:
            # 创建工作流引擎
            self.engine = get_workflow_engine(
                novel_id=hash(self.project_id) % 100000,
                project_path=str(self.project_path)
            )
            
            # 创建文件管理器
            self.file_manager = NovelFileManager(str(self.project_path))
            
            # 注册Agent
            self._agents = {
                "analyzer": GenreAnalyzerAgent(),
                "world_builder": WorldBuilderAgent(),
                "character_designer": CharacterDesignerAgent(),
                "plot_designer": PlotDesignerAgent(),
                "outline_generator": OutlineGeneratorAgent(),
                "writer": ChapterWriterAgent(),
                "reviewer": ReviewerAgent(),
                "memory_manager": MemoryManagerAgent(),
            }
            
            # 注册Agent到引擎
            for name, agent in self._agents.items():
                self.engine.register_agent(name, agent)
    
    # ===== 交互式执行 =====
    
    async def run_interactive(self):
        """交互式执行工作流"""
        print("\n" + "=" * 60)
        print("📚 小说创作工作流")
        print("=" * 60)
        print(f"项目: {self.project_id}")
        print()
        
        # 检查状态
        if BACKEND_AVAILABLE:
            state = await self.engine.load_state()
            if state and state.current_phase != WorkflowPhase.DEMAND_ANALYSIS:
                print(f"📍 从上次中断处继续: {self.PHASE_NAMES.get(state.current_phase, state.current_phase.value)}")
            else:
                print("🆕 开始新的创作流程")
        else:
            print("⚠️ 后端不可用，使用独立模式")
        
        print()
        
        # 阶段1: 需求分析
        await self._phase_demand_analysis()
        
        # 等待确认
        if not self._wait_confirm("是否继续进入世界观构建？"):
            return
        
        # 阶段2: 世界观构建
        await self._phase_world_building()
        
        if not self._wait_confirm("是否继续进入角色设计？"):
            return
        
        # 阶段3: 角色设计
        await self._phase_character_design()
        
        if not self._wait_confirm("是否继续进入冲突伏笔设计？"):
            return
        
        # 阶段4: 冲突伏笔设计
        await self._phase_plot_design()
        
        if not self._wait_confirm("是否继续生成大纲？"):
            return
        
        # 阶段5: 大纲生成
        await self._phase_outline()
        
        print("\n" + "=" * 60)
        print("✅ 规划阶段完成！")
        print("=" * 60)
        print("\n下一步可执行:")
        print("  /write <章节号>  - 撰写章节")
        print("  /outline        - 查看大纲")
        print("  /status         - 查看进度")
    
    async def _phase_demand_analysis(self):
        """需求分析阶段"""
        print("\n📊 第一阶段: 需求分析")
        print("-" * 40)
        
        # 收集用户需求
        questions = [
            ("类型", "请选择小说类型（玄幻/都市/仙侠/科幻/历史/悬疑/言情）："),
            ("核心卖点", "请描述核心卖点（如：装逼打脸/热血成长/恋爱甜蜜）："),
            ("主角人设", "请描述主角的人设（身份/性格/目标）："),
            ("字数目标", "预计总字数（50万/100万/150万+）："),
            ("参考文风", "参考哪位作者的文风（可选）："),
        ]
        
        answers = {}
        for key, question in questions:
            print(f"\n{question}")
            if key == "类型":
                print("  1. 玄幻  2. 都市  3. 仙侠  4. 科幻  5. 历史  6. 悬疑  7. 言情")
            answer = input("  > ").strip()
            answers[key] = answer
        
        # 保存需求分析结果
        demand_analysis = {
            "genre": answers.get("类型", "玄幻"),
            "main_selling_points": answers.get("核心卖点", ""),
            "protagonist": answers.get("主角人设", ""),
            "target_words": answers.get("字数目标", "100万"),
            "style_reference": answers.get("参考文风", ""),
        }
        
        self._save_json("00_作品设定.json", demand_analysis)
        
        print("\n✅ 需求分析完成")
        print(json.dumps(demand_analysis, ensure_ascii=False, indent=2))
    
    async def _phase_world_building(self):
        """世界观构建阶段"""
        print("\n🌍 第二阶段: 世界观构建")
        print("-" * 40)
        
        if BACKEND_AVAILABLE and "world_builder" in self._agents:
            # 使用Agent生成
            demand = self._load_json("00_作品设定.json")
            
            print("\n⏳ 正在构建世界观，请稍候...")
            result = await self._agents["world_builder"].process({
                "genre": demand.get("genre", "玄幻"),
                "demand_analysis": demand,
            })
            
            if result.get("success"):
                world_setting = result.get("world_setting", {})
                self._save_json("01_世界观设定.json", world_setting)
                
                print("\n✅ 世界观构建完成")
                print(f"\n世界名称: {world_setting.get('world_name', '未命名')}")
                print(f"力量体系: {[s.get('name') for s in world_setting.get('power_systems', [])]}")
                print(f"主要势力: {[f.get('name') for f in world_setting.get('social_structure', {}).get('main_factions', [])]}")
            else:
                print(f"\n❌ 世界观构建失败: {result.get('error')}")
        else:
            # 独立模式：引导式输入
            world_setting = await self._collect_world_setting()
            self._save_json("01_世界观设定.json", world_setting)
            print("\n✅ 世界观构建完成")
    
    async def _collect_world_setting(self) -> Dict:
        """收集世界观设定"""
        print("\n请依次输入世界观设定：")
        
        setting = {
            "world_name": input("  世界名称: ").strip() or "待定",
            "overview": input("  世界概述: ").strip() or "待定",
            "power_systems": [],
            "social_structure": {"main_factions": []},
        }
        
        # 力量体系
        print("\n  添加力量体系（输入空结束）:")
        while True:
            name = input("    体系名称: ").strip()
            if not name:
                break
            desc = input("    体系描述: ").strip()
            setting["power_systems"].append({
                "name": name,
                "description": desc,
            })
        
        # 势力
        print("\n  添加势力（输入空结束）:")
        while True:
            name = input("    势力名称: ").strip()
            if not name:
                break
            desc = input("    势力描述: ").strip()
            setting["social_structure"]["main_factions"].append({
                "name": name,
                "description": desc,
            })
        
        return setting
    
    async def _phase_character_design(self):
        """角色设计阶段"""
        print("\n👥 第三阶段: 角色设计")
        print("-" * 40)
        
        if BACKEND_AVAILABLE and "character_designer" in self._agents:
            print("\n⏳ 正在设计角色，请稍候...")
            
            result = await self._agents["character_designer"].process({
                "genre": self._load_json("00_作品设定.json").get("genre", "玄幻"),
                "plot_summary": "",
                "num_characters": 5,
            })
            
            if result.get("success"):
                characters = result.get("characters", [])
                self._save_json("02_角色设定.json", {"characters": characters})
                
                print("\n✅ 角色设计完成")
                for i, char in enumerate(characters, 1):
                    print(f"  {i}. {char.get('name', '未知')}（{char.get('role_type', '配角')}）")
            else:
                print(f"\n❌ 角色设计失败: {result.get('error')}")
        else:
            characters = await self._collect_characters()
            self._save_json("02_角色设定.json", {"characters": characters})
            print("\n✅ 角色设计完成")
    
    async def _collect_characters(self) -> list:
        """收集角色设定"""
        characters = []
        
        print("\n请依次输入角色设定（输入空角色名结束）:")
        
        while True:
            name = input("\n  角色名称（空结束）: ").strip()
            if not name:
                break
            
            role = input(f"  {name}的角色定位（主角/反派/配角）: ").strip() or "配角"
            personality = input(f"  {name}的性格特点: ").strip()
            background = input(f"  {name}的背景故事: ").strip()
            goals = input(f"  {name}的目标: ").strip()
            
            characters.append({
                "name": name,
                "role_type": role,
                "profile": {
                    "personality": personality,
                    "background": background,
                    "goals": [goals] if goals else [],
                }
            })
        
        return characters
    
    async def _phase_plot_design(self):
        """冲突伏笔设计阶段"""
        print("\n🎭 第四阶段: 冲突与伏笔设计")
        print("-" * 40)
        
        if BACKEND_AVAILABLE and "plot_designer" in self._agents:
            print("\n⏳ 正在设计冲突与伏笔，请稍候...")
            
            result = await self._agents["plot_designer"].process({
                "world_setting": self._load_json("01_世界观设定.json"),
                "characters": self._load_json("02_角色设定.json", {}).get("characters", []),
                "demand_analysis": self._load_json("00_作品设定.json"),
            })
            
            if result.get("success"):
                plot_setting = result.get("plot_setting", {})
                self._save_json("03_故事线设定.json", plot_setting)
                
                print("\n✅ 冲突与伏笔设计完成")
                print(f"\n核心冲突: {len(plot_setting.get('core_conflicts', []))}个")
                print(f"伏笔计划: {len(plot_setting.get('foreshadowing_plan', []))}个")
            else:
                print(f"\n❌ 设计失败: {result.get('error')}")
        else:
            plot_setting = await self._collect_plot_setting()
            self._save_json("03_故事线设定.json", plot_setting)
            print("\n✅ 冲突与伏笔设计完成")
    
    async def _collect_plot_setting(self) -> Dict:
        """收集冲突伏笔设定"""
        setting = {
            "core_conflicts": [],
            "foreshadowing_plan": [],
        }
        
        print("\n添加核心冲突（输入空结束）:")
        while True:
            name = input("\n  冲突名称（空结束）: ").strip()
            if not name:
                break
            conflict_type = input(f"  {name}的类型（内/外/群体）: ").strip() or "外部"
            parties = input(f"  {name}的冲突方: ").strip()
            
            setting["core_conflicts"].append({
                "name": name,
                "type": conflict_type,
                "parties": parties.split("、"),
            })
        
        print("\n添加伏笔（输入空结束）:")
        while True:
            title = input("\n  伏笔标题（空结束）: ").strip()
            if not title:
                break
            first_ch = input(f"  {title}首次出现章节: ").strip()
            resolve_ch = input(f"  {title}回收章节: ").strip()
            
            setting["foreshadowing_plan"].append({
                "title": title,
                "first_appearance": {"chapter": int(first_ch) if first_ch.isdigit() else 1},
                "resolution": {"chapter": int(resolve_ch) if resolve_ch.isdigit() else 50},
            })
        
        return setting
    
    async def _phase_outline(self):
        """大纲生成阶段"""
        print("\n📝 第五阶段: 剧情大纲生成")
        print("-" * 40)
        
        if BACKEND_AVAILABLE and "outline_generator" in self._agents:
            print("\n⏳ 正在生成大纲，请稍候...")
            
            result = await self._agents["outline_generator"].process({
                "genre": self._load_json("00_作品设定.json").get("genre", "玄幻"),
                "characters": self._load_json("02_角色设定.json", {}).get("characters", []),
                "plot_summary": json.dumps(self._load_json("03_故事线设定.json"), ensure_ascii=False),
                "total_volumes": 3,
                "chapters_per_volume": 100,
            })
            
            if result.get("success"):
                outline = {
                    "volumes": result.get("volumes", []),
                    "overall_arc": result.get("overall_arc", ""),
                    "estimated_chapters": result.get("estimated_chapters", 0),
                }
                self._save_json("04_分卷大纲/大纲总览.json", outline)
                
                print("\n✅ 大纲生成完成")
                for vol in outline.get("volumes", []):
                    print(f"  第{vol.get('volume_number', '?')}卷: {vol.get('title', '未命名')}")
            else:
                print(f"\n❌ 大纲生成失败: {result.get('error')}")
        else:
            print("\n⚠️ 后端不可用，请手动编辑大纲文件")
    
    # ===== 辅助方法 =====
    
    def _wait_confirm(self, question: str) -> bool:
        """等待用户确认"""
        print(f"\n{question} (y/n)")
        answer = input("  > ").strip().lower()
        return answer in ["y", "yes", "是", "好"]
    
    def _load_json(self, filename: str, default=None) -> Dict:
        """加载JSON文件"""
        filepath = self.project_path / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return default or {}
    
    def _save_json(self, filename: str, data: Dict) -> None:
        """保存JSON文件"""
        filepath = self.project_path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data["saved_at"] = datetime.now().isoformat()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ===== 脚本式执行 =====
    
    async def run_script(self, script_file: str):
        """执行脚本文件"""
        with open(script_file, "r", encoding="utf-8") as f:
            script = json.load(f)
        
        print(f"\n📜 执行脚本: {script_file}")
        print("=" * 60)
        
        for step in script.get("steps", []):
            phase = step.get("phase")
            input_data = step.get("input", {})
            
            print(f"\n➡️  {phase}")
            
            if phase == "demand_analysis":
                self._save_json("00_作品设定.json", input_data)
            elif phase == "world_building":
                self._save_json("01_世界观设定.json", input_data)
            elif phase == "character_design":
                self._save_json("02_角色设定.json", {"characters": input_data.get("characters", [])})
            elif phase == "plot_design":
                self._save_json("03_故事线设定.json", input_data)
            elif phase == "outline":
                self._save_json("04_分卷大纲/大纲总览.json", input_data)
            
            print(f"   ✅ 完成")
        
        print("\n" + "=" * 60)
        print("✅ 脚本执行完成")
    
    # ===== 状态查询 =====
    
    async def get_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        status = {
            "project_id": self.project_id,
            "project_path": str(self.project_path),
            "files": {},
        }
        
        # 检查各文件是否存在
        files_to_check = [
            ("00_作品设定.json", "demand_analysis"),
            ("01_世界观设定.json", "world_setting"),
            ("02_角色设定.json", "character_design"),
            ("03_故事线设定.json", "plot_design"),
            ("04_分卷大纲/大纲总览.json", "outline"),
        ]
        
        for filename, key in files_to_check:
            filepath = self.project_path / filename
            status["files"][key] = filepath.exists()
        
        # 统计章节
        outline_count = len(list(self.project_path.glob("05_章节细纲/**/*.json")))
        chapter_count = len(list(self.project_path.glob("06_正文/**/*.md")))
        
        status["outline_count"] = outline_count
        status["chapter_count"] = chapter_count
        
        # 统计字数
        total_words = 0
        for chapter_file in self.project_path.glob("06_正文/**/*.md"):
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content.startswith("---"):
                    content = content.split("---", 2)[-1]
                total_words += len([c for c in content if '\u4e00' <= c <= '\u9fff'])
        
        status["total_words"] = total_words
        
        # 计算进度
        completed = sum(1 for v in status["files"].values() if v)
        status["progress"] = int((completed / 5) * 100)
        
        return status
    
    def print_status(self):
        """打印状态"""
        status = asyncio.run(self.get_status())
        
        print(f"\n📚 项目状态: {self.project_id}")
        print("=" * 60)
        print(f"路径: {status['project_path']}")
        print(f"进度: {status['progress']}%")
        print()
        
        file_names = {
            "demand_analysis": "需求分析",
            "world_setting": "世界观设定",
            "character_design": "角色设计",
            "plot_design": "冲突伏笔",
            "outline": "剧情大纲",
        }
        
        for key, name in file_names.items():
            check = "✅" if status["files"].get(key) else "⬜"
            print(f"  {check} {name}")
        
        print()
        print(f"📊 章节细纲: {status['outline_count']}章")
        print(f"📖 正文: {status['chapter_count']}章 ({status['total_words']:,}字)")
        print()


def main():
    parser = argparse.ArgumentParser(description="小说创作工作流执行器")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    run_parser = subparsers.add_parser("run", help="运行工作流")
    run_parser.add_argument("project_path", help="项目路径")
    run_parser.add_argument("--interactive", "-i", action="store_true", help="交互式执行")
    run_parser.add_argument("--script", "-s", help="执行脚本文件")
    
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.add_argument("project_path", help="项目路径")
    
    args = parser.parse_args()
    
    if args.command == "run":
        runner = WorkflowRunner(args.project_path)
        
        if args.interactive:
            asyncio.run(runner.run_interactive())
        elif args.script:
            asyncio.run(runner.run_script(args.script))
        else:
            # 默认交互式
            asyncio.run(runner.run_interactive())
    
    elif args.command == "status":
        runner = WorkflowRunner(args.project_path)
        runner.print_status()


if __name__ == "__main__":
    main()
