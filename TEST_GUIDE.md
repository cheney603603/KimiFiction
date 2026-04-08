# KimiFiction 测试指南

## 📅 日期：2026-03-30

---

## 🚀 一键启动

项目需要 Docker 服务（MySQL、Redis、Qdrant），请使用一键启动脚本：

### Windows
```bash
cd D:\310Programm\KimiFiction
start.bat
```

### 或手动启动

```bash
# 1. 启动Docker服务
cd D:\310Programm\KimiFiction
docker-compose up -d

# 2. 等待服务就绪（约10秒）
timeout /t 10

# 3. 启动后端
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 4. 启动前端（新窗口）
cd frontend
npm run dev
```

---

## 🔧 服务说明

| 服务 | 端口 | 说明 | 必需 |
|------|------|------|------|
| MySQL | 3306 | 数据库存储 | ✅ 必需 |
| Redis | 6379 | 状态缓存 | ✅ 必需 |
| Qdrant | 6333 | 向量数据库(RAG) | ⚠️ 可选 |

### Qdrant说明
Qdrant用于RAG（检索增强生成）功能。如果不启动：
- RAG功能将使用轻量级关键词匹配替代
- 其他功能不受影响

---

## 📋 测试前检查清单

### 1. Docker服务检查
```bash
# 检查Docker是否运行
docker ps

# 应该看到3个容器运行
# mysql, redis, qdrant
```

### 2. 端口检查
```bash
# 检查端口占用
netstat -an | findstr "3306 6379 6333 8000 5173"
```

### 3. 环境变量检查
确认 `backend/.env` 或环境变量配置正确：
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
REDIS_HOST=localhost
REDIS_PORT=6379
```

---

## 功能测试清单

### 🔴 高优先级测试

#### 1. 用户认证
- [ ] 注册新用户
- [ ] 登录
- [ ] 登出
- [ ] Token刷新

#### 2. 小说项目管理
- [ ] 创建新小说
- [ ] 查看小说列表
- [ ] 查看小说详情
- [ ] 删除小说

#### 3. 新版工作流 (`/novel/{id}/workflow/new`)
- [ ] 进入工作流页面
- [ ] 查看阶段进度条
- [ ] 查看阶段指示器
- [ ] 执行各阶段
- [ ] 暂停/恢复工作流
- [ ] WebSocket实时更新

#### 4. 章节撰写
- [ ] 输入章节号
- [ ] 点击开始撰写
- [ ] 查看生成的章节

#### 5. 章节修订
- [ ] 选择已有章节
- [ ] 输入修改反馈
- [ ] 提交修订

### 🟡 中优先级测试

#### 6. 章节管理
- [ ] 查看章节列表
- [ ] 阅读章节内容
- [ ] 编辑章节

#### 7. 角色管理
- [ ] 查看角色列表
- [ ] 创建/编辑角色

#### 8. 大纲管理
- [ ] 查看大纲
- [ ] 编辑大纲

### 🟢 低优先级测试

#### 9. 导出功能
- [ ] 导出为TXT
- [ ] 导出为Markdown

---

## 常见问题

### Q1: Docker服务启动失败
```
可能原因：
1. Docker Desktop未启动
2. 端口被占用
3. 内存不足

解决方案：
1. 启动Docker Desktop
2. 检查端口: netstat -an | findstr "3306"
3. 增加Docker内存分配
```

### Q2: MySQL连接失败
```
错误: Can't connect to MySQL server

解决方案：
1. 等待MySQL完全启动（约10秒）
2. 检查Docker状态: docker ps
3. 查看MySQL日志: docker logs kimi_mysql
```

### Q3: 页面无法访问
```
检查：
1. 前端是否运行 (http://localhost:5173)
2. 后端是否运行 (http://localhost:8000)
3. 浏览器控制台是否有错误
```

### Q4: 章节生成失败
```
检查：
1. LLM服务是否配置（API Key）
2. 网络连接
3. 查看后端日志
```

---

## 测试报告模板

```
## 测试报告

**日期**: 2026-03-XX
**测试人**: 
**版本**: v2.0

### 测试结果汇总

| 功能模块 | 测试项数 | 通过数 | 失败数 | 状态 |
|---------|---------|-------|-------|------|
| 用户认证 | 4 | X | X | ✅/❌ |
| 小说管理 | 4 | X | X | ✅/❌ |
| 新版工作流 | 8 | X | X | ✅/❌ |
| 章节管理 | 4 | X | X | ✅/❌ |

### 发现的问题

1. **问题描述**: 
   - 预期行为: 
   - 实际行为: 
   - 优先级: 

### 总结

是否可上线: 是/否
```
