import React from 'react';
import { FileText, Database, Filter } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface DataStats {
  totalRows: number;
  cleanedRows: number;
  duplicatesRemoved: number;
  domesticSources: number;
  foreignSources: number;
}

interface DataPreviewProps {
  stats: DataStats;
  reportReady: boolean;
  onDownloadReport: () => void;
}

export const DataPreview: React.FC<DataPreviewProps> = ({
  stats,
  reportReady,
  onDownloadReport
}) => {

  const StatCard = ({
    icon: Icon,
    title,
    value,
    color = "text-gray-600"
  }: {
    icon: React.ElementType;
    title: string;
    value: number;
    color?: string;
  }) => (
    <div className="flex flex-col items-center text-center p-6 md:p-8 bg-white rounded-xl border border-gray-200 hover:shadow-lg transition-all duration-300 min-h-[130px] md:min-h-[150px] hover:border-gray-300">
      <div className={`p-4 rounded-full bg-gray-50 mb-3 group-hover:bg-gray-100`}>
        <Icon className={`h-6 w-6 md:h-7 md:w-7 ${color}`} />
      </div>
      <div className="w-full">
        <p className="text-sm md:text-base text-gray-600 leading-tight mb-2 font-medium" title={title}>
          {title}
        </p>
        <p className="text-xl md:text-2xl lg:text-3xl font-bold text-gray-900">
          {value.toLocaleString()}
        </p>
      </div>
    </div>
  );

  return (
    <div className="w-full">
      {/* 标题区域 */}
      <div className="mb-6">
        <h2 className="flex items-center gap-3 text-2xl font-bold text-gray-900">
          <Database className="h-8 w-8 text-blue-600" />
          数据统计概览
        </h2>
      </div>

      {/* 主要数据统计 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 lg:gap-8 mb-8">
        <StatCard
          icon={FileText}
          title="原始数据条数"
          value={stats.totalRows}
          color="text-blue-600"
        />
        <StatCard
          icon={Filter}
          title="清洗后数据"
          value={stats.cleanedRows}
          color="text-green-600"
        />
        <StatCard
          icon={Database}
          title="去重数量"
          value={stats.duplicatesRemoved}
          color="text-orange-600"
        />
        <StatCard
          icon={FileText}
          title="境内数据源"
          value={stats.domesticSources}
          color="text-purple-600"
        />
        <StatCard
          icon={FileText}
          title="境外数据源"
          value={stats.foreignSources}
          color="text-red-600"
        />
      </div>

      {/* 数据完整性单独成行 */}
      <div className="mb-8">
        <div className="flex items-center gap-4 p-6 md:p-8 bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl border border-blue-200 hover:shadow-lg transition-all duration-300">
          <div className="p-4 rounded-full bg-blue-200 flex-shrink-0">
            <Database className="h-7 w-7 text-blue-700" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-base md:text-lg text-blue-700 font-medium mb-1">数据完整性</p>
            <p className="text-2xl md:text-3xl lg:text-4xl font-bold text-blue-900">
              {stats.totalRows > 0 ? ((stats.cleanedRows / stats.totalRows) * 100).toFixed(1) : 0}%
            </p>
          </div>
          <div className="text-sm md:text-base text-blue-600 flex-shrink-0 text-right font-medium">
            <div className="whitespace-nowrap text-lg md:text-xl font-semibold">
              {stats.cleanedRows} / {stats.totalRows}
            </div>
            <div className="whitespace-nowrap text-sm md:text-base">
              条数据保留
            </div>
          </div>
        </div>
      </div>

      {/* 下载报告按钮 */}
      {reportReady && (
        <div className="flex justify-center">
          <button
            onClick={onDownloadReport}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 px-8 rounded-xl transition-colors flex items-center justify-center gap-3 text-lg shadow-lg hover:shadow-xl"
          >
            <FileText className="h-6 w-6" />
            下载舆情日报
          </button>
        </div>
      )}
    </div>
  );
};