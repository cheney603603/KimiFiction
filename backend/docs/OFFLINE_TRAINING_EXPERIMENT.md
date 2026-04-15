# 离线训练实验说明

这个文档对应根目录脚本 `run_offline_training_experiment.py`。

## 目的

在当前机器与仓库条件下，尽可能真实地完成以下工作：

1. 运行模仿学习数据生成
2. 检查 Qwen GGUF 模型是否具备真实 SFT/LoRA 微调条件
3. 执行可复现的离线 GRPO 策略优化
4. 生成 baseline / imitation / GRPO 三阶段输出对比
5. 沉淀完整实验产物与报告

## 为什么不是“真实 LoRA 已训练成功”

当前仓库下可用基础模型是：

- `models/Qwen3.5-2B-Q4_K_M.gguf`

这会带来两个现实限制：

1. `GGUF` 不是 HuggingFace 可训练权重目录，不能直接走 `transformers + peft` 的常规 LoRA/SFT 训练流程。
2. 当前机器缺少 `nmake` / `cl`，无法现场编译 `llama-cpp-python` 或补齐 `llama.cpp` 的训练工具链。

因此，脚本不会伪造“LoRA 训练完成”，而是把 SFT 阶段如实记录为可行性检查结果，并输出阻塞原因。

## 运行方式

在仓库根目录执行：

```powershell
python run_offline_training_experiment.py
```

## 产物目录

每次执行会创建：

```text
training_runs/offline_experiment_时间戳/
```

其中包含：

- `01_imitation_learning/`
- `02_sft_check/`
- `03_grpo_training/`
- `04_evaluation/`
- `RUN_SUMMARY.json`

## 阶段说明

### 1. 模仿学习

直接复用仓库中的 `backend/app/training/imitation_learning.py`：

- 加载 `reference/` 下参考小说
- 提取风格特征
- 生成训练样本
- 导出 `json/jsonl`

### 2. SFT 可行性检查

不会假装训练，而是检查：

- 模型是否为可训练权重
- 本地是否具备编译工具链
- 是否存在 `llama.cpp/lora-finetune`

### 3. GRPO

直接复用仓库中的 `backend/app/training/grpo_trainer.py` 的：

- `GRPOConfig`
- `GRPOTrainer`
- `RewardFunction`
- `GRPOPolicy`

但候选文本生成改成离线方式：

- 用模仿学习样本构造 baseline
- 用参考文本生成 imitation 阶段候选
- 用 `generate/revise/delete/keep` 四类动作做 GRPO 迭代
- 用启发式 reader feedback 驱动 reward

### 4. 评估

输出：

- prompt 级别三阶段文本
- 各阶段 reader score
- imitation/baseline、grpo/imitation、grpo/baseline 提升值

## 如果要升级成真实 Qwen SFT + RL

至少需要补齐下面任一方案：

1. 准备 HuggingFace 格式的 Qwen 可训练权重目录，并安装 `transformers/peft/datasets/accelerate`。
2. 安装完整 `llama.cpp` 训练工具链，并确认 `lora-finetune` 可用。
3. 安装 Windows MSVC Build Tools，让本机具备 `cl` 和 `nmake`。

在这些条件满足之前，当前仓库能够稳定、如实复现的是：

- 模仿学习数据构建
- 离线 GRPO 策略优化
- 阶段性对比报告
