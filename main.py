from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from mirai import Voice, Plain
import os
import requests
import logging
import re
from pydub import AudioSegment
import pilk
import httpx
import shutil

# 注册插件
@register(name="Music", description="get_music", version="0.2", author="zzseki")
class GetMusic(BasePlugin):
    def __init__(self, host: APIHost):
        self.token = "gsciO57hQTgxA9aR"  # 请替换为实际的token
        self.cookie = ""  # 请替换为实际的cookie
        self.logger = logging.getLogger(__name__)
        temp_dir = os.path.join(os.path.dirname(__file__), "temp")
        os.makedirs(temp_dir, exist_ok=True)  # 确保临时目录存在

    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        await self.handle_music_request(ctx, ctx.event.text_message)

    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        await self.handle_music_request(ctx, ctx.event.text_message)

    async def handle_music_request(self, ctx: EventContext, message: str):
        MUSIC_PATTERN = re.compile(r"播放音乐：(.+)")
        match = MUSIC_PATTERN.search(message)
        if match:
            music_name = match.group(1)
            music_id = await self.get_music_id(music_name)
            if music_id:
                msg, url = await self.get_music_url(music_id)
                if url:
                    silk_file = await self.download_and_convert(url)
                    if silk_file:
                        ctx.add_return("reply", [Voice(path=str(silk_file))])
                        self.logger.info(f"播放音乐：{music_name}")
                        ctx.prevent_default()
                    else:
                        ctx.add_return("reply", [Plain("音频文件转换失败。")])
                else:
                    ctx.add_return("reply", [Plain(f"无法获取音乐链接：{msg}")])
            else:
                ctx.add_return("reply", [Plain("无法找到对应的音乐。")])

    async def get_music_id(self, keyword: str):
        url = "https://v2.alapi.cn/api/music/search"
        params = {"keyword": keyword, "token": self.token}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json().get("data", {}).get("songs", [])
                return data[0]["id"] if data else None
        except Exception as e:
            self.logger.error(f"获取音乐 ID 失败: {e}")
            return None

    async def get_music_url(self, music_id: str):
        url = "https://v2.alapi.cn/api/music/url"
        params = {"id": music_id, "format": "json", "token": self.token, "cookie": self.cookie}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json().get("data")
                return response.json().get("msg"), data["url"] if data else None
        except Exception as e:
            self.logger.error(f"获取音乐链接失败: {e}")
            return "请求失败", None

    async def download_and_convert(self, audio_url: str):
        temp_dir = os.path.join(os.path.dirname(__file__), "temp")
        temp_audio_path = os.path.join(temp_dir, "temp_audio")
        silk_path = os.path.join(temp_dir, "temp.silk")
        try:
            # 下载音频文件
            response = requests.get(audio_url, stream=True)
            if response.status_code == 200:
                with open(temp_audio_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        file.write(chunk)
                self.logger.info(f"音频文件已成功保存为 {temp_audio_path}")

                # 转换为 SILK
                self.logger.info(f"正在将音频文件 {temp_audio_path} 转换为 SILK")
                media = AudioSegment.from_file(temp_audio_path)
                pcm_path = os.path.splitext(temp_audio_path)[0] + ".pcm"
                media.export(pcm_path, format="s16le", parameters=["-ar", str(media.frame_rate), "-ac", "1"])
                pilk.encode(pcm_path, silk_path, pcm_rate=media.frame_rate, tencent=True)

                self.logger.info(f"音频文件已成功转换为 SILK 文件 {silk_path}")
                return silk_path
            else:
                self.logger.error(f"音频文件下载失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"音频文件转换失败: {e}")
            return None
        finally:
            # 清理临时文件
            for temp_file in [temp_audio_path, os.path.splitext(temp_audio_path)[0] + ".pcm"]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

    def __del__(self):
        temp_dir = os.path.join(os.path.dirname(__file__), "temp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
