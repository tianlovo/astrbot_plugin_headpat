"""
GIF 缓存服务核心模块

提供 GIF 资源的缓存管理功能，遵守 AstrBot 大文件存储规范。
缓存目录: data/plugin_data/{plugin_name}/gif_cache/
"""

import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

from astrbot.api import logger

try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
except ImportError:
    # 兼容旧版本
    get_astrbot_data_path = None

from .exceptions import CacheError, CacheNotFoundError, CacheExpiredError, CacheStorageError


@dataclass
class CacheEntry:
    """缓存条目元数据"""
    user_id: str
    file_path: str
    avatar_hash: Optional[str]
    created_at: float
    accessed_at: float
    size: int


class GifCacheService:
    """GIF 缓存服务类
    
    提供 GIF 资源的缓存管理功能，包括：
    - 存储：将生成的 GIF 存储到缓存目录
    - 读取：优先返回缓存的 GIF
    - 更新：支持刷新和替换缓存
    - 清理：支持过期清理、LRU清理、手动清理
    
    存储路径遵守 AstrBot 规范：
    data/plugin_data/{plugin_name}/gif_cache/
    """
    
    def __init__(self, plugin_name: str, config: dict = None):
        """初始化缓存服务
        
        Args:
            plugin_name: 插件名称，用于构建缓存路径
            config: 配置字典，包含缓存相关配置
        """
        self.plugin_name = plugin_name
        self.config = config or {}
        
        # 缓存配置
        self.enabled = self.config.get("cache_enabled", True)
        self.ttl = self.config.get("cache_ttl", 3600)  # 默认1小时
        self.max_size = self.config.get("max_cache_size", 100)  # 默认100个文件
        self.auto_cleanup = self.config.get("auto_cleanup", True)
        self.cleanup_interval = self.config.get("cleanup_interval", 3600)  # 默认1小时
        
        # 缓存目录
        self.cache_dir = self._get_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 元数据文件
        self.metadata_file = self.cache_dir / ".cache_metadata.json"
        self._metadata: dict[str, CacheEntry] = {}
        self._load_metadata()
        
        # 自动清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"[{plugin_name}] GIF缓存服务初始化完成，缓存目录: {self.cache_dir}")
    
    def _get_cache_dir(self) -> Path:
        """获取缓存目录路径，遵守 Astr Bot 存储规范
        
        Returns:
            缓存目录路径: data/plugin_data/{plugin_name}/gif_cache/
        """
        if get_astrbot_data_path:
            # AstrBot >= 4.9.2
            base_path = Path(get_astrbot_data_path())
        else:
            # 兼容旧版本，使用插件目录
            base_path = Path(__file__).resolve().parent.parent.parent
        
        cache_dir = base_path / "plugin_data" / self.plugin_name / "gif_cache"
        return cache_dir
    
    def _load_metadata(self):
        """加载缓存元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        self._metadata[key] = CacheEntry(**value)
            except Exception as e:
                logger.warning(f"[{self.plugin_name}] 加载缓存元数据失败: {e}")
                self._metadata = {}
    
    def _save_metadata(self):
        """保存缓存元数据"""
        try:
            data = {k: asdict(v) for k, v in self._metadata.items()}
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[{self.plugin_name}] 保存缓存元数据失败: {e}")
    
    def _generate_cache_key(self, user_id: str, avatar_hash: Optional[str] = None) -> str:
        """生成缓存键
        
        Args:
            user_id: 用户ID
            avatar_hash: 头像哈希（可选）
            
        Returns:
            缓存键字符串
        """
        if avatar_hash:
            return f"{user_id}_{avatar_hash}"
        return user_id
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """获取缓存文件路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            缓存文件路径
        """
        # 使用哈希作为文件名的一部分，避免特殊字符
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:8]
        return self.cache_dir / f"headpat_{cache_key[:20]}_{key_hash}.gif"
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查缓存是否过期
        
        Args:
            entry: 缓存条目
            
        Returns:
            是否过期
        """
        if self.ttl <= 0:
            return False  # TTL <= 0 表示永不过期
        return time.time() - entry.accessed_at > self.ttl
    
    def _cleanup_lru(self, needed_space: int = 1) -> int:
        """LRU 清理策略
        
        当缓存达到上限时，清理最久未访问的缓存
        
        Args:
            needed_space: 需要的空间（文件数量）
            
        Returns:
            清理的文件数量
        """
        if len(self._metadata) + needed_space <= self.max_size:
            return 0
        
        # 按访问时间排序，清理最久未访问的
        sorted_entries = sorted(
            self._metadata.items(),
            key=lambda x: x[1].accessed_at
        )
        
        to_remove = len(self._metadata) + needed_space - self.max_size
        removed = 0
        
        for key, entry in sorted_entries[:to_remove]:
            try:
                file_path = Path(entry.file_path)
                if file_path.exists():
                    file_path.unlink()
                del self._metadata[key]
                removed += 1
            except Exception as e:
                logger.warning(f"[{self.plugin_name}] LRU清理失败: {e}")
        
        if removed > 0:
            self._save_metadata()
            logger.info(f"[{self.plugin_name}] LRU清理完成，清理了 {removed} 个文件")
        
        return removed
    
    def get(self, user_id: str, avatar_hash: Optional[str] = None) -> Optional[Path]:
        """获取缓存的 GIF
        
        Args:
            user_id: 用户ID
            avatar_hash: 头像哈希（可选）
            
        Returns:
            缓存文件路径，如果不存在或已过期则返回 None
        """
        if not self.enabled:
            return None
        
        cache_key = self._generate_cache_key(user_id, avatar_hash)
        
        if cache_key not in self._metadata:
            return None
        
        entry = self._metadata[cache_key]
        
        # 检查是否过期
        if self._is_expired(entry):
            logger.debug(f"[{self.plugin_name}] 缓存已过期: {cache_key}")
            self.delete(user_id, avatar_hash)
            return None
        
        # 检查文件是否存在
        file_path = Path(entry.file_path)
        if not file_path.exists():
            logger.warning(f"[{self.plugin_name}] 缓存文件不存在: {file_path}")
            self.delete(user_id, avatar_hash)
            return None
        
        # 更新访问时间
        entry.accessed_at = time.time()
        self._save_metadata()
        
        logger.debug(f"[{self.plugin_name}] 缓存命中: {cache_key}")
        return file_path
    
    def set(self, user_id: str, gif_path: Path, avatar_hash: Optional[str] = None) -> Path:
        """存储 GIF 到缓存
        
        Args:
            user_id: 用户ID
            gif_path: GIF 文件路径
            avatar_hash: 头像哈希（可选）
            
        Returns:
            缓存文件路径
            
        Raises:
            CacheStorageError: 存储失败时抛出
        """
        if not self.enabled:
            return gif_path
        
        cache_key = self._generate_cache_key(user_id, avatar_hash)
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            # LRU 清理
            self._cleanup_lru(needed_space=1)
            
            # 复制文件到缓存目录
            shutil.copy2(gif_path, cache_file)
            
            # 获取文件大小
            file_size = cache_file.stat().st_size
            
            # 更新元数据
            now = time.time()
            self._metadata[cache_key] = CacheEntry(
                user_id=user_id,
                file_path=str(cache_file),
                avatar_hash=avatar_hash,
                created_at=now,
                accessed_at=now,
                size=file_size
            )
            self._save_metadata()
            
            logger.debug(f"[{self.plugin_name}] 缓存已存储: {cache_key}")
            return cache_file
            
        except Exception as e:
            logger.error(f"[{self.plugin_name}] 缓存存储失败: {e}")
            raise CacheStorageError(f"缓存存储失败: {e}")
    
    def delete(self, user_id: Optional[str] = None, avatar_hash: Optional[str] = None) -> bool:
        """删除缓存
        
        Args:
            user_id: 用户ID，为 None 时删除所有缓存
            avatar_hash: 头像哈希（可选）
            
        Returns:
            是否成功删除
        """
        if user_id is None:
            # 删除所有缓存
            return self.clear_all() > 0
        
        cache_key = self._generate_cache_key(user_id, avatar_hash)
        
        if cache_key not in self._metadata:
            return False
        
        entry = self._metadata[cache_key]
        
        try:
            file_path = Path(entry.file_path)
            if file_path.exists():
                file_path.unlink()
            
            del self._metadata[cache_key]
            self._save_metadata()
            
            logger.debug(f"[{self.plugin_name}] 缓存已删除: {cache_key}")
            return True
            
        except Exception as e:
            logger.warning(f"[{self.plugin_name}] 缓存删除失败: {e}")
            return False
    
    def clear_expired(self) -> int:
        """清理过期缓存
        
        Returns:
            清理的文件数量
        """
        if self.ttl <= 0:
            return 0  # TTL <= 0 表示永不过期
        
        expired_keys = [
            key for key, entry in self._metadata.items()
            if self._is_expired(entry)
        ]
        
        removed = 0
        for key in expired_keys:
            try:
                entry = self._metadata[key]
                file_path = Path(entry.file_path)
                if file_path.exists():
                    file_path.unlink()
                del self._metadata[key]
                removed += 1
            except Exception as e:
                logger.warning(f"[{self.plugin_name}] 清理过期缓存失败: {e}")
        
        if removed > 0:
            self._save_metadata()
            logger.info(f"[{self.plugin_name}] 过期缓存清理完成，清理了 {removed} 个文件")
        
        return removed
    
    def clear_all(self) -> int:
        """清理所有缓存
        
        Returns:
            清理的文件数量
        """
        count = len(self._metadata)
        
        try:
            # 删除所有缓存文件
            for entry in self._metadata.values():
                file_path = Path(entry.file_path)
                if file_path.exists():
                    file_path.unlink()
            
            # 清空元数据
            self._metadata.clear()
            self._save_metadata()
            
            logger.info(f"[{self.plugin_name}] 所有缓存已清理，共 {count} 个文件")
            return count
            
        except Exception as e:
            logger.error(f"[{self.plugin_name}] 清理所有缓存失败: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        total_size = sum(entry.size for entry in self._metadata.values())
        expired_count = sum(1 for entry in self._metadata.values() if self._is_expired(entry))
        
        return {
            "enabled": self.enabled,
            "cache_dir": str(self.cache_dir),
            "total_files": len(self._metadata),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "expired_files": expired_count,
            "ttl_seconds": self.ttl,
            "max_size": self.max_size,
            "auto_cleanup": self.auto_cleanup,
            "cleanup_interval_seconds": self.cleanup_interval,
        }
    
    async def _cleanup_loop(self):
        """自动清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self.clear_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"[{self.plugin_name}] 自动清理失败: {e}")
    
    def start_auto_cleanup(self):
        """启动自动清理任务"""
        if not self.auto_cleanup or not self.enabled:
            return
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(f"[{self.plugin_name}] 自动清理任务已启动，间隔: {self.cleanup_interval}秒")
    
    def stop_auto_cleanup(self):
        """停止自动清理任务"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info(f"[{self.plugin_name}] 自动清理任务已停止")
