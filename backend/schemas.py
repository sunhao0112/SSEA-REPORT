from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any

class UploadResponse(BaseModel):
    upload_id: int
    processing_id: Optional[int] = None
    message: str

class ProcessingStatusResponse(BaseModel):
    processing_id: int
    upload_id: int
    current_step: str
    status: str
    progress: float
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_time: datetime
    updated_time: Optional[datetime] = None

class DataStatsResponse(BaseModel):
    total_rows: int
    cleaned_rows: int
    duplicates_removed: int
    domestic_sources: int
    foreign_sources: int

class RawDataItem(BaseModel):
    url: Optional[str] = None
    source_name: Optional[str] = None
    author_username: Optional[str] = None
    title: Optional[str] = None
    hit_sentence: Optional[str] = None
    language: Optional[str] = None

class ProcessedDataResponse(BaseModel):
    domestic_sources: List[Dict[str, Any]]
    foreign_sources: List[Dict[str, Any]]

class UploadHistoryItem(BaseModel):
    id: int
    filename: str
    file_size: int
    upload_time: datetime
    status: str
    error_message: Optional[str] = None
    report_path: Optional[str] = None

class UploadHistoryResponse(BaseModel):
    uploads: List[UploadHistoryItem]
    total: int