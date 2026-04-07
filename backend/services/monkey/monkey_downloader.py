# -*- coding: utf-8 -*-
"""
仿油猴子下载器
封装完整下载流程：解析 → 获取playlist → 下载片段 → 合并 → MP4
"""
import os
import re
import time
import base64
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, Callable
from utils.logger import logger
from .parsers import ALL_PARSERS, BaseParser

# PNG 伪装头长度（每个片段前57字节是PNG头）
PNG_SKIP = 57

# 默认请求头
REF_BASE = "https://jiexi.789jiexi.icu:4433/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'Referer': REF_BASE,
}


class MonkeyDownloader:
    """
    仿油猴子下载器

    支持多解析器降级：
    1. 尝试第一个解析器
    2. 失败则尝试下一个
    3. 全部失败则返回错误
    """

    def __init__(self, parsers: list = None, concurrency: int = 12):
        """
        Args:
            parsers: 解析器列表（按优先级排序），默认为 ALL_PARSERS
            concurrency: 下载并发数
        """
        self.parsers = parsers or [p() for p in ALL_PARSERS]
        self.concurrency = concurrency

    def _fetch_m3u8(self, m3u8_url: str) -> Tuple[bool, str, int]:
        """
        获取 M3U8 playlist 内容

        Returns:
            (成功, 内容或错误信息, HTTP状态码)
        """
        try:
            resp = requests.get(m3u8_url, headers=HEADERS, timeout=15, allow_redirects=True)
            if resp.status_code == 200 and '#EXTM3U' in resp.text:
                return True, resp.text, 200
            elif resp.status_code == 200:
                return False, f"非M3U8内容: {resp.text[:200]}", 200
            else:
                return False, f"HTTP {resp.status_code}", resp.status_code
        except requests.RequestException as e:
            return False, f"请求异常: {e}", 0

    def _parse_segments(self, m3u8_content: str) -> Tuple[bool, list]:
        """
        解析 M3U8 playlist，提取所有片段 URL

        Returns:
            (成功, 片段URL列表)
        """
        try:
            segments = []
            for line in m3u8_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # 直接 URL
                if line.startswith('http'):
                    segments.append(line)
                # hls_video 伪装 URL（base64编码）
                elif 'hls_video' in line:
                    match = re.search(r'hls_video([A-Za-z0-9+/=]+)', line)
                    if match:
                        b64 = match.group(1).rstrip('~')
                        try:
                            pad = (4 - len(b64) % 4) % 4
                            decoded = base64.b64decode(b64 + '=' * pad).decode('utf-8')
                            segments.append(decoded)
                        except Exception:
                            continue

            # 去重（保持顺序）
            unique = list(dict.fromkeys(segments))
            return True, unique

        except Exception as e:
            return False, []

    def _download_segment(self, session: requests.Session, url: str, idx: int,
                         progress_cb: Callable = None) -> Tuple[Optional[bytes], int]:
        """
        下载单个片段，去除 PNG 伪装头

        Returns:
            (视频数据, 片段索引)
        """
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                return None, idx

            data = resp.content

            # 去除 PNG 伪装头
            if len(data) > PNG_SKIP and data[:4] == b'\x89PNG':
                return data[PNG_SKIP:], idx

            # 没有 PNG 头，直接返回
            return data, idx

        except Exception:
            return None, idx

    def _download_all_segments(self, segments: list,
                               progress_cb: Callable = None) -> Tuple[dict, list]:
        """
        多线程下载所有片段

        Returns:
            (成功片段字典 {索引: 数据}, 失败索引列表)
        """
        logger.info(f"[仿油猴子] 开始下载 {len(segments)} 个片段 (并发 {self.concurrency})")
        t0 = time.time()

        session = requests.Session()
        results, failed = {}, []

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            futures = {
                ex.submit(self._download_segment, session, url, i, progress_cb): i
                for i, url in enumerate(segments)
            }

            done = 0
            for future in as_completed(futures):
                data, idx = future.result()
                if data:
                    results[idx] = data
                else:
                    failed.append(idx)

                done += 1
                if done % 50 == 0 or done == len(segments):
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    logger.info(f"[仿油猴子] 下载进度: {done}/{len(segments)}, "
                               f"成功:{len(results)}, 失败:{len(failed)}, 速度:{rate:.1f}个/秒")

        elapsed = time.time() - t0
        logger.info(f"[仿油猴子] 下载完成: {len(results)}/{len(segments)} ({elapsed:.1f}s)")

        return results, failed

    def _merge_to_ts(self, results: dict, output_path: str) -> int:
        """
        将所有片段合并为 TS 文件

        Returns:
            文件大小（字节）
        """
        logger.info(f"[仿油猴子] 合并为 TS: {output_path}")

        with open(output_path, 'wb') as f:
            for i in sorted(results.keys()):
                f.write(results[i])

        size = os.path.getsize(output_path)
        logger.info(f"[仿油猴子] TS 文件: {size / 1024 / 1024:.1f} MB")
        return size

    def _convert_to_mp4(self, ts_path: str, mp4_path: str) -> Tuple[bool, int]:
        """
        ffmpeg 转换 TS → MP4

        Returns:
            (成功标志, 文件大小)
        """
        import subprocess

        logger.info(f"[仿油猴子] 转换 MP4: {mp4_path}")

        result = subprocess.run([
            'ffmpeg', '-i', ts_path,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y', mp4_path
        ], capture_output=True, text=True, timeout=7200)

        if result.returncode == 0:
            os.remove(ts_path)
            size = os.path.getsize(mp4_path)
            logger.info(f"[仿油猴子] ✅ MP4: {mp4_path} ({size / 1024 / 1024:.1f} MB)")
            return True, size
        else:
            logger.error(f"[仿油猴子] ffmpeg 失败: {result.stderr[:200]}")
            return False, 0

    def download(self, video_url: str, output_path: str,
                 progress_cb: Callable = None) -> Tuple[bool, str]:
        """
        完整下载流程

        Args:
            video_url: 视频页面 URL
            output_path: 输出文件路径（.mp4）
            progress_cb: 进度回调函数

        Returns:
            (成功标志, 输出文件路径或错误信息)
        """
        t_total = time.time()
        ts_path = output_path.replace('.mp4', '.ts')

        # ========== Step 1: 解析视频 URL ==========
        m3u8_url = None
        for parser in self.parsers:
            if not parser.available:
                continue

            logger.info(f"[仿油猴子] 尝试解析器: {parser.name}")
            success, result = parser.parse(video_url)

            if success:
                m3u8_url = result
                logger.info(f"[仿油猴子] ✅ {parser.name} 解析成功")
                break
            else:
                logger.warning(f"[仿油猴子] ❌ {parser.name} 失败: {result}，尝试下一个...")

        if not m3u8_url:
            return False, "所有解析器均失败"

        # ========== Step 2: 获取 M3U8 playlist ==========
        logger.info(f"[仿油猴子] 获取 M3U8 playlist...")
        success, content, status = self._fetch_m3u8(m3u8_url)
        if not success:
            return False, f"M3U8请求失败: {content}"

        # ========== Step 3: 解析片段 ==========
        logger.info(f"[仿油猴子] 解析片段...")
        success, segments = self._parse_segments(content)
        if not success or not segments:
            return False, "片段解析失败"

        logger.info(f"[仿油猴子] 共 {len(segments)} 个片段")

        # ========== Step 4: 下载片段 ==========
        results, failed = self._download_all_segments(segments, progress_cb)
        if not results:
            return False, "所有片段下载失败"

        # ========== Step 5: 合并 TS ==========
        self._merge_to_ts(results, ts_path)

        # ========== Step 6: 转换 MP4 ==========
        success, _ = self._convert_to_mp4(ts_path, output_path)

        total = time.time() - t_total
        if success:
            logger.info(f"[仿油猴子] 🎉 完成: {output_path} (总耗时: {total:.1f}s)")
            return True, output_path
        else:
            return False, "MP4转换失败，TS文件已保留"
