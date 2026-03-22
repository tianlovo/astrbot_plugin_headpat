"""
GIF 缓存服务单元测试

测试覆盖：
- 缓存存储
- 缓存读取
- 缓存过期（TTL）
- 缓存清理
- LRU 策略
- 自动清理
"""

import asyncio
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service import GifCacheService, CacheStorageError


class TestGifCacheService(unittest.TestCase):
    """GIF 缓存服务测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 配置
        self.config = {
            "cache_enabled": True,
            "cache_ttl": 3600,
            "max_cache_size": 5,
            "auto_cleanup": False,
            "cleanup_interval": 3600,
        }
        
        # 初始化缓存服务（使用临时目录）
        self.cache = GifCacheService("test_plugin", self.config)
        # 替换缓存目录为临时目录
        self.original_cache_dir = self.cache.cache_dir
        self.cache.cache_dir = Path(self.temp_dir)
        self.cache.metadata_file = self.cache.cache_dir / ".cache_metadata.json"
        self.cache.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache._metadata = {}
    
    def tearDown(self):
        """测试后清理"""
        # 停止自动清理
        self.cache.stop_auto_cleanup()
        
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_gif(self, content: bytes = b"test_gif_content") -> Path:
        """创建测试 GIF 文件"""
        test_file = Path(self.temp_dir) / f"test_{time.time()}.gif"
        test_file.write_bytes(content)
        return test_file
    
    def test_cache_storage(self):
        """测试缓存存储"""
        # 创建测试文件
        test_file = self._create_test_gif()
        
        # 存储缓存
        cache_path = self.cache.set("user123", test_file)
        
        # 验证缓存文件存在
        self.assertTrue(cache_path.exists())
        
        # 验证元数据
        self.assertIn("user123", self.cache._metadata)
        self.assertEqual(self.cache._metadata["user123"].user_id, "user123")
    
    def test_cache_retrieval(self):
        """测试缓存读取"""
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user456", test_file)
        
        # 读取缓存
        cached_path = self.cache.get("user456")
        
        # 验证缓存命中
        self.assertIsNotNone(cached_path)
        self.assertTrue(cached_path.exists())
    
    def test_cache_miss(self):
        """测试缓存未命中"""
        # 读取不存在的缓存
        cached_path = self.cache.get("nonexistent_user")
        
        # 验证返回 None
        self.assertIsNone(cached_path)
    
    def test_cache_expiration(self):
        """测试缓存过期（TTL）"""
        # 设置短 TTL
        self.cache.ttl = 1  # 1秒过期
        
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user789", test_file)
        
        # 立即读取，应该命中
        cached_path = self.cache.get("user789")
        self.assertIsNotNone(cached_path)
        
        # 等待过期
        time.sleep(2)
        
        # 再次读取，应该过期
        cached_path = self.cache.get("user789")
        self.assertIsNone(cached_path)
    
    def test_cache_no_expiration(self):
        """测试缓存永不过期（TTL <= 0）"""
        # 设置 TTL <= 0
        self.cache.ttl = 0
        
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user_no_expire", test_file)
        
        # 等待一段时间
        time.sleep(1)
        
        # 读取缓存，应该仍然命中
        cached_path = self.cache.get("user_no_expire")
        self.assertIsNotNone(cached_path)
    
    def test_cache_delete(self):
        """测试缓存删除"""
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user_delete", test_file)
        
        # 删除缓存
        result = self.cache.delete("user_delete")
        
        # 验证删除成功
        self.assertTrue(result)
        self.assertNotIn("user_delete", self.cache._metadata)
    
    def test_cache_clear_expired(self):
        """测试清理过期缓存"""
        # 设置短 TTL
        self.cache.ttl = 1
        
        # 创建并存储测试文件
        test_file1 = self._create_test_gif(b"content1")
        test_file2 = self._create_test_gif(b"content2")
        self.cache.set("user_expire1", test_file1)
        self.cache.set("user_expire2", test_file2)
        
        # 等待过期
        time.sleep(2)
        
        # 清理过期缓存
        removed = self.cache.clear_expired()
        
        # 验证清理数量
        self.assertEqual(removed, 2)
        self.assertEqual(len(self.cache._metadata), 0)
    
    def test_cache_clear_all(self):
        """测试清理所有缓存"""
        # 创建并存储多个测试文件
        for i in range(3):
            test_file = self._create_test_gif(f"content{i}".encode())
            self.cache.set(f"user_{i}", test_file)
        
        # 清理所有缓存
        removed = self.cache.clear_all()
        
        # 验证清理数量
        self.assertEqual(removed, 3)
        self.assertEqual(len(self.cache._metadata), 0)
    
    def test_lru_cleanup(self):
        """测试 LRU 清理策略"""
        # 设置最大缓存数量为 3
        self.cache.max_size = 3
        
        # 创建并存储 5 个测试文件（超过上限）
        for i in range(5):
            test_file = self._create_test_gif(f"content{i}".encode())
            self.cache.set(f"lru_user_{i}", test_file)
            time.sleep(0.1)  # 确保访问时间不同
        
        # 验证缓存数量不超过上限
        self.assertLessEqual(len(self.cache._metadata), 3)
        
        # 验证最久未访问的缓存被清理（user_0 和 user_1 应该被清理）
        self.assertIsNone(self.cache.get("lru_user_0"))
        self.assertIsNone(self.cache.get("lru_user_1"))
        
        # 验证最近的缓存仍然存在
        self.assertIsNotNone(self.cache.get("lru_user_4"))
    
    def test_cache_with_avatar_hash(self):
        """测试带头像哈希的缓存"""
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user_hash", test_file, avatar_hash="abc123")
        
        # 使用相同头像哈希读取
        cached_path = self.cache.get("user_hash", avatar_hash="abc123")
        self.assertIsNotNone(cached_path)
        
        # 使用不同头像哈希读取
        cached_path = self.cache.get("user_hash", avatar_hash="def456")
        self.assertIsNone(cached_path)
    
    def test_cache_disabled(self):
        """测试禁用缓存"""
        # 禁用缓存
        self.cache.enabled = False
        
        # 创建测试文件
        test_file = self._create_test_gif()
        
        # 存储缓存应该直接返回原路径
        cache_path = self.cache.set("user_disabled", test_file)
        self.assertEqual(cache_path, test_file)
        
        # 读取缓存应该返回 None
        cached_path = self.cache.get("user_disabled")
        self.assertIsNone(cached_path)
    
    def test_cache_stats(self):
        """测试缓存统计信息"""
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user_stats", test_file)
        
        # 获取统计信息
        stats = self.cache.get_stats()
        
        # 验证统计字段
        self.assertIn("enabled", stats)
        self.assertIn("cache_dir", stats)
        self.assertIn("total_files", stats)
        self.assertIn("total_size_bytes", stats)
        self.assertIn("total_size_mb", stats)
        self.assertIn("expired_files", stats)
        self.assertIn("ttl_seconds", stats)
        self.assertIn("max_size", stats)
        self.assertIn("auto_cleanup", stats)
        self.assertIn("cleanup_interval_seconds", stats)
        
        # 验证统计值
        self.assertEqual(stats["total_files"], 1)
        self.assertTrue(stats["enabled"])
    
    def test_cache_update_access_time(self):
        """测试更新访问时间"""
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user_access", test_file)
        
        # 获取初始访问时间
        initial_access_time = self.cache._metadata["user_access"].accessed_at
        
        # 等待一段时间
        time.sleep(0.1)
        
        # 读取缓存
        self.cache.get("user_access")
        
        # 验证访问时间已更新
        updated_access_time = self.cache._metadata["user_access"].accessed_at
        self.assertGreater(updated_access_time, initial_access_time)


class TestGifCacheServiceAsync(unittest.IsolatedAsyncioTestCase):
    """GIF 缓存服务异步测试类"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        
        self.config = {
            "cache_enabled": True,
            "cache_ttl": 3600,
            "max_cache_size": 100,
            "auto_cleanup": True,
            "cleanup_interval": 1,  # 1秒间隔，方便测试
        }
        
        self.cache = GifCacheService("test_plugin_async", self.config)
        self.cache.cache_dir = Path(self.temp_dir)
        self.cache.metadata_file = self.cache.cache_dir / ".cache_metadata.json"
        self.cache.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache._metadata = {}
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        self.cache.stop_auto_cleanup()
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_gif(self, content: bytes = b"test_gif_content") -> Path:
        """创建测试 GIF 文件"""
        test_file = Path(self.temp_dir) / f"test_{time.time()}.gif"
        test_file.write_bytes(content)
        return test_file
    
    async def test_auto_cleanup(self):
        """测试自动清理"""
        # 设置短 TTL
        self.cache.ttl = 1
        
        # 创建并存储测试文件
        test_file = self._create_test_gif()
        self.cache.set("user_auto_cleanup", test_file)
        
        # 启动自动清理
        self.cache.start_auto_cleanup()
        
        # 验证缓存存在
        self.assertIsNotNone(self.cache.get("user_auto_cleanup"))
        
        # 等待过期和清理
        await asyncio.sleep(3)
        
        # 验证缓存已被清理
        self.assertEqual(len(self.cache._metadata), 0)
    
    async def test_stop_auto_cleanup(self):
        """测试停止自动清理"""
        # 启动自动清理
        self.cache.start_auto_cleanup()
        
        # 验证任务存在
        self.assertIsNotNone(self.cache._cleanup_task)
        
        # 停止自动清理
        self.cache.stop_auto_cleanup()
        
        # 等待任务取消
        await asyncio.sleep(0.1)
        
        # 验证任务已取消或完成
        self.assertTrue(self.cache._cleanup_task.done() or self.cache._cleanup_task.cancelled())


class TestGifCacheStoragePath(unittest.TestCase):
    """测试缓存存储路径（遵守 AstrBot 规范）"""
    
    def test_cache_dir_structure(self):
        """测试缓存目录结构"""
        cache = GifCacheService("test_plugin_path", {})
        
        # 验证缓存目录包含 plugin_data
        self.assertIn("plugin_data", str(cache.cache_dir))
        
        # 验证缓存目录包含插件名称
        self.assertIn("test_plugin_path", str(cache.cache_dir))
        
        # 验证缓存目录包含 gif_cache
        self.assertIn("gif_cache", str(cache.cache_dir))


if __name__ == "__main__":
    unittest.main()
