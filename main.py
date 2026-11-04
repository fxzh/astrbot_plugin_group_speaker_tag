import datetime

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger("astrbot")

try:  # 兼容不同版本的 AstrBot
    from astrbot.api import AstrBotConfig
except ImportError:
    try:
        from astrbot.api.config import AstrBotConfig
    except ImportError:
        AstrBotConfig = None

DEFAULT_FORMAT = "[{nickname}/{time}] {message}"


@register(
    "astrbot_plugin_group_speaker_tag",
    "fengxue",
    "群聊共享上下文中，为触发对话的当前消息标注发言人（昵称/ID），让 bot 分得清谁是谁",
    "1.1.0",
)
class GroupSpeakerTag(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config
        # 让位状态：None=未观测，True=内置「用户识别」开启中（本插件让位），False=工作中
        self._yielding = None

    def _builtin_identifier_on(self, event: AstrMessageEvent) -> bool:
        """内置「用户识别」（provider_settings.identifier）是否开启。

        取值口径与核心 _decorate_llm_request 一致：按会话(umo)解析配置，
        支持会话级覆盖。检测失败时按"未开启"处理，本插件继续工作。
        """
        try:
            try:
                cfg = self.context.get_config(umo=event.unified_msg_origin)
            except TypeError:  # 旧版 get_config 不接受 umo 参数
                cfg = self.context.get_config()
            settings = cfg.get("provider_settings") or {}
            return bool(settings.get("identifier"))
        except Exception as e:
            logger.warning(
                f"group_speaker_tag 检测内置「用户识别」失败，按未开启处理: {e}"
            )
            return False

    def _fmt(self) -> str:
        try:
            if self.config is not None:
                fmt = self.config.get("format", "")
                if fmt:
                    return str(fmt)
        except Exception:
            pass
        return DEFAULT_FORMAT

    @filter.on_llm_request()
    async def tag_sender(self, event: AstrMessageEvent, req: ProviderRequest):
        """在发给 LLM 的当前消息前加上发言人标注。

        与内置「群聊上下文感知」互补：那边只给历史消息加 [昵称/时间] 标注，
        当前触发消息本身是匿名的；这里补上它的身份。

        与内置「用户识别」（provider_settings.identifier）功能重复：那边会在
        用户消息尾部追加 <system_reminder>User ID..., Nickname...</system_reminder>。
        该选项开启时本插件让位，避免同一条消息带两份身份标注；关闭后自动恢复。
        """
        try:
            if not event.get_group_id():
                return  # 仅群聊生效

            if self._builtin_identifier_on(event):
                if self._yielding is not True:
                    self._yielding = True
                    logger.info(
                        "group_speaker_tag: 内置「用户识别」已开启，当前消息身份由内置功能标注，"
                        "本插件自动让位；关闭该选项后自动恢复。"
                    )
                return
            if self._yielding is True:
                self._yielding = False
                logger.info("group_speaker_tag: 内置「用户识别」已关闭，本插件恢复标注当前发言人。")

            if event.get_extra("_speaker_tag_done"):
                return  # agent 多轮请求时防重复标注
            prompt = req.prompt
            if not isinstance(prompt, str) or not prompt.strip():
                return  # 纯 @ 无正文等情况，交给内置逻辑处理

            sender = getattr(event.message_obj, "sender", None)
            nickname = None
            if sender is not None:
                nickname = getattr(sender, "nickname", None) or getattr(
                    sender, "remark", None
                )
            nickname = (
                nickname
                or event.get_sender_name()
                or str(event.get_sender_id() or "群成员")
            )
            user_id = str(event.get_sender_id() or "")

            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            req.prompt = self._fmt().format(
                nickname=nickname,
                user_id=user_id,
                time=time_str,
                message=prompt,
            )
            event.set_extra("_speaker_tag_done", True)
        except Exception as e:
            logger.warning(f"group_speaker_tag 标注失败: {e}")
