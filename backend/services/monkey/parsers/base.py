# -*- coding: utf-8 -*-
"""
仿油猴子解析器基类
每个解析接口对应一个子类实现
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from utils.logger import logger


class BaseParser(ABC):
    """仿油猴子解析器基类"""

    # 解析器名称（如"789解析"）
    name: str = "未命名解析器"

    # 解析接口地址
    api_url: str = ""

    # 是否可用
    available: bool = True

    def __init__(self):
        self.logger = logger

    @abstractmethod
    def get_m3u8_url(self, video_url: str) -> Optional[str]:
        """
        调用解析接口，返回解密后的 M3U8 URL

        Args:
            video_url: 视频页面 URL

        Returns:
            解密后的 M3U8 URL，解析失败返回 None
        """
        pass

    def parse(self, video_url: str) -> Tuple[bool, str]:
        """
        解析视频 URL，返回 M3U8 地址

        Args:
            video_url: 视频页面 URL

        Returns:
            (成功标志, M3U8 URL 或错误信息)
        """
        try:
            m3u8_url = self.get_m3u8_url(video_url)
            if m3u8_url:
                self.logger.info(f"[{self.name}] 解析成功: {video_url} -> {m3u8_url[:80]}...")
                return True, m3u8_url
            else:
                self.logger.warning(f"[{self.name}] 解析返回空: {video_url}")
                return False, "解析返回空"
        except Exception as e:
            self.logger.error(f"[{self.name}] 解析异常: {video_url}, 错误: {e}")
            return False, str(e)

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} available={self.available}>"
