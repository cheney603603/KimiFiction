#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端 Writer-Reader RL 测试脚本"""
import sys, os, asyncio, re, time
sys.path.insert(0, os.path.dirname(__file__))

from app.services.llm_service import LLMService, LLMProvider
from app.agents.writer import ChapterWriterAgent
from app.agents.reader import ReaderAgent
from app.writer_reader_rl import WriterReaderLoop


def clean_think(raw):
    """清理思考标签"""
    return re.sub(r"<[^>]+>", "", raw).strip()


async def test_llm_basic():
    """测试1: LLM基础调用"""
    print("[1/5] Test LLM basic call (Ollama deepseek-r1:8b)...")
    llm = LLMService(provider=LLMProvider.LOCAL_LLAMA, model="deepseek-r1:8b", max_tokens=300)

    t0 = time.time()
    resp = await llm.chat([{"role": "user", "content": "用一句话描述你是什么"}])
    t = time.time() - t0

    clean = clean_think(resp)
    ok = len(clean) > 5
    print("    [%s] time=%.1fs, len=%d" % ("OK" if ok else "FAIL", t, len(clean)))
    print("    Reply: " + clean[:100])
    return ok


async def test_writer_agent():
    """测试2: Writer Agent"""
    print("[2/5] Test Writer Agent...")
    agent = ChapterWriterAgent()

    ctx = {
        "novel_id": 999,
        "chapter_number": 1,
        "outline": {
            "summary": "李云在城门口告别家人，踏上未知旅程",
            "key_events": ["告别家人", "踏上旅途", "看到新风景"],
        },
        "characters": [{"name": "李云", "profile": {"personality": "沉稳内敛", "age": 18}}],
        "context": {},
        "writing_style": "叙事流畅，情节紧凑",
        "env_level": "normal",
        "dialogue_ratio": 0.3,
    }

    t0 = time.time()
    result = await agent.process(ctx)
    t = time.time() - t0

    ok = result.get("success", False)
    content = result.get("content", "")
    print("    [%s] time=%.1fs, chapter_len=%d" % ("OK" if ok else "FAIL", t, len(content)))
    if ok:
        print("    Preview: " + content[:80] + "...")
    return ok, content[:500] if ok else ""


async def test_reader_agent(chapter_content):
    """测试3: Reader Agent"""
    print("[3/5] Test Reader Agent...")
    agent = ReaderAgent()

    ctx = {
        "chapter_number": 1,
        "chapter_content": chapter_content,
        "outline": {"summary": "李云告别家人踏上旅程"},
        "characters": [{"name": "李云"}],
    }

    t0 = time.time()
    result = await agent.process(ctx)
    t = time.time() - t0

    ok = result.get("success", False)
    feedback = result.get("reader_feedback", {})
    score = feedback.get("reader_score", 0)
    hook = feedback.get("hook_score", 0)

    print("    [%s] time=%.1fs, reader_score=%.2f, hook_score=%.2f" % ("OK" if ok else "FAIL", t, score, hook))
    if ok:
        print("    Feedback: " + str(feedback)[:150])
    return ok


async def test_writer_reader_loop():
    """测试4: Writer-Reader RL 完整循环"""
    print("[4/5] Test Writer-Reader RL loop (2 rounds)...")

    loop = WriterReaderLoop(
        novel_id=999,
        chapter_number=1,
        max_rounds=2,
        score_threshold=0.5,
    )

    t0 = time.time()
    result = await loop.run(
        outline={
            "chapter_number": 1,
            "summary": "主角李云在城门口告别家人，踏上未知旅程",
            "key_events": ["告别家人", "踏上旅途", "看到新风景"],
        },
        characters=[{"name": "李云", "profile": {"personality": "沉稳内敛", "age": 18}}],
        context={"writing_style": "叙事流畅"},
        initial_draft="",
    )
    t = time.time() - t0

    ok = result.get("success", False)
    rounds = result.get("total_rounds", 0)
    reward = result.get("final_reward", 0)
    word_count = result.get("word_count", 0)
    passed = result.get("passed", False)

    print("    [%s] time=%.1fs, rounds=%d, reward=%.3f, words=%d" % ("OK" if ok else "FAIL", t, rounds, reward, word_count))
    if ok:
        report = loop.get_learning_report()
        print("    Most effective action: " + report.get("most_effective_action", "?"))
        print("    Passed threshold: " + str(passed))
    return ok


async def test_rag_system():
    """测试5: RAG 系统"""
    print("[5/5] Test RAG system...")
    from app.rag_system import HierarchicalRAG

    rag = HierarchicalRAG(novel_id=999)

    result = await rag.index_chapter(
        chapter_number=1,
        chapter_content="李云站在城门口，望着远处的群山。他深吸一口气，转身离去。",
        chapter_summary="主角离别家乡",
    )

    chunks = result.get("indexed_chunks", 0)
    print("    [OK] indexed_chunks=%d" % chunks)

    # 检索测试
    retrieve_result = await rag.retrieve_for_writer(
        {"summary": "李云离别", "key_events": ["告别", "旅途"]},
        top_k=5,
    )
    retrieved = len(retrieve_result.get("chunks", []))
    print("    [OK] retrieved_chunks=%d, method=%s" % (retrieved, retrieve_result.get("retrieval_method", "?")))
    return True


async def main():
    print("=" * 60)
    print("KimiFiction Writer-Reader RL E2E Test")
    print("Model: Ollama deepseek-r1:8b")
    print("=" * 60)
    print()

    results = {}

    # 1: LLM
    try:
        results["llm"] = await test_llm_basic()
    except Exception as e:
        print("    [FAIL] " + str(e))
        results["llm"] = False
    print()

    # 2: Writer Agent
    if results.get("llm"):
        try:
            ok, content = await test_writer_agent()
            results["writer"] = ok
            results["chapter"] = content
        except Exception as e:
            print("    [FAIL] " + str(e))
            results["writer"] = False
    else:
        results["writer"] = False
        print("    [SKIP] LLM failed")
    print()

    # 3: Reader Agent
    if results.get("chapter"):
        try:
            ok = await test_reader_agent(results["chapter"])
            results["reader"] = ok
        except Exception as e:
            print("    [FAIL] " + str(e))
            results["reader"] = False
    else:
        results["reader"] = False
        print("    [SKIP] Writer failed")
    print()

    # 4: RL Loop
    try:
        ok = await test_writer_reader_loop()
        results["rl_loop"] = ok
    except Exception as e:
        print("    [FAIL] " + str(e))
        results["rl_loop"] = False
    print()

    # 5: RAG
    try:
        ok = await test_rag_system()
        results["rag"] = ok
    except Exception as e:
        print("    [FAIL] " + str(e))
        results["rag"] = False
    print()

    # Summary
    print("=" * 60)
    print("Results:")
    names = {"llm": "LLM Call", "writer": "Writer Agent", "reader": "Reader Agent", "rl_loop": "RL Loop", "rag": "RAG System"}
    for key, label in names.items():
        ok = results.get(key, False)
        print("  %-20s: %s" % (label, "PASS" if ok else "FAIL"))
    passed = sum(1 for v in results.values() if v)
    print("\nPass rate: %d/%d" % (passed, len(results)))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
