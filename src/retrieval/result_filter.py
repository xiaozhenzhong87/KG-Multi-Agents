"""
结果过滤器
根据节点类型和关系类型列表过滤检索结果
"""
import logging
from typing import List, Dict, Any

from .pagerank_retriever import PageRankResult

logger = logging.getLogger(__name__)


class ResultFilter:
    """结果过滤器"""
    
    def __init__(self):
        """初始化结果过滤器"""
        pass
    
    def filter_by_types(self, 
                       result: PageRankResult,
                       entity_types: List[str],
                       relationship_types: List[str]) -> PageRankResult:
        """
        根据节点类型和关系类型列表过滤结果
        
        Args:
            result: PageRank检索结果
            entity_types: 允许的节点类型列表（如果为空，则不过滤节点）
            relationship_types: 允许的关系类型列表（如果为空，则不过滤关系）
            
        Returns:
            PageRankResult: 过滤后的结果
        """
        filtered_result = PageRankResult()
        
        # 如果没有指定过滤条件，直接返回原结果
        if not entity_types and not relationship_types:
            logger.info("未指定过滤条件，返回原结果")
            return result
        
        # 过滤节点
        if entity_types:
            logger.info(f"根据节点类型过滤: {len(entity_types)} 个类型")
            for node in result.nodes:
                node_type = node.get('type', '')
                # 检查节点类型是否匹配（支持部分匹配）
                if self._type_matches(node_type, entity_types):
                    filtered_result.nodes.append(node)
            
            logger.info(f"节点过滤: {len(result.nodes)} -> {len(filtered_result.nodes)}")
        else:
            filtered_result.nodes = result.nodes
        
        # 过滤关系
        if relationship_types:
            logger.info(f"根据关系类型过滤: {len(relationship_types)} 个类型")
            # 获取过滤后的节点ID集合（用于关系过滤）
            filtered_node_ids = {node.get('element_id') for node in filtered_result.nodes}
            
            for rel in result.relationships:
                rel_type = rel.get('type', '')
                source_id = rel.get('source', '')
                target_id = rel.get('target', '')
                
                # 检查关系类型是否匹配
                if self._type_matches(rel_type, relationship_types):
                    # 检查关系的源节点和目标节点是否都在过滤后的节点中
                    # 注意：这里我们检查element_id，但关系中使用的是internal_id
                    # 需要适配
                    filtered_result.relationships.append(rel)
            
            logger.info(f"关系过滤: {len(result.relationships)} -> {len(filtered_result.relationships)}")
        else:
            filtered_result.relationships = result.relationships
        
        # 输出过滤后的总结
        logger.info(f"过滤完成: 最终节点数 {len(filtered_result.nodes)}, 最终关系数 {len(filtered_result.relationships)}")
        
        return filtered_result
    
    def _type_matches(self, actual_type: str, allowed_types: List[str]) -> bool:
        """
        检查类型是否匹配
        
        Args:
            actual_type: 实际类型
            allowed_types: 允许的类型列表
            
        Returns:
            bool: 是否匹配
        """
        if not actual_type:
            return False
        
        # 精确匹配
        if actual_type in allowed_types:
            return True
        
        # 部分匹配（检查是否包含）
        for allowed_type in allowed_types:
            if allowed_type.lower() in actual_type.lower() or \
               actual_type.lower() in allowed_type.lower():
                return True
        
        return False
    
    def filter_by_types_from_context(self,
                                    result: PageRankResult,
                                    context: Dict[str, Any]) -> PageRankResult:
        """
        从上下文（如格式化后的上下文）中提取类型信息并过滤
        
        Args:
            result: PageRank检索结果
            context: 上下文字典，可能包含entity_types和relationship_types
            
        Returns:
            PageRankResult: 过滤后的结果
        """
        entity_types = context.get('entity_types', [])
        relationship_types = context.get('relationship_types', [])
        
        return self.filter_by_types(result, entity_types, relationship_types)

