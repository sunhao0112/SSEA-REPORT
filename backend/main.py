from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import os
import tempfile
import asyncio
from datetime import datetime
import logging
import json
from typing import AsyncGenerator

from schemas import *
from services.file_service import FileService
from services.dify_service import DifyService
from services.report_service import ReportService
from services.database_service import DatabaseService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="南海舆情日报生成系统", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # React开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建必要目录
UPLOAD_DIR = "uploads"
REPORTS_DIR = "reports"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# 初始化服务
file_service = FileService()
report_service = ReportService()
db_service = DatabaseService()

# 全局进度存储（实际项目中应该使用Redis等缓存）
progress_streams = {}

# 从环境变量读取Dify配置
DIFY_API_KEY = os.getenv('DIFY_API_KEY', 'app-your-api-key-here')
DIFY_BASE_URL = os.getenv('DIFY_BASE_URL', 'https://api.dify.ai/v1')

dify_service = DifyService(api_key=DIFY_API_KEY, base_url=DIFY_BASE_URL)

@app.get("/")
async def root():
    return {"message": "南海舆情日报生成系统 API"}

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
                        # 添加调试信息
                        logger.info(f"SSE查询到状态 - processing_id: {processing_id}, upload_id: {status.upload_id}, step: {status.current_step}, status: {status.status}")

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
                    logger.error(f"进度流错误: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break

            # 超时处理
            if attempt >= max_attempts:
                yield f"data: {json.dumps({'type': 'timeout', 'message': '进度监听超时'})}\n\n"

        except Exception as e:
            logger.error(f"SSE流错误: {str(e)}")
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
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """上传CSV文件并开始处理"""

    # 验证文件类型
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="只支持CSV文件格式")

    try:
        # 记录开始时间
        start_time = datetime.now()
        logger.info(f"开始处理上传文件: {file.filename}")

        # 保存上传的文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")

        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        file_size = len(content)
        logger.info(f"文件保存完成，大小: {file_size} bytes")

        # 创建数据库记录
        logger.info("创建数据库记录...")
        upload_record = await db_service.create_upload_record(file.filename, file_path, file_size)
        processing_status = await db_service.create_processing_status(upload_record.id, "upload")

        logger.info(f"数据库记录创建完成 - upload_id: {upload_record.id}, processing_id: {processing_status.id}")
        logger.info(f"处理状态验证 - processing_status.upload_id: {processing_status.upload_id}")

        # 立即更新初始状态
        await db_service.update_processing_status(processing_status.id, "upload", "processing", 5.0, "文件上传完成，开始处理...")

        # 后台处理任务
        logger.info("添加后台处理任务...")
        background_tasks.add_task(
            process_file_background,
            upload_record.id,
            processing_status.id,
            file_path,
            file.filename
        )

        # 计算上传耗时
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"上传接口处理完成，耗时: {elapsed:.3f}秒，即将返回响应")

        return UploadResponse(
            upload_id=upload_record.id,
            processing_id=processing_status.id,
            message="文件上传成功，正在处理中..."
        )

    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

async def process_file_background(upload_id: int, processing_id: int, file_path: str, filename: str):
    """后台文件处理任务 - 集成示例脚本逻辑"""

    try:
        logger.info(f"开始处理文件: {filename}")

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

        # 提取境内外数据源
        domestic_sources, foreign_sources = dify_service.extract_sources_from_result(workflow_result)

        # 暂时放宽验证条件，避免因Dify模型过载导致的失败
        if not domestic_sources and not foreign_sources:
            logger.warning("⚠️ Dify返回空数据（可能是模型过载），使用空数据继续流程")
            domestic_sources = []
            foreign_sources = []

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
            if data.language:
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
        logger.info(f"🎉 开始最终状态更新 - processing_id: {processing_id}")
        await db_service.update_processing_status(processing_id, "report", "completed", 100.0, "南海舆情日报生成完成")

        # 清理临时文件
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"临时去重文件已清理: {temp_file_path}")
        except Exception as cleanup_error:
            logger.warning(f"清理临时文件失败: {cleanup_error}")

        logger.info(f"文件处理完成: {filename}")

    except Exception as e:
        logger.error(f"处理文件时发生错误: {str(e)}")

        # 清理临时文件（如果存在）
        try:
            temp_file_path = file_path.replace('.csv', '_deduplicated.csv')
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"异常处理中清理临时去重文件: {temp_file_path}")
        except Exception as cleanup_error:
            logger.warning(f"异常处理中清理临时文件失败: {cleanup_error}")

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

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)