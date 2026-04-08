#!/bin/bash

# NovelGen 快速启动脚本
# 支持 Linux/Mac

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                 NovelGen 启动脚本                            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  多智能体小说生成系统                                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    echo "请访问 https://docs.docker.com/get-docker/ 安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    echo "请访问 https://docs.docker.com/compose/install/ 安装 Docker Compose"
    exit 1
fi

# 函数：检查服务是否健康
check_service() {
    local name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}等待 $name 启动...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}$name 已就绪${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}\n$name 启动超时${NC}"
    return 1
}

# 选择启动模式
echo ""
echo "请选择启动模式:"
echo "1) 使用 OpenAI API（需要API Key）"
echo "2) 使用 Chat2Api Service（本地AI）"
echo "3) 仅启动基础设施（MySQL/Redis/Qdrant）"
echo ""
read -p "请输入选项 (1-3): " choice

case $choice in
    1)
        echo -e "${BLUE}使用 OpenAI API 模式${NC}"
        
        # 检查配置
        if [ ! -f "backend/.env" ]; then
            echo -e "${YELLOW}创建配置文件...${NC}"
            cp backend/.env.example backend/.env
        fi
        
        # 检查API Key
        if ! grep -q "OPENAI_API_KEY=sk-" backend/.env; then
            echo -e "${YELLOW}请输入 OpenAI API Key:${NC}"
            read -s api_key
            echo ""
            
            # 更新配置
            sed -i.bak "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$api_key/" backend/.env
            sed -i.bak "s/LLM_PROVIDER=.*/LLM_PROVIDER=openai/" backend/.env
            rm -f backend/.env.bak
            
            echo -e "${GREEN}API Key 已配置${NC}"
        fi
        
        # 启动服务
        echo -e "${BLUE}启动服务...${NC}"
        docker-compose up -d
        
        # 等待服务就绪
        check_service "MySQL" "localhost:3306" || true
        check_service "后端API" "http://localhost:8000/health"
        check_service "前端" "http://localhost:5173"
        
        echo ""
        echo -e "${GREEN}✅ 服务已启动！${NC}"
        echo ""
        echo "访问地址:"
        echo "  前端界面: http://localhost:5173"
        echo "  API文档:  http://localhost:8000/docs"
        ;;
        
    2)
        echo -e "${BLUE}使用 Chat2Api Service 模式${NC}"
        
        # 检查 chat2api_service 是否运行
        if ! curl -s http://localhost:8000/api/status > /dev/null 2>&1; then
            echo -e "${RED}错误: Chat2Api Service 未运行${NC}"
            echo ""
            echo "请先启动 Chat2Api Service:"
            echo "  cd chat2api_service"
            echo "  pip install -r requirements.txt"
            echo "  python main.py"
            echo ""
            echo "然后在浏览器中访问 http://localhost:8000 完成登录"
            exit 1
        fi
        
        # 显示可用的AI
        echo -e "${BLUE}可用的 AI 提供商:${NC}"
        curl -s http://localhost:8000/api/status | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/api/status
        echo ""
        
        # 选择AI
        echo "请选择要使用的 AI:"
        echo "1) Kimi"
        echo "2) DeepSeek"
        echo "3) 腾讯元宝"
        read -p "请输入选项 (1-3): " ai_choice
        
        case $ai_choice in
            1) provider="kimi" ;;
            2) provider="deepseek" ;;
            3) provider="yuanbao" ;;
            *) provider="kimi" ;;
        esac
        
        # 更新配置
        if [ ! -f "backend/.env" ]; then
            cp backend/.env.example backend/.env
        fi
        
        sed -i.bak "s/LLM_PROVIDER=.*/LLM_PROVIDER=$provider/" backend/.env
        sed -i.bak "s|CHAT2API_BASE_URL=.*|CHAT2API_BASE_URL=http://host.docker.internal:8000|" backend/.env
        rm -f backend/.env.bak
        
        echo -e "${GREEN}已配置使用 $provider${NC}"
        
        # 启动服务
        echo -e "${BLUE}启动服务...${NC}"
        docker-compose up -d
        
        # 等待服务就绪
        check_service "后端API" "http://localhost:8000/health"
        check_service "前端" "http://localhost:5173"
        
        echo ""
        echo -e "${GREEN}✅ 服务已启动！${NC}"
        echo ""
        echo "访问地址:"
        echo "  前端界面: http://localhost:5173"
        echo "  API文档:  http://localhost:8000/docs"
        ;;
        
    3)
        echo -e "${BLUE}仅启动基础设施${NC}"
        docker-compose up -d mysql redis qdrant
        
        check_service "MySQL" "localhost:3306" || true
        check_service "Redis" "localhost:6379" || true
        check_service "Qdrant" "localhost:6333" || true
        
        echo ""
        echo -e "${GREEN}✅ 基础设施已启动${NC}"
        echo ""
        echo "你可以手动启动前后端:"
        echo "  后端: cd backend && python main.py"
        echo "  前端: cd frontend && npm run dev"
        ;;
        
    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}常用命令:${NC}"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart"
echo ""
echo -e "${GREEN}开始使用 NovelGen 创作你的小说吧！${NC}"
