# 创建 src/retrieval/cross_layer_connector.py
"""
跨层关联模块
"""
import logging
from typing import List, Dict, Any
from difflib import SequenceMatcher

from .multi_layer_retriever import PrivateLayerResult, PublicLayerResult

logger = logging.getLogger(__name__)

class CrossLayerConnector:
    """跨层关联器"""
    
    def build_cross_layer_chains(self, private_result: PrivateLayerResult, 
                               public_result: PublicLayerResult) -> List[Dict]:
        """
        构建跨层推理链，包含所有节点属性信息
        
        Args:
            private_result: 私有层结果
            public_result: 公有层结果
            
        Returns:
            List[Dict]: 跨层推理链列表
        """
        cross_chains = []
        
        logging.info(f"开始构建跨层推理链: 私有层节点数={len(private_result.nodes)}, 公有层概念数={len(public_result.concepts)}")
        
        # 遍历所有私有层节点，不仅仅是推理链中的节点
        for private_node in private_result.nodes:
            # 查找相关的公有层概念
            for public_concept in public_result.concepts:
                # 基于名称相似度匹配
                similarity = self._calculate_similarity(
                    private_node['name'].lower(), 
                    public_concept['name'].lower()
                )
                
                # 添加调试信息
                if similarity > 0.01:  # 记录所有有相似度的匹配
                    logging.debug(f"相似度匹配: '{private_node['name']}' vs '{public_concept['name']}' = {similarity:.3f}")
                
                if similarity > 0.05:  # 进一步降低相似度阈值
                    # 构建跨层推理链
                    cross_chain = {
                        "chain_id": f"cross_{private_node['internal_id']}_{public_concept['internal_id']}",
                        "private_node": private_node,
                        "public_concept": public_concept,
                        "similarity": similarity,
                        "relation_type": "SEMANTIC_SIMILARITY",
                        "reasoning": f"私有层实体 '{private_node['name']}' 与公有层概念 '{public_concept['name']}' 语义相似"
                    }
                    
                    # 添加测试结果信息（如果存在）
                    if private_node.get('properties', {}).get('value') is not None:
                        cross_chain["test_value"] = private_node['properties']['value']
                        cross_chain["reference_range"] = private_node['properties'].get('reference_range')
                        cross_chain["unit"] = private_node['properties'].get('unit')
                        cross_chain["test_name"] = private_node['properties'].get('test_name')
                    
                    # 添加评估信息（如果存在）
                    if private_node.get('properties', {}).get('score') is not None:
                        cross_chain["score"] = private_node['properties']['score']
                        cross_chain["activity_level"] = private_node['properties'].get('activity_level')
                        cross_chain["assessment_note"] = private_node['properties'].get('assessment_note')
                    
                    cross_chains.append(cross_chain)
        
        # 按相似度排序
        cross_chains.sort(key=lambda x: x['similarity'], reverse=True)
        
        logging.info(f"构建了 {len(cross_chains)} 个跨层推理链")
        return cross_chains

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            float: 相似度分数 (0-1)
        """
        return SequenceMatcher(None, text1, text2).ratio()