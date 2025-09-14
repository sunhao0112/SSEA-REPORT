import React from 'react';
import { CheckCircle, Clock, AlertCircle, Loader2 } from 'lucide-react';

interface ProcessingStatusProps {
  currentStep: string;
  status: 'idle' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  errorMessage?: string;
}

export const ProcessingStatus: React.FC<ProcessingStatusProps> = ({
  currentStep,
  status,
  progress,
  message,
  errorMessage
}) => {
  const steps = [
    { id: 'upload', title: '文件上传', description: '上传CSV数据文件' },
    { id: 'clean', title: '数据清洗', description: '清理和标准化数据' },
    { id: 'dedupe', title: '数据去重', description: '去除重复数据' },
    { id: 'workflow', title: 'AI分析', description: '智能分析和数据分离' },
    { id: 'report', title: '生成报告', description: '生成舆情日报文档' }
  ];

  const getStepStatus = (stepId: string) => {
    const stepIndex = steps.findIndex(s => s.id === stepId);
    const currentIndex = steps.findIndex(s => s.id === currentStep);

    // 处理错误状态
    if (status === 'failed') {
      if (currentStep === 'error') {
        // 如果是全局错误，标记当前正在处理的步骤为错误
        return stepIndex === steps.length - 1 ? 'error' : (stepIndex < steps.length - 1 ? 'completed' : 'pending');
      } else if (stepIndex === currentIndex) {
        return 'error';
      }
    }

    // 处理完成状态 - 支持 'completed' 步骤名
    if (currentStep === 'completed' && status === 'completed') {
      return 'completed';
    }

    if (stepIndex < currentIndex || (stepIndex === currentIndex && status === 'completed')) {
      return 'completed';
    } else if (stepIndex === currentIndex && status === 'processing') {
      return 'processing';
    } else {
      return 'pending';
    }
  };

  const getStepIcon = (stepStatus: string) => {
    switch (stepStatus) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'processing':
        return <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />;
      case 'error':
        return <AlertCircle className="h-5 w-5 text-red-600" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStepColor = (stepStatus: string) => {
    switch (stepStatus) {
      case 'completed':
        return 'border-green-200 bg-green-50';
      case 'processing':
        return 'border-blue-200 bg-blue-50';
      case 'error':
        return 'border-red-200 bg-red-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      {/* 全局错误消息 */}
      {status === 'failed' && currentStep === 'error' && errorMessage && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start">
            <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 mr-2 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-800">系统错误</p>
              <p className="text-sm text-red-700 mt-1">{errorMessage}</p>
            </div>
          </div>
        </div>
      )}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800">处理进度</h3>
        <div className="mt-2 bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${
              status === 'failed' ? 'bg-red-600' : 'bg-blue-600'
            }`}
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <div className="flex justify-between items-center mt-1">
          <p className="text-sm text-gray-600">{progress}% 完成</p>
          {status === 'failed' && (
            <p className="text-sm text-red-600 font-medium">处理失败</p>
          )}
          {status === 'completed' && (
            <p className="text-sm text-green-600 font-medium">处理完成</p>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((step, index) => {
          const stepStatus = getStepStatus(step.id);
          return (
            <div
              key={step.id}
              className={`
                flex items-center gap-3 p-3 rounded-lg border transition-all duration-200
                ${getStepColor(stepStatus)}
                ${currentStep === step.id ? 'ring-2 ring-blue-200' : ''}
              `}
            >
              {getStepIcon(stepStatus)}
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900">
                    {index + 1}. {step.title}
                  </span>
                  <span className="text-xs text-gray-500 capitalize">
                    {stepStatus === 'processing' ? '处理中...' : 
                     stepStatus === 'completed' ? '已完成' :
                     stepStatus === 'error' ? '错误' : '等待中'}
                  </span>
                </div>
                <p className="text-sm text-gray-600">{step.description}</p>
                {(currentStep === step.id || (currentStep === 'completed' && step.id === 'report')) && message && (
                  <p className="text-sm text-blue-600 mt-1">{message}</p>
                )}
                {((currentStep === step.id || currentStep === 'error') && errorMessage) && (
                  <p className="text-sm text-red-600 mt-1">{errorMessage}</p>
                )}
                {status === 'failed' && stepStatus === 'error' && !errorMessage && (
                  <p className="text-sm text-red-600 mt-1">处理失败</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};