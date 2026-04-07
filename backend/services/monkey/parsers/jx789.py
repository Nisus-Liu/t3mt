# -*- coding: utf-8 -*-
"""
789 解析器
已验证可用：https://jiexi.789jiexi.icu:4433/api.php
"""
import time
import requests
from typing import Optional
from .base import BaseParser
from utils.decrypt import AESTool


class JX789Parser(BaseParser):
    """789 解析器"""

    name = "789解析"
    api_url = "https://jiexi.789jiexi.icu:4433/api.php"

    # 请求头
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://jiexi.789jiexi.icu:4433',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    }

    def __init__(self):
        super().__init__()
        self.session = requests.Session()

    def get_m3u8_url(self, video_url: str) -> Optional[str]:
        """
        调用 789 api.php 获取并解密 M3U8 URL

        关键发现：api.php 不验证 key 参数，只需 url + 当前时间戳 + 任意 key
        """
        current_time = str(int(time.time()))
        fake_key = "fake_key_for_monkey"

        ref_url = f"https://jiexi.789jiexi.icu:4433/jx.php?url={video_url}"
        headers = dict(self.HEADERS)
        headers['Referer'] = ref_url

        try:
            # 调用 api.php
            resp = self.session.post(
                self.api_url,
                data={
                    'url': video_url,
                    'time': current_time,
                    'key': fake_key,
                },
                headers=headers,
                timeout=15
            )

            if resp.status_code != 200:
                self.logger.warning(f"[{self.name}] HTTP {resp.status_code}: {video_url}")
                return None

            data = resp.json()
            if data.get('code') != 200:
                self.logger.warning(f"[{self.name}] API错误: {data.get('msg')}, {video_url}")
                return None

            encrypted_url = data.get('url', '')
            if not encrypted_url:
                self.logger.warning(f"[{self.name}] 加密URL为空: {video_url}")
                return None

            # AES 解密
            m3u8_url = AESTool.decrypt_jx789(encrypted_url)
            return m3u8_url

        except requests.RequestException as e:
            self.logger.error(f"[{self.name}] 请求异常: {e}")
            return None
        except Exception as e:
            self.logger.error(f"[{self.name}] 解析异常: {e}")
            return None
