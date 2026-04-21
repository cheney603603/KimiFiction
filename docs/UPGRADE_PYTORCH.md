# KimiFiction PyTorch 2.8.0 升级指南

## 更新的依赖版本

### 核心框架
| 框架 | 旧版本 | 新版本 |
|------|--------|--------|
| **PyTorch** | 2.2.0 | **2.8.0** |
| Transformers | 4.37.2 | >=4.40.0 |
| Sentence-Transformers | 2.5.1 | >=2.6.0 |
| Accelerate | 0.27.0 | >=0.28.0 |

### LoRA微调
| 框架 | 旧版本 | 新版本 |
|------|--------|--------|
| PEFT | 0.8.2 | >=0.10.0 |
| BitsAndBytes | 0.42.0 | >=0.43.0 |
| Datasets | 2.17.0 | >=2.18.0 |

---

## 安装步骤

### 方法1: 全新安装（推荐）

```bash
# 1. 创建新的虚拟环境
conda create -n kimifiction python=3.10
conda activate kimifiction

# 2. 先安装PyTorch 2.8.0
pip install torch==2.8.0

# 3. 安装其他依赖
cd D:\310Programm\KimiFiction\backend
pip install -r requirements.txt
```

### 方法2: 升级现有环境

```bash
# 1. 激活现有环境
conda activate kimifiction  # 或你的环境名

# 2. 升级PyTorch
pip install torch==2.8.0 --upgrade

# 3. 升级其他依赖
pip install transformers>=4.40.0 sentence-transformers>=2.6.0 --upgrade

# 4. 安装LLM推理库
pip install llama-cpp-python>=0.2.56
```

### 方法3: 如果llama-cpp-python编译失败

```bash
# 安装预编译版本（CPU）
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# 或安装GPU版本（CUDA 12.x）
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

---

## 兼容性说明

PyTorch 2.8.0 主要新特性：
- ✅ 更好的内存管理
- ✅ 改进的编译优化
- ✅ 更好的CUDA支持
- ✅ 向后兼容 2.x 代码

所有项目代码无需修改即可运行。

---

## 验证安装

```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import transformers; print(f'Transformers: {transformers.__version__}')"
python -c "import sentence_transformers; print(f'Sentence-Transformers OK')"
```

---

## 如果遇到问题

### 问题1: CUDA版本不匹配
```bash
# 检查CUDA版本
nvidia-smi

# 安装对应CUDA版本的PyTorch
pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu121
```

### 问题2: bitsandbytes安装失败
```bash
# Windows需要特殊处理
pip install bitsandbytes-windows
```

### 问题3: 内存不足
```bash
# 使用量化模型减少内存
# 项目已支持4bit量化
```
