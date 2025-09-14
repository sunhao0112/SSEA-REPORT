# 南海舆情报告生成系统 - Linux服务器部署指南

## 📋 概述

本文档提供了将南海舆情报告生成系统部署到Linux服务器的完整指南，包括自动化部署脚本和手动部署方法。

## 🚀 一键部署 (推荐)

### 系统要求

- **操作系统**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **内存**: 至少 4GB RAM (推荐 8GB+)
- **存储**: 至少 20GB 可用空间
- **网络**: 稳定的互联网连接

### 快速部署步骤

1. **下载项目代码**
   ```bash
   git clone https://github.com/your-repo/nanhai-report-system.git
   cd nanhai-report-system
   ```

2. **运行一键部署脚本**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

3. **配置环境变量**
   ```bash
   # 编辑配置文件
   vim .env

   # 修改以下必要配置：
   # SUPABASE_URL=https://your-project.supabase.co
   # SUPABASE_ANON_KEY=your_supabase_anon_key
   # DIFY_API_KEY=app-your-dify-api-key
   ```

4. **重启服务应用配置**
   ```bash
   docker-compose restart
   ```

5. **访问应用**
   - 应用地址: `http://your-server-ip:8000`
   - API文档: `http://your-server-ip:8000/docs`
   - 健康检查: `http://your-server-ip:8000/api/health`

## 🛠️ 手动部署

### 步骤1: 准备环境

#### 安装Docker
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 启动Docker服务
sudo systemctl enable docker
sudo systemctl start docker
```

#### 安装Docker Compose
```bash
# 方法1: 使用包管理器
sudo apt-get install docker-compose-plugin

# 方法2: 手动安装最新版本
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 步骤2: 准备项目文件

```bash
# 克隆项目
git clone https://github.com/your-repo/nanhai-report-system.git
cd nanhai-report-system

# 创建必要目录
mkdir -p uploads reports logs cache nginx/ssl
```

### 步骤3: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**必须配置的关键变量：**
```env
# 数据库配置
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...your_key_here

# AI服务配置
DIFY_API_KEY=app-your-dify-api-key-here
DIFY_BASE_URL=https://api.dify.ai/v1

# 跨域配置
CORS_ORIGINS=http://localhost:8000,https://yourdomain.com
```

### 步骤4: 构建和启动

```bash
# 构建镜像
docker-compose build

# 启动服务 (基础版本)
docker-compose up -d

# 启动服务 (包含Nginx反向代理)
docker-compose --profile with-nginx up -d
```

## 🔧 高级配置

### SSL/HTTPS配置

1. **获取SSL证书**
   ```bash
   # 使用Let's Encrypt (推荐)
   sudo apt install certbot
   sudo certbot certonly --standalone -d yourdomain.com
   ```

2. **配置Nginx SSL**
   ```bash
   # 复制证书到项目目录
   sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
   sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
   sudo chown $USER:$USER nginx/ssl/*
   ```

3. **更新Nginx配置**
   编辑 `nginx/nginx.conf`，添加SSL配置：
   ```nginx
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/nginx/ssl/fullchain.pem;
       ssl_certificate_key /etc/nginx/ssl/privkey.pem;

       # 其他SSL配置...
   }
   ```

### 域名配置

1. **DNS设置**
   - 将域名A记录指向服务器IP
   - 等待DNS生效 (通常5-30分钟)

2. **更新配置文件**
   ```env
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

### 防火墙配置

```bash
# Ubuntu/Debian - UFW
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw enable

# CentOS/RHEL - Firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 📊 监控和维护

### 常用管理命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
docker-compose logs -f nanhai-app

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新应用
git pull
docker-compose build
docker-compose up -d
```

### 健康检查

```bash
# 检查应用健康状态
curl http://localhost:8000/api/health

# 检查容器状态
docker-compose ps

# 查看资源使用情况
docker stats
```

### 备份和恢复

```bash
# 备份数据卷
docker-compose down
sudo tar -czf backup-$(date +%Y%m%d).tar.gz \
  uploads/ reports/ logs/ .env

# 恢复数据
sudo tar -xzf backup-20240914.tar.gz
docker-compose up -d
```

### 日志管理

```bash
# 清理Docker日志
sudo docker system prune -f

# 设置日志轮转
sudo crontab -e
# 添加: 0 1 * * * /usr/bin/docker system prune -f
```

## 🚨 故障排除

### 常见问题

1. **容器启动失败**
   ```bash
   # 检查日志
   docker-compose logs nanhai-app

   # 检查端口占用
   netstat -tlnp | grep 8000
   ```

2. **文件上传失败**
   - 检查 `uploads/` 目录权限
   - 确认 `MAX_FILE_SIZE` 配置
   - 查看Nginx客户端最大体积限制

3. **数据库连接错误**
   - 验证 `SUPABASE_URL` 和 `SUPABASE_ANON_KEY`
   - 检查网络连接和防火墙设置

4. **AI服务调用失败**
   - 确认 `DIFY_API_KEY` 有效性
   - 检查API配额和限制

### 性能优化

1. **资源限制调整**
   ```yaml
   # docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 4G
         cpus: '2.0'
   ```

2. **缓存优化**
   ```env
   # 启用Redis缓存
   CACHE_TYPE=redis
   REDIS_URL=redis://localhost:6379/0
   ```

3. **数据库连接池**
   ```env
   # 调整连接池大小
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=0
   ```

## 📞 技术支持

如遇到部署问题，可通过以下方式获取帮助：

- **GitHub Issues**: 提交详细的错误日志和环境信息
- **文档更新**: 查看最新的部署文档
- **社区支持**: 参与技术讨论

## 🔒 安全建议

1. **定期更新**
   - 及时更新系统和Docker镜像
   - 关注项目更新和安全补丁

2. **访问控制**
   - 配置强密码和密钥
   - 限制API访问频率
   - 启用HTTPS加密

3. **监控告警**
   - 设置系统资源监控
   - 配置错误日志告警
   - 定期检查访问日志

## 📋 部署检查清单

- [ ] 服务器环境准备完成
- [ ] Docker和Docker Compose安装
- [ ] 项目代码下载和配置
- [ ] 环境变量正确配置
- [ ] Supabase数据库连接测试
- [ ] Dify API密钥配置验证
- [ ] 应用成功启动和健康检查
- [ ] 文件上传功能测试
- [ ] 报告生成流程测试
- [ ] SSL证书配置 (生产环境)
- [ ] 域名解析配置
- [ ] 防火墙和安全设置
- [ ] 备份策略制定
- [ ] 监控和日志配置