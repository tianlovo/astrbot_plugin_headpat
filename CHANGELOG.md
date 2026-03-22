# Changelog

## v1.2.1 (2026-03-22)

### 新增
- **透明背景配置**: 新增 `transparent_background` 配置项，默认启用透明背景
- **背景颜色配置**: 新增 `background_color` 配置项，当不启用透明背景时可指定背景颜色（默认白色 #FFFFFF）
- **颜色解析**: 支持十六进制颜色值，包括短格式（#RGB）和标准格式（#RRGGBB）

## v1.2.0 (2026-03-22)

### 变更
- **作者更新**: 从 `mjy1113451` 改为 `tianluoqaq`
- **仓库地址更新**: 从 `https://github.com/mjy1113451/touch_head` 改为 `https://github.com/tianlovo/astrbot_plugin_headpat`
- **插件名称**: 从 `astrbot_plugin_touch_head` 改为 `astrbot_plugin_headpat`

### 新增
- **QQ群白名单配置**: 新增 `allowed_groups` 配置项，只有在白名单列表中的群才能触发插件功能，为空则允许所有群

### 修改
- **触发规则重构**:
  - 移除 `.petset` 命令（配置改为通过 WebUI 管理）
  - 移除拍一拍事件监听
  - 移除普通消息前缀匹配触发
  - 改为使用 AstrBot 标准命令系统: `@filter.command("摸头", alias={"摸摸", "摸", "摸头杀"})`
  - 需要 at 机器人后才能触发命令
  - 支持命令别名: 摸摸、摸、摸头杀
  - 匹配以命令或别名开头的文本，如 "摸摸可以吗"

- **目标用户选择逻辑**:
  - 如果消息中只有一个 at（机器人自己），生成机器人自己的摸头 GIF
  - 如果消息中有多个 at，生成第二个 at 用户（非机器人）的摸头 GIF

### 移除
- `.petset` 命令（速度、触发词设置改为 WebUI 配置）
- 拍一拍事件监听功能

## v1.1.1

### 功能
- 基础摸头 GIF 生成功能
- 支持通过命令触发
- 支持拍一拍事件触发（仅限 QQ 平台）
