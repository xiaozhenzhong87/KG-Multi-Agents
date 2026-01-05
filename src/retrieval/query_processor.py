"""
查询处理模块
"""
import logging
import re
from typing import List, Dict, Any, Optional
from ..core.models import QueryResult
from .retriever import MedicalRetriever

logger = logging.getLogger(__name__)

class QueryProcessor:
    """查询处理器"""
    
    def __init__(self):
        self.retriever = MedicalRetriever()
    
    def process_query(self, query: str) -> QueryResult:
        """处理查询"""
        try:
            # 预处理查询
            processed_query = self._preprocess_query(query)
            
            # 执行检索
            result = self.retriever.retrieve(processed_query)
            
            # 后处理结果
            result = self._postprocess_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}")
            raise
    
    def _preprocess_query(self, query: str) -> str:
        """预处理查询"""
        # 去除多余空格
        query = re.sub(r'\s+', ' ', query.strip())
        return query
    
    def _postprocess_result(self, result: QueryResult) -> QueryResult:
        """后处理结果"""
        # 可以在这里添加结果过滤、排序等逻辑
        return result
