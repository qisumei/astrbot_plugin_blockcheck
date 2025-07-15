# main.py
import re
import datetime
import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

WORLD_NAME_MAP = {
    "主世界": "minecraft:overworld",
    "末地": "minecraft:the_end",
    "下界": "minecraft:the_nether",
}
ACTION_MAP = {0: "破坏", 1: "放置", 2: "使用"}

@register("block_query", "qisumei", "查询 Minecraft 方块日志", "1.1.0")
class BlockQueryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.api_base_url = "http://110.42.14.118:21003"

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        raw = event.message_str.strip()
        m = re.match(
            r"^查询-(主世界|末地|下界)-方块-(具体|范围)-\((-?\d+),(-?\d+),(-?\d+)\)(?:,(\d+))?$",
            raw,
        )
        if not m:
            return
        world_ch, mode, xs, ys, zs, rs = m.groups()
        x, y, z = map(int, (xs, ys, zs))
        radius = int(rs) if rs else None
        if mode == "具体" and radius:
            mode = "范围"

        reply = await self._build_reply(world_ch, mode, x, y, z, radius)
        yield event.plain_result(reply)

    async def _build_reply(self, world_ch, mode, x, y, z, radius):
        try:
            world_id = WORLD_NAME_MAP[world_ch]
            if mode == "具体":
                url_path = "/query-blocks"
                params = {"x": x, "y": y, "z": z, "world": world_id}
            else:
                if radius is None:
                    return "范围查询需要指定半径，例如：…,(radius)"
                url_path = "/query-range-blocks"
                params = {"x": x, "y": y, "z": z, "radius": radius, "world": world_id}

            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_base_url + url_path, params=params) as resp:
                    if resp.status != 200:
                        return f"API 查询失败: {resp.status}"
                    data = await resp.json()
            if not data:
                return f"未找到对应方块记录。"

            lines = []
            prefix = "📋 坐标" if mode == "具体" else f"🔍 范围查询 ±{radius}"
            lines.append(f"{prefix} ({x},{y},{z}) 共{len(data)}条：")
            for r in data:
                dt = datetime.datetime.fromtimestamp(r["time"] / 1000)
                action_desc = ACTION_MAP.get(r["action"], f"未知({r['action']})")
                coord = f"({r['x']},{r['y']},{r['z']})" if mode == "范围" else f"({x},{y},{z})"
                lines.append(f"[{dt:%Y-%m-%d %H:%M:%S}] 坐标{coord} — {r['material']} — 玩家 {r['username']} — 动作: {action_desc}")
            return "\n".join(lines)
        except Exception as e:
            logger.error("构建回复失败", exc_info=e)
            return "查询执行失败，请检查日志。"
