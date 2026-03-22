"""
GIF 缓存服务模块

提供 GIF 资源的缓存管理功能，包括存储、读取、更新和清理机制。
遵守 AstrBot 大文件存储规范。
"""

from .exceptions import CacheError, CacheExpiredError, CacheNotFoundError
from .gif_cache import GifCacheService

__all__ = [
    "GifCacheService",
    "CacheError",
    "CacheNotFoundError",
    "CacheExpiredError",
]

__version__ = "1.0.0"
