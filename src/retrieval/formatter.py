# 创建 src/retrieval/formatter.py
"""
格式化输出模块
"""
import logging
from typing import List, Dict, Any

from .multi_layer_retriever import PrivateLayerResult, PublicLayerResult
from .pagerank_retriever import PageRankResult

logger = logging.getLogger(__name__)

from ..core.umls_mapping import UMLS_SEMANTIC_TYPE_MAPPING

class ContextFormatter:
    """上下文格式化器"""
    
    def _get_semantic_type_name(self, semantic_type_id: str) -> str:
        """
        获取UMLS语义类型的人类可读名称
        
        Args:
            semantic_type_id: 语义类型ID (如 "T047")
            
        Returns:
            str: 人类可读的类型名称
        """
        return UMLS_SEMANTIC_TYPE_MAPPING.get(semantic_type_id, semantic_type_id)
    
    def format_private_layer_for_prompt(self, private_result: PrivateLayerResult) -> str:
        """
        格式化私有层信息用于提示
        
        Args:
            private_result: 私有层结果
            
        Returns:
            str: 格式化的私有层信息
        """
        if not private_result.nodes:
            return "**Private Layer Data:** No data available\n"
        
        parts = ["**Private Layer Data:**"]
        parts.append(f"- Total Nodes: {len(private_result.nodes)}")
        parts.append(f"- Reasoning Chains: {len(private_result.reasoning_chains)}")
        parts.append("")
        
        # 按类型分组节点
        type_groups = {}
        for node in private_result.nodes:
            node_type = node.get('type', 'Unknown')
            if node_type not in type_groups:
                type_groups[node_type] = []
            type_groups[node_type].append(node)
        
        for node_type, nodes in type_groups.items():
            parts.append(f"**{node_type} Nodes:**")
            for node in nodes[:10]:  # 限制显示数量
                parts.append(f"- {node['name']} (ID: {node['internal_id']})")
                # 添加关键属性
                props = node.get('properties', {})
                if props.get('value') is not None:
                    parts.append(f"  - Value: {props['value']} {props.get('unit', '')}")
                if props.get('reference_range'):
                    parts.append(f"  - Reference: {props['reference_range']}")
                if props.get('score') is not None:
                    parts.append(f"  - Score: {props['score']}")
            parts.append("")
        
        return "\n".join(parts)

    def format_public_layer_for_prompt(self, public_result: PublicLayerResult) -> str:
        """
        格式化公有层信息用于提示
        
        Args:
            public_result: 公有层结果
            
        Returns:
            str: 格式化的公有层信息
        """
        if not public_result.concepts:
            return "**Public Layer Data:** No UMLS concepts available\n"
        
        parts = ["**Public Layer Data:**"]
        parts.append(f"- Total Concepts: {len(public_result.concepts)}")
        parts.append(f"- Reasoning Chains: {len(public_result.reasoning_chains)}")
        parts.append("")
        
        # 显示UMLS概念
        parts.append("**UMLS Concepts:**")
        for concept in public_result.concepts[:15]:  # 限制显示数量
            concept_type = concept.get('type', 'Unknown')
            # 获取人类可读的语义类型名称
            semantic_type_name = self._get_semantic_type_name(concept_type)
            parts.append(f"- {concept['name']} (Type: {semantic_type_name}, CUI: {concept.get('cui', 'N/A')})")
            # 添加关键属性
            props = concept.get('properties', {})
            if props.get('definition'):
                parts.append(f"  - Definition: {props['definition'][:100]}...")
            if props.get('semantic_type'):
                semantic_type_id = props['semantic_type']
                semantic_type_name = self._get_semantic_type_name(semantic_type_id)
                parts.append(f"  - Semantic Type: {semantic_type_name} ({semantic_type_id})")
        parts.append("")
        
        return "\n".join(parts)

    def format_cross_layer_chains_for_prompt(self, cross_chains: List[Dict]) -> str:
        """
        格式化跨层推理链用于提示
        
        Args:
            cross_chains: 跨层推理链列表
            
        Returns:
            str: 格式化的跨层推理链信息
        """
        if not cross_chains:
            return "**Cross-Layer Associations:** No associations found\n"
        
        parts = ["**Cross-Layer Associations:**"]
        parts.append(f"- Total Associations: {len(cross_chains)}")
        parts.append("")
        
        for chain in cross_chains[:10]:  # 限制显示数量
            parts.append(f"**Association {chain['chain_id']}:**")
            parts.append(f"- Private Entity: {chain['private_node']['name']}")
            parts.append(f"- Public Concept: {chain['public_concept']['name']}")
            parts.append(f"- Similarity: {chain['similarity']:.3f}")
            parts.append(f"- Relation Type: {chain['relation_type']}")
            
            # 添加测试结果信息
            if 'test_value' in chain:
                parts.append(f"- Test Value: {chain['test_value']} {chain.get('unit', '')}")
                if chain.get('reference_range'):
                    parts.append(f"- Reference Range: {chain['reference_range']}")
            
            # 添加评估信息
            if 'score' in chain:
                parts.append(f"- Assessment Score: {chain['score']}")
                if chain.get('activity_level'):
                    parts.append(f"- Activity Level: {chain['activity_level']}")
            
            parts.append("")
        
        return "\n".join(parts)

    def format_structured_context(self, query: str, private_result: PrivateLayerResult, 
                                public_result: PublicLayerResult, 
                                cross_chains: List[Dict]) -> str:
        """
        生成结构化的上下文信息
        
        Args:
            query: 用户查询
            private_result: 私有层结果
            public_result: 公有层结果
            cross_chains: 跨层推理链
            
        Returns:
            str: 结构化的上下文字符串
        """
        context_parts = []
        
        # 添加查询信息
        context_parts.append(f"**User Query:** {query}")
        context_parts.append("")
        
        # 添加私有层信息
        private_formatted = self.format_private_layer_for_prompt(private_result)
        context_parts.append(private_formatted)
        
        # 添加公有层信息
        public_formatted = self.format_public_layer_for_prompt(public_result)
        context_parts.append(public_formatted)
        
        # 添加跨层推理链信息
        cross_formatted = self.format_cross_layer_chains_for_prompt(cross_chains)
        context_parts.append(cross_formatted)
        
        return "\n".join(context_parts)
    
    def format_pagerank_result_for_prompt(self, pagerank_result: PageRankResult) -> str:
        """
        格式化PageRank检索结果用于提示
        
        Args:
            pagerank_result: PageRank检索结果
            
        Returns:
            str: 格式化的PageRank结果信息
        """
        if not pagerank_result.nodes:
            return "**PageRank Retrieval Results:** No relevant entities found\n"
        
        parts = ["**PageRank Retrieval Results:**"]
        parts.append(f"- Total Entities: {len(pagerank_result.nodes)}")
        parts.append(f"- Total Relationships: {len(pagerank_result.relationships)}")
        parts.append("")
        
        # 按PageRank分数排序（如果可用）
        sorted_nodes = sorted(
            pagerank_result.nodes, 
            key=lambda x: x.get('pagerank_score', 0), 
            reverse=True
        )
        
        # 显示实体信息
        parts.append("**Top Relevant Entities (sorted by PageRank score):**")
        for i, node in enumerate(sorted_nodes[:20], 1):  # 限制显示前20个
            node_type = node.get('type', node.get('entity_type', 'Unknown'))
            node_name = node.get('name', 'Unknown')
            pagerank_score = node.get('pagerank_score', 0)
            cui = node.get('cui', 'N/A')
            
            parts.append(f"{i}. {node_name}")
            parts.append(f"   - Type: {node_type}")
            if cui != 'N/A':
                parts.append(f"   - CUI: {cui}")
            if pagerank_score > 0:
                parts.append(f"   - PageRank Score: {pagerank_score:.6f}")
            
            # 添加关键属性
            props = node.get('properties', {})
            if props.get('definition'):
                parts.append(f"   - Definition: {props['definition'][:150]}...")
            parts.append("")
        
        # 显示关系信息
        if pagerank_result.relationships:
            parts.append("**Key Relationships:**")
            # 按关系类型分组
            rel_groups = {}
            for rel in pagerank_result.relationships[:30]:  # 限制显示前30个关系
                rel_type = rel.get('type', 'RELATED_TO')
                if rel_type not in rel_groups:
                    rel_groups[rel_type] = []
                rel_groups[rel_type].append(rel)
            
            for rel_type, rels in list(rel_groups.items())[:10]:  # 限制关系类型数量
                # 将关系类型转换为更可读的格式（如果有下划线，替换为空格）
                rel_type_display = rel_type.replace('_', ' ').title()
                parts.append(f"**{rel_type_display}:**")
                for rel in rels[:5]:  # 每种类型最多显示5个
                    # 优先使用实体名称，如果没有则使用ID
                    source_name = rel.get('source_name', rel.get('source', 'Unknown'))
                    target_name = rel.get('target_name', rel.get('target', 'Unknown'))
                    parts.append(f"  - {source_name} --[{rel_type_display}]--> {target_name}")
                parts.append("")
        
        return "\n".join(parts)
    
    def format_structured_context_from_pagerank(self, query: str, 
                                               pagerank_result: PageRankResult) -> str:
        """
        从PageRank结果生成结构化的上下文信息
        
        Args:
            query: 用户查询
            pagerank_result: PageRank检索结果
            
        Returns:
            str: 结构化的上下文字符串
        """
        context_parts = []
        
        # 添加查询信息
        context_parts.append(f"**User Query:** {query}")
        context_parts.append("")
        
        # 添加PageRank检索结果
        pagerank_formatted = self.format_pagerank_result_for_prompt(pagerank_result)
        context_parts.append(pagerank_formatted)
        
        return "\n".join(context_parts)