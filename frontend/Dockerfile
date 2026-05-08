# KimiFiction 前端 Dockerfile
# 多阶段构建：构建 React 静态文件 → Nginx  serving

# ── Stage 1: 构建 ─────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# 先复制 package 文件，利用 Docker 缓存
COPY frontend/package*.json ./

# 安装依赖
RUN npm install

# 复制源代码
COPY frontend/ .

# 构建生产版本（VITE_API_URL 在此阶段注入）
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
ENV NODE_ENV=production

RUN npm run build

# ── Stage 2: 服务 ─────────────────────────────
FROM nginx:alpine

# 删除默认 nginx 配置
RUN rm -rf /etc/nginx/conf.d/default.conf

# 复制自定义 nginx 配置
COPY nginx/frontend.conf /etc/nginx/conf.d/

# 从构建阶段复制静态文件
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]