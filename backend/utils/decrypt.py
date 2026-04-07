# -*- coding: utf-8 -*-
"""
AES 解密工具
用于解密仿油猴子解析接口返回的加密 M3U8 URL
"""
import base64
from Crypto.Cipher import AES


class AESTool:
    """AES-128-CBC 解密工具"""

    # 789 解析器专用密钥
    JX789_KEY = b'ARTPLAYERliUlanG'
    JX789_IV = b'ArtplayerliUlanG'

    @staticmethod
    def decrypt_aes_cbc(encrypted_b64: str, key: bytes = None, iv: bytes = None) -> str:
        """
        AES-128-CBC 解密

        Args:
            encrypted_b64: base64 编码的加密字符串
            key: AES 密钥（默认为 789 解析器密钥）
            iv: AES IV（默认为 789 解析器 IV）

        Returns:
            解密后的明文字符串
        """
        if key is None:
            key = AESTool.JX789_KEY
        if iv is None:
            iv = AESTool.JX789_IV

        encrypted = base64.b64decode(encrypted_b64)
        decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted)

        # 去除 PKCS7 padding
        pad_len = decrypted[-1]
        if pad_len <= 16:
            decrypted = decrypted[:-pad_len]

        return decrypted.decode('utf-8')

    @staticmethod
    def decrypt_jx789(encrypted_b64: str) -> str:
        """
        解密 789 解析器返回的加密 URL

        Args:
            encrypted_b64: base64 编码的加密字符串

        Returns:
            解密后的 M3U8 URL
        """
        return AESTool.decrypt_aes_cbc(
            encrypted_b64,
            AESTool.JX789_KEY,
            AESTool.JX789_IV
        )
