from models import UploadRecord, ProcessingStatus, RawData, ProcessedData, ReportGeneration
from schemas import RawDataItem, UploadHistoryResponse, UploadHistoryItem
from typing import List, Optional
from datetime import datetime
import json
import pandas as pd
import numpy as np

def clean_for_json(value):
    """清理数据值以确保JSON兼容性"""
    if pd.isna(value) or value is None:
        return None
    elif isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    elif isinstance(value, str) and value.lower() in ['nan', 'null', '']:
        return None
    else:
        return str(value).strip() if value else None

def clean_dict_for_json(data_dict):
    """递归清理字典中的NaN值"""
    if isinstance(data_dict, dict):
        return {k: clean_dict_for_json(v) for k, v in data_dict.items()}
    elif isinstance(data_dict, list):
        return [clean_dict_for_json(item) for item in data_dict]
    else:
        return clean_for_json(data_dict)

class DatabaseService:
    """数据库操作服务 - 使用Supabase异步模型"""

    def __init__(self):
        # 不再需要db session，使用异步模型
        pass

    async def create_upload_record(self, filename: str, file_path: str, file_size: int) -> UploadRecord:
        """创建上传记录"""

        upload_data = {
            "filename": filename,
            "file_path": file_path,
            "file_size": file_size,
            "status": "uploaded"
        }

        return await UploadRecord.create(upload_data)

    async def create_processing_status(self, upload_id: int, current_step: str) -> ProcessingStatus:
        """创建处理状态记录"""

        status_data = {
            "upload_id": upload_id,
            "current_step": current_step,
            "status": "processing",
            "progress": 0.0
        }

        return await ProcessingStatus.create(status_data)

    async def update_processing_status(
        self,
        processing_id: int,
        current_step: str = None,
        status: str = None,
        progress: float = None,
        message: str = None,
        error_message: str = None
    ) -> Optional[ProcessingStatus]:
        """更新处理状态"""

        # 获取现有记录 - 直接通过processing_id查询
        processing_status = await ProcessingStatus.get_by_id(processing_id)
        if not processing_status:
            return None

        # 准备更新数据
        update_data = {}
        if current_step:
            update_data["current_step"] = current_step
        if status:
            update_data["status"] = status
        if progress is not None:
            update_data["progress"] = progress
        if message:
            update_data["message"] = message
        if error_message:
            update_data["error_message"] = error_message

        if update_data:
            # 添加调试日志
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"更新处理状态 - processing_id: {processing_id}, 更新数据: {update_data}")

            result = await processing_status.update(update_data)

            logger.info(f"状态更新成功 - processing_id: {processing_id}, 新状态: step={result.current_step}, status={result.status}, progress={result.progress}")

            return result

        return processing_status

    async def save_raw_data(self, upload_id: int, raw_data):
        """保存原始数据到数据库"""

        data_list = []
        for item in raw_data:
            # 处理字典格式的数据
            if isinstance(item, dict):
                # 清理字典中的NaN值
                clean_item = clean_dict_for_json(item)
                raw_data_item = {
                    "upload_id": upload_id,
                    "url": clean_for_json(clean_item.get('URL')),
                    "source_name": clean_for_json(clean_item.get('来源名称')),
                    "author_username": clean_for_json(clean_item.get('作者用户名称')),
                    "title": clean_for_json(clean_item.get('标题')),
                    "hit_sentence": clean_for_json(clean_item.get('命中句子')),
                    "language": clean_for_json(clean_item.get('语言')),
                    "original_data": clean_item
                }
            else:
                # 处理 RawDataItem 对象
                raw_data_item = {
                    "upload_id": upload_id,
                    "url": clean_for_json(item.url),
                    "source_name": clean_for_json(item.source_name),
                    "author_username": clean_for_json(item.author_username),
                    "title": clean_for_json(item.title),
                    "hit_sentence": clean_for_json(item.hit_sentence),
                    "language": clean_for_json(item.language),
                    "original_data": clean_dict_for_json(item.dict()) if hasattr(item, 'dict') else clean_for_json(str(item))
                }

            data_list.append(raw_data_item)

        # 批量创建
        if data_list:
            await RawData.bulk_create(data_list)

    async def save_processed_data(self, upload_id: int, domestic_sources: List[dict], foreign_sources: List[dict]):
        """保存处理后的数据"""

        # 保存境内数据
        if domestic_sources:
            # 清理数据中的NaN值
            clean_domestic = clean_dict_for_json(domestic_sources)
            domestic_data = {
                "upload_id": upload_id,
                "data_type": "domestic",
                "structured_data": clean_domestic
            }
            await ProcessedData.create(domestic_data)

        # 保存境外数据
        if foreign_sources:
            # 清理数据中的NaN值
            clean_foreign = clean_dict_for_json(foreign_sources)
            foreign_data = {
                "upload_id": upload_id,
                "data_type": "foreign",
                "structured_data": clean_foreign
            }
            await ProcessedData.create(foreign_data)

    async def create_report_generation(self, upload_id: int, report_path: str, report_type: str, file_size: int) -> ReportGeneration:
        """创建报告生成记录"""

        report_data = {
            "upload_id": upload_id,
            "report_path": report_path,
            "report_type": report_type,
            "file_size": file_size
        }

        report_generation = await ReportGeneration.create(report_data)

        # 更新上传记录的报告路径
        upload_record = await UploadRecord.get_by_id(upload_id)
        if upload_record:
            await upload_record.update({
                "report_path": report_path,
                "status": "completed"
            })

        return report_generation

    async def get_upload_history(self, limit: int = 50, offset: int = 0) -> UploadHistoryResponse:
        """获取上传历史记录"""

        # 查询所有记录（注意：实际应用中需要分页）
        records = await UploadRecord.get_all()

        # 计算总数
        total = len(records)

        # 应用分页
        start_idx = offset
        end_idx = offset + limit
        paginated_records = records[start_idx:end_idx]

        uploads = []
        for record in paginated_records:
            uploads.append(UploadHistoryItem(
                id=record.id,
                filename=record.filename,
                file_size=record.file_size,
                upload_time=record.upload_time,
                status=record.status,
                error_message=record.error_message,
                report_path=record.report_path
            ))

        return UploadHistoryResponse(uploads=uploads, total=total)

    async def get_processing_status(self, processing_id: int) -> Optional[ProcessingStatus]:
        """获取处理状态"""
        return await ProcessingStatus.get_by_id(processing_id)

    async def get_upload_record(self, upload_id: int) -> Optional[UploadRecord]:
        """获取上传记录"""

        return await UploadRecord.get_by_id(upload_id)

    async def get_raw_data_by_upload_id(self, upload_id: int) -> List[RawData]:
        """根据上传ID获取原始数据"""

        return await RawData.get_by_upload_id(upload_id)

    async def get_processed_data(self, upload_id: int) -> dict:
        """获取处理后的数据"""

        processed_data_list = await ProcessedData.get_by_upload_id(upload_id)

        domestic_sources = []
        foreign_sources = []

        for data in processed_data_list:
            if data.data_type == "domestic":
                domestic_sources = data.structured_data
            elif data.data_type == "foreign":
                foreign_sources = data.structured_data

        return {
            "domestic_sources": domestic_sources,
            "foreign_sources": foreign_sources
        }

    async def get_data_stats(self, upload_id: int) -> dict:
        """获取数据统计信息"""

        # 原始数据统计
        raw_data_list = await RawData.get_by_upload_id(upload_id)
        total_raw = len(raw_data_list)

        # 统计有效的命中句子数量（去重后的数量）
        unique_hit_sentences = set()
        inside_count = 0  # 语言包含Chinese的数量
        outside_count = 0  # 语言不是Chinese (simpl.)的数量

        for data in raw_data_list:
            # 统计唯一命中句子
            if data.hit_sentence and data.hit_sentence.strip():
                unique_hit_sentences.add(data.hit_sentence.strip())

            # 根据语言列统计境内外数量
            if data.language:
                language = data.language.strip()
                if "Chinese" in language:
                    inside_count += 1
                else:
                    outside_count += 1

        # 去重后的实际数量
        cleaned_rows = len(unique_hit_sentences)

        # 处理后数据统计（AI分析结果）
        processed_data_list = await ProcessedData.get_by_upload_id(upload_id)

        domestic_ai_count = 0
        foreign_ai_count = 0

        for data in processed_data_list:
            if data.data_type == "domestic":
                domestic_ai_count = len(data.structured_data)
            elif data.data_type == "foreign":
                foreign_ai_count = len(data.structured_data)

        return {
            "total_rows": total_raw,
            "cleaned_rows": cleaned_rows,  # 实际去重后的唯一命中句子数
            "duplicates_removed": max(0, total_raw - cleaned_rows),
            "domestic_sources": inside_count,  # 语言包含Chinese的数量
            "foreign_sources": outside_count,  # 语言不包含Chinese的数量
            "ai_domestic_count": domestic_ai_count,  # AI分析的境内观点数
            "ai_foreign_count": foreign_ai_count    # AI分析的境外观点数
        }