# 多阶段构建 - 前端构建
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制前端依赖文件
COPY frontend/package*.json ./

# 使用中国npm镜像源加速安装
RUN npm config set registry https://registry.npmmirror.com && \
    npm ci

# 复制前端源代码
COPY frontend/ ./

# 构建前端
RUN npm run build

# 多阶段构建 - 后端运行环境
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# 使用中国镜像源加速下载
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    libmagic1 \
    file \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 复制后端依赖文件
COPY backend/requirements.txt ./

# 安装 Python 依赖，使用中国镜像源加速
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 复制后端代码
COPY backend/ ./

# 从前端构建阶段复制构建结果
COPY --from=frontend-builder /app/frontend/dist ./static

# 创建必要的目录
RUN mkdir -p uploads reports templates logs cache && \
    chown -R appuser:appuser /app

# 复制模板文件
COPY template.docx ./templates/

# 切换到非root用户
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]