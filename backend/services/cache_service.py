"""
缓存服务
提供内存缓存、Redis缓存、文件缓存等功能
用于优化数据库查询、API响应、文件处理等性能
"""
import os
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Union
from pathlib import Path
import asyncio
import aiofiles
from cachetools import TTLCache, LRUCache
import threading
from services.logger_config import get_logger

logger = get_logger("cache")

class CacheManager:
    """缓存管理器 - 支持多级缓存"""

    def __init__(self):
        # 内存缓存配置
        self.memory_cache_size = int(os.getenv('CACHE_MEMORY_SIZE', '1000'))
        self.memory_cache_ttl = int(os.getenv('CACHE_MEMORY_TTL', '300'))  # 5分钟

        # 文件缓存配置
        self.file_cache_dir = Path(os.getenv('CACHE_FILE_DIR', './cache'))
        self.file_cache_ttl = int(os.getenv('CACHE_FILE_TTL', '3600'))  # 1小时

        # 初始化缓存
        self._setup_caches()
        self._lock = threading.RLock()
        self._cleanup_task_started = True

        logger.info(
            "缓存管理器初始化完成",
            memory_size=self.memory_cache_size,
            memory_ttl=self.memory_cache_ttl,
            file_cache_dir=str(self.file_cache_dir),
            file_ttl=self.file_cache_ttl
        )

    def _setup_caches(self):
        """初始化各类缓存"""
        # 1. 内存缓存 - TTL缓存（自动过期）
        self.memory_cache = TTLCache(
            maxsize=self.memory_cache_size,
            ttl=self.memory_cache_ttl
        )

        # 2. API响应缓存 - LRU缓存
        self.api_cache = LRUCache(maxsize=500)

        # 3. 数据库查询缓存
        self.db_cache = TTLCache(maxsize=200, ttl=60)  # 1分钟

        # 4. 文件处理结果缓存
        self.file_processing_cache = TTLCache(maxsize=100, ttl=1800)  # 30分钟

        # 创建文件缓存目录
        self.file_cache_dir.mkdir(parents=True, exist_ok=True)

        # 定期清理任务
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """启动定期清理任务"""
        async def cleanup_task():
            while True:
                try:
                    await asyncio.sleep(300)  # 每5分钟清理一次
                    await self._cleanup_file_cache()
                    self._log_cache_stats()
                except Exception as e:
                    logger.error("缓存清理任务错误", error=str(e))

        # 检查是否有运行中的事件循环
        try:
            asyncio.get_running_loop()
            # 在后台运行清理任务
            asyncio.create_task(cleanup_task())
        except RuntimeError:
            # 没有运行中的事件循环，延迟到首次调用时启动
            self._cleanup_task_started = False

    async def get(self, key: str, cache_type: str = "memory") -> Optional[Any]:
        """获取缓存数据"""
        try:
            cache_key = self._generate_cache_key(key)

            if cache_type == "memory":
                with self._lock:
                    value = self.memory_cache.get(cache_key)
                if value is not None:
                    logger.debug(f"内存缓存命中", key=cache_key)
                    return value

            elif cache_type == "api":
                with self._lock:
                    value = self.api_cache.get(cache_key)
                if value is not None:
                    logger.debug(f"API缓存命中", key=cache_key)
                    return value

            elif cache_type == "db":
                with self._lock:
                    value = self.db_cache.get(cache_key)
                if value is not None:
                    logger.debug(f"数据库缓存命中", key=cache_key)
                    return value

            elif cache_type == "file":
                value = await self._get_file_cache(cache_key)
                if value is not None:
                    logger.debug(f"文件缓存命中", key=cache_key)
                    return value

            elif cache_type == "file_processing":
                with self._lock:
                    value = self.file_processing_cache.get(cache_key)
                if value is not None:
                    logger.debug(f"文件处理缓存命中", key=cache_key)
                    return value

            logger.debug(f"缓存未命中", key=cache_key, cache_type=cache_type)
            return None

        except Exception as e:
            logger.error(f"获取缓存失败", key=key, cache_type=cache_type, error=str(e))
            return None

    async def set(self, key: str, value: Any, cache_type: str = "memory", ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        try:
            cache_key = self._generate_cache_key(key)

            if cache_type == "memory":
                with self._lock:
                    self.memory_cache[cache_key] = value
                logger.debug(f"设置内存缓存", key=cache_key)

            elif cache_type == "api":
                with self._lock:
                    self.api_cache[cache_key] = value
                logger.debug(f"设置API缓存", key=cache_key)

            elif cache_type == "db":
                with self._lock:
                    self.db_cache[cache_key] = value
                logger.debug(f"设置数据库缓存", key=cache_key)

            elif cache_type == "file":
                await self._set_file_cache(cache_key, value, ttl)
                logger.debug(f"设置文件缓存", key=cache_key)

            elif cache_type == "file_processing":
                with self._lock:
                    self.file_processing_cache[cache_key] = value
                logger.debug(f"设置文件处理缓存", key=cache_key)

            return True

        except Exception as e:
            logger.error(f"设置缓存失败", key=key, cache_type=cache_type, error=str(e))
            return False

    async def delete(self, key: str, cache_type: str = "memory") -> bool:
        """删除缓存数据"""
        try:
            cache_key = self._generate_cache_key(key)

            if cache_type == "memory":
                with self._lock:
                    self.memory_cache.pop(cache_key, None)
            elif cache_type == "api":
                with self._lock:
                    self.api_cache.pop(cache_key, None)
            elif cache_type == "db":
                with self._lock:
                    self.db_cache.pop(cache_key, None)
            elif cache_type == "file":
                await self._delete_file_cache(cache_key)
            elif cache_type == "file_processing":
                with self._lock:
                    self.file_processing_cache.pop(cache_key, None)

            logger.debug(f"删除缓存", key=cache_key, cache_type=cache_type)
            return True

        except Exception as e:
            logger.error(f"删除缓存失败", key=key, cache_type=cache_type, error=str(e))
            return False

    async def clear(self, cache_type: str = "all") -> bool:
        """清空缓存"""
        try:
            if cache_type == "all" or cache_type == "memory":
                with self._lock:
                    self.memory_cache.clear()
                logger.info("清空内存缓存")

            if cache_type == "all" or cache_type == "api":
                with self._lock:
                    self.api_cache.clear()
                logger.info("清空API缓存")

            if cache_type == "all" or cache_type == "db":
                with self._lock:
                    self.db_cache.clear()
                logger.info("清空数据库缓存")

            if cache_type == "all" or cache_type == "file":
                await self._clear_file_cache()
                logger.info("清空文件缓存")

            if cache_type == "all" or cache_type == "file_processing":
                with self._lock:
                    self.file_processing_cache.clear()
                logger.info("清空文件处理缓存")

            return True

        except Exception as e:
            logger.error(f"清空缓存失败", cache_type=cache_type, error=str(e))
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            return {
                "memory_cache": {
                    "size": len(self.memory_cache),
                    "maxsize": self.memory_cache.maxsize,
                    "hits": getattr(self.memory_cache, 'hits', 0),
                    "misses": getattr(self.memory_cache, 'misses', 0)
                },
                "api_cache": {
                    "size": len(self.api_cache),
                    "maxsize": self.api_cache.maxsize,
                    "hits": getattr(self.api_cache, 'hits', 0),
                    "misses": getattr(self.api_cache, 'misses', 0)
                },
                "db_cache": {
                    "size": len(self.db_cache),
                    "maxsize": self.db_cache.maxsize,
                },
                "file_processing_cache": {
                    "size": len(self.file_processing_cache),
                    "maxsize": self.file_processing_cache.maxsize,
                }
            }

    def _generate_cache_key(self, key: str) -> str:
        """生成缓存键"""
        if isinstance(key, str) and len(key) < 100:
            return key
        # 对于长键使用哈希
        return hashlib.md5(str(key).encode()).hexdigest()

    async def _get_file_cache(self, cache_key: str) -> Optional[Any]:
        """从文件缓存获取数据"""
        cache_file = self.file_cache_dir / f"{cache_key}.cache"
        meta_file = self.file_cache_dir / f"{cache_key}.meta"

        try:
            if not cache_file.exists() or not meta_file.exists():
                return None

            # 检查是否过期
            async with aiofiles.open(meta_file, 'r') as f:
                meta_content = await f.read()
                meta = json.loads(meta_content)

            expire_time = datetime.fromisoformat(meta['expire_time'])
            if datetime.utcnow() > expire_time:
                # 已过期，删除文件
                await self._delete_file_cache(cache_key)
                return None

            # 读取缓存数据
            async with aiofiles.open(cache_file, 'rb') as f:
                content = await f.read()
                return pickle.loads(content)

        except Exception as e:
            logger.warning(f"读取文件缓存失败", cache_key=cache_key, error=str(e))
            # 清理可能损坏的缓存文件
            await self._delete_file_cache(cache_key)
            return None

    async def _set_file_cache(self, cache_key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置文件缓存"""
        cache_file = self.file_cache_dir / f"{cache_key}.cache"
        meta_file = self.file_cache_dir / f"{cache_key}.meta"

        try:
            # 设置过期时间
            if ttl is None:
                ttl = self.file_cache_ttl
            expire_time = datetime.utcnow() + timedelta(seconds=ttl)

            # 写入数据文件
            async with aiofiles.open(cache_file, 'wb') as f:
                await f.write(pickle.dumps(value))

            # 写入元数据文件
            meta = {
                'created_time': datetime.utcnow().isoformat(),
                'expire_time': expire_time.isoformat(),
                'ttl': ttl
            }
            async with aiofiles.open(meta_file, 'w') as f:
                await f.write(json.dumps(meta))

            return True

        except Exception as e:
            logger.error(f"设置文件缓存失败", cache_key=cache_key, error=str(e))
            return False

    async def _delete_file_cache(self, cache_key: str) -> bool:
        """删除文件缓存"""
        cache_file = self.file_cache_dir / f"{cache_key}.cache"
        meta_file = self.file_cache_dir / f"{cache_key}.meta"

        try:
            if cache_file.exists():
                cache_file.unlink()
            if meta_file.exists():
                meta_file.unlink()
            return True
        except Exception as e:
            logger.warning(f"删除文件缓存失败", cache_key=cache_key, error=str(e))
            return False

    async def _clear_file_cache(self) -> bool:
        """清空文件缓存"""
        try:
            for cache_file in self.file_cache_dir.glob("*.cache"):
                cache_file.unlink()
            for meta_file in self.file_cache_dir.glob("*.meta"):
                meta_file.unlink()
            return True
        except Exception as e:
            logger.error("清空文件缓存失败", error=str(e))
            return False

    async def _cleanup_file_cache(self):
        """清理过期的文件缓存"""
        try:
            current_time = datetime.utcnow()
            cleaned_count = 0

            for meta_file in self.file_cache_dir.glob("*.meta"):
                try:
                    async with aiofiles.open(meta_file, 'r') as f:
                        meta_content = await f.read()
                        meta = json.loads(meta_content)

                    expire_time = datetime.fromisoformat(meta['expire_time'])
                    if current_time > expire_time:
                        # 过期，删除相关文件
                        cache_key = meta_file.stem
                        await self._delete_file_cache(cache_key)
                        cleaned_count += 1

                except Exception as e:
                    logger.warning(f"清理文件缓存条目失败", file=str(meta_file), error=str(e))

            if cleaned_count > 0:
                logger.info(f"文件缓存清理完成", cleaned_count=cleaned_count)

        except Exception as e:
            logger.error("文件缓存清理失败", error=str(e))

    def _log_cache_stats(self):
        """记录缓存统计信息"""
        stats = self.get_stats()
        logger.info("缓存统计信息", **stats)

# 全局缓存管理器实例
cache_manager = CacheManager()

# 缓存装饰器
def cached(cache_type: str = "memory", ttl: Optional[int] = None, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # 尝试从缓存获取
            cached_result = await cache_manager.get(cache_key, cache_type)
            if cached_result is not None:
                return cached_result

            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, cache_type, ttl)
            return result

        def sync_wrapper(*args, **kwargs):
            # 同步版本的缓存装饰器（简化版本）
            cache_key = f"{key_prefix}{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # 只支持内存缓存的同步版本
            with cache_manager._lock:
                cached_result = cache_manager.memory_cache.get(cache_key)

            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)

            with cache_manager._lock:
                cache_manager.memory_cache[cache_key] = result

            return result

        # 根据函数类型选择包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator