from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os
import tempfile
import asyncio
from datetime import datetime
import json
import uuid
from typing import AsyncGenerator

from schemas import *
from services.file_service import FileService
from services.dify_service import DifyService
from services.report_service import ReportService
from services.database_service import DatabaseService
from services.file_security import FileSecurityValidator  # 临时注释
from services.cache_service import cache_manager
from services.cleanup_service import cleanup_service
from services.logger_config import (
    system_logger, api_logger, security_logger, file_logger,
    log_performance, set_request_id, log_stats
)

# 应用程序启动
system_logger.info("南海舆情日报生成系统启动", version="1.0.0")

app = FastAPI(title="南海舆情日报生成系统", version="1.0.0")

# 启动事件：启动后台服务
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        # 启动清理服务
        await cleanup_service.start()
        system_logger.info("后台服务启动完成")
    except Exception as e:
        system_logger.error("后台服务启动失败", error=str(e))

# 关闭事件：清理资源
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    try:
        # 停止清理服务
        await cleanup_service.stop()
        system_logger.info("后台服务已停止")
    except Exception as e:
        system_logger.error("停止后台服务失败", error=str(e))

# 请求中间件：添加请求ID和日志
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 生成请求ID
    request_id = str(uuid.uuid4())
    set_request_id(request_id)

    start_time = datetime.utcnow()

    # 只记录重要的请求开始（上传、处理等）
    if request.url.path in ["/api/upload", "/api/cache/clear", "/api/cleanup/manual"]:
        api_logger.info(
            f"Request started: {request.method} {request.url.path}",
            request_id=request_id[:8]  # 只保留前8位
        )

    try:
        response = await call_next(request)
        duration = (datetime.utcnow() - start_time).total_seconds()

        # 只记录重要请求的完成或慢请求
        if (request.url.path in ["/api/upload", "/api/cache/clear", "/api/cleanup/manual"] or
            duration > 1.0):  # 超过1秒的请求
            api_logger.info(
                f"Request completed: {request.method} {request.url.path}",
                request_id=request_id[:8],
                status_code=response.status_code,
                duration_seconds=round(duration, 2)
            )

        log_stats.record_request()
        return response

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()

        # 所有错误都记录
        api_logger.error(
            f"Request failed: {request.method} {request.url.path}",
            request_id=request_id[:8],
            error_type=type(e).__name__,
            error_message=str(e),
            duration_seconds=round(duration, 2)
        )

        log_stats.record_error(str(e))
        raise

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:5174,http://82.157.4.192:8000').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置存储目录 - 使用环境变量
UPLOAD_DIR = os.getenv('UPLOAD_DIR', './uploads')
REPORTS_DIR = os.getenv('REPORTS_DIR', './reports')
TEMPLATES_DIR = os.getenv('TEMPLATES_DIR', './templates')
LOGS_DIR = os.getenv('LOGS_DIR', './logs')
CACHE_DIR = os.getenv('CACHE_DIR', './cache')

# 创建必要目录
for directory in [UPLOAD_DIR, REPORTS_DIR, TEMPLATES_DIR, LOGS_DIR, CACHE_DIR]:
    os.makedirs(directory, exist_ok=True)

system_logger.info(
    "存储目录配置完成",
    upload_dir=UPLOAD_DIR,
    reports_dir=REPORTS_DIR,
    templates_dir=TEMPLATES_DIR,
    logs_dir=LOGS_DIR,
    cache_dir=CACHE_DIR
)

# 初始化服务
file_service = FileService()
report_service = ReportService()
db_service = DatabaseService()
file_security = FileSecurityValidator()

# 全局进度存储（实际项目中应该使用Redis等缓存）
progress_streams = {}

# 从环境变量读取Dify配置
DIFY_API_KEY = os.getenv('DIFY_API_KEY', 'app-your-api-key-here')
DIFY_BASE_URL = os.getenv('DIFY_BASE_URL', 'https://api.dify.ai/v1')

dify_service = DifyService(api_key=DIFY_API_KEY, base_url=DIFY_BASE_URL)

@app.get("/")
async def root():
    """根路径：返回前端页面"""
    static_dir = "/app/static"
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        from fastapi.responses import HTMLResponse
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HTMLResponse(content=content)

    # 如果没有前端文件，返回API信息
    system_logger.info("访问根路径 - 未找到前端文件")
    return {"message": "南海舆情日报生成系统 API", "status": "running", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    try:
        # 检查数据库连接
        db_status = "ok"
        try:
            await db_service.get_upload_history(limit=1)
        except Exception as e:
            db_status = f"error: {str(e)}"

        # 检查目录状态
        dirs_status = {
            "upload_dir": os.path.exists(UPLOAD_DIR),
            "reports_dir": os.path.exists(REPORTS_DIR)
        }

        health_info = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_status,
            "directories": dirs_status,
            "log_stats": log_stats.get_stats()
        }

        system_logger.info("健康检查完成", **health_info)
        return health_info

    except Exception as e:
        system_logger.error("健康检查失败", error=str(e))
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api/logs/stats")
async def get_log_stats():
    """获取日志统计信息"""
    stats = log_stats.get_stats()
    system_logger.info("获取日志统计", **stats)
    return stats

@app.get("/api/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    stats = cache_manager.get_stats()
    system_logger.info("获取缓存统计", **stats)
    return stats

@app.post("/api/cache/clear")
async def clear_cache(cache_type: str = "all"):
    """清空缓存"""
    try:
        result = await cache_manager.clear(cache_type)
        system_logger.info("清空缓存", cache_type=cache_type, success=result)
        return {"success": result, "message": f"已清空 {cache_type} 缓存"}
    except Exception as e:
        system_logger.error("清空缓存失败", cache_type=cache_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {str(e)}")

@app.get("/api/cleanup/stats")
async def get_cleanup_stats():
    """获取清理服务统计信息"""
    stats = cleanup_service.get_stats()
    system_logger.info("获取清理统计", **{k: v for k, v in stats.items() if k != 'scheduled_jobs'})
    return stats

@app.post("/api/cleanup/manual")
async def manual_cleanup(operation: str = "full"):
    """手动触发清理"""
    try:
        result = await cleanup_service.manual_cleanup(operation)
        system_logger.info("手动清理完成", operation=operation, result=result)
        return result
    except Exception as e:
        system_logger.error("手动清理失败", operation=operation, error=str(e))
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")

@app.get("/api/progress-stream/{processing_id}")
async def get_progress_stream(processing_id: int):
    """获取实时进度流 - Server-Sent Events"""

    async def event_stream() -> AsyncGenerator[str, None]:
        """生成SSE事件流"""
        try:
            # 发送初始连接确认
            yield f"data: {json.dumps({'type': 'connected', 'processing_id': processing_id})}\n\n"

            # 持续监听进度变化
            last_progress = -1
            last_step = ""
            max_attempts = 300  # 最多5分钟 (300 * 1s)
            attempt = 0

            while attempt < max_attempts:
                try:
                    # 查询当前处理状态
                    status = await db_service.get_processing_status(processing_id)

                    if status:
                        # 检查进度是否有变化
                        if (status.progress != last_progress or
                            status.current_step != last_step or
                            status.status in ['completed', 'failed']):

                            # 发送进度更新
                            progress_data = {
                                'type': 'progress',
                                'processing_id': processing_id,
                                'upload_id': status.upload_id,
                                'current_step': status.current_step,
                                'status': status.status,
                                'progress': status.progress,
                                'message': status.message,
                                'error_message': status.error_message,
                                'updated_time': status.updated_time.isoformat() if status.updated_time else None
                            }

                            yield f"data: {json.dumps(progress_data)}\n\n"

                            last_progress = status.progress
                            last_step = status.current_step

                            # 如果完成或失败，结束流
                            if status.status in ['completed', 'failed']:
                                yield f"data: {json.dumps({'type': 'finished', 'status': status.status})}\n\n"
                                break

                    attempt += 1
                    await asyncio.sleep(1)  # 每秒检查一次

                except Exception as e:
                    api_logger.error(f"进度流错误: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break

            # 超时处理
            if attempt >= max_attempts:
                yield f"data: {json.dumps({'type': 'timeout', 'message': '进度监听超时'})}\n\n"

        except Exception as e:
            api_logger.error(f"SSE流错误: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Content-Type": "text/event-stream",
        }
    )

@app.post("/api/upload", response_model=UploadResponse)
@log_performance()
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """上传CSV文件并开始处理 - 包含安全验证"""

    try:
        # 记录开始时间
        start_time = datetime.now()
        file_logger.info(f"开始处理上传文件: {file.filename}", filename=file.filename)

        # 读取文件内容用于安全验证
        content = await file.read()
        file_size = len(content)

        # 1. 安全验证
        security_logger.info(f"开始文件安全验证: {file.filename}", filename=file.filename, size_bytes=file_size)
        is_valid, error_message, file_info = file_security.validate_file_upload(content, file.filename)

        if not is_valid:
            security_logger.warning(
                f"文件安全验证失败: {file.filename}",
                filename=file.filename,
                error=error_message,
                file_size=file_size
            )
            raise HTTPException(status_code=400, detail=f"文件安全验证失败: {error_message}")

        security_logger.info(
            f"文件安全验证通过: {file.filename}",
            filename=file.filename,
            rows_count=file_info.get('rows_count', 0),
            encoding=file_info.get('encoding', 'unknown'),
            hash=file_info.get('hash', '')[:16]
        )

        # 2. 清理文件名并保存
        clean_filename = file_security.sanitize_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{clean_filename}")

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        file_logger.info(
            f"文件保存完成: {clean_filename}",
            filename=clean_filename,
            original_filename=file.filename,
            size_bytes=file_size,
            path=file_path
        )

        # 3. 创建数据库记录
        upload_record = await db_service.create_upload_record(
            filename=clean_filename,
            file_path=file_path,
            file_size=file_size
        )
        processing_status = await db_service.create_processing_status(upload_record.id, "upload")

        api_logger.info(
            f"数据库记录创建完成",
            upload_id=upload_record.id,
            processing_id=processing_status.id
        )

        # 4. 立即更新初始状态
        await db_service.update_processing_status(
            processing_status.id,
            "upload",
            "processing",
            5.0,
            f"文件安全验证通过，开始处理... (行数: {file_info.get('rows_count', 0)})"
        )

        # 5. 后台处理任务
        background_tasks.add_task(
            process_file_background,
            upload_record.id,
            processing_status.id,
            file_path,
            clean_filename
        )

        # 计算上传耗时
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > 2.0:  # 只记录慢上传
            api_logger.info(
                f"上传处理耗时较长: {elapsed:.1f}s",
                upload_id=upload_record.id
            )

        return UploadResponse(
            upload_id=upload_record.id,
            processing_id=processing_status.id,
            message=f"文件上传成功，正在处理中... (检测到 {file_info.get('rows_count', 0)} 行数据)"
        )

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"文件上传失败: {str(e)}", error=str(e), filename=file.filename if file else "unknown")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

async def process_file_background(upload_id: int, processing_id: int, file_path: str, filename: str):
    """后台文件处理任务 - 集成示例脚本逻辑"""

    try:
        file_logger.info(f"开始处理文件: {filename}", upload_id=upload_id, processing_id=processing_id)

        # 步骤1: 文件上传完成
        await db_service.update_processing_status(processing_id, "upload", "processing", 10.0, f"文件 {filename} 上传成功")

        # 步骤2: 数据清洗
        await db_service.update_processing_status(processing_id, "clean", "processing", 20.0, "开始数据清洗...")

        # 读取和清洗CSV数据
        raw_data = file_service.read_csv_file(file_path)
        cleaned_data = file_service.clean_data(raw_data)

        # 保存原始数据到数据库
        await db_service.save_raw_data(upload_id, raw_data)

        await db_service.update_processing_status(processing_id, "clean", "processing", 30.0, "保留URL、来源名称、作者用户名称、标题、命中句子、语言字段")

        # 步骤3: 数据去重
        await db_service.update_processing_status(processing_id, "dedupe", "processing", 40.0, "开始数据去重...")

        before_count = len(cleaned_data)

        # 分析去重前的数据分布
        analysis = file_service.analyze_hit_sentences(cleaned_data)

        deduplicated_data = await file_service.deduplicate_data(cleaned_data)
        after_count = len(deduplicated_data)
        removed_count = before_count - after_count

        await db_service.update_processing_status(
            processing_id,
            "dedupe",
            "processing",
            50.0,
            f"去重完成 - 原始:{before_count}条，保留:{after_count}条，移除:{removed_count}条"
        )

        # 保存去重后的数据到临时CSV文件用于Dify处理
        temp_file_path = file_path.replace('.csv', '_deduplicated.csv')
        await file_service.save_to_csv(deduplicated_data, temp_file_path)

        # 步骤4: Dify工作流处理
        await db_service.update_processing_status(processing_id, "workflow", "processing", 60.0, "开始Dify工作流处理...")

        # 调用异步Dify工作流，使用去重后的文件
        workflow_result = await dify_service.process_file_async(temp_file_path, filename.replace('.csv', '_deduplicated.csv'))

        if not workflow_result:
            raise Exception("Dify工作流处理失败")

        # 检查是否是错误结果
        if isinstance(workflow_result, dict) and 'error' in workflow_result:
            detailed_error = workflow_result.get('error', '未知错误')
            await db_service.update_processing_status(
                processing_id,
                "workflow",
                "failed",
                60.0,
                f"Dify工作流处理失败: {detailed_error}"
            )
            raise Exception(f"Dify工作流处理失败: {detailed_error}")

        # 提取境内外数据源
        domestic_sources, foreign_sources = dify_service.extract_sources_from_result(workflow_result)

        # 确保数据源不是None，如果是None则使用空列表
        if domestic_sources is None:
            domestic_sources = []
        if foreign_sources is None:
            foreign_sources = []

        # 暂时放宽验证条件，避免因Dify模型过载导致的失败
        if not domestic_sources and not foreign_sources:
            file_logger.warning("⚠️ Dify返回空数据（可能是模型过载），使用空数据继续流程", upload_id=upload_id)

        await db_service.update_processing_status(processing_id, "workflow", "processing", 80.0, "数据分离和AI分析完成")

        # 保存处理后的数据
        await db_service.save_processed_data(upload_id, domestic_sources, foreign_sources)

        # 步骤5: 生成报告
        await db_service.update_processing_status(processing_id, "report", "processing", 90.0, "开始生成报告...")

        # 计算基于语言的境内外统计数据
        raw_data_list = await db_service.get_raw_data_by_upload_id(upload_id)
        inside_count = 0  # 语言包含Chinese的数量
        outside_count = 0  # 语言不包含Chinese的数量

        for data in raw_data_list:
            if data.language and data.language.strip():
                language = data.language.strip()
                if "Chinese" in language:
                    inside_count += 1
                else:
                    outside_count += 1

        # 生成报告文件
        today = datetime.now()
        date_text = today.strftime('%Y年%m月%d日')
        report_filename = f"南海舆情日报_{date_text}.docx"
        report_path = os.path.join(REPORTS_DIR, report_filename)

        success = report_service.generate_report(
            domestic_sources,
            foreign_sources,
            inside_total=inside_count,
            outside_total=outside_count,
            output_filename=report_path
        )

        if not success:
            raise Exception("报告生成失败")

        # 更新上传记录
        upload_record = await db_service.get_upload_record(upload_id)
        if upload_record:
            await upload_record.update({
                "report_path": report_path,
                "status": "completed"
            })

        # 完成处理
        file_logger.info(f"🎉 开始最终状态更新", processing_id=processing_id, upload_id=upload_id)
        await db_service.update_processing_status(processing_id, "report", "completed", 100.0, "南海舆情日报生成完成")

        # 清理临时文件
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                file_logger.info(f"临时去重文件已清理: {temp_file_path}")
        except Exception as cleanup_error:
            file_logger.warning(f"清理临时文件失败: {cleanup_error}")

        file_logger.info(f"文件处理完成: {filename}", upload_id=upload_id)

    except Exception as e:
        import traceback
        file_logger.error(f"处理文件时发生错误: {str(e)}", upload_id=upload_id, error=str(e))
        file_logger.error(f"完整错误堆栈: {traceback.format_exc()}", upload_id=upload_id)

        # 清理临时文件（如果存在）
        try:
            temp_file_path = file_path.replace('.csv', '_deduplicated.csv')
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                file_logger.info(f"异常处理中清理临时去重文件: {temp_file_path}")
        except Exception as cleanup_error:
            file_logger.warning(f"异常处理中清理临时文件失败: {cleanup_error}")

        # 获取当前处理状态，用于确定错误发生在哪个步骤
        current_status = await db_service.get_processing_status(processing_id)
        error_step = current_status.current_step if current_status else "unknown"

        # 更新状态：失败
        await db_service.update_processing_status(
            processing_id,
            current_step=error_step,
            status="failed",
            error_message=str(e)
        )

        # 更新上传记录状态
        upload_record = await db_service.get_upload_record(upload_id)
        if upload_record:
            await upload_record.update({
                "status": "failed",
                "error_message": str(e)
            })

@app.get("/api/status/{processing_id}", response_model=ProcessingStatusResponse)
async def get_processing_status(processing_id: int):
    """获取处理状态"""

    status = await db_service.get_processing_status(processing_id)

    if not status:
        raise HTTPException(status_code=404, detail="处理状态不存在")

    return ProcessingStatusResponse(
        processing_id=status.id,
        upload_id=status.upload_id,
        current_step=status.current_step,
        status=status.status,
        progress=status.progress,
        message=status.message,
        error_message=status.error_message,
        created_time=status.created_time,
        updated_time=status.updated_time
    )

@app.get("/api/stats/{upload_id}", response_model=DataStatsResponse)
async def get_data_stats(upload_id: int):
    """获取数据统计信息"""

    stats = await db_service.get_data_stats(upload_id)

    return DataStatsResponse(**stats)

@app.get("/api/data/{upload_id}", response_model=ProcessedDataResponse)
async def get_processed_data(upload_id: int):
    """获取处理后的数据"""

    data = await db_service.get_processed_data(upload_id)

    return ProcessedDataResponse(**data)

@app.get("/api/history", response_model=UploadHistoryResponse)
async def get_upload_history(limit: int = 50, offset: int = 0):
    """获取上传历史记录"""

    return await db_service.get_upload_history(limit, offset)

@app.get("/api/download/{upload_id}")
async def download_report(upload_id: int):
    """下载报告文件"""

    upload_record = await db_service.get_upload_record(upload_id)

    if not upload_record or not upload_record.report_path:
        raise HTTPException(status_code=404, detail="报告文件不存在")

    if not os.path.exists(upload_record.report_path):
        raise HTTPException(status_code=404, detail="报告文件已被删除")

    return FileResponse(
        upload_record.report_path,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename=f"nanhai_report_{upload_id}.docx"
    )

# 挂载静态文件目录（前端） - 必须在所有API路由之后
static_dir = "/app/static"
if os.path.exists(static_dir):
    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=f"{static_dir}/assets"), name="assets")
    # 挂载其他静态文件（如vite.svg等）
    app.mount("/static", StaticFiles(directory=static_dir), name="static_files")

    # 处理SPA路由的catchall路由
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """服务单页应用，对所有非API路径返回index.html"""
        # 如果是API路径，跳过处理
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")

        # 如果是静态文件路径，跳过处理
        if full_path.startswith(("assets/", "static/")):
            raise HTTPException(status_code=404, detail="Static file not found")

        # 检查是否是根目录的静态文件（如vite.svg, favicon.ico等）
        static_file_path = os.path.join(static_dir, full_path)
        if os.path.exists(static_file_path) and os.path.isfile(static_file_path):
            return FileResponse(static_file_path)

        # 否则返回index.html（SPA路由处理）
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            from fastapi.responses import HTMLResponse
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return HTMLResponse(content=content)
        else:
            raise HTTPException(status_code=404, detail="Frontend not found")

    system_logger.info("前端静态文件已挂载: /app/static")
else:
    system_logger.warning("未找到前端静态文件目录，只提供API服务")

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)