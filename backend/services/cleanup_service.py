"""
定期清理服务
提供自动清理临时文件、过期数据、日志文件等功能
"""
import os
import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# APScheduler 可选依赖
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    AsyncIOScheduler = None
    CronTrigger = None
    IntervalTrigger = None

from services.logger_config import get_logger
from services.cache_service import cache_manager

logger = get_logger("cleanup")

class CleanupService:
    """定期清理服务"""

    def __init__(self):
        if HAS_APSCHEDULER:
            self.scheduler = AsyncIOScheduler()
        else:
            self.scheduler = None
        self.is_running = False

        # 清理配置
        self.config = {
            'temp_files_max_age_hours': int(os.getenv('CLEANUP_TEMP_FILES_MAX_AGE', '24')),
            'old_uploads_max_age_days': int(os.getenv('CLEANUP_UPLOADS_MAX_AGE', '30')),
            'old_reports_max_age_days': int(os.getenv('CLEANUP_REPORTS_MAX_AGE', '90')),
            'log_files_max_age_days': int(os.getenv('CLEANUP_LOGS_MAX_AGE', '30')),
            'max_upload_files_count': int(os.getenv('CLEANUP_MAX_UPLOAD_FILES', '1000')),
            'max_report_files_count': int(os.getenv('CLEANUP_MAX_REPORT_FILES', '500')),
            'cleanup_interval_minutes': int(os.getenv('CLEANUP_INTERVAL_MINUTES', '60')),
            'cache_cleanup_interval_minutes': int(os.getenv('CACHE_CLEANUP_INTERVAL', '30'))
        }

        # 清理统计
        self.stats = {
            'last_cleanup_time': None,
            'total_cleanups': 0,
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': 0
        }

        logger.info("定期清理服务初始化完成", **self.config)

    async def start(self):
        """启动定期清理服务"""
        if not HAS_APSCHEDULER:
            logger.warning("APScheduler not available, cleanup service disabled")
            return

        if self.is_running:
            logger.warning("定期清理服务已在运行")
            return

        try:
            # 添加定期清理任务
            self.scheduler.add_job(
                self.run_full_cleanup,
                IntervalTrigger(minutes=self.config['cleanup_interval_minutes']),
                id='full_cleanup',
                name='完整清理任务',
                max_instances=1
            )

            # 添加缓存清理任务
            self.scheduler.add_job(
                self.run_cache_cleanup,
                IntervalTrigger(minutes=self.config['cache_cleanup_interval_minutes']),
                id='cache_cleanup',
                name='缓存清理任务',
                max_instances=1
            )

            # 添加每日深度清理任务
            self.scheduler.add_job(
                self.run_deep_cleanup,
                CronTrigger(hour=2, minute=0),  # 每天凌晨2点
                id='deep_cleanup',
                name='每日深度清理任务',
                max_instances=1
            )

            # 添加日志轮转任务
            self.scheduler.add_job(
                self.run_log_rotation,
                CronTrigger(hour=1, minute=0),  # 每天凌晨1点
                id='log_rotation',
                name='日志轮转任务',
                max_instances=1
            )

            self.scheduler.start()
            self.is_running = True

            logger.info("定期清理服务启动成功")

        except Exception as e:
            logger.error("定期清理服务启动失败", error=str(e))
            raise

    async def stop(self):
        """停止定期清理服务"""
        if not self.is_running:
            return

        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("定期清理服务已停止")
        except Exception as e:
            logger.error("停止定期清理服务失败", error=str(e))

    async def run_full_cleanup(self):
        """运行完整清理"""
        logger.info("开始完整清理")
        start_time = datetime.utcnow()

        try:
            cleanup_results = []

            # 1. 清理临时文件
            result = await self.cleanup_temp_files()
            cleanup_results.append(result)

            # 2. 清理过期缓存
            result = await self.cleanup_cache()
            cleanup_results.append(result)

            # 3. 清理旧的上传文件（如果数量过多）
            result = await self.cleanup_old_uploads()
            cleanup_results.append(result)

            # 4. 清理空目录
            result = await self.cleanup_empty_directories()
            cleanup_results.append(result)

            # 更新统计
            self.stats['last_cleanup_time'] = datetime.utcnow().isoformat()
            self.stats['total_cleanups'] += 1

            total_files = sum(r.get('files_deleted', 0) for r in cleanup_results)
            total_bytes = sum(r.get('bytes_freed', 0) for r in cleanup_results)

            self.stats['files_deleted'] += total_files
            self.stats['bytes_freed'] += total_bytes

            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                "完整清理完成",
                duration_seconds=duration,
                files_deleted=total_files,
                bytes_freed=total_bytes,
                results=cleanup_results
            )

        except Exception as e:
            self.stats['errors'] += 1
            logger.error("完整清理失败", error=str(e))

    async def run_cache_cleanup(self):
        """运行缓存清理"""
        logger.info("开始缓存清理")

        try:
            # 清理过期的文件缓存
            await cache_manager._cleanup_file_cache()
            logger.info("缓存清理完成")

        except Exception as e:
            logger.error("缓存清理失败", error=str(e))

    async def run_deep_cleanup(self):
        """运行深度清理（每日）"""
        logger.info("开始每日深度清理")
        start_time = datetime.utcnow()

        try:
            cleanup_results = []

            # 1. 清理过期的报告文件
            result = await self.cleanup_old_reports()
            cleanup_results.append(result)

            # 2. 清理过期的上传文件
            result = await self.cleanup_old_uploads(force=True)
            cleanup_results.append(result)

            # 3. 清理日志文件
            result = await self.cleanup_old_logs()
            cleanup_results.append(result)

            # 4. 压缩清理
            result = await self.compress_old_files()
            cleanup_results.append(result)

            duration = (datetime.utcnow() - start_time).total_seconds()
            total_files = sum(r.get('files_deleted', 0) for r in cleanup_results)
            total_bytes = sum(r.get('bytes_freed', 0) for r in cleanup_results)

            logger.info(
                "深度清理完成",
                duration_seconds=duration,
                files_deleted=total_files,
                bytes_freed=total_bytes,
                results=cleanup_results
            )

        except Exception as e:
            self.stats['errors'] += 1
            logger.error("深度清理失败", error=str(e))

    async def run_log_rotation(self):
        """运行日志轮转"""
        logger.info("开始日志轮转")

        try:
            log_dir = Path(os.getenv('LOG_DIR', './logs'))
            if not log_dir.exists():
                return

            rotated_count = 0
            for log_file in log_dir.glob('*.log'):
                if log_file.stat().st_size > 50 * 1024 * 1024:  # 50MB
                    # 重命名日志文件
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    rotated_file = log_file.with_suffix(f'.{timestamp}.log')
                    log_file.rename(rotated_file)
                    rotated_count += 1

            if rotated_count > 0:
                logger.info(f"日志轮转完成", rotated_files=rotated_count)

        except Exception as e:
            logger.error("日志轮转失败", error=str(e))

    async def cleanup_temp_files(self) -> Dict[str, Any]:
        """清理临时文件"""
        logger.debug("清理临时文件")

        result = {
            'operation': 'cleanup_temp_files',
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': []
        }

        try:
            temp_dirs = [
                Path('./temp'),
                Path('./cache/temp'),
                Path('/tmp/nanhai_system'),
            ]

            cutoff_time = datetime.utcnow() - timedelta(hours=self.config['temp_files_max_age_hours'])

            for temp_dir in temp_dirs:
                if not temp_dir.exists():
                    continue

                for temp_file in temp_dir.rglob('*'):
                    if temp_file.is_file():
                        try:
                            file_modified = datetime.utcfromtimestamp(temp_file.stat().st_mtime)
                            if file_modified < cutoff_time:
                                file_size = temp_file.stat().st_size
                                temp_file.unlink()
                                result['files_deleted'] += 1
                                result['bytes_freed'] += file_size

                        except Exception as e:
                            result['errors'].append(f"删除文件 {temp_file} 失败: {str(e)}")

        except Exception as e:
            result['errors'].append(f"清理临时文件失败: {str(e)}")

        return result

    async def cleanup_cache(self) -> Dict[str, Any]:
        """清理过期缓存"""
        logger.debug("清理过期缓存")

        result = {
            'operation': 'cleanup_cache',
            'files_deleted': 0,
            'bytes_freed': 0,
            'cache_cleared': False
        }

        try:
            # 清理文件缓存
            await cache_manager._cleanup_file_cache()
            result['cache_cleared'] = True

        except Exception as e:
            result['errors'] = [f"清理缓存失败: {str(e)}"]

        return result

    async def cleanup_old_uploads(self, force: bool = False) -> Dict[str, Any]:
        """清理旧的上传文件"""
        logger.debug("清理旧的上传文件", force=force)

        result = {
            'operation': 'cleanup_old_uploads',
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': []
        }

        try:
            uploads_dir = Path('./backend/uploads')
            if not uploads_dir.exists():
                return result

            upload_files = list(uploads_dir.glob('*.csv'))
            total_files = len(upload_files)

            # 根据配置决定清理策略
            if force or total_files > self.config['max_upload_files_count']:
                # 按修改时间排序，删除最旧的文件
                upload_files.sort(key=lambda f: f.stat().st_mtime)

                if force:
                    # 深度清理：删除超过指定天数的文件
                    cutoff_time = datetime.utcnow() - timedelta(days=self.config['old_uploads_max_age_days'])
                    files_to_delete = [
                        f for f in upload_files
                        if datetime.utcfromtimestamp(f.stat().st_mtime) < cutoff_time
                    ]
                else:
                    # 常规清理：保留最新的文件，删除超出限制的
                    keep_count = self.config['max_upload_files_count']
                    files_to_delete = upload_files[:-keep_count] if total_files > keep_count else []

                for file_path in files_to_delete:
                    try:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        result['files_deleted'] += 1
                        result['bytes_freed'] += file_size
                    except Exception as e:
                        result['errors'].append(f"删除文件 {file_path} 失败: {str(e)}")

        except Exception as e:
            result['errors'].append(f"清理上传文件失败: {str(e)}")

        return result

    async def cleanup_old_reports(self) -> Dict[str, Any]:
        """清理旧的报告文件"""
        logger.debug("清理旧的报告文件")

        result = {
            'operation': 'cleanup_old_reports',
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': []
        }

        try:
            reports_dir = Path('./backend/reports')
            if not reports_dir.exists():
                return result

            cutoff_time = datetime.utcnow() - timedelta(days=self.config['old_reports_max_age_days'])

            for report_file in reports_dir.glob('*.docx'):
                try:
                    file_modified = datetime.utcfromtimestamp(report_file.stat().st_mtime)
                    if file_modified < cutoff_time:
                        file_size = report_file.stat().st_size
                        report_file.unlink()
                        result['files_deleted'] += 1
                        result['bytes_freed'] += file_size

                except Exception as e:
                    result['errors'].append(f"删除报告 {report_file} 失败: {str(e)}")

        except Exception as e:
            result['errors'].append(f"清理报告文件失败: {str(e)}")

        return result

    async def cleanup_old_logs(self) -> Dict[str, Any]:
        """清理旧的日志文件"""
        logger.debug("清理旧的日志文件")

        result = {
            'operation': 'cleanup_old_logs',
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': []
        }

        try:
            log_dir = Path(os.getenv('LOG_DIR', './logs'))
            if not log_dir.exists():
                return result

            cutoff_time = datetime.utcnow() - timedelta(days=self.config['log_files_max_age_days'])

            # 清理旧的轮转日志文件
            for log_file in log_dir.glob('*.*.log'):  # 轮转的日志文件
                try:
                    file_modified = datetime.utcfromtimestamp(log_file.stat().st_mtime)
                    if file_modified < cutoff_time:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        result['files_deleted'] += 1
                        result['bytes_freed'] += file_size

                except Exception as e:
                    result['errors'].append(f"删除日志 {log_file} 失败: {str(e)}")

        except Exception as e:
            result['errors'].append(f"清理日志文件失败: {str(e)}")

        return result

    async def cleanup_empty_directories(self) -> Dict[str, Any]:
        """清理空目录"""
        logger.debug("清理空目录")

        result = {
            'operation': 'cleanup_empty_directories',
            'directories_deleted': 0,
            'errors': []
        }

        try:
            base_dirs = [
                Path('./cache'),
                Path('./temp'),
                Path('./logs'),
            ]

            for base_dir in base_dirs:
                if not base_dir.exists():
                    continue

                # 自底向上遍历，清理空目录
                for dir_path in sorted(base_dir.rglob('*'), key=lambda p: str(p), reverse=True):
                    if dir_path.is_dir():
                        try:
                            if not any(dir_path.iterdir()):  # 目录为空
                                dir_path.rmdir()
                                result['directories_deleted'] += 1
                        except Exception as e:
                            result['errors'].append(f"删除目录 {dir_path} 失败: {str(e)}")

        except Exception as e:
            result['errors'].append(f"清理空目录失败: {str(e)}")

        return result

    async def compress_old_files(self) -> Dict[str, Any]:
        """压缩旧文件"""
        logger.debug("压缩旧文件")

        result = {
            'operation': 'compress_old_files',
            'files_compressed': 0,
            'bytes_saved': 0,
            'errors': []
        }

        try:
            import gzip

            # 压缩超过7天的日志文件
            log_dir = Path(os.getenv('LOG_DIR', './logs'))
            if log_dir.exists():
                cutoff_time = datetime.utcnow() - timedelta(days=7)

                for log_file in log_dir.glob('*.log'):
                    if log_file.name.endswith('.gz'):
                        continue  # 已压缩

                    try:
                        file_modified = datetime.utcfromtimestamp(log_file.stat().st_mtime)
                        if file_modified < cutoff_time:
                            # 压缩文件
                            original_size = log_file.stat().st_size
                            compressed_file = log_file.with_suffix('.log.gz')

                            with open(log_file, 'rb') as f_in:
                                with gzip.open(compressed_file, 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)

                            compressed_size = compressed_file.stat().st_size
                            log_file.unlink()  # 删除原文件

                            result['files_compressed'] += 1
                            result['bytes_saved'] += (original_size - compressed_size)

                    except Exception as e:
                        result['errors'].append(f"压缩文件 {log_file} 失败: {str(e)}")

        except Exception as e:
            result['errors'].append(f"压缩文件失败: {str(e)}")

        return result

    async def manual_cleanup(self, operation: str = "full") -> Dict[str, Any]:
        """手动触发清理"""
        logger.info("手动触发清理", operation=operation)

        if operation == "full":
            await self.run_full_cleanup()
        elif operation == "deep":
            await self.run_deep_cleanup()
        elif operation == "cache":
            await self.run_cache_cleanup()
        else:
            raise ValueError(f"不支持的清理操作: {operation}")

        return {"success": True, "operation": operation}

    def get_stats(self) -> Dict[str, Any]:
        """获取清理统计信息"""
        return {
            **self.stats,
            'config': self.config,
            'is_running': self.is_running,
            'scheduled_jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }

# 全局清理服务实例
cleanup_service = CleanupService()