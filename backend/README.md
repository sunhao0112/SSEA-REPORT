# 南海舆情日报生成系统 - 后端API

## 项目简介

这是南海舆情日报生成系统的后端API服务，基于Python FastAPI框架开发，提供CSV文件上传、数据处理、Dify工作流集成和报告生成等功能。

## 技术栈

- **框架**: FastAPI + Uvicorn
- **数据库**: SQLAlchemy + SQLite/PostgreSQL
- **数据处理**: Pandas
- **外部集成**: Dify API
- **文档生成**: python-docx
- **异步处理**: aiohttp + asyncio

## 功能特性

- ✅ CSV文件上传和验证
- ✅ 数据清洗和去重处理
- ✅ 完整数据存储到数据库
- ✅ Dify工作流集成
- ✅ 境内外数据源分离
- ✅ AI报告生成
- ✅ Word文档导出
- ✅ 处理状态实时跟踪
- ✅ 历史记录管理

## 安装和运行

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 激活虚拟环境 (Linux/Mac)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 环境配置

复制 `.env` 文件并配置相关参数：

```bash
# 数据库配置
DATABASE_URL=sqlite:///./nanhai_report.db

# Dify API 配置
DIFY_API_KEY=your_dify_api_key_here
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_WORKFLOW_ID=your_workflow_id_here
```

### 3. 启动服务

```bash
# 使用启动脚本
python start.py

# 或直接使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问服务

- API服务: http://localhost:8000
- API文档: http://localhost:8000/docs
- 交互式文档: http://localhost:8000/redoc

## API接口

### 文件上传
- `POST /api/upload` - 上传CSV文件并开始处理

### 状态查询
- `GET /api/status/{processing_id}` - 获取处理状态
- `GET /api/stats/{upload_id}` - 获取数据统计信息

### 数据获取
- `GET /api/data/{upload_id}` - 获取处理后的数据
- `GET /api/history` - 获取上传历史记录

### 文件下载
- `GET /api/download/{upload_id}` - 下载生成的报告

## 项目结构

```
backend/
├── main.py                 # FastAPI应用主文件
├── database.py            # 数据库配置
├── models.py              # 数据库模型
├── schemas.py             # Pydantic数据模式
├── start.py               # 启动脚本
├── requirements.txt       # 依赖包列表
├── .env                   # 环境变量配置
├── services/              # 服务层
│   ├── __init__.py
│   ├── file_service.py    # 文件处理服务
│   ├── dify_service.py    # Dify工作流服务
│   ├── report_service.py  # 报告生成服务
│   └── database_service.py # 数据库操作服务
├── uploads/               # 上传文件目录
└── reports/               # 生成报告目录
```

## 开发说明

### 数据处理流程

1. **文件上传**: 接收CSV文件并保存到本地
2. **数据清洗**: 提取必需字段（URL、来源名称、作者用户名、标题、命中句子、语言）
3. **数据去重**: 基于命中句子进行去重处理
4. **数据存储**: 将原始数据完整保存到数据库
5. **工作流处理**: 调用Dify API进行数据分析
6. **数据分离**: 分离境内外数据源
7. **报告生成**: 生成Word格式的舆情报告
8. **状态更新**: 实时更新处理状态和进度

### 扩展开发

- 添加新的数据处理逻辑到 `services/file_service.py`
- 扩展Dify工作流集成到 `services/dify_service.py`
- 增加新的报告格式到 `services/report_service.py`
- 添加新的API接口到 `main.py`

## 注意事项

1. 确保Dify API密钥配置正确
2. 数据库文件会自动创建在项目根目录
3. 上传的文件和生成的报告会保存在对应目录
4. 建议在生产环境中使用PostgreSQL数据库
5. 大文件处理可能需要较长时间，请耐心等待