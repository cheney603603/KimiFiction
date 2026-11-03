"""
小说写作管线 V2（§3.1 / P1）
============================

场景节拍规划(1×JSON) → 逐场景生成(3×纯文本 ~1000 字) → 规则化缝合(0 LLM)
→ 硬门禁(确定性规则，≤1 次定向重写) → 异构盲评(1×) → 三尺度诊断指标

置于 `WRITING_PIPELINE_V2` 开关之后（默认关闭，§9 回滚策略）。
"""
import json
import re
from typing import Any, Dict, List, Optional, Sequence
from loguru import logger

from app.services.llm_service import LLMProvider
from app.services.llm_service_tracked import TrackedLLMService
from app.services.hard_gate import ChapterHardGate, count_words
from app.services.writing_diagnostics import compute_diagnostics
from app.core.json_utils import extract_json_from_response


class ChapterTypePool:
    """反模板化：章节类型池，禁止连续 3 章同类型（§5.1②）。"""

    TYPES = ["conflict", "transition", "emotion", "information", "ensemble"]
    LABELS = {
        "conflict": "冲突章",
        "transition": "过渡章",
        "emotion": "情绪章",
        "information": "信息章",
        "ensemble": "群像章",
    }

    @classmethod
    def pick(cls, recent: Sequence[str]) -> str:
        """从近几章类型中选一个不构成 3 连的章节类型。"""
        recent = list(recent or [])
        for t in cls.TYPES:
            if recent[-2:] != [t, t]:
                return t
        return "conflict"


class ScenePipeline:
    """分场景写作管线。"""

    SCENE_TEMPLATES = {
        "conflict": (
            "冲突章铁律：开场即进冲突，对话推进，爽点放在中后段；"
            "人物台词要具体、带情绪，反派嚣张具体化；本场景必须有明确的胜负/矛盾推进。"
        ),
        "transition": (
            "过渡章铁律：节奏放缓但不拖沓，用细节和人物互动承接上一场景；"
            "可写赶路、休整、布置计划；禁堆砌环境描写，忌流水账，要有一个人物变化或新发现。"
        ),
        "emotion": (
            "情绪章铁律：以人物内心戏与互动情绪为主，写具体动作细节代替内心独白抒情；"
            "允许慢节奏，但每段要有画面感，禁空泛抒情、禁'一种说不出的感觉'类套话。"
        ),
        "information": (
            "信息章铁律：以对话和观察带出设定（境界、势力、往事），不写说明书；"
            "把信息嵌进人物行动与对话，一段讲一件事，避免大段旁白。"
        ),
        "ensemble": (
            "群像章铁律：多角色轮流出场，每个角色要有一句特征性台词或动作；"
            "用对比制造张力，避免角色间对话同质化。"
        ),
    }

    def __init__(
        self,
        novel_id: int,
        chapter_number: int,
        *,
        target_words: int = 3000,
        chapter_type: str = "conflict",
        style_samples: Optional[Sequence[str]] = None,
    ):
        self.novel_id = novel_id
        self.chapter_number = chapter_number
        self.target_words = target_words
        self.chapter_type = chapter_type if chapter_type in ChapterTypePool.TYPES else "conflict"
        self.style_samples = list(style_samples or [])
        self.llm = TrackedLLMService(
            provider=LLMProvider.DEEPSEEK,
            novel_id=novel_id,
            agent_name="scene_pipeline",
            auto_track=True,
        )

    # ── 主入口 ─────────────────────────────

    async def run(
        self,
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        scenes = await self._plan_scenes(outline)
        scene_texts = []
        scene_ends = []
        cursor = 0
        for scene in scenes:
            text = await self._generate_scene(scene, outline, characters, context)
            text = (text or "").strip()
            scene_texts.append(text)
            cursor += len(text)
            scene_ends.append(cursor)

        content = self._stitch(scene_texts)

        # 硬门禁 + ≤1 次定向重写
        hard_gate = await self._apply_hard_gate(
            content, scene_ends, outline, characters, context
        )
        content = hard_gate["content"]
        flagged = hard_gate["flagged"]

        # 异构盲评
        review = await self._blind_review(content, outline)

        # 三尺度诊断指标
        prev_openings = context.get("prev_openings")
        diagnostics = compute_diagnostics(content, prev_openings=prev_openings)

        return {
            "success": True,
            "final_draft": content,
            "word_count": count_words(content),
            "scenes": [s.get("goal", "") for s in scenes],
            "chapter_type": self.chapter_type,
            "hard_gate": hard_gate["details"],
            "flagged": flagged,
            "gate_failures": hard_gate["failures"],
            "blind_review": review,
            "diagnostics": diagnostics,
            "total_llm_calls": 4 + (1 if hard_gate["rewritten"] else 0),
        }

    # ── [1] 场景节拍规划（1×JSON）──────────

    async def _plan_scenes(self, outline: Dict[str, Any]) -> List[Dict[str, Any]]:
        label = ChapterTypePool.LABELS.get(self.chapter_type, "冲突章")
        system = (
            "你是网文章节'场景节拍规划器'。将章节拆分为恰好 3 个场景，每个场景 1000 字左右。"
            "只输出合法 JSON 数组，不要其他文字。每项字段："
            '{"view":"视角人物","goal":"本场景目标(一句)","conflict":"冲突/事件(一句)",'
            '"close":"收束/钩子(一句)","words":目标字数}'
        )
        user = (
            f"章节类型：{label}\n"
            f"章节细纲：{json.dumps(outline, ensure_ascii=False)}\n"
            "请拆分 3 个场景。"
        )
        try:
            raw = await self.llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                json_mode=True,
                temperature=0.4,
            )
            parsed, _ = extract_json_from_response(raw)
            scenes = parsed if isinstance(parsed, list) else []
            scenes = [s for s in scenes if isinstance(s, dict)]
            if len(scenes) != 3:
                raise ValueError(f"场景规划应返回 3 个，实际 {len(scenes)}")
            for s in scenes:
                s.setdefault("words", self.target_words // 3)
            logger.info(f"[ScenePipeline] 场景规划完成: {len(scenes)} 场景")
            return scenes
        except Exception as e:
            logger.warning(f"[ScenePipeline] 场景规划失败，降级为固定三分: {e}")
            return [
                {"view": "", "goal": "开场，进入本章第一个事件", "conflict": "引出冲突", "close": "小冲突结束留悬念", "words": self.target_words // 3},
                {"view": "", "goal": "推进主线，展开细节", "conflict": "矛盾升级", "close": "抛出新信息", "words": self.target_words // 3},
                {"view": "", "goal": "本章收束，制造钩子", "conflict": "冲突顶点", "close": "章末钩子", "words": self.target_words // 3},
            ]

    # ── [2] 逐场景生成（纯文本）────────────

    async def _generate_scene(
        self,
        scene: Dict[str, Any],
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
    ) -> str:
        words = int(scene.get("words") or self.target_words // 3)
        label = ChapterTypePool.LABELS.get(self.chapter_type, "冲突章")
        rules = self.SCENE_TEMPLATES.get(self.chapter_type, self.SCENE_TEMPLATES["conflict"])

        system_parts = [
            "你是一位网文写手，专写大白话、快节奏、读起来上头的网文。",
            f"【章节类型】{label}",
            f"【本章铁律】{rules}",
            "【写作要求】",
            "1. 全篇大白话，句子要短，一句一个意思。",
            "2. 禁堆砌形容词与空泛修饰（夜色如墨、若有所思、心中涌起一股等一律删掉）。",
            "3. 只输出本场景正文，从第一句开始，不写标题，不加解释。",
        ]
        if self.style_samples:
            system_parts.append(
                "【风格锚点·模仿对象】（模仿这些文本的语感和句法，不是抄内容）：\n"
                + "\n---\n".join(s[:500] for s in self.style_samples[:3])
            )

        char_info = "\n".join(
            f"{c.get('name','')}:{c.get('profile',{}).get('personality','') or c.get('personality','')}"
            for c in (characters or [])[:5]
        ) or "（无）"

        user = (
            f"【场景节拍】\n{json.dumps(scene, ensure_ascii=False)}\n\n"
            f"【全局设定】\n{json.dumps(context.get('world_setting', {}), ensure_ascii=False)[:1500]}\n\n"
            f"【前情提要】\n{context.get('previous_chapter_summary', '')[:600] or '（本章为首章）'}\n\n"
            f"【进行中的剧情线】\n{json.dumps(context.get('ongoing_plots', []), ensure_ascii=False)[:500]}\n\n"
            f"【主要人物】\n{char_info}\n\n"
            f"【章节细纲】\n{json.dumps(outline, ensure_ascii=False)[:800]}\n\n"
            f"请写出本场景正文（约 {words} 字）："
        )

        try:
            text = await self.llm.chat(
                [{"role": "system", "content": "\n".join(system_parts)},
                 {"role": "user", "content": user}],
                json_mode=False,
                temperature=0.7,
                max_tokens=8192,
            )
            text = (text or "").strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            return text
        except Exception as e:
            logger.error(f"[ScenePipeline] 场景生成失败: {e}")
            return ""

    # ── [3] 场景缝合（0 LLM，规则化）───────

    def _stitch(self, scene_texts: List[str]) -> str:
        parts = [t for t in scene_texts if t and t.strip()]
        if not parts:
            return ""
        # 规则化过渡：空行分节 + 去除每段首部的括号说明（如"（切换视角）"），保持最小干预
        cleaned = []
        for p in parts:
            p = p.strip()
            if p.startswith("（") or p.startswith("("):
                p = re.sub(r"^（.*?）", "", p).strip()
                p = re.sub(r"^\(.*?\)", "", p).strip()
            cleaned.append(p)
        return "\n\n".join(cleaned)

    # ── [4] 硬门禁 + 定向重写 ──────────────

    async def _apply_hard_gate(
        self,
        content: str,
        scene_ends: List[int],
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        char_names = [c.get("name") for c in (characters or []) if c.get("name")]
        gate = ChapterHardGate(target_words=self.target_words)
        result = gate.check(
            content,
            character_names=char_names,
            power_levels=context.get("power_levels"),
            expected_scenes=3,
            scene_ends=scene_ends,
            overdue_foreshadowing=context.get("overdue_foreshadowing"),
        )
        details = {
            "passed": result.passed,
            "checks": [c.__dict__ for c in result.checks],
            "failures": [c.__dict__ for c in result.failures],
            "rewritten": False,
        }
        if result.passed:
            return {"content": content, "flagged": False, "failures": [], "rewritten": False, "details": details}

        # 定向重写 ≤1 次（P2 成本熔断：预算不足则跳过重写，直接标记）
        from app.services.cost_breaker import CostBreaker
        breaker = CostBreaker.from_params(context or {})
        if not breaker.should_rewrite(len(context.get("loop_history") or [])):
            details["flagged"] = True
            return {
                "content": content,
                "flagged": True,
                "failures": [c["rule"] for c in details["failures"]],
                "rewritten": False,
                "details": details,
            }

        # 定向重写 ≤1 次
        logger.warning(f"[ScenePipeline] 硬门禁未通过(第{self.chapter_number}章): {result.failure_summary()}")
        rewritten = await self._targeted_rewrite(content, result.failure_summary(), outline, characters, context)
        details["rewritten"] = bool(rewritten)
        if rewritten and rewritten != content:
            gate2 = ChapterHardGate(target_words=self.target_words)
            result2 = gate2.check(
                rewritten,
                character_names=char_names,
                power_levels=context.get("power_levels"),
                expected_scenes=3,
                scene_ends=scene_ends,
                overdue_foreshadowing=context.get("overdue_foreshadowing"),
            )
            details["rewrite_passed"] = result2.passed
            if result2.passed:
                return {"content": rewritten, "flagged": False, "failures": [], "rewritten": True, "details": details}

        details["flagged"] = True
        return {
            "content": rewritten or content,
            "flagged": True,
            "failures": [c["rule"] for c in details["failures"]],
            "rewritten": bool(rewritten),
            "details": details,
        }

    async def _targeted_rewrite(
        self,
        content: str,
        failure_summary: str,
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
    ) -> str:
        user = (
            f"上一版草稿（保留其中最好的部分）：\n{content[:6000]}\n\n"
            f"硬门禁未通过，请针对性修订：\n{failure_summary}\n\n"
            "输出修订后的完整正文，不要输出说明。"
        )
        try:
            text = await self.llm.chat(
                [{"role": "system", "content": "你是网文写手，负责定向修订章节，保留原稿精华。"},
                 {"role": "user", "content": user}],
                json_mode=False,
                temperature=0.5,
                max_tokens=8192,
            )
            return (text or "").strip()
        except Exception as e:
            logger.error(f"[ScenePipeline] 定向重写失败: {e}")
            return ""

    # ── [5] 异构盲评（换 persona + 温度）────

    async def _blind_review(self, content: str, outline: Dict[str, Any]) -> Dict[str, Any]:
        system = (
            "你是一位匿名的网络小说审稿人。你只会收到一段正文，"
            "不知道作者、版本或来源。请仅凭文本质量判断。"
            "只输出 JSON：{score(1-10 读者愿意追读程度), naturalness(1-5 像不像真人手写), "
            "looks_ai(true/false 是否像AI写的), comments(数组，具体指出问题)}"
        )
        user = f"正文如下（节选）：\n{content[:8000]}"
        try:
            raw = await self.llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                json_mode=True,
                temperature=0.3,
            )
            parsed, _ = extract_json_from_response(raw)
            if isinstance(parsed, dict):
                return {
                    "score": parsed.get("score"),
                    "naturalness": parsed.get("naturalness"),
                    "looks_ai": bool(parsed.get("looks_ai", False)),
                    "comments": parsed.get("comments") or [],
                }
            return {"error": "盲评解析失败"}
        except Exception as e:
            logger.warning(f"[ScenePipeline] 盲评失败: {e}")
            return {"error": str(e)}
