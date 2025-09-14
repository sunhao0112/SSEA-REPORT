"""
生产级日志配置服务
提供结构化日志记录、日志轮转、性能监控、错误跟踪等功能
"""
import os
import sys
import logging
import logging.handlers
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import traceback
from contextvars import ContextVar
from functools import wraps

# 上下文变量用于跟踪请求ID
request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

class StructuredFormatter(logging.Formatter):
    """结构化日志格式器"""

    def format(self, record):
        # 基础日志信息
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # 添加请求ID（如果存在）
        request_id = request_id_context.get()
        if request_id:
            log_entry['request_id'] = request_id

        # 添加异常信息
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        # 添加自定义字段
        if hasattr(record, 'extra_data'):
            log_entry['extra'] = record.extra_data

        return json.dumps(log_entry, ensure_ascii=False)

class ColoredConsoleFormatter(logging.Formatter):
    """彩色控制台输出格式器"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        # 获取颜色
        color = self.COLORS.get(record.levelname, self.RESET)

        # 格式化时间
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]

        # 构建日志消息
        message = f"{color}[{timestamp}] {record.levelname:8s} {record.name:20s} | {record.getMessage()}{self.RESET}"

        # 添加请求ID
        request_id = request_id_context.get()
        if request_id:
            message = f"{color}[{request_id[:8]}] {message[len(color):]}"

        return message

class LoggerConfig:
    """日志配置管理器"""

    def __init__(self, app_name: str = "nanhai_system"):
        self.app_name = app_name
        self.log_dir = Path(os.getenv('LOG_DIR', './logs'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.environment = os.getenv('ENVIRONMENT', 'development').lower()

        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 配置根日志器
        self._setup_root_logger()

    def _setup_root_logger(self):
        """设置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level))

        # 清除现有的处理器
        root_logger.handlers.clear()

        # 添加处理器
        if self.environment == 'production':
            self._add_production_handlers(root_logger)
        else:
            self._add_development_handlers(root_logger)

    def _add_production_handlers(self, logger: logging.Logger):
        """生产环境处理器"""
        # 1. 应用日志文件（结构化JSON）
        app_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / f'{self.app_name}.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        app_handler.setFormatter(StructuredFormatter())
        app_handler.setLevel(logging.INFO)
        logger.addHandler(app_handler)

        # 2. 错误日志文件（只记录ERROR及以上）
        error_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / f'{self.app_name}.error.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        error_handler.setFormatter(StructuredFormatter())
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)

        # 3. 控制台输出（简化版）
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)

    def _add_development_handlers(self, logger: logging.Logger):
        """开发环境处理器"""
        # 1. 彩色控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredConsoleFormatter())
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

        # 2. 开发日志文件
        dev_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / f'{self.app_name}.dev.log',
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        dev_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s'
        )
        dev_handler.setFormatter(dev_formatter)
        dev_handler.setLevel(logging.DEBUG)
        logger.addHandler(dev_handler)

class ApplicationLogger:
    """应用程序日志器"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def debug(self, message: str, **extra):
        """调试日志"""
        self._log(logging.DEBUG, message, extra)

    def info(self, message: str, **extra):
        """信息日志"""
        self._log(logging.INFO, message, extra)

    def warning(self, message: str, **extra):
        """警告日志"""
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, **extra):
        """错误日志"""
        self._log(logging.ERROR, message, extra)

    def critical(self, message: str, **extra):
        """严重错误日志"""
        self._log(logging.CRITICAL, message, extra)

    def _log(self, level: int, message: str, extra: Dict[str, Any]):
        """内部日志记录方法"""
        if extra:
            # 创建一个带有额外数据的日志记录
            record = self.logger.makeRecord(
                name=self.logger.name,
                level=level,
                fn='',
                lno=0,
                msg=message,
                args=(),
                exc_info=None
            )
            record.extra_data = extra
            self.logger.handle(record)
        else:
            self.logger.log(level, message)

# 性能监控装饰器
def log_performance(logger: ApplicationLogger = None):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            func_logger = logger or ApplicationLogger(f"performance.{func.__module__}.{func.__name__}")

            try:
                result = await func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds()

                func_logger.info(
                    f"Function {func.__name__} completed successfully",
                    duration_seconds=duration,
                    function=func.__name__,
                    module=func.__module__
                )
                return result

            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                func_logger.error(
                    f"Function {func.__name__} failed with error: {str(e)}",
                    duration_seconds=duration,
                    function=func.__name__,
                    module=func.__module__,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            func_logger = logger or ApplicationLogger(f"performance.{func.__module__}.{func.__name__}")

            try:
                result = func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds()

                func_logger.info(
                    f"Function {func.__name__} completed successfully",
                    duration_seconds=duration,
                    function=func.__name__,
                    module=func.__module__
                )
                return result

            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                func_logger.error(
                    f"Function {func.__name__} failed with error: {str(e)}",
                    duration_seconds=duration,
                    function=func.__name__,
                    module=func.__module__,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise

        # 根据函数类型选择包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

# 全局日志器实例
logger_config = LoggerConfig()

# 创建各模块的日志器
system_logger = ApplicationLogger("system")
security_logger = ApplicationLogger("security")
api_logger = ApplicationLogger("api")
database_logger = ApplicationLogger("database")
file_logger = ApplicationLogger("file")
performance_logger = ApplicationLogger("performance")

def get_logger(name: str) -> ApplicationLogger:
    """获取指定名称的日志器"""
    return ApplicationLogger(name)

def set_request_id(request_id: str):
    """设置当前请求的ID"""
    request_id_context.set(request_id)

def get_request_id() -> Optional[str]:
    """获取当前请求的ID"""
    return request_id_context.get()

# 日志统计
class LogStats:
    """日志统计信息"""

    def __init__(self):
        self.stats = {
            'total_requests': 0,
            'error_count': 0,
            'warning_count': 0,
            'last_error': None,
            'start_time': datetime.utcnow()
        }

    def record_request(self):
        """记录请求"""
        self.stats['total_requests'] += 1

    def record_error(self, error_message: str):
        """记录错误"""
        self.stats['error_count'] += 1
        self.stats['last_error'] = {
            'message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }

    def record_warning(self):
        """记录警告"""
        self.stats['warning_count'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = datetime.utcnow() - self.stats['start_time']
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'uptime_formatted': str(uptime)
        }

# 全局统计实例
log_stats = LogStats()