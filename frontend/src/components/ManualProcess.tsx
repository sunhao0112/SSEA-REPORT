import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { apiService } from '../services/api';

interface ManualProcessProps {
  onBackToHome: () => void;
}

export function ManualProcess({ onBackToHome }: ManualProcessProps) {
  const [jsonInput, setJsonInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  const handleOpenDifyWorkflow = () => {
    window.open('https://udify.app/workflow/NZte5RMoP5zVb6RD', '_blank');
  };

  const handleGenerateReport = async () => {
    if (!jsonInput.trim()) {
      setError('请粘贴Dify工作流的JSON响应结果');
      return;
    }

    try {
      setIsGenerating(true);
      setError('');
      setSuccess('');

      // 解析JSON
      const jsonData = JSON.parse(jsonInput);

      // 验证JSON结构
      if (!jsonData.structured_output) {
        throw new Error('JSON格式不正确，请确保包含structured_output字段');
      }

      const structuredOutput = jsonData.structured_output;

      if (!structuredOutput.domestic_sources || !structuredOutput.foreign_sources) {
        throw new Error('JSON中缺少domestic_sources或foreign_sources字段');
      }

      // 调用后端API生成报告
      const response = await fetch('/api/generate-report-from-json', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          domestic_sources: structuredOutput.domestic_sources,
          foreign_sources: structuredOutput.foreign_sources
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '生成报告失败');
      }

      // 获取文件名
      const contentDisposition = response.headers.get('content-disposition');
      let filename = '南海舆情日报.docx';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      // 下载文件
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccess('报告生成成功并已下载！');
      setJsonInput(''); // 清空输入

    } catch (error) {
      console.error('生成报告失败:', error);
      if (error instanceof SyntaxError) {
        setError('JSON格式错误，请检查粘贴的内容是否完整');
      } else {
        setError(error instanceof Error ? error.message : '生成报告失败，请重试');
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const validateJson = (input: string) => {
    try {
      if (!input.trim()) return true; // 空输入不显示错误
      JSON.parse(input);
      return true;
    } catch {
      return false;
    }
  };

  const isValidJson = validateJson(jsonInput);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 顶部导航栏 */}
      <header className="bg-blue-900 text-white shadow-lg w-full">
        <div className="w-full px-4 md:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">南</span>
              </div>
              <h1 className="text-xl font-bold">南海舆情日报生成系统 - 半自动流程</h1>
            </div>
            <div className="flex items-center space-x-4">
              <Button
                variant="outline"
                onClick={onBackToHome}
                className="bg-transparent border-blue-300 text-blue-200 hover:bg-blue-700 hover:text-white"
              >
                返回首页
              </Button>
              <div className="w-8 h-8 bg-blue-700 rounded-full flex items-center justify-center">
                <span className="text-sm">用</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      <main className="px-4 md:px-6 lg:px-8 py-8 w-full">
        <div className="max-w-4xl mx-auto space-y-6">

          {/* 操作指南 */}
          <Card className="border-blue-200 shadow-lg">
            <CardHeader className="bg-blue-50">
              <CardTitle className="text-blue-900 flex items-center">
                <span className="mr-2">📋</span>
                半自动流程操作指南
              </CardTitle>
              <CardDescription className="text-blue-700">
                按照以下步骤完成舆情报告生成
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center font-semibold">
                    1
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">访问Dify工作流</h3>
                    <p className="text-gray-600 mb-2">
                      点击下方按钮跳转到Dify工作流页面，手动上传您的融文数据CSV文件
                    </p>
                    <Button
                      onClick={handleOpenDifyWorkflow}
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      🔗 打开Dify工作流页面
                    </Button>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center font-semibold">
                    2
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">获取JSON响应</h3>
                    <p className="text-gray-600">
                      工作流处理完成后，复制JSON响应结果，格式为：{`{"structured_output": {...}}`}
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center font-semibold">
                    3
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">粘贴并生成报告</h3>
                    <p className="text-gray-600">
                      将JSON响应粘贴到下方文本框中，点击生成报告按钮即可下载Word文档
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* JSON输入和报告生成 */}
          <Card className="border-blue-200 shadow-lg">
            <CardHeader className="bg-blue-50">
              <CardTitle className="text-blue-900 flex items-center">
                <span className="mr-2">📄</span>
                JSON响应处理
              </CardTitle>
              <CardDescription className="text-blue-700">
                粘贴Dify工作流的JSON响应结果并生成Word报告
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Dify工作流JSON响应结果
                  </label>
                  <textarea
                    value={jsonInput}
                    onChange={(e) => {
                      setJsonInput(e.target.value);
                      setError('');
                      setSuccess('');
                    }}
                    placeholder="请在此处粘贴Dify工作流的完整JSON响应结果..."
                    className={`w-full h-64 p-3 border rounded-lg resize-none font-mono text-sm ${
                      jsonInput && !isValidJson
                        ? 'border-red-300 bg-red-50'
                        : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
                    }`}
                  />
                  {jsonInput && !isValidJson && (
                    <p className="mt-1 text-sm text-red-600">
                      JSON格式不正确，请检查是否完整复制了响应结果
                    </p>
                  )}
                </div>

                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-red-800 text-sm">
                      <span className="font-semibold">错误：</span>{error}
                    </p>
                  </div>
                )}

                {success && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                    <p className="text-green-800 text-sm">
                      <span className="font-semibold">成功：</span>{success}
                    </p>
                  </div>
                )}

                <div className="flex justify-end">
                  <Button
                    onClick={handleGenerateReport}
                    disabled={!jsonInput.trim() || !isValidJson || isGenerating}
                    className="bg-green-600 hover:bg-green-700 text-white px-6 py-2"
                  >
                    {isGenerating ? (
                      <>
                        <span className="mr-2">⏳</span>
                        生成中...
                      </>
                    ) : (
                      <>
                        <span className="mr-2">📄</span>
                        生成Word报告
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 注意事项 */}
          <Card className="border-yellow-200 bg-yellow-50">
            <CardContent className="pt-6">
              <div className="flex items-start space-x-3">
                <span className="text-yellow-600 text-xl">⚠️</span>
                <div>
                  <h3 className="font-semibold text-yellow-800 mb-2">注意事项</h3>
                  <ul className="text-yellow-700 text-sm space-y-1">
                    <li>• 请确保复制的是完整的JSON响应，包含所有字段</li>
                    <li>• JSON必须包含 domestic_sources 和 foreign_sources 字段</li>
                    <li>• 生成的报告将自动下载到您的下载文件夹</li>
                    <li>• 如果遇到问题，请检查JSON格式或联系技术支持</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}