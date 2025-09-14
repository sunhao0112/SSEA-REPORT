export interface CachedReport {
  id: string;
  uploadId: number;
  filename: string;
  uploadTime: string;
  completedTime: string;
  fileSize: number;
  stats: {
    totalRows: number;
    cleanedRows: number;
    duplicatesRemoved: number;
    domesticSources: number;
    foreignSources: number;
  };
}

const CACHE_KEY = 'nanhai_reports_cache';
const MAX_CACHE_SIZE = 50; // 最多缓存50个报告

export class CacheService {
  private static getCachedReports(): CachedReport[] {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      return cached ? JSON.parse(cached) : [];
    } catch (error) {
      console.error('Failed to load cached reports:', error);
      return [];
    }
  }

  private static saveCachedReports(reports: CachedReport[]): void {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(reports));
    } catch (error) {
      console.error('Failed to save cached reports:', error);
    }
  }

  static addReport(report: CachedReport): void {
    const reports = this.getCachedReports();

    // 检查是否已存在相同的报告
    const existingIndex = reports.findIndex(r => r.uploadId === report.uploadId);
    if (existingIndex !== -1) {
      // 更新已存在的报告
      reports[existingIndex] = report;
    } else {
      // 添加新报告
      reports.unshift(report); // 最新的在前面

      // 限制缓存大小
      if (reports.length > MAX_CACHE_SIZE) {
        reports.splice(MAX_CACHE_SIZE);
      }
    }

    this.saveCachedReports(reports);
  }

  static getReports(): CachedReport[] {
    return this.getCachedReports();
  }

  static getReport(uploadId: number): CachedReport | undefined {
    const reports = this.getCachedReports();
    return reports.find(r => r.uploadId === uploadId);
  }

  static removeReport(uploadId: number): void {
    const reports = this.getCachedReports();
    const filteredReports = reports.filter(r => r.uploadId !== uploadId);
    this.saveCachedReports(filteredReports);
  }

  static clearCache(): void {
    localStorage.removeItem(CACHE_KEY);
  }

  static getRecentReports(limit: number = 10): CachedReport[] {
    const reports = this.getCachedReports();
    return reports.slice(0, limit);
  }
}