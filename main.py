import asyncio
import datetime
import traceback
import json
from uapi import UapiClient
from uapi.errors import UapiError
from urllib.parse import quote
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.message_event_result import MessageChain

@register("tutulivedcheck", "xiaohuangshu", "兔兔直播监听插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context,config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.push_time = self.config.push_time
        self.push_way = self.config.push_way
        logger.info(f"插件配置: {self.config}")
        # 启动定时任务
        # self._monitoring_task = asyncio.create_task(self._auto_task())
        logger.info("兔兔直播提醒已加载")
    
    @filter.command("直播了么")            
    async def tutulived(self, event: AstrMessageEvent):
        """
        命令获取 直播状态
        通过发送“直播状态”命令，获取当前的直播状态
        """
        news_content = await self._getlived()
        yield event.plain_result(news_content)
        # await self._send_to_groups()

        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    # @filter.command("helloworld")
    # async def helloworld(self, event: AstrMessageEvent):
    #     """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
    #     user_name = event.get_sender_name()
    #     message_str = event.message_str # 用户发的纯文本消息字符串
    #     message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
    #     logger.info(message_chain)
    #     yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        

    async def _getlived(self) -> str:
        """获取直播状态"""
        client = UapiClient("https://uapis.cn")
        try:
            data = client.social.get_social_bilibili_liveroom(mid="", room_id="6411294")
            # print(result)
            # result = self.live_status(result[live_status])
            result = f"🔴兔兔正在直播中,开始时间：{data['live_time']}" if data['live_status'] == 1 else "⚫兔兔未开播"
        except UapiError as exc:
            result = (f"API error: {exc}")
        return result
    
    
    async def _send_to_groups(self):
        """
        推送目标群组
        """
        result = await self._getlived()
        for target in self.config.groups:
            try:
                message_chain = MessageChain().message(result) 
                logger.info(f"{result}")
                await self.context.send_message(target, message_chain)
                logger.info(f"已向{target}推送。")
                await asyncio.sleep(2)  # 防止推送过快
            except Exception as e:
                error_message = str(e) if str(e) else "未知错误"
                logger.error(f"推送失败: {error_message}")
                # 可选：记录堆栈跟踪信息
                logger.exception("详细错误信息：")
                await asyncio.sleep(2)  # 防止推送过快

    def live_status(self):
        """使用 if-elif-else 实现 switch"""
        if self == 0:
            return "未开播"
        elif self == 1:
            return "直播中"
        elif self == 2:
            return "轮播中"

