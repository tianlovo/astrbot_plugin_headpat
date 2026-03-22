# astrbot_plugin_headpat - 摸头杀插件

AstrBot 摸头杀插件 - at机器人发送"摸头"命令生成个性化摸头GIF动图。

## 功能特性

- 🖼️ **动态生成**: 使用用户QQ头像实时生成个性化摸头GIF
- ⌨️ **命令触发**: 支持通过 at 机器人后发送"摸头"命令触发
- 📝 **命令别名**: 支持"摸摸"、"摸"、"摸头杀"等多种别名
- 👥 **智能识别**: 多at时自动识别目标用户，单at时生成机器人自己的摸头gif
- ⚙️ **群白名单**: 支持配置允许使用功能的QQ群列表
- 🎨 **透明背景**: 默认启用透明背景，支持自定义背景颜色
- 💾 **GIF缓存**: 智能缓存机制，避免重复生成，提高响应速度
- ✨ **精美动画**: 5帧流畅动画，包含手部和挤压效果

## 依赖

- Pillow >= 10.0.0
- httpx >= 0.24.0

## 使用方法

### 命令格式

需要先 at 机器人，然后发送摸头命令：

```
@机器人 摸头
@机器人 摸摸
@机器人 摸
@机器人 摸头杀
```

### 目标用户选择

- **仅at机器人**: 生成机器人自己的摸头GIF
- **at机器人+其他用户**: 生成第二个at用户的摸头GIF

示例：
```
@机器人 摸摸 @小明    → 生成小明的摸头GIF
@机器人 摸头          → 生成机器人的摸头GIF
```

### 命令别名

以下命令均可触发：
- `摸头`
- `摸摸`
- `摸`
- `摸头杀`

支持带后缀文本，如："摸摸可以吗"、"摸头~"

## 平台支持

- ✅ QQ (通过 NapCat / aiocqhttp / LLOneBot 适配器)
- ⚠️ 其他平台可能支持，但未经过测试

## 安装

1. 将插件放入 AstrBot 的 `data/plugins/` 目录
2. 重启 AstrBot 或在插件管理页面重载插件

## 配置说明

在 AstrBot 管理面板的插件配置页面进行设置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable` | bool | true | 是否启用摸头功能 |
| `speed` | float | 1.0 | 摸头动画速度，值越大越快（建议 0.5 ~ 3.0） |
| `cooldown_seconds` | float | 3.0 | 冷却时间（秒），防止刷屏 |
| `allowed_groups` | list | [] | 允许使用功能的QQ群列表，为空则允许所有群 |
| `transparent_background` | bool | true | 是否启用透明背景 |
| `background_color` | string | "#FFFFFF" | 背景颜色（十六进制），不启用透明背景时生效 |
| `cache_enabled` | bool | true | 是否启用GIF缓存 |
| `cache_ttl` | int | 3600 | 缓存有效期（秒），默认1小时，0或负数表示永不过期 |
| `max_cache_size` | int | 100 | 最大缓存文件数量，超过时按LRU策略清理 |
| `auto_cleanup` | bool | true | 是否启用自动过期清理 |
| `cleanup_interval` | int | 3600 | 自动清理间隔（秒），默认1小时 |
| `cleanup_on_startup` | bool | false | 启动时是否执行一次过期缓存清理 |

### QQ群白名单配置

在 `allowed_groups` 中添加群号，只有这些群才能使用摸头功能：

```json
{
  "allowed_groups": ["123456789", "987654321"]
}
```

留空 `[]` 则允许所有群使用。

### 背景颜色配置

- **透明背景**: 默认启用 (`transparent_background: true`)，GIF背景为透明
- **自定义颜色**: 禁用透明背景后，可设置 `background_color` 指定背景颜色

支持的颜色格式：
- 标准十六进制: `#FFFFFF`（白色）、`#000000`（黑色）、`#FF5733`（橙色）
- 短格式: `#FFF`（白色）、`#000`（黑色）

示例配置：
```json
{
  "transparent_background": false,
  "background_color": "#F0F0F0"
}
```

### GIF缓存配置

缓存功能默认启用，支持以下配置：

```json
{
  "cache_enabled": true,
  "cache_ttl": 3600,
  "max_cache_size": 100,
  "auto_cleanup": true,
  "cleanup_interval": 3600,
  "cleanup_on_startup": false
}
```

**缓存策略说明：**
- **TTL（生存时间）**: 缓存文件超过TTL时间未访问会被标记为过期
- **LRU策略**: 当缓存数量达到上限时，自动清理最久未访问的缓存
- **自动清理**: 定期自动清理过期缓存，可配置间隔
- **启动清理**: 插件启动时可选择执行一次过期缓存清理

**缓存存储位置：**
遵守 AstrBot 大文件存储规范，缓存存储于：
```
data/plugin_data/astrbot_plugin_headpat/gif_cache/
```

## 技术实现

- 使用 Pillow 库本地生成GIF动画
- 通过 QQ 官方头像 API 获取用户头像
- 使用 AstrBot 标准命令系统 `@filter.command`
- 支持命令别名和参数解析
- GIF缓存服务遵守 AstrBot 大文件存储规范

## 项目结构

```
astrbot_plugin_headpat/
├── main.py                 # 主程序
├── service/                # 服务模块
│   ├── __init__.py
│   ├── gif_cache.py       # GIF缓存服务
│   ├── exceptions.py      # 异常类
│   └── README.md          # 模块文档
├── tests/                  # 单元测试
│   ├── __init__.py
│   └── test_gif_cache.py  # 缓存服务测试
├── data/petpet/           # 素材目录
├── _conf_schema.json      # 配置Schema
├── config.json            # 默认配置
└── README.md              # 本文档
```

## 更新日志

### v1.3.0 (2026-03-22)

- **新增**: GIF缓存服务模块，提供智能缓存机制
  - 基于用户ID的缓存存储，遵守 AstrBot 存储规范
  - 支持TTL过期清理、LRU容量清理、自动定时清理
  - 可配置的缓存参数（启用/禁用、TTL、容量、清理策略）
- **新增**: 完整的单元测试覆盖
- **架构**: 模块化设计，缓存服务与业务逻辑解耦

### v1.2.1 (2026-03-22)

- **新增**: 透明背景配置 `transparent_background`，默认启用
- **新增**: 背景颜色配置 `background_color`，支持十六进制颜色值
- **优化**: 支持短格式和标准格式十六进制颜色

### v1.2.0 (2026-03-22)

- **变更**: 作者更新为 tianluoqaq，仓库地址更新
- **新增**: QQ群白名单配置 `allowed_groups`
- **重构**: 触发规则改为 at 机器人后发送命令
- **新增**: 支持命令别名：摸摸、摸、摸头杀
- **优化**: 多at时智能识别目标用户
- **移除**: `.petset` 命令（改为 WebUI 配置）
- **移除**: 拍一拍事件监听

### v1.1.0

- 🎨 重构动画效果，更流畅的摸头动画
- ✨ 新增 5 帧动画
- 🖐️ 完整的手部绘制
- 📤 使用文件路径发送图片

### v1.0.0

- 🎉 初始版本发布
- ✅ 支持拍一拍事件触发
- ✅ 支持手动命令触发
- ✅ 基础摸头 GIF 生成

## 支持与反馈

- 仓库地址: https://github.com/tianlovo/astrbot_plugin_headpat
- [AstrBot 官方文档](https://astrbot.app)
