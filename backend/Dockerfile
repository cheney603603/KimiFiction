# 多智能体小说生成系统 - 后端 Dockerfile
# 支持可选的 PyTorch 训练依赖安装
#
# Build args:
#   INSTALL_TORCH: "false" (默认) - 不安装，镜像约 500MB
#                  "true" - 安装 PyTorch 2.8.0，镜像约 2.5GB
#   CUDA_VERSION: "12.1" (默认) - CUDA 12.1
#   INSTALL_TRAINING_DEPS: "false" (默认) - 仅安装 PyTorch
#                         "true" - 安装完整训练依赖 (transformers, peft, etc.)

FROM python:3.11-slim

# Build arguments
ARG INSTALL_TORCH=false
ARG CUDA_VERSION=12.1
ARG INSTALL_TRAINING_DEPS=false

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── 基础依赖（始终安装）────────────────────────
COPY backend/requirements.txt /tmp/requirements_base.txt

# 分离 requirements：基础依赖 vs 训练依赖
RUN grep -v "^torch" /tmp/requirements_base.txt > /tmp/requirements_no_torch.txt && \
    grep "^torch" /tmp/requirements_base.txt > /tmp/requirements_torch.txt

# 安装基础依赖（不含 torch）
RUN pip install --no-cache-dir -r /tmp/requirements_no_torch.txt

# ── PyTorch 安装（可选）────────────────────────
# 当 INSTALL_TORCH=true 时安装
RUN if [ "$INSTALL_TORCH" = "true" ]; then \
        pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cu121; \
    fi

# ── 训练依赖（可选）────────────────────────────
# 当 INSTALL_TRAINING_DEPS=true 时安装
# transformers, peft, accelerate, datasets 等
RUN if [ "$INSTALL_TRAINING_DEPS" = "true" ]; then \
        pip install --no-cache-dir \
            transformers>=4.40.0 \
            sentence-transformers>=2.6.0 \
            peft>=0.10.0 \
            bitsandbytes>=0.43.0 \
            accelerate>=0.28.0 \
            datasets>=2.18.0; \
    fi

# ── 应用代码 ─────────────────────────────────
COPY backend/ .

# 创建目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]