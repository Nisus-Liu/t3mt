# -*- coding: utf-8 -*-
"""
仿油猴子解析器
"""
from .base import BaseParser
from .jx789 import JX789Parser

# 注册所有解析器
ALL_PARSERS = [
    JX789Parser,
]

__all__ = ['BaseParser', 'JX789Parser', 'ALL_PARSERS']
