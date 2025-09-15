import React, { useState, useEffect, useRef } from 'react';
import { FileUpload } from './components/FileUpload';
import { ProcessingStatus } from './components/ProcessingStatus';
import { DataPreview } from './components/DataPreview';
import { ReportHistory } from './components/ReportHistory';
import { ManualProcess } from './components/ManualProcess';
import { apiService, ProcessingStatusResponse, DataStatsResponse } from './services/api';
import { CacheService } from './services/cacheService';
import './App.css';

interface ProcessingState {
  processingId?: number;
  uploadId?: number;
  currentStep: string;
  status: 'idle' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  errorMessage?: string;
}

interface DataStats {
  totalRows: number;
  cleanedRows: number;
  duplicatesRemoved: number;
  domesticSources: number;
  foreignSources: number;
}

function App() {
  const [currentPage, setCurrentPage] = useState<'home' | 'manual'>('home');
  const [processingState, setProcessingState] = useState<ProcessingState>({
    currentStep: 'idle',
    status: 'idle',
    progress: 0
  });

  const [dataStats, setDataStats] = useState<DataStats>({
    totalRows: 0,
    cleanedRows: 0,
    duplicatesRemoved: 0,
    domesticSources: 0,
    foreignSources: 0
  });

  const [reportReady, setReportReady] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [currentFileName, setCurrentFileName] = useState<string>('');
  const [currentFileSize, setCurrentFileSize] = useState<number>(0);

  // SSE流式进度更新 - 使用ref避免依赖问题
  const eventSourceRef = useRef<EventSource | null>(null);

  // SSE连接管理
  useEffect(() => {
    // 如果有processing_id且状态为processing，建立SSE连接
    if (processingState.processingId && processingState.status === 'processing') {
      console.log('🔗 建立SSE连接，processing_id:', processingState.processingId);

      // 关闭之前的连接
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const handleProgress = (data: any) => {
        console.log('📡 收到SSE数据:', data);

        switch (data.type) {
          case 'connected':
            console.log('✅ SSE连接已建立');
            break;

          case 'progress':
            console.log('🔄 进度更新:', data.progress + '%', '-', data.current_step);
            setProcessingState(prev => ({
              ...prev,
              uploadId: data.upload_id, // 确保 uploadId 被正确保存
              currentStep: data.current_step,
              status: data.status as any,
              progress: data.progress,
              message: data.message,
              errorMessage: data.error_message
            }));

            // 如果处理完成，获取数据统计并缓存报告
            if (data.status === 'completed' && data.upload_id) {
              console.log('🎉 处理完成，获取数据统计');
              apiService.getDataStats(data.upload_id).then(stats => {
                const statsData = {
                  totalRows: stats.total_rows,
                  cleanedRows: stats.cleaned_rows,
                  duplicatesRemoved: stats.duplicates_removed,
                  domesticSources: stats.domestic_sources,
                  foreignSources: stats.foreign_sources
                };

                setDataStats(statsData);
                setReportReady(true);

                // 缓存报告信息
                const cachedReport = {
                  id: `report_${data.upload_id}_${Date.now()}`,
                  uploadId: data.upload_id, // 使用从 SSE 数据中获取的 upload_id
                  filename: currentFileName || '未知文件名',
                  uploadTime: new Date().toISOString(),
                  completedTime: new Date().toISOString(),
                  fileSize: currentFileSize || 0,
                  stats: statsData
                };

                CacheService.addReport(cachedReport);
                console.log('📦 报告已缓存到本地:', cachedReport);
              }).catch(error => {
                console.error('❌ 获取数据统计失败:', error);
              });
            }
            break;

          case 'finished':
            console.log('🏁 处理流程完成，状态:', data.status);
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
            break;

          case 'error':
            console.error('❌ SSE错误:', data.message);
            setProcessingState(prev => ({
              ...prev,
              status: 'failed',
              errorMessage: data.message
            }));
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
            break;

          case 'timeout':
            console.warn('⏰ SSE超时:', data.message);
            setProcessingState(prev => ({
              ...prev,
              status: 'failed',
              errorMessage: data.message || 'SSE连接超时'
            }));
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
            break;
        }
      };

      const handleError = (error: string) => {
        console.error('🔴 SSE连接错误:', error);
        setProcessingState(prev => ({
          ...prev,
          status: 'failed',
          errorMessage: `连接错误: ${error}`
        }));
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      };

      // 创建新的SSE连接
      try {
        const newEventSource = apiService.createProgressStream(
          processingState.processingId,
          handleProgress,
          handleError
        );
        eventSourceRef.current = newEventSource;
        console.log('🚀 SSE连接已启动');
      } catch (error) {
        console.error('❌ 创建SSE连接失败:', error);
        setProcessingState(prev => ({
          ...prev,
          status: 'failed',
          errorMessage: '无法建立实时连接'
        }));
      }
    }

    // 清理函数
    return () => {
      if (eventSourceRef.current) {
        console.log('🔌 关闭SSE连接');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [processingState.processingId, processingState.status]);

  // 组件卸载时清理SSE连接
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        console.log('🧹 组件卸载，清理SSE连接');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const handleFileUpload = async (file: File) => {
    try {
      console.log('开始上传文件:', file.name);

      // 保存文件信息
      setCurrentFileName(file.name);
      setCurrentFileSize(file.size);

      // 重置状态
      setProcessingState({
        currentStep: 'upload',
        status: 'processing',
        progress: 0,
        message: '文件上传中...'
      });
      setReportReady(false);

      // 调用API上传文件
      const response = await apiService.uploadFile(file);

      console.log('📤 文件上传完成，获得processing_id:', response.processing_id);

      setProcessingState(prev => ({
        ...prev,
        processingId: response.processing_id,
        uploadId: response.upload_id,
        progress: 10,
        message: response.message
      }));

      console.log('🔄 状态已更新，SSE连接应该会在useEffect中建立');

    } catch (error) {
      console.error('文件上传失败:', error);
      setProcessingState(prev => ({
        ...prev,
        currentStep: 'upload',
        status: 'failed',
        errorMessage: error instanceof Error ? error.message : '文件上传失败，请检查文件格式或网络连接'
      }));
    }
  };

  const handleDownloadReport = async () => {
    if (processingState.uploadId) {
      try {
        await apiService.downloadReport(processingState.uploadId);
      } catch (error) {
        console.error('下载报告失败:', error);
        alert('下载报告失败，请稍后重试');
      }
    }
  };

  return (
    <>
      {currentPage === 'home' ? (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
          {/* 顶部导航栏 */}
          <header className="bg-blue-900 text-white shadow-lg w-full">
            <div className="w-full px-4 md:px-6 lg:px-8 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-lg">南</span>
                  </div>
                  <h1 className="text-xl font-bold">南海舆情日报生成系统</h1>
                </div>
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => setShowHistory(!showHistory)}
                    className={`text-blue-200 hover:text-white transition-colors ${showHistory ? 'text-white' : ''}`}
                  >
                    历史记录
                  </button>
                  <button
                    onClick={() => setCurrentPage('manual')}
                    className="text-blue-200 hover:text-white transition-colors"
                  >
                    半自动流程
                  </button>
                  <button className="text-blue-200 hover:text-white transition-colors">
                    帮助文档
                  </button>
                  <div className="w-8 h-8 bg-blue-700 rounded-full flex items-center justify-center">
                    <span className="text-sm">用</span>
                  </div>
                </div>
              </div>
            </div>
          </header>

          {/* 主要内容区域 */}
          <main className="px-4 md:px-6 lg:px-8 py-8 w-full">
            <div className="max-w-5xl mx-auto space-y-8">
              {/* 历史记录部分 */}
              {showHistory && (
                <ReportHistory onRefresh={() => {}} />
              )}

              {/* 文件上传和处理状态 */}
              <div className="w-full">
                <FileUpload onFileUpload={handleFileUpload} />

                {/* 处理状态面板 */}
                {processingState.status !== 'idle' && (
                  <div className="mt-6">
                    <ProcessingStatus
                      currentStep={processingState.currentStep}
                      status={processingState.status}
                      progress={processingState.progress}
                      message={processingState.message}
                      errorMessage={processingState.errorMessage}
                    />
                  </div>
                )}
              </div>

              {/* 数据统计预览 */}
              {(processingState.status === 'completed' || reportReady) && (
                <div className="w-full">
                  <DataPreview
                    stats={dataStats}
                    reportReady={reportReady}
                    onDownloadReport={handleDownloadReport}
                  />
                </div>
              )}
            </div>
          </main>
        </div>
      ) : (
        <ManualProcess onBackToHome={() => setCurrentPage('home')} />
      )}
    </>
  );
}

export default App;