# -*- coding: utf-8 -*-
"""
动态解析器 - 支持用户配置的任意解析接口
"""
import time
import requests
from typing import Optional
from .base import BaseParser
from utils.logger import logger


class DynamicParser(BaseParser):
    """
    动态解析器，根据用户配置的 api_url 动态解析视频
    
    支持两种模式：
    1. 直接返回模式：api_url?url=video_url → 直接返回 m3u8 URL
    2. 789兼容模式：api_url + POST {url, time, key} → 返回加密url需解密
    """

    name = "动态解析器"
    api_url = ""

    def __init__(self, api_url: str = "", name: str = "动态解析器"):
        super().__init__()
        self.api_url = api_url.rstrip('/')
        self.name = name
        self.session = requests.Session()

    def get_m3u8_url(self, video_url: str) -> Optional[str]:
        """
        调用解析接口获取 M3U8 URL
        
        策略：
        1. 先尝试 789 兼容模式（POST + 解密）
        2. 失败则尝试直接模式（GET ?url=）
        """
        # 尝试 789 兼容模式
        m3u8_url = self._try_789_mode(video_url)
        if m3u8_url:
            return m3u8_url
        
        # 尝试直接模式
        m3u8_url = self._try_direct_mode(video_url)
        if m3u8_url:
            return m3u8_url
        
        return None

    def _try_789_mode(self, video_url: str) -> Optional[str]:
        """789 兼容模式：POST + AES 解密"""
        try:
            from utils.decrypt import AESTool
            
            current_time = str(int(time.time()))
            fake_key = "fake_key_for_monkey"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f"{self.api_url}/jx.php?url={video_url}",
                'Origin': self.api_url,
            }
            
            resp = self.session.post(
                f"{self.api_url}/api.php",
                data={
                    'url': video_url,
                    'time': current_time,
                    'key': fake_key,
                },
                headers=headers,
                timeout=15
            )
            
            if resp.status_code != 200:
                self.logger.warning(f"[{self.name}] 789模式 HTTP {resp.status_code}")
                return None
            
            data = resp.json()
            if data.get('code') != 200:
                self.logger.warning(f"[{self.name}] 789模式 API错误: {data.get('msg')}")
                return None
            
            encrypted_url = data.get('url', '')
            if not encrypted_url:
                return None
            
            # AES 解密
            m3u8_url = AESTool.decrypt_jx789(encrypted_url)
            return m3u8_url
            
        except Exception as e:
            self.logger.warning(f"[{self.name}] 789模式异常: {e}")
            return None

    def _try_direct_mode(self, video_url: str) -> Optional[str]:
        """直接模式：GET ?url=video_url"""
        try:
            # 构造解析 URL
            parse_url = f"{self.api_url}/jiexi.php?url={video_url}"
            if '?' not in self.api_url:
                parse_url = f"{self.api_url}?url={video_url}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Referer': f"{self.api_url}/",
            }
            
            resp = self.session.get(parse_url, headers=headers, timeout=15, allow_redirects=True)
            
            if resp.status_code != 200:
                return None
            
            content_type = resp.headers.get('content-type', '')
            
            # 检查是否是 m3u8
            if 'application/vnd.apple.mpegurl' in content_type or 'application/x-mpegurl' in content_type or 'audio/mpegurl' in content_type:
                return resp.url
            
            text = resp.text.strip()
            
            # 检查是否是 m3u8 内容
            if text.startswith('#EXTM3U'):
                # 返回最终 URL（可能跟随了重定向）
                return resp.url
            
            # 检查是否是 JSON 格式
            if 'application/json' in content_type or text.startswith('{'):
                try:
                    data = resp.json()
                    # 尝试常见字段
                    for key in ['url', 'm3u8', 'm3u8_url', 'download_url', 'final_url']:
                        if key in data and data[key]:
                            return data[key]
                except:
                    pass
            
            return None
            
        except Exception as e:
            self.logger.warning(f"[{self.name}] 直接模式异常: {e}")
            return None
