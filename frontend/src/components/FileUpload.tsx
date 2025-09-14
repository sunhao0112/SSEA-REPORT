import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, X, CheckCircle, AlertCircle, Info } from 'lucide-react';

interface FileUploadProps {
  onFileUpload: (file: File) => void;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onFileUpload
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setShowConfirm(true);
      } else {
        alert('请上传CSV格式的文件');
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv']
    },
    multiple: false
  });

  const handleConfirmUpload = () => {
    if (selectedFile) {
      onFileUpload(selectedFile);
      setShowConfirm(false);
      setSelectedFile(null);
    }
  };

  const handleCancelUpload = () => {
    setSelectedFile(null);
    setShowConfirm(false);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <Upload className="h-6 w-6 text-blue-600" />
          南海舆情数据上传
        </h2>
        <p className="text-gray-600 mt-1">请上传包含舆情数据的CSV文件</p>
      </div>

      {/* 文件确认对话框 */}
      {showConfirm && selectedFile && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-blue-900 mb-2">确认文件信息</h3>
              <div className="space-y-2 text-sm text-blue-800">
                <div className="flex items-center justify-between">
                  <span className="font-medium">文件名:</span>
                  <span className="text-right">{selectedFile.name}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-medium">文件大小:</span>
                  <span className="text-right">{formatFileSize(selectedFile.size)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-medium">文件类型:</span>
                  <span className="text-right">CSV</span>
                </div>
              </div>
              <div className="flex gap-3 mt-4">
                <button
                  onClick={handleConfirmUpload}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <CheckCircle className="h-4 w-4" />
                  确认开始处理
                </button>
                <button
                  onClick={handleCancelUpload}
                  className="flex-1 bg-gray-500 hover:bg-gray-600 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <X className="h-4 w-4" />
                  重新选择
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all duration-200
          ${isDragActive || dragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }
        `}
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-4">
          <div className="p-4 bg-blue-100 rounded-full">
            <Upload className="h-8 w-8 text-blue-600" />
          </div>
          <div>
            <p className="text-lg font-medium text-gray-900 mb-2">
              拖拽CSV文件到此处，或点击选择文件
            </p>
            <p className="text-sm text-gray-500">
              支持CSV格式文件，文件第一行应为列标题
            </p>
          </div>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            选择文件
          </button>
        </div>
      </div>
    </div>
  );
};