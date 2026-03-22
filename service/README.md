# GIF 缓存服务模块

摸头杀插件的 GIF 缓存服务模块，提供 GIF 资源的缓存管理功能。

## 功能特性

- **缓存存储**: 将生成的 GIF 存储到缓存目录，避免重复生成
- **缓存读取**: 优先返回缓存的 GIF，提高响应速度
- **缓存更新**: 支持刷新和替换缓存
- **过期清理**: 基于 TTL 的自动过期清理
- **LRU 清理**: 容量达到上限时自动清理最久未使用的缓存
- **自动清理**: 支持定时自动清理过期缓存
- **存储规范**: 遵守 AstrBot 大文件存储规范

## 存储路径

遵守 AstrBot 大文件存储规范，缓存存储于：

```
data/plugin_data/astrbot_plugin_headpat/gif_cache/
```

缓存文件命名格式：
```
headpat_{user_id}_{hash}.gif
```

## 使用方法

### 基本使用

```python
from service import GifCacheService

# 初始化缓存服务
config = {
    "cache_enabled": True,
    "cache_ttl": 3600,
    "max_cache_size": 100,
    "auto_cleanup": True,
    "cleanup_interval": 3600,
}
cache_service = GifCacheService("astrbot_plugin_headpat", config)

# 存储缓存
cache_path = cache_service.set("123456", Path("/path/to/generated.gif"))

# 读取缓存
cached_file = cache_service.get("123456")
if cached_file:
    # 使用缓存文件
    pass
else:
    # 生成新的 GIF
    pass

# 删除指定用户缓存
cache_service.delete("123456")

# 清理过期缓存
removed_count = cache_service.clear_expired()

# 清理所有缓存
removed_count = cache_service.clear_all()

# 获取统计信息
stats = cache_service.get_stats()
```

### 自动清理

```python
# 启动自动清理任务（在插件初始化时调用）
cache_service.start_auto_cleanup()

# 停止自动清理任务（在插件卸载时调用）
cache_service.stop_auto_cleanup()
```

## 接口定义

### GifCacheService 类

#### `__init__(plugin_name: str, config: dict = None)`

初始化缓存服务。

**参数:**
- `plugin_name`: 插件名称，用于构建缓存路径
- `config`: 配置字典，包含以下可选配置：
  - `cache_enabled` (bool): 是否启用缓存，默认 True
  - `cache_ttl` (int): 缓存有效期（秒），默认 3600
  - `max_cache_size` (int): 最大缓存文件数量，默认 100
  - `auto_cleanup` (bool): 是否启用自动清理，默认 True
  - `cleanup_interval` (int): 自动清理间隔（秒），默认 3600

#### `get(user_id: str, avatar_hash: str = None) -> Optional[Path]`

获取缓存的 GIF。

**参数:**
- `user_id`: 用户ID
- `avatar_hash`: 头像哈希（可选）

**返回:**
- 缓存文件路径，如果不存在或已过期则返回 None

#### `set(user_id: str, gif_path: Path, avatar_hash: str = None) -> Path`

存储 GIF 到缓存。

**参数:**
- `user_id`: 用户ID
- `gif_path`: GIF 文件路径
- `avatar_hash`: 头像哈希（可选）

**返回:**
- 缓存文件路径

**异常:**
- `CacheStorageError`: 存储失败时抛出

#### `delete(user_id: str = None, avatar_hash: str = None) -> bool`

删除缓存。

**参数:**
- `user_id`: 用户ID，为 None 时删除所有缓存
- `avatar_hash`: 头像哈希（可选）

**返回:**
- 是否成功删除

#### `clear_expired() -> int`

清理过期缓存。

**返回:**
- 清理的文件数量

#### `clear_all() -> int`

清理所有缓存。

**返回:**
- 清理的文件数量

#### `get_stats() -> dict`

获取缓存统计信息。

**返回:**
统计信息字典，包含以下字段：
- `enabled`: 是否启用缓存
- `cache_dir`: 缓存目录路径
- `total_files`: 缓存文件总数
- `total_size_bytes`: 总大小（字节）
- `total_size_mb`: 总大小（MB）
- `expired_files`: 已过期文件数量
- `ttl_seconds`: TTL 配置
- `max_size`: 最大缓存数量
- `auto_cleanup`: 是否启用自动清理
- `cleanup_interval_seconds`: 清理间隔

#### `start_auto_cleanup()`

启动自动清理任务。

#### `stop_auto_cleanup()`

停止自动清理任务。

## 配置参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `cache_enabled` | bool | true | 是否启用GIF缓存 |
| `cache_ttl` | int | 3600 | 缓存有效期（秒），默认1小时，0或负数表示永不过期 |
| `max_cache_size` | int | 100 | 最大缓存文件数量 |
| `auto_cleanup` | bool | true | 是否启用自动过期清理 |
| `cleanup_interval` | int | 3600 | 自动清理间隔（秒），默认1小时 |
| `cleanup_on_startup` | bool | false | 启动时是否执行一次过期清理 |

## AstrBot 存储规范

本模块遵守 AstrBot 大文件存储规范：

1. **存储位置**: 所有缓存文件存储于 `data/plugin_data/{plugin_name}/gif_cache/`
2. **路径获取**: 使用 `astrbot.core.utils.astrbot_path.get_astrbot_data_path()` 获取数据目录
3. **兼容性**: 兼容 AstrBot >= 4.9.2，旧版本自动回退到插件目录

## 注意事项

1. **缓存键生成**: 缓存键由 `user_id` 和可选的 `avatar_hash` 组成，确保同一用户不同头像能分别缓存
2. **元数据文件**: 缓存元数据存储于 `.cache_metadata.json`，请勿手动修改
3. **TTL 设置**: `cache_ttl` 设置为 0 或负数表示缓存永不过期
4. **LRU 策略**: 当缓存达到上限时，自动清理最久未访问的缓存
5. **异常处理**: 缓存操作失败时会记录日志，不会抛出异常影响主流程
6. **自动清理**: 自动清理任务为异步协程，需要在插件卸载时调用 `stop_auto_cleanup()`

## 异常类

### CacheError

缓存操作基础异常。

### CacheNotFoundError

缓存不存在异常。

### CacheExpiredError

缓存已过期异常。

### CacheStorageError

缓存存储异常。

## 示例代码

### 完整使用示例

```python
import asyncio
from pathlib import Path
from service import GifCacheService

async def main():
    # 配置
    config = {
        "cache_enabled": True,
        "cache_ttl": 3600,
        "max_cache_size": 100,
        "auto_cleanup": True,
        "cleanup_interval": 3600,
    }
    
    # 初始化
    cache = GifCacheService("astrbot_plugin_headpat", config)
    
    # 启动自动清理
    cache.start_auto_cleanup()
    
    try:
        user_id = "123456"
        
        # 尝试获取缓存
        cached = cache.get(user_id)
        if cached:
            print(f"缓存命中: {cached}")
        else:
            print("缓存未命中，生成新的GIF...")
            # 生成 GIF 的代码...
            generated_path = Path("/path/to/new.gif")
            
            # 存储到缓存
            cache.set(user_id, generated_path)
        
        # 获取统计信息
        stats = cache.get_stats()
        print(f"缓存统计: {stats}")
        
    finally:
        # 停止自动清理
        cache.stop_auto_cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```
