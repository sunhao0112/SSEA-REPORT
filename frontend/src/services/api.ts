// API服务配置
const API_BASE_URL = window.location.origin;

export interface UploadResponse {
  upload_id: number;
  processing_id?: number;
  message: string;
}

export interface ProcessingStatusResponse {
  processing_id: number;
  upload_id: number;
  current_step: string;
  status: string;
  progress: number;
  message?: string;
  error_message?: string;
  created_time: string;
  updated_time?: string;
}

export interface DataStatsResponse {
  total_rows: number;
  cleaned_rows: number;
  duplicates_removed: number;
  domestic_sources: number;
  foreign_sources: number;
}

export interface ProcessedDataResponse {
  domestic_sources: any[];
  foreign_sources: any[];
}

export interface UploadHistoryItem {
  id: number;
  filename: string;
  file_size: number;
  upload_time: string;
  status: string;
  error_message?: string;
  report_path?: string;
}

export interface UploadHistoryResponse {
  uploads: UploadHistoryItem[];
  total: number;
}

class ApiService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/api/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '文件上传失败');
    }

    return response.json();
  }

  async getProcessingStatus(processingId: number): Promise<ProcessingStatusResponse> {
    const response = await fetch(`${this.baseUrl}/api/status/${processingId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '获取处理状态失败');
    }

    return response.json();
  }

  /**
   * 创建实时进度流连接 (Server-Sent Events)
   */
  createProgressStream(processingId: number, onProgress: (data: any) => void, onError?: (error: string) => void): EventSource {
    const eventSource = new EventSource(`${this.baseUrl}/api/progress-stream/${processingId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onProgress(data);
      } catch (error) {
        console.error('解析SSE数据失败:', error);
        onError?.('数据解析错误');
      }
    };

    eventSource.onerror = (event) => {
      console.error('SSE连接错误:', event);
      onError?.('连接错误');
    };

    return eventSource;
  }

  async getDataStats(uploadId: number): Promise<DataStatsResponse> {
    const response = await fetch(`${this.baseUrl}/api/stats/${uploadId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '获取数据统计失败');
    }

    return response.json();
  }

  async getProcessedData(uploadId: number): Promise<ProcessedDataResponse> {
    const response = await fetch(`${this.baseUrl}/api/data/${uploadId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '获取处理数据失败');
    }

    return response.json();
  }

  async getUploadHistory(limit: number = 50, offset: number = 0): Promise<UploadHistoryResponse> {
    const response = await fetch(`${this.baseUrl}/api/history?limit=${limit}&offset=${offset}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '获取上传历史失败');
    }

    return response.json();
  }

  getDownloadUrl(uploadId: number): string {
    return `${this.baseUrl}/api/download/${uploadId}`;
  }

  async downloadReport(uploadId: number): Promise<void> {
    const url = this.getDownloadUrl(uploadId);
    const link = document.createElement('a');
    link.href = url;
    link.download = `nanhai_report_${uploadId}.docx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

export const apiService = new ApiService();