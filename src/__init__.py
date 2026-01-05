"""
医疗知识图谱系统
"""
__version__ = "2.0.0"
__author__ = "zxz"
__email__ = "zxz@example.com"

# 导入主要模块
from .core import *
from .kg_builder import *
from .retrieval import *
# 延迟导入api，避免触发fastapi等不必要的依赖
try:
    from .api import *
except ImportError:
    pass
from .utils import *
from .config import settings

__all__ = [
    'settings',
    # 其他导出的模块会在各自的 __init__.py 中定义
]