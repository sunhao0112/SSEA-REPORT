import React from 'react';
import { Download, FileText, Clock, Database, Trash2 } from 'lucide-react';
import { CachedReport, CacheService } from '../services/cacheService';
import { apiService } from '../services/api';

interface ReportHistoryProps {
  onRefresh?: () => void;
}

export const ReportHistory: React.FC<ReportHistoryProps> = ({ onRefresh }) => {
  const [cachedReports, setCachedReports] = React.useState<CachedReport[]>([]);
  const [downloadingIds, setDownloadingIds] = React.useState<Set<number>>(new Set());

  React.useEffect(() => {
    loadCachedReports();
  }, []);

  const loadCachedReports = () => {
    const reports = CacheService.getRecentReports(20);
    setCachedReports(reports);
  };

  const handleDownload = async (report: CachedReport) => {
    try {
      setDownloadingIds(prev => new Set(prev).add(report.uploadId));
      await apiService.downloadReport(report.uploadId);
    } catch (error) {
      console.error('下载报告失败:', error);
      alert('下载失败，可能报告文件已被清理，请重新生成');
    } finally {
      setDownloadingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(report.uploadId);
        return newSet;
      });
    }
  };

  const handleRemove = (report: CachedReport) => {
    if (confirm(`确定要从历史记录中删除 "${report.filename}" 吗？`)) {
      CacheService.removeReport(report.uploadId);
      loadCachedReports();
      onRefresh?.();
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('zh-CN');
    } catch {
      return dateString;
    }
  };

  if (cachedReports.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="h-6 w-6 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-800">历史报告</h3>
        </div>
        <div className="text-center py-8">
          <FileText className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">暂无历史报告</p>
          <p className="text-sm text-gray-400 mt-1">处理完成的报告会自动保存到这里</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="h-6 w-6 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-800">历史报告</h3>
          <span className="text-sm text-gray-500">({cachedReports.length})</span>
        </div>
        <button
          onClick={loadCachedReports}
          className="text-blue-600 hover:text-blue-700 text-sm font-medium"
        >
          刷新
        </button>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {cachedReports.map((report) => (
          <div
            key={report.id}
            className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-all duration-200"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="h-4 w-4 text-blue-600 flex-shrink-0" />
                  <h4 className="font-medium text-gray-900 truncate" title={report.filename}>
                    {report.filename}
                  </h4>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 mb-2">
                  <div>上传时间: {formatDate(report.uploadTime)}</div>
                  <div>完成时间: {formatDate(report.completedTime)}</div>
                  <div>文件大小: {formatFileSize(report.fileSize)}</div>
                  <div>数据质量: {((report.stats.cleanedRows / report.stats.totalRows) * 100).toFixed(0)}%</div>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <Database className="h-3 w-3" />
                    {report.stats.totalRows} 条原始数据
                  </span>
                  <span>{report.stats.domesticSources} 境内 / {report.stats.foreignSources} 境外</span>
                </div>
              </div>
              <div className="flex items-center gap-2 ml-3">
                <button
                  onClick={() => handleDownload(report)}
                  disabled={downloadingIds.has(report.uploadId)}
                  className="p-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50"
                  title="下载报告"
                >
                  <Download className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleRemove(report)}
                  className="p-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                  title="从历史中删除"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="flex justify-between items-center text-sm text-gray-500">
          <span>本地缓存，最多保存50条记录</span>
          <button
            onClick={() => {
              if (confirm('确定要清空所有历史记录吗？此操作不可恢复。')) {
                CacheService.clearCache();
                loadCachedReports();
                onRefresh?.();
              }
            }}
            className="text-red-600 hover:text-red-700 font-medium"
          >
            清空历史
          </button>
        </div>
      </div>
    </div>
  );
};