import asyncio
import traceback
import time  # 添加了time模块导入
from datetime import datetime
from uapi import UapiClient
from uapi.errors import UapiError
from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
import astrbot.api.message_components as Comp

LIVE_TIME: str = ""

@register("tutulivedcheck", "xiaohuangshu", "兔兔直播监听插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("插件加载ok")
        
        # 初始化配置
        self.targets = self.config.get("targets", [])
        self.last_status = {name: True for name in self.targets}
        
        # 启动定时任务
        self._monitoring_task = None
        self._running = True
        self._start_monitoring()
        logger.info("兔兔直播提醒已加载")
    
    def _start_monitoring(self):
        """启动监控任务"""
        is_master_on = self.config.get("auto_check", False)
        push_list = self.config.get("auto_push_groups", [])
        
        if is_master_on and push_list:
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
            self._monitoring_task = asyncio.create_task(self._auto_task())
    
    @filter.command("直播了么", alias={'直播了没', '直播了吗', '直播没', '查直播'})
    async def tutulived(self, event: AstrMessageEvent):
        """
        命令获取直播状态
        通过发送"直播状态"命令，获取当前的直播状态
        """
        news_content = await self._getlivedsd()
        
        # 构建消息组件列表
        components = [
            Comp.Plain(news_content)
        ]
        message_obj = MessageChain(components)
        
        # 发送消息
        await self.context.send_message(event.room_id, message_obj)

    async def terminate(self):
        """插件销毁方法"""
        logger.info("直播提醒定时任务已停止")
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def _getlived(self) -> str:
        """获取直播状态"""
        client = UapiClient("https://uapis.cn")
        try:
            data = client.social.get_social_bilibili_liveroom(mid="", room_id="6411294")
            l_time = data['live_time']
            if data['live_status'] == 1:
                global LIVE_TIME
                if l_time == LIVE_TIME:
                    logger.info("已做提醒")
                    result = "已做提醒"
                else:
                    LIVE_TIME = l_time
                    result = f"🔴兔兔正在直播中:\n({data['title']})\n开始时间:\n{data['live_time']}\n跳转:https://live.bilibili.com/6411294\n(此消息为自动发送)"
            else:
                result = "⚫兔兔未开播"
        except UapiError as exc:
            logger.error(f"API错误: {exc}")
            result = f"错误了"
        except Exception as e:
            logger.error(f"获取直播状态失败: {e}")
            result = f"错误了"
        return result
    
    async def _getlivedsd(self) -> str:
        """获取直播状态（简版）"""
        client = UapiClient("https://uapis.cn")
        try:
            data = client.social.get_social_bilibili_liveroom(mid="", room_id="6411294")
            if data['live_status'] == 1:
                result = f"🔴兔兔正在直播中:\n({data['title']})\n开始时间:\n{data['live_time']}"
            else:
                result = "⚫兔兔未开播"
        except UapiError as exc:
            result = f"错误了"
        except Exception as e:
            result = f"错误了"
        return result

    async def _auto_task(self):
        """
        定时任务主循环定时查看直播状态
        """
        push_list = self.config.get("auto_push_groups", [])
        interval = self.config.get("check_interval", 5)  # 默认5分钟
        
        # 验证配置
        if not push_list:
            logger.warning("auto_push_groups 列表为空，定时任务不会执行")
            return
        
        logger.info(f"定时任务启动，检查间隔: {interval}分钟，推送群组: {len(push_list)}个")
        
        last_log_time = 0
        while self._running:
            try:
                now = datetime.now()
                hour = now.hour
                
                if 9 <= hour < 22:  # 9-22点执行
                    # 当前时间戳（用于减少日志频率）
                    current_time = time.time()
                    
                    # 减少日志频率，每小时只记录一次
                    if current_time - last_log_time > 3600:
                        logger.info(f"[live] 检查时间: {now.strftime('%H:%M:%S')}")
                        last_log_time = current_time
                    
                    try:
                        news_content = await self._getlived()
                        
                        if news_content == "⚫兔兔未开播":
                            # 仅在长时间未开播时记录日志
                            if current_time - last_log_time > 3600:
                                logger.debug("[live] 兔兔未开播")
                        elif news_content == "已做提醒":
                            logger.info("[live] 兔兔直播已提醒。")
                        elif news_content == "错误了":
                            logger.info("看上面报错内容")
                        else:
                            logger.info("[live] 兔兔正在直播！准备推送")
                            
                            # 构建消息组件列表，包含@全体成员
                            components = [
                                Comp.AtAll(),  # 添加@全体成员
                                Comp.Plain("\n"),  # 添加换行
                                Comp.Plain(news_content)
                            ]
                            # 使用 AstrBot 定义的 MessageChain
                            message_obj = MessageChain(components)
                            
                            success_count = 0
                            for unified_id in push_list:
                                try:
                                    # 确保 unified_id 为字符串
                                    target_id = str(unified_id).strip()
                                    await self.context.send_message(target_id, message_obj)
                                    success_count += 1
                                except Exception as e:
                                    logger.error(f"定时推送失败，目标: {unified_id}，错误: {e}")
                            
                            if success_count > 0:
                                logger.info(f"[live] 成功推送到 {success_count}/{len(push_list)} 个群组")
                                await asyncio.sleep(3600) #成功后休息1个小时

                    except Exception as e:
                        logger.error(f"[live] 获取直播状态失败: {e}")
                        # 出错后等待更长时间再重试
                        await asyncio.sleep(60)
                
                else:
                    # 不在执行时间范围，进行更长的休眠
                    # 计算到第二天9点的秒数
                    if hour < 9:
                        # 当前时间在0-9点，等待到9点
                        wait_hours = 9 - hour
                    else:
                        # 当前时间在22-24点，等待到第二天9点
                        wait_hours = (24 - hour) + 9
                    
                    wait_seconds = wait_hours * 3600
                    logger.info(f"[live] 非工作时间，休眠 {wait_hours} 小时 ({wait_seconds}秒)")
                    
                    # 使用可中断的长时间睡眠
                    sleep_seconds = wait_seconds
                    while sleep_seconds > 0 and self._running:
                        # 每分钟检查一次是否终止
                        current_sleep = min(60, sleep_seconds)
                        await asyncio.sleep(current_sleep)
                        sleep_seconds -= current_sleep
                    
                    if not self._running:
                        break
                    continue  # 继续循环，重新检查时间
                
                # 等待下一次检查（使用可中断的睡眠）
                logger.debug(f"[live] 下次检查将在 {interval} 分钟后")
                sleep_seconds = interval * 60
                while sleep_seconds > 0 and self._running:
                    # 每分钟检查一次是否终止
                    current_sleep = min(60, sleep_seconds)
                    await asyncio.sleep(current_sleep)
                    sleep_seconds -= current_sleep
                
                if not self._running:
                    break
                    
            except asyncio.CancelledError:
                logger.info("监控任务被取消")
                break
            except Exception as e:
                logger.error(f"监控任务异常: {e}")
                # 异常时等待1分钟再重试
                await asyncio.sleep(60)
