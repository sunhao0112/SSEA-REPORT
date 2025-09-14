from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
from database import db_service

class UploadRecord(BaseModel):
    """上传记录数据模型"""
    id: Optional[int] = None
    filename: str
    file_path: str
    file_size: int
    upload_time: Optional[datetime] = None
    status: str = "uploaded"  # uploaded, processing, completed, failed
    error_message: Optional[str] = None
    report_path: Optional[str] = None

    class Config:
        from_attributes = True

    @classmethod
    async def create(cls, data: dict) -> "UploadRecord":
        """创建上传记录"""
        if 'upload_time' not in data:
            data['upload_time'] = datetime.now().isoformat()

        result = await db_service.insert_data("upload_records", data)
        return cls(**result)

    @classmethod
    async def get_by_id(cls, upload_id: int) -> Optional["UploadRecord"]:
        """根据ID获取上传记录"""
        data = await db_service.get_data("upload_records", {"id": upload_id})
        if data:
            return cls(**data[0])
        return None

    @classmethod
    async def get_all(cls) -> List["UploadRecord"]:
        """获取所有上传记录"""
        data = await db_service.get_data("upload_records")
        return [cls(**item) for item in data]

    async def update(self, data: dict) -> "UploadRecord":
        """更新上传记录"""
        result = await db_service.update_data("upload_records", data, {"id": self.id})
        if result:
            for key, value in result.items():
                setattr(self, key, value)
        return self

class ProcessingStatus(BaseModel):
    """处理状态数据模型"""
    id: Optional[int] = None
    upload_id: int
    current_step: str  # upload, clean, dedupe, workflow, report
    status: str = "processing"  # processing, completed, failed
    progress: float = 0.0  # 0-100
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    async def create(cls, data: dict) -> "ProcessingStatus":
        """创建处理状态"""
        if 'created_time' not in data:
            data['created_time'] = datetime.now().isoformat()
        if 'updated_time' not in data:
            data['updated_time'] = datetime.now().isoformat()

        result = await db_service.insert_data("processing_status", data)
        return cls(**result)

    @classmethod
    async def get_by_upload_id(cls, upload_id: int) -> List["ProcessingStatus"]:
        """根据上传ID获取处理状态"""
        data = await db_service.get_data("processing_status", {"upload_id": upload_id})
        return [cls(**item) for item in data]

    @classmethod
    async def get_by_id(cls, processing_id: int) -> Optional["ProcessingStatus"]:
        """根据处理状态ID获取处理状态"""
        data = await db_service.get_data("processing_status", {"id": processing_id})
        if data:
            return cls(**data[0])
        return None

    async def update(self, data: dict) -> "ProcessingStatus":
        """更新处理状态"""
        data['updated_time'] = datetime.now().isoformat()
        result = await db_service.update_data("processing_status", data, {"id": self.id})
        if result:
            for key, value in result.items():
                setattr(self, key, value)
        return self

class RawData(BaseModel):
    """原始数据模型"""
    id: Optional[int] = None
    upload_id: int
    url: Optional[str] = None
    source_name: Optional[str] = None
    author_username: Optional[str] = None
    title: Optional[str] = None
    hit_sentence: Optional[str] = None
    language: Optional[str] = None
    original_data: Optional[Dict[str, Any]] = None
    created_time: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    async def create(cls, data: dict) -> "RawData":
        """创建原始数据记录"""
        if 'created_time' not in data:
            data['created_time'] = datetime.now().isoformat()

        result = await db_service.insert_data("raw_data", data)
        return cls(**result)

    @classmethod
    async def get_by_upload_id(cls, upload_id: int) -> List["RawData"]:
        """根据上传ID获取原始数据"""
        data = await db_service.get_data("raw_data", {"upload_id": upload_id})
        return [cls(**item) for item in data]

    @classmethod
    async def bulk_create(cls, data_list: List[dict]) -> List["RawData"]:
        """批量创建原始数据记录 - 真正的批量操作"""
        if not data_list:
            return []

        # 为所有数据添加创建时间
        current_time = datetime.now().isoformat()
        for data in data_list:
            if 'created_time' not in data:
                data['created_time'] = current_time

        # 使用真正的批量插入
        results = await db_service.bulk_insert_data("raw_data", data_list)
        return [cls(**item) for item in results]

class ProcessedData(BaseModel):
    """处理后数据模型"""
    id: Optional[int] = None
    upload_id: int
    data_type: str  # domestic, foreign
    structured_data: List[Dict[str, Any]]  # 修改为列表类型，符合Dify返回的数据结构
    created_time: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    async def create(cls, data: dict) -> "ProcessedData":
        """创建处理后数据记录"""
        if 'created_time' not in data:
            data['created_time'] = datetime.now().isoformat()

        result = await db_service.insert_data("processed_data", data)
        return cls(**result)

    @classmethod
    async def get_by_upload_id(cls, upload_id: int) -> List["ProcessedData"]:
        """根据上传ID获取处理后数据"""
        data = await db_service.get_data("processed_data", {"upload_id": upload_id})
        return [cls(**item) for item in data]

class ReportGeneration(BaseModel):
    """报告生成模型"""
    id: Optional[int] = None
    upload_id: int
    report_path: str
    report_type: str = "docx"  # docx, pdf
    generation_time: Optional[datetime] = None
    file_size: Optional[int] = None

    class Config:
        from_attributes = True

    @classmethod
    async def create(cls, data: dict) -> "ReportGeneration":
        """创建报告生成记录"""
        if 'generation_time' not in data:
            data['generation_time'] = datetime.now().isoformat()

        result = await db_service.insert_data("report_generations", data)
        return cls(**result)

    @classmethod
    async def get_by_upload_id(cls, upload_id: int) -> Optional["ReportGeneration"]:
        """根据上传ID获取报告生成记录"""
        data = await db_service.get_data("report_generations", {"upload_id": upload_id})
        if data:
            return cls(**data[0])
        return None