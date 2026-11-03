# KimiFiction 项目进度

**最后更新**: 2026-11-03

---

## ✅ 已完成模块

### 1. 基础框架与部署
- [x] Docker Compose 一键启动（MySQL / Redis / Qdrant）
- [x] 前后端分离架构（React 5173 → FastAPI 8080）
- [x] JWT 认证、WebSocket 实时推送、Redis 任务队列

### 2. 多智能体创作管线
- [x] 12+ Agent / 6 阶段工作流（需求分析 → 世界观构建 → 角色设计 → 剧情设计 → 大纲草案 → 大纲细化）
- [x] LangGraph 工作流编排 + 状态快照 + 任务进度追踪
- [x] 长文本记忆（RAG 向量检索 + 分层摘要，1000 章不遗忘）
- [x] 章节自动撰写 + 实体自动抽取回流知识库

### 3. 世界观可视化与实体管理
- [x] 实体管理 API + 页面（character/faction/skill/item/location 五类，关系边，批量删除）
- [x] 世界观聚合接口 `GET /novels/{id}/world`
- [x] 可视化三页：实体图谱（ReactFlow 力导向图）/ 小说地图 / 知识库
- [x] 演示世界观种子脚本 `scripts/seed_demo_world.py`

### 4. LLM 接入
- [x] DeepSeek 直连（默认，含联影网关兼容、流式调用）
- [x] OpenAI / chat2api（Kimi/元宝）/ Ollama
- [x] 本地 GGUF 模型（Qwen3.5-2B / 35B-A3B），CPU/RTX4070 自适应

### 5. 写作质量管线与评测
- [x] Rubric 八维评测（LLM-as-Judge，权重可配，历史可追溯）
- [x] 评测规则优化器（`evaluation_optimizer`，迭代 `evaluate_rules_llm.csv`）
- [x] 确定性硬门禁（字数/结尾/场景均衡/角色名白名单/力量等级白名单/伏笔台账，≤1 次定向重写，仍不过标记 flagged）
- [x] 写作管线 V2（分场景生成 3×~1000字 + 场景节拍规划 + 规则化缝合，开关 `WRITING_PIPELINE_V2`）
- [x] 反模板化（章节类型池 5 类，禁 3 连同型）与风格锚点（style_profile few-shot，无样本降级）
- [x] 异构盲评（匿名审稿人 persona）与三尺度诊断指标（句长方差/AI词命中/段落熵/总结句密度/跨章相似度/情绪曲线）
- [x] 成本熔断（单章 LLM 调用预算，超限跳过重写）与伏笔台账（埋设/回收/超期检测）
- [x] 移除 RL 训练体系（GRPO/TPO/模仿/LoRA 已清理，LLM-Judge/数据审计/八维评测保留）

### 6. 运维与自动化
- [x] 全流程驱动脚本 `scripts/run_novel_pipeline.py`（design/full/status，断点续跑 `--from-phase`，`full --watch` 守护，`--webhook` 通知）
- [x] 端到端测试脚本（`comprehensive_test.py` / `e2e_uiai.py` / `test_frontend.py`）
- [x] 世界观页面验收脚本（`verify_world_pages.py` / `screenshot_world_pages.py`）
- [x] 数据导出（TXT/Markdown/JSON/角色/大纲）与 EPUB

---

## 🚀 一键启动

```bash
docker-compose up -d          # MySQL/Redis/Qdrant
cd backend && python main.py  # 后端 8080
cd frontend && npm run dev    # 前端 5173
```

Windows 直接运行 `start.bat`。

## 🎯 快速验收路线

```bash
# 1. 灌入演示世界观（可视化三页验收）
python scripts/seed_demo_world.py <novel_id> e2e_test_user Test123

# 2. 全流程设计阶段（6 阶段自动跑通）
python scripts/run_novel_pipeline.py design --title "修真大佬重返都市" --genre "都市修真" --idea "..."

# 3. 批量写章节
python scripts/run_novel_pipeline.py chapters --novel <id> --from 1 --count 5
```

---

## 📋 下一步计划

- [ ] 更多图表类型（时间线、情感曲线）
- [ ] 盲读 A/B 验收（改造前 A 组 vs 改造后 B 组，§8 协议）
- [ ] 评测反馈回流写作提示词（评分驱动定向修订）
- [ ] 集成测试覆盖与性能基准
- [ ] 细粒度人工干预（单章改写/剧情分支）
