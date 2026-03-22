"""
GIF 缓存服务异常类
"""


class CacheError(Exception):
    """缓存操作基础异常"""

    pass


class CacheNotFoundError(CacheError):
    """缓存不存在异常"""

    pass


class CacheExpiredError(CacheError):
    """缓存已过期异常"""

    pass


class CacheStorageError(CacheError):
    """缓存存储异常"""

    pass
