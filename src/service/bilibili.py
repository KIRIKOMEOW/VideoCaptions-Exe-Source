"""
B站服务 - 字幕下载和处理
"""

import logging
import os
import re
import subprocess
import tempfile
import urllib.parse
from typing import Dict, Any, Optional, List

import httpx

# 禁用 httpx 的 HTTP 请求日志
logging.getLogger("httpx").setLevel(logging.WARNING)

from .base import SubtitleService
from core.formatter import ResponseFormat, format_subtitle
from core.audio import extract_audio
from core.asr import transcribe_with_asr
from core.logging import (
    log_debug,
    log_success,
    log_warning,
    log_step,
)
from core.text import make_safe_filename
from core.cookie import get_sessdata


API_BASE_URL = "https://api.bilibili.com"
BILIBILI_ZH_PRIORITY = ["ai-zh", "zh-Hans", "zh-CN", "zh"]
BILIBILI_EN_PRIORITY = ["ai-en", "en", "en-US", "en-GB"]


class BilibiliService(SubtitleService):
    """B站字幕服务"""

    def __init__(self, browser: Optional[str] = "auto"):
        self.browser = browser
        self._sessdata = None
        self._tried_cookie_lookup = False

    @property
    def name(self) -> str:
        return "bilibili"

    def is_supported(self, source: str) -> bool:
        """判断是否为 B站视频"""
        patterns = [
            r'bilibili\.com/video/',
            r'bilibili\.com/list/',
            r'^BV[\w]+$',
        ]
        for pattern in patterns:
            if re.search(pattern, source, re.IGNORECASE):
                return True
        return False

    def _extract_bvid(self, url: str) -> str:
        """从 URL 中提取 BV 号"""
        if url.startswith('BV'):
            return url.split('?')[0].split('#')[0]
        if '/video/' in url:
            return url.split('/video/')[1].split('/')[0].split('?')[0].split('#')[0].rstrip('/')
        if 'bvid=' in url.upper():
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            bvid = params.get('bvid') or params.get('BVID')
            if bvid:
                return bvid[0]
        last_part = url.rstrip('/').split('/')[-1].split('?')[0]
        if last_part.startswith('BV'):
            return last_part
        raise ValueError(f"无法从 URL 中提取 BV 号: {url}")

    def _ensure_sessdata(self) -> str:
        """确保获取 SESSDATA，如果没有则抛出异常"""
        if self._sessdata:
            return self._sessdata

        sessdata = get_sessdata(self.browser)
        if not sessdata:
            raise ValueError(
                "未找到 B站 SESSDATA。请通过以下方式之一提供：\n"
                "1. 在浏览器中登录 B站（推荐）\n"
                "2. 设置环境变量 BILIBILI_SESSDATA"
            )
        self._sessdata = sessdata
        return sessdata

    def _get_cookies(self) -> dict:
        if self._sessdata:
            return {'SESSDATA': self._sessdata}

        env_sessdata = os.environ.get('BILIBILI_SESSDATA')
        if env_sessdata:
            self._sessdata = env_sessdata
            return {'SESSDATA': env_sessdata}

        if not self.browser or self.browser == "auto" or self._tried_cookie_lookup:
            return {}

        self._tried_cookie_lookup = True
        sessdata = get_sessdata(self.browser)
        if sessdata:
            self._sessdata = sessdata
            return {'SESSDATA': sessdata}
        return {}

    def _select_subtitle(self, subtitles: List[Dict[str, Any]], language: str) -> Optional[Dict[str, Any]]:
        priority = BILIBILI_EN_PRIORITY if language == "en" else BILIBILI_ZH_PRIORITY

        for lan in priority:
            for sub in subtitles:
                if sub.get('lan') == lan:
                    return sub

        for sub in subtitles:
            lan = (sub.get('lan') or '').lower()
            if language == "en" and lan.startswith("en"):
                return sub
            if language == "zh" and (lan.startswith("zh") or lan == "ai-zh"):
                return sub

        return subtitles[0] if subtitles else None

    async def get_info(self, source: str) -> Dict[str, Any]:
        """获取 B站视频基本信息"""
        bvid = self._extract_bvid(source)
        url = f"{API_BASE_URL}/x/web-interface/view?bvid={bvid}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/'
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, cookies=self._get_cookies())
            response.raise_for_status()
            data = response.json()

        if data['code'] != 0:
            raise ValueError(f"B站 API 返回错误: {data.get('message', '未知错误')}")

        video_data = data['data']
        return {
            "title": video_data.get('title'),
            "id": video_data.get('bvid'),
            "duration": video_data.get('duration', 0),
            "description": video_data.get('desc', ''),
            "author": video_data.get('owner', {}).get('name'),
            "has_subtitle": bool(video_data.get('subtitle', {}).get('list')),
            "cid": video_data.get('cid')
        }

    async def list_subtitles(self, source: str) -> Dict[str, Any]:
        """列出 B站视频可用的字幕"""
        video_info = await self.get_info(source)
        bvid = video_info['id']
        cid = video_info.get('cid')

        url = f"{API_BASE_URL}/x/player/wbi/v2?bvid={bvid}&cid={cid}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': f'https://www.bilibili.com/video/{bvid}',
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, cookies=self._get_cookies())
            response.raise_for_status()
            data = response.json()

        if data['code'] != 0:
            return {"available": False, "subtitles": [], "subtitle_count": 0, "error": data.get('message')}

        subtitle_list = data['data'].get('subtitle', {}).get('subtitles', [])
        subtitles = [
            {"lan": sub.get('lan'), "lan_doc": sub.get('lan_doc'), "subtitle_url": sub.get('subtitle_url')}
            for sub in subtitle_list
        ]

        return {"available": len(subtitles) > 0, "subtitles": subtitles, "subtitle_count": len(subtitles)}

    async def download_subtitle(
        self,
        source: str,
        format: ResponseFormat = ResponseFormat.TEXT,
        model_size: str = "large",
        show_progress: bool = True,
        language: str = "zh",
    ) -> Dict[str, Any]:
        """下载 B站视频字幕，无字幕时自动 ASR 兜底"""
        try:
            subtitle_info = await self.list_subtitles(source)

            if subtitle_info['available']:
                # 有 API 字幕
                selected_subtitle = self._select_subtitle(subtitle_info['subtitles'], language)
                if not selected_subtitle:
                    return {"error": "无法选择字幕"}

                video_info = await self.get_info(source)
                subtitle_url = selected_subtitle['subtitle_url']
                if not subtitle_url.startswith('http'):
                    subtitle_url = 'https:' + subtitle_url

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(subtitle_url)
                    response.raise_for_status()
                    subtitle_json = response.json()

                body = subtitle_json.get('body', [])
                log_success(f"API 获取成功，共 {len(body)} 条字幕")

                segments = [
                    {"start": item.get("from", 0), "end": item.get("to", 0), "content": item.get("content", "")}
                    for item in body
                ]

                return format_subtitle(segments, video_info['title'], format, source="bilibili_api")

            # 无 API 字幕，ASR 兜底
            log_warning("该视频没有可用字幕，切换到 ASR 模式")
            return await self._download_with_asr(source, format, model_size, show_progress, language)

        except Exception as e:
            return {"error": f"下载字幕失败: {type(e).__name__}", "message": str(e)}

    async def _download_with_asr(
        self,
        source: str,
        format: ResponseFormat,
        model_size: str,
        show_progress: bool,
        language: str,
    ) -> Dict[str, Any]:
        """ASR 兜底下载"""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                log_step("下载视频并提取音频")
                audio_file, video_title, video_id = await self.download_audio(source, temp_dir)
                log_success(f"音频提取完成: {os.path.basename(audio_file)}")

                log_step("ASR 语音识别", "这可能需要几分钟...")
                asr_result = await transcribe_with_asr(audio_file, model_size, show_progress, language)

                segments = asr_result.get("segments", [])
                log_success(f"ASR 完成，共 {len(segments)} 个片段")

                formatted = [
                    {"start": seg["start"], "end": seg["end"], "content": seg["text"]}
                    for seg in segments
                ]

                return format_subtitle(formatted, video_title, format, source="whisper_asr")

            except subprocess.CalledProcessError as e:
                stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
                suggestion = "请检查网络连接"
                if 'not found' in stderr.lower():
                    suggestion = "请确保已安装 yt-dlp 和 ffmpeg"
                return {"error": f"ASR失败: {type(e).__name__}", "message": str(e), "suggestion": suggestion}
            except Exception as e:
                return {"error": f"ASR失败: {type(e).__name__}", "message": str(e)}

    async def download_audio(self, source: str, output_dir: str) -> tuple[str, str, str]:
        """Download Bilibili audio directly from the playurl API for ASR."""
        info = await self.get_info(source)
        video_title = info.get("title", "video")
        bvid = info.get("id", self._extract_bvid(source))
        cid = info.get("cid")
        if not cid:
            raise ValueError("Bilibili video is missing cid; cannot get audio")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
            'Referer': f'https://www.bilibili.com/video/{bvid}/',
            'Origin': 'https://www.bilibili.com',
        }
        playurl = f"{API_BASE_URL}/x/player/playurl?bvid={bvid}&cid={cid}&qn=16&fnval=16&fourk=0"

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(playurl, headers=headers, cookies=self._get_cookies())
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                raise ValueError(f"Bilibili playurl API error: {data.get('message', 'unknown error')}")

            play_data = data.get("data", {})
            audio_items = play_data.get("dash", {}).get("audio") or []
            media_url = None
            if audio_items:
                media_url = audio_items[0].get("baseUrl") or audio_items[0].get("base_url")
            elif play_data.get("durl"):
                media_url = play_data["durl"][0].get("url")

            if not media_url:
                raise ValueError("Bilibili did not return a downloadable audio URL")

            os.makedirs(output_dir, exist_ok=True)
            safe_title = make_safe_filename(video_title).strip() or bvid
            audio_file = os.path.join(output_dir, f"{safe_title}.m4a")

            async with client.stream("GET", media_url, headers=headers) as media_response:
                media_response.raise_for_status()
                with open(audio_file, "wb") as f:
                    async for chunk in media_response.aiter_bytes():
                        if chunk:
                            f.write(chunk)

        if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
            raise ValueError("Bilibili audio download failed; file is empty")

        return audio_file, video_title, bvid

    async def download_video(
        self,
        source: str,
        output_dir: str,
        show_progress: bool = True
    ) -> tuple[str, str, str]:
        """下载 B站视频"""
        info = await self.get_info(source)
        video_title = info.get("title", "video")
        bvid = info.get("id", self._extract_bvid(source))

        safe_title = make_safe_filename(video_title)
        video_filename = os.path.join(output_dir, f"{safe_title}.mp4")

        os.makedirs(output_dir, exist_ok=True)

        if os.path.exists(video_filename):
            return video_filename, video_title, bvid

        if show_progress:
            log_step("正在下载视频")

        result = subprocess.run(['yt-dlp', '--quiet', '--no-progress', '-o', video_filename, f"https://www.bilibili.com/video/{bvid}"], capture_output=True)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, stderr=result.stderr.decode('utf-8', errors='ignore'))

        return video_filename, video_title, bvid

    def extract_audio(self, video_file: str, output_dir: Optional[str] = None, show_progress: bool = True) -> str:
        return extract_audio(video_file, output_dir, show_progress)
