import asyncio
import base64
import hashlib
import io
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from PIL import Image

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .service import GifCacheService


QQ_AVATAR_URLS = [
    "https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640&img_type=jpg",
    "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640",
]

COMMAND_ALIASES = {"摸摸", "摸", "摸头杀"}


@register("astrbot_plugin_headpat", "tianluoqaq", "摸头杀插件 - at机器人后发送摸头命令生成GIF", "1.3.0")
class HeadpatPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.patpat_config = self.config.get("patpat", {})
        self.base_dir = Path(__file__).resolve().parent
        self.assets_dir = self.base_dir / "data" / "petpet"
        self.output_dir = self.assets_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 初始化GIF缓存服务
        self.cache_service = GifCacheService("astrbot_plugin_headpat", self.patpat_config)
        
        # 如果配置了启动时清理，执行一次过期清理
        if self.patpat_config.get("cleanup_on_startup", False):
            try:
                removed = self.cache_service.clear_expired()
                if removed > 0:
                    logger.info(f"[headpat] 启动时清理了 {removed} 个过期缓存")
            except Exception as e:
                logger.warning(f"[headpat] 启动时清理缓存失败: {e}")

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        # 启动旧版清理任务（清理临时文件）
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_gif_loop())
        
        # 启动缓存自动清理任务
        self.cache_service.start_auto_cleanup()
        
        logger.info("[headpat] 插件已加载，定时清理任务已启动")

    @filter.on_plugin_unloaded()
    async def on_plugin_unloaded(self):
        """插件卸载时清理资源"""
        # 停止旧版清理任务
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        # 停止缓存自动清理任务
        self.cache_service.stop_auto_cleanup()
        
        logger.info("[headpat] 插件已卸载，清理任务已停止")

    @filter.command("摸头", alias={"摸摸", "摸", "摸头杀"})
    async def headpat_command(self, event: AstrMessageEvent):
        '''摸头命令 - at机器人后发送摸头命令生成个性化摸头GIF
        别名: 摸摸、摸、摸头杀
        用法: @机器人 摸头 @目标用户
        如果只@机器人，则生成机器人自己的摸头GIF
        '''
        # 检查插件是否启用
        if not self.patpat_config.get("enable", True):
            return

        # 获取消息对象
        msg_obj = getattr(event, "message_obj", None)
        if not msg_obj:
            return

        # 获取群号并检查白名单
        group_id = getattr(msg_obj, "group_id", "")
        if group_id and not self._is_group_allowed(str(group_id)):
            return

        # 获取机器人ID
        bot_id = getattr(msg_obj, "self_id", "")

        # 检查是否at了机器人
        if not self._is_at_bot(event, bot_id):
            yield event.plain_result("请at机器人后使用摸头命令~")
            return

        # 获取目标用户ID
        target_user_id = self._get_target_user_id(event, bot_id)
        if not target_user_id:
            yield event.plain_result("无法识别目标用户，请稍后再试。")
            return

        # 检查素材是否就绪
        if not self._assets_ready():
            logger.error("[headpat] 缺少素材，请检查 data/petpet/frame0.png ~ frame4.png")
            yield event.plain_result("摸头素材缺失，请联系管理员检查插件目录下 data/petpet/frame0~4.png")
            return

        # 计算头像哈希用于缓存
        avatar_hash = None
        
        # 尝试从缓存获取
        if self.patpat_config.get("cache_enabled", True):
            try:
                cached_path = self.cache_service.get(target_user_id, avatar_hash)
                if cached_path and cached_path.exists():
                    logger.info(f"[headpat] 缓存命中: {target_user_id}")
                    yield self._image_result(event, cached_path)
                    return
            except Exception as e:
                logger.warning(f"[headpat] 读取缓存失败: {e}")

        # 获取头像
        avatar = await self._resolve_avatar(event, target_user_id)
        if avatar is None:
            yield event.plain_result("未能获取目标头像，请稍后再试。")
            return
        
        # 计算头像哈希
        try:
            avatar_hash = self._calculate_avatar_hash(avatar)
        except Exception as e:
            logger.warning(f"[headpat] 计算头像哈希失败: {e}")
            avatar_hash = None
        
        # 再次检查缓存（使用哈希）
        if self.patpat_config.get("cache_enabled", True) and avatar_hash:
            try:
                cached_path = self.cache_service.get(target_user_id, avatar_hash)
                if cached_path and cached_path.exists():
                    logger.info(f"[headpat] 缓存命中（带哈希）: {target_user_id}")
                    yield self._image_result(event, cached_path)
                    return
            except Exception as e:
                logger.warning(f"[headpat] 读取缓存失败: {e}")

        # 生成GIF
        try:
            speed = float(self.patpat_config.get("speed", 1.0))
            interval = 0.06 / speed
            transparent_bg = self.patpat_config.get("transparent_background", True)
            bg_color = self.patpat_config.get("background_color", "#FFFFFF")
            gif_path = self._build_petpet_gif(avatar, interval, transparent_bg, bg_color)
        except Exception:
            logger.exception("[headpat] 生成 GIF 失败")
            yield event.plain_result("生成摸头 GIF 失败，请稍后再试。")
            return

        # 存入缓存
        if self.patpat_config.get("cache_enabled", True):
            try:
                cache_path = self.cache_service.set(target_user_id, gif_path, avatar_hash)
                logger.info(f"[headpat] 已缓存: {target_user_id}")
                # 使用缓存路径发送
                yield self._image_result(event, cache_path)
            except Exception as e:
                logger.warning(f"[headpat] 缓存存储失败: {e}")
                # 缓存失败也发送原文件
                yield self._image_result(event, gif_path)
        else:
            # 发送结果
            yield self._image_result(event, gif_path)

    def _calculate_avatar_hash(self, avatar: Image.Image) -> str:
        """计算头像哈希值
        
        Args:
            avatar: 头像图片
            
        Returns:
            哈希字符串
        """
        # 缩小图片以加快计算
        small = avatar.resize((32, 32), Image.Resampling.LANCZOS)
        # 转换为字节
        data = small.tobytes()
        # 计算MD5哈希
        return hashlib.md5(data).hexdigest()[:8]

    def _is_group_allowed(self, group_id: str) -> bool:
        """检查群是否允许使用摸头功能"""
        allowed_groups = self.patpat_config.get("allowed_groups", [])
        if not allowed_groups:
            return True
        return group_id in allowed_groups

    def _is_at_bot(self, event: AstrMessageEvent, bot_id: str) -> bool:
        """检查消息是否at了机器人"""
        msg_obj = getattr(event, "message_obj", None)
        if not msg_obj:
            return False

        chain = getattr(msg_obj, "message", None) or []
        for seg in chain:
            seg_type = seg.__class__.__name__.lower()
            if seg_type == "at":
                target_id = self._first_attr(seg, ("qq", "user_id", "id", "target"))
                if target_id and str(target_id) == str(bot_id):
                    return True
        return False

    def _get_target_user_id(self, event: AstrMessageEvent, bot_id: str) -> Optional[str]:
        """获取目标用户ID
        规则：
        1. 如果只有一个at（机器人自己），返回机器人ID
        2. 如果有多个at，返回第二个at的用户ID（非机器人）
        """
        msg_obj = getattr(event, "message_obj", None)
        if not msg_obj:
            return None

        chain = getattr(msg_obj, "message", None) or []
        at_list = []

        for seg in chain:
            seg_type = seg.__class__.__name__.lower()
            if seg_type == "at":
                target_id = self._first_attr(seg, ("qq", "user_id", "id", "target"))
                if target_id:
                    at_list.append(str(target_id))

        # 去重保持顺序
        unique_at_list = []
        for at_id in at_list:
            if at_id not in unique_at_list:
                unique_at_list.append(at_id)

        if not unique_at_list:
            return None

        if len(unique_at_list) == 1:
            # 只有一个at，返回该用户（应该是机器人自己）
            return unique_at_list[0]

        # 有多个at，找到第二个at（非机器人）
        for at_id in unique_at_list:
            if at_id != str(bot_id):
                return at_id

        # 如果都是机器人（理论上不会发生），返回第一个
        return unique_at_list[0]

    async def _resolve_avatar(self, event: AstrMessageEvent, user_id: str) -> Optional[Image.Image]:
        """解析用户头像"""
        candidates = []

        # 尝试从event方法获取
        for name in ("get_user_avatar", "get_avatar", "get_target_avatar", "get_sender_avatar"):
            fn = getattr(event, name, None)
            if callable(fn):
                try:
                    import inspect
                    data = fn() if name == "get_sender_avatar" else fn(user_id)
                    if inspect.isawaitable(data):
                        data = await data
                    candidates.append(data)
                except Exception:
                    continue

        # 尝试从sender对象获取
        msg_obj = getattr(event, "message_obj", None)
        sender = getattr(msg_obj, "sender", None)
        sender_uid = self._first_attr(sender, ("user_id", "id"))
        if sender and sender_uid and str(sender_uid) == str(user_id):
            for k in ("avatar", "avatar_url", "face", "icon"):
                v = getattr(sender, k, None)
                if v:
                    candidates.append(v)

        # 尝试转换为图片
        for data in candidates:
            img = self._to_image(data)
            if img is not None:
                return img.convert("RGBA")

        # 尝试下载QQ头像
        img = await self._download_qq_avatar(user_id)
        if img is not None:
            return img

        return None

    async def _download_qq_avatar(self, user_id: str) -> Optional[Image.Image]:
        """下载QQ头像"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            for url_template in QQ_AVATAR_URLS:
                url = url_template.format(user_id=user_id)
                try:
                    resp = await client.get(url, headers=headers, follow_redirects=True)
                    if resp.status_code == 200 and len(resp.content) > 0:
                        img = Image.open(io.BytesIO(resp.content))
                        logger.info(f"[headpat] 从QQ头像API获取头像成功: {user_id}")
                        return img.convert("RGBA")
                except Exception as e:
                    logger.warning(f"[headpat] 获取头像失败 {url}: {e}")
        return None

    def _to_image(self, data: Any) -> Optional[Image.Image]:
        """将数据转换为图片"""
        if data is None:
            return None
        if isinstance(data, Image.Image):
            return data
        if isinstance(data, (bytes, bytearray)):
            try:
                return Image.open(io.BytesIO(data)).convert("RGBA")
            except Exception:
                return None
        if isinstance(data, str):
            text = data.strip()
            if text.startswith("http://") or text.startswith("https://"):
                return None
            if text.startswith("data:image"):
                try:
                    raw = base64.b64decode(text.split(",", 1)[1])
                    return Image.open(io.BytesIO(raw)).convert("RGBA")
                except Exception:
                    return None
            p = Path(text)
            if p.exists() and p.is_file():
                try:
                    return Image.open(p).convert("RGBA")
                except Exception:
                    return None
        return None

    def _build_petpet_gif(self, avatar: Image.Image, interval: float, transparent_bg: bool = True, bg_color: str = "#FFFFFF") -> Path:
        """构建摸头GIF
        
        Args:
            avatar: 用户头像
            interval: 帧间隔
            transparent_bg: 是否使用透明背景
            bg_color: 背景颜色（十六进制）
        """
        canvas_size = (112, 112)
        avatar_size = 75
        avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

        squeeze_data = [
            (1.0, 1.0, 0, 0),
            (1.0, 0.9, 0, 3),
            (0.95, 0.85, 2, 5),
            (1.0, 0.9, 0, 3),
            (1.0, 1.0, 0, 0),
        ]

        # 解析背景颜色
        bg_rgba = self._parse_color(bg_color, transparent_bg)

        frames = []
        for i in range(5):
            hand = Image.open(self.assets_dir / f"frame{i}.png").convert("RGBA")
            
            # 创建画布，根据配置决定是否透明
            if transparent_bg:
                canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
            else:
                canvas = Image.new("RGBA", canvas_size, bg_rgba)

            sx, sy, ox, oy = squeeze_data[i]
            w = int(avatar_size * sx)
            h = int(avatar_size * sy)
            squeezed = avatar.resize((w, h), Image.Resampling.LANCZOS)

            x = (canvas_size[0] - w) // 2 + ox
            y = (canvas_size[1] - h) // 2 + oy

            canvas.paste(squeezed, (x, y))
            canvas = Image.alpha_composite(canvas, hand)

            frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))

        out_path = self.output_dir / f"petpet_{uuid.uuid4().hex}.gif"
        frames[0].save(
            out_path,
            save_all=True,
            append_images=frames[1:],
            duration=max(20, int(interval * 1000)),
            loop=0,
            optimize=False,
            disposal=2,
        )
        return out_path

    def _parse_color(self, color_str: str, transparent: bool = False) -> tuple:
        """解析颜色字符串为RGBA元组
        
        Args:
            color_str: 十六进制颜色字符串，如 #FFFFFF
            transparent: 是否透明背景
            
        Returns:
            RGBA元组
        """
        if transparent:
            return (255, 255, 255, 0)
        
        # 移除 # 前缀
        color_str = color_str.lstrip("#")
        
        # 处理不同长度的颜色值
        if len(color_str) == 3:
            # 短格式 #RGB -> #RRGGBB
            r = int(color_str[0] * 2, 16)
            g = int(color_str[1] * 2, 16)
            b = int(color_str[2] * 2, 16)
        elif len(color_str) == 6:
            # 标准格式 #RRGGBB
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
        else:
            # 默认白色
            return (255, 255, 255, 255)
        
        return (r, g, b, 255)

    async def _cleanup_gif_loop(self):
        """定时清理GIF文件"""
        while True:
            try:
                self._cleanup_old_gifs(max_age_seconds=6 * 3600)
            except Exception:
                logger.exception("[headpat] 定时清理失败")
            await asyncio.sleep(3600)

    def _cleanup_old_gifs(self, max_age_seconds: int):
        """清理过期的GIF文件"""
        now = time.time()
        for f in self.output_dir.glob("petpet_*.gif"):
            try:
                if now - f.stat().st_mtime > max_age_seconds:
                    f.unlink(missing_ok=True)
            except Exception:
                continue

    def _assets_ready(self) -> bool:
        """检查素材是否就绪"""
        return all((self.assets_dir / f"frame{i}.png").exists() for i in range(5))

    def _image_result(self, event: AstrMessageEvent, path: Path):
        """生成图片结果"""
        if hasattr(event, "make_result"):
            result = event.make_result()
            if hasattr(result, "image"):
                result.image(str(path))
                return result
        return event.image_result(str(path))

    @staticmethod
    def _first_attr(obj: Any, keys: tuple[str, ...]) -> Optional[Any]:
        """获取对象的第一个非空属性"""
        if obj is None:
            return None
        for k in keys:
            v = getattr(obj, k, None)
            if v is not None and v != "":
                return v
        return None
