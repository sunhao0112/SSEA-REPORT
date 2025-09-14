#!/bin/bash

# 南海舆情报告生成系统 - 一键部署脚本
# 适用于 Ubuntu/Debian/CentOS Linux 服务器

set -e  # 遇到错误时停止执行

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "建议不要以root用户运行此脚本"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        log_error "无法检测操作系统"
        exit 1
    fi
    log_info "检测到操作系统: $OS $VER"
}

# 安装Docker
install_docker() {
    log_info "检查Docker安装状态..."

    if command -v docker &> /dev/null; then
        log_success "Docker已安装: $(docker --version)"
        return
    fi

    log_info "开始安装Docker..."

    # 安装Docker官方GPG密钥
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg lsb-release

    # 添加Docker官方APT仓库
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # 安装Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # 启动Docker服务
    sudo systemctl enable docker
    sudo systemctl start docker

    # 将当前用户添加到docker组
    sudo usermod -aG docker $USER

    log_success "Docker安装完成"
}

# 安装Docker Compose
install_docker_compose() {
    log_info "检查Docker Compose安装状态..."

    if command -v docker-compose &> /dev/null; then
        log_success "Docker Compose已安装: $(docker-compose --version)"
        return
    fi

    if docker compose version &> /dev/null; then
        log_success "Docker Compose (插件版本)已安装"
        return
    fi

    log_info "安装Docker Compose..."

    # 下载最新版本的Docker Compose
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    log_success "Docker Compose安装完成"
}

# 创建环境配置文件
create_env_file() {
    log_info "创建环境配置文件..."

    if [[ -f .env ]]; then
        log_warning ".env文件已存在，是否覆盖?"
        read -p "覆盖现有文件? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return
        fi
    fi

    cat > .env << EOF
# 南海舆情报告生成系统 - 生产环境配置

# 数据库配置 (Supabase)
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Dify AI配置
DIFY_API_KEY=app-your-api-key-here
DIFY_BASE_URL=https://api.dify.ai/v1

# 应用配置
DEBUG=false
LOG_LEVEL=INFO

# CORS配置 (根据需要修改域名)
CORS_ORIGINS=http://localhost:8000,https://yourdomain.com

# 端口配置
HTTP_PORT=8000
HTTPS_PORT=443

EOF

    log_success ".env文件已创建"
    log_warning "请编辑 .env 文件，填入正确的配置信息："
    log_info "  - SUPABASE_URL: 你的Supabase项目URL"
    log_info "  - SUPABASE_ANON_KEY: 你的Supabase匿名密钥"
    log_info "  - DIFY_API_KEY: 你的Dify API密钥"
    log_info "  - CORS_ORIGINS: 允许的跨域来源"
}

# 创建Nginx配置
create_nginx_config() {
    log_info "创建Nginx配置..."

    mkdir -p nginx

    cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream app {
        server nanhai-app:8000;
    }

    # 限制请求大小 (用于大文件上传)
    client_max_body_size 100M;

    # 基本配置
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # MIME类型
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 日志格式
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;

    # Gzip压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        application/atom+xml
        application/geo+json
        application/javascript
        application/x-javascript
        application/json
        application/ld+json
        application/manifest+json
        application/rdf+xml
        application/rss+xml
        application/xhtml+xml
        application/xml
        font/eot
        font/otf
        font/ttf
        image/svg+xml
        text/css
        text/javascript
        text/plain
        text/xml;

    server {
        listen 80;
        server_name _;

        # 前端静态文件
        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # API接口
        location /api/ {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # 超时设置
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 300s;
        }

        # 文件上传特殊处理
        location /api/upload {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # 上传超时设置
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;

            # 缓冲区设置
            proxy_request_buffering off;
            proxy_buffering off;
        }

        # SSE (Server-Sent Events) 特殊处理
        location /api/progress-stream/ {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # SSE特殊设置
            proxy_buffering off;
            proxy_cache off;
            proxy_set_header Connection '';
            proxy_http_version 1.1;
            chunked_transfer_encoding off;

            # CORS for SSE
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS';
            add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
        }

        # 健康检查
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF

    log_success "Nginx配置文件已创建"
}

# 创建systemd服务文件
create_systemd_service() {
    log_info "创建systemd服务..."

    sudo tee /etc/systemd/system/nanhai-app.service > /dev/null << EOF
[Unit]
Description=南海舆情报告生成系统
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable nanhai-app.service

    log_success "systemd服务已创建并启用"
}

# 部署应用
deploy_app() {
    log_info "开始部署应用..."

    # 构建并启动容器
    docker-compose build
    docker-compose up -d

    log_success "应用部署完成!"
}

# 显示部署后信息
show_info() {
    echo
    log_success "🎉 南海舆情报告生成系统部署完成!"
    echo
    log_info "📋 部署信息:"
    log_info "  • 应用地址: http://$(hostname -I | awk '{print $1}'):8000"
    log_info "  • API文档: http://$(hostname -I | awk '{print $1}'):8000/docs"
    log_info "  • 健康检查: http://$(hostname -I | awk '{print $1}'):8000/api/health"
    echo
    log_info "🛠️ 常用命令:"
    log_info "  • 查看日志: docker-compose logs -f"
    log_info "  • 重启服务: docker-compose restart"
    log_info "  • 停止服务: docker-compose down"
    log_info "  • 更新应用: git pull && docker-compose build && docker-compose up -d"
    echo
    log_warning "⚠️  重要提醒:"
    log_warning "  1. 请编辑 .env 文件，配置正确的数据库和API密钥"
    log_warning "  2. 确保防火墙允许8000端口访问"
    log_warning "  3. 生产环境建议使用HTTPS和域名访问"
    echo
}

# 主函数
main() {
    echo "🚀 南海舆情报告生成系统 - Linux部署脚本"
    echo "============================================"
    echo

    # 检查权限
    check_root

    # 检测操作系统
    detect_os

    # 安装依赖
    install_docker
    install_docker_compose

    # 创建配置文件
    create_env_file
    create_nginx_config

    # 创建系统服务
    create_systemd_service

    # 部署应用
    deploy_app

    # 显示部署信息
    show_info
}

# 执行主函数
main "$@"