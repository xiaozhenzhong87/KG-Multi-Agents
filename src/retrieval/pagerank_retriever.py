"""
基于PageRank算法的检索模块
使用Neo4j原生Cypher实现PageRank，不依赖NetworkX或GDS库
"""
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from neo4j import Driver

from ..core.database import db_manager
from ..config.settings import settings
from ..core.umls_mapping import UMLS_SEMANTIC_TYPE_MAPPING

logger = logging.getLogger(__name__)

@dataclass
class PageRankResult:
    """PageRank检索结果"""
    nodes: List[Dict] = None
    relationships: List[Dict] = None
    
    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []
        if self.relationships is None:
            self.relationships = []

class PageRankRetriever:
    """基于PageRank的检索器"""
    
    def __init__(self):
        self.damping_factor = settings.PAGERANK_DAMPING_FACTOR
        self.max_iterations = settings.PAGERANK_MAX_ITERATIONS
        self.tolerance = settings.PAGERANK_TOLERANCE
        self.max_results = settings.PAGERANK_MAX_RESULTS
        self.use_gds = settings.PAGERANK_USE_GDS
        
        # Personalized PageRank配置
        self.use_personalized_pagerank = settings.USE_PERSONALIZED_PAGERANK
        self.use_pagerank_retrieval = settings.USE_PAGERANK_RETRIEVAL
        
        # 子图构建配置
        self.enable_subgraph_limit = settings.PAGERANK_ENABLE_SUBGRAPH_LIMIT
        self.subgraph_max_depth = settings.PAGERANK_SUBGRAPH_MAX_DEPTH
        self.subgraph_max_nodes_per_level = settings.PAGERANK_SUBGRAPH_MAX_NODES_PER_LEVEL
        self.subgraph_max_total_nodes = settings.PAGERANK_SUBGRAPH_MAX_TOTAL_NODES
        
        # 初始节点查找配置
        self.initial_nodes_per_entity = settings.PAGERANK_INITIAL_NODES_PER_ENTITY
        self.initial_nodes_max_total = settings.PAGERANK_INITIAL_NODES_MAX_TOTAL
        self.use_query_fallback = settings.PAGERANK_USE_QUERY_FALLBACK
    
    def retrieve(self, query: str, graph: Driver = None, seed_entities: List[str] = None, 
                 max_results: int = None) -> PageRankResult:
        """
        使用PageRank算法进行检索
        
        Args:
            query: 查询字符串
            graph: Neo4j图数据库连接对象（如果为None则使用db_manager）
            seed_entities: LLM提取的种子实体列表（如果提供，将优先使用这些实体查找初始节点）
            max_results: 最大返回结果数（如果为None则使用配置文件中的PAGERANK_MAX_RESULTS）
            
        Returns:
            PageRankResult: 检索结果
        """
        logger.info(f'开始PageRank检索: {query}')
        if seed_entities:
            logger.info(f'使用LLM提取的种子实体: {seed_entities}')
        
        if graph is None:
            db_manager.connect()
            graph = db_manager.driver
        
        result = PageRankResult()
        
        try:
            # 步骤1: 根据query或seed_entities查找初始节点集合
            initial_nodes = self._find_initial_nodes(query, graph, seed_entities=seed_entities)
            
            if not initial_nodes:
                logger.warning(f'未找到与查询相关的初始节点: {query}')
                return result
            
            logger.info(f'找到 {len(initial_nodes)} 个初始节点')
            
            # 步骤2: 构建子图（包含初始节点及其邻居）
            subgraph_nodes = self._build_subgraph(initial_nodes, graph)
            
            logger.info(f'子图包含 {len(subgraph_nodes)} 个节点')
            
            # 步骤3: 计算PageRank分数（根据配置选择PPR或PR）
            if self.use_personalized_pagerank:
                logger.info('使用Personalized PageRank (PPR)')
                pagerank_scores = self._calculate_personalized_pagerank(subgraph_nodes, initial_nodes, graph)
            else:
                logger.info('使用标准PageRank (PR)')
                pagerank_scores = self._calculate_pagerank(subgraph_nodes, graph)
            
            # 步骤4: 根据PageRank分数排序并获取top-k节点
            # 如果提供了max_results参数，使用它；否则使用配置中的值
            effective_max_results = max_results if max_results is not None else self.max_results
            logger.info(f'使用max_results={effective_max_results} 选择Top-K节点')
            top_nodes = self._get_top_nodes_by_pagerank(pagerank_scores, graph, effective_max_results)
            
            # 步骤5: 获取这些节点的关系
            result.nodes = top_nodes
            result.relationships = self._get_relationships(top_nodes, graph)
            
            logger.info(f'PageRank检索完成，返回 {len(result.nodes)} 个节点和 {len(result.relationships)} 个关系')
            
            return result
            
        except Exception as e:
            logger.error(f'PageRank检索过程中发生错误: {e}')
            return result
    
    def _find_initial_nodes(self, query: str, graph: Driver, seed_entities: List[str] = None) -> List[str]:
        """
        根据query或seed_entities查找初始节点集合
        
        Args:
            query: 查询字符串
            graph: Neo4j图数据库连接对象
            seed_entities: LLM提取的种子实体列表（如果提供，将优先使用这些实体）
            
        Returns:
            List[str]: 节点ID列表
        """
        initial_nodes = []
        found_node_ids = set()  # 用于去重
        
        # 如果提供了seed_entities，优先使用这些实体进行匹配
        if seed_entities:
            logger.info(f'使用种子实体查找初始节点: {seed_entities}')
            for entity in seed_entities:
                # 检查是否已达到总节点数上限
                if len(initial_nodes) >= self.initial_nodes_max_total:
                    logger.info(f'已达到初始节点总数上限 ({self.initial_nodes_max_total})，停止查找')
                    break
                
                # 记录当前实体已找到的节点数
                entity_node_count = 0
                
                # 对每个实体，尝试多种匹配方式
                # 1. 精确匹配
                # 2. 包含匹配（不区分大小写）
                # 3. 模糊匹配（处理可能的变体）
                
                queries_to_try = [
                    # 精确匹配
                    """
                    MATCH (n:Entity)
                    WHERE n.name = $entity
                    AND (n.namespace = 'umls_kg' OR n.namespace IS NULL)
                    RETURN elementId(n) as node_id, n.name as name, n.id as id
                    LIMIT $limit
                    """,
                    # 包含匹配（不区分大小写）
                    """
                    MATCH (n:Entity)
                    WHERE toLower(n.name) CONTAINS toLower($entity)
                    AND (n.namespace = 'umls_kg' OR n.namespace IS NULL)
                    RETURN elementId(n) as node_id, n.name as name, n.id as id
                    LIMIT $limit
                    """,
                    # 反向包含匹配（实体名称包含在节点名称中）
                    """
                    MATCH (n:Entity)
                    WHERE toLower($entity) CONTAINS toLower(n.name) AND size(n.name) > 2
                    AND (n.namespace = 'umls_kg' OR n.namespace IS NULL)
                    RETURN elementId(n) as node_id, n.name as name, n.id as id
                    LIMIT $limit
                    """
                ]
                
                for query_str in queries_to_try:
                    # 检查是否已达到该实体的节点数上限
                    if entity_node_count >= self.initial_nodes_per_entity:
                        break
                    
                    # 检查是否已达到总节点数上限
                    if len(initial_nodes) >= self.initial_nodes_max_total:
                        break
                    
                    # 计算还可以添加的节点数
                    remaining_for_entity = self.initial_nodes_per_entity - entity_node_count
                    remaining_total = self.initial_nodes_max_total - len(initial_nodes)
                    limit = min(remaining_for_entity, remaining_total)
                    
                    try:
                        with graph.session() as session:
                            result = session.run(query_str, {
                                "entity": entity,
                                "limit": limit
                            })
                            for record in result:
                                # 再次检查上限（可能在循环中已到达）
                                if len(initial_nodes) >= self.initial_nodes_max_total:
                                    break
                                if entity_node_count >= self.initial_nodes_per_entity:
                                    break
                                
                                node_id = record['node_id']
                                if node_id not in found_node_ids:
                                    found_node_ids.add(node_id)
                                    initial_nodes.append(node_id)
                                    entity_node_count += 1
                                    logger.debug(f'通过实体"{entity}"找到初始节点: {record["name"]} (ID: {node_id})')
                    except Exception as e:
                        logger.warning(f'使用实体"{entity}"查找节点时发生错误: {e}')
                
                logger.debug(f'实体"{entity}"找到 {entity_node_count} 个节点')
        
        # 如果没有seed_entities或通过seed_entities找到的节点太少，尝试使用原始query（如果启用）
        if self.use_query_fallback and (not seed_entities or len(initial_nodes) < 3):
            logger.info(f'使用原始查询查找初始节点（作为补充）: {query}')
            
            # 计算还可以添加的节点数
            remaining_total = self.initial_nodes_max_total - len(initial_nodes)
            if remaining_total > 0:
                query_str = """
                MATCH (n:Entity)
                WHERE toLower(n.name) CONTAINS toLower($query)
                AND (n.namespace = 'umls_kg' OR n.namespace IS NULL)
                RETURN elementId(n) as node_id, n.name as name, n.id as id
                LIMIT $limit
                """
                
                try:
                    with graph.session() as session:
                        result = session.run(query_str, {
                            "query": query,
                            "limit": remaining_total
                        })
                        for record in result:
                            if len(initial_nodes) >= self.initial_nodes_max_total:
                                break
                            node_id = record['node_id']
                            if node_id not in found_node_ids:
                                found_node_ids.add(node_id)
                                initial_nodes.append(node_id)
                                logger.debug(f'通过查询找到初始节点: {record["name"]} (ID: {node_id})')
                except Exception as e:
                    logger.error(f'查找初始节点时发生错误: {e}')
        
        logger.info(f'总共找到 {len(initial_nodes)} 个初始节点')
        return initial_nodes
    
    def _build_subgraph(self, initial_nodes: List[str], graph: Driver) -> Set[str]:
        """
        构建子图：包含初始节点及其多跳邻居
        
        Args:
            initial_nodes: 初始节点ID列表
            graph: Neo4j图数据库连接对象
            
        Returns:
            Set[str]: 子图中所有节点的ID集合
        """
        subgraph_nodes = set(initial_nodes)
        
        # 根据配置决定是否启用限制
        if not self.enable_subgraph_limit:
            logger.info('子图限制已禁用，将构建完整子图（不限制深度和节点数）')
            max_depth = 3  # 使用默认的3跳深度
            max_nodes_per_level = None  # 不限制每层节点数
            max_total_nodes = None  # 不限制总节点数
        else:
            logger.info(f'子图限制已启用: 最大深度={self.subgraph_max_depth}, 每层最大节点数={self.subgraph_max_nodes_per_level}, 总节点数上限={self.subgraph_max_total_nodes}')
            max_depth = self.subgraph_max_depth
            max_nodes_per_level = self.subgraph_max_nodes_per_level
            max_total_nodes = self.subgraph_max_total_nodes
        
        # 使用广度优先搜索扩展子图
        current_level = set(initial_nodes)
        
        for depth in range(max_depth):
            # 检查是否已达到总节点数上限（仅在启用限制时）
            if self.enable_subgraph_limit and max_total_nodes and len(subgraph_nodes) >= max_total_nodes:
                logger.info(f'子图已达到最大节点数限制 ({max_total_nodes})，停止扩展')
                break
            
            if not current_level:
                break
            
            next_level = set()
            
            # 构建查询语句
            if self.enable_subgraph_limit and max_nodes_per_level:
                # 启用限制时，使用LIMIT限制每层查询的节点数
                query_str = """
                UNWIND $node_ids as node_id
                MATCH (n:Entity)
                WHERE elementId(n) = node_id
                MATCH (n)-[r]-(neighbor:Entity)
                WHERE (neighbor.namespace = 'umls_kg' OR neighbor.namespace IS NULL)
                RETURN DISTINCT elementId(neighbor) as neighbor_id
                LIMIT $max_nodes_per_level
                """
            else:
                # 未启用限制时，不限制查询结果数
                query_str = """
                UNWIND $node_ids as node_id
                MATCH (n:Entity)
                WHERE elementId(n) = node_id
                MATCH (n)-[r]-(neighbor:Entity)
                WHERE (neighbor.namespace = 'umls_kg' OR neighbor.namespace IS NULL)
                RETURN DISTINCT elementId(neighbor) as neighbor_id
                """
            
            try:
                query_params = {"node_ids": list(current_level)}
                
                # 仅在启用限制时添加限制参数
                if self.enable_subgraph_limit and max_nodes_per_level:
                    remaining_nodes = max_total_nodes - len(subgraph_nodes) if max_total_nodes else max_nodes_per_level
                    max_nodes_this_level = min(max_nodes_per_level, remaining_nodes) if max_total_nodes else max_nodes_per_level
                    query_params["max_nodes_per_level"] = max_nodes_this_level
                
                with graph.session() as session:
                    result = session.run(query_str, query_params)
                    
                    for record in result:
                        # 检查是否已达到总节点数上限（仅在启用限制时）
                        if self.enable_subgraph_limit and max_total_nodes and len(subgraph_nodes) >= max_total_nodes:
                            break
                        
                        neighbor_id = record['neighbor_id']
                        if neighbor_id not in subgraph_nodes:
                            subgraph_nodes.add(neighbor_id)
                            next_level.add(neighbor_id)
                
                current_level = next_level
                logger.info(f'深度 {depth + 1}: 添加了 {len(next_level)} 个新节点，子图总节点数: {len(subgraph_nodes)}')
                
            except Exception as e:
                logger.error(f'构建子图时发生错误: {e}')
                break
        
        limit_info = f' (限制: {max_total_nodes})' if (self.enable_subgraph_limit and max_total_nodes) else ' (无限制)'
        logger.info(f'子图构建完成，总节点数: {len(subgraph_nodes)}{limit_info}')
        return subgraph_nodes
    
    def _calculate_pagerank(self, nodes: Set[str], graph: Driver) -> Dict[str, float]:
        """
        计算PageRank分数（使用Cypher实现，不依赖GDS）
        
        Args:
            nodes: 节点ID集合
            graph: Neo4j图数据库连接对象
            
        Returns:
            Dict[str, float]: 节点ID到PageRank分数的映射
        """
        if not nodes:
            return {}
        
        # 初始化PageRank分数
        pagerank = {node_id: 1.0 / len(nodes) for node_id in nodes}
        
        # 获取所有边的信息
        edges = self._get_edges(nodes, graph)
        
        # 计算每个节点的出度
        out_degrees = {}
        for source, target in edges:
            out_degrees[source] = out_degrees.get(source, 0) + 1
        
        # PageRank迭代
        for iteration in range(self.max_iterations):
            new_pagerank = {}
            
            # 计算新的PageRank分数
            for node_id in nodes:
                # 来自其他节点的贡献
                incoming_sum = 0.0
                
                # 找到所有指向当前节点的边
                for source, target in edges:
                    if target == node_id:
                        source_out_degree = out_degrees.get(source, 1)
                        if source_out_degree > 0:
                            incoming_sum += pagerank.get(source, 0) / source_out_degree
                
                # PageRank公式: PR(A) = (1-d) + d * sum(PR(B) / L(B))
                # 其中d是阻尼系数，L(B)是节点B的出度
                new_pagerank[node_id] = (1 - self.damping_factor) / len(nodes) + \
                                       self.damping_factor * incoming_sum
            
            # 检查收敛
            max_diff = max(abs(new_pagerank[node_id] - pagerank.get(node_id, 0)) 
                          for node_id in nodes)
            
            pagerank = new_pagerank
            
            if max_diff < self.tolerance:
                logger.info(f'PageRank在第 {iteration + 1} 次迭代后收敛')
                break
            
            if iteration % 5 == 0:
                logger.debug(f'PageRank迭代 {iteration + 1}/{self.max_iterations}, 最大差异: {max_diff:.6f}')
        
        # 归一化PageRank分数
        total_score = sum(pagerank.values())
        if total_score > 0:
            pagerank = {node_id: score / total_score for node_id, score in pagerank.items()}
        
        logger.info(f'PageRank计算完成，计算了 {len(pagerank)} 个节点的分数')
        
        return pagerank
    
    def _calculate_personalized_pagerank(self, nodes: Set[str], initial_nodes: List[str], 
                                        graph: Driver) -> Dict[str, float]:
        """
        计算Personalized PageRank分数
        
        Personalized PageRank与标准PageRank的区别：
        - 标准PageRank: teleportation概率均匀分布到所有节点
        - Personalized PageRank: teleportation概率根据reset probability分布（优先跳转到初始节点）
        
        Args:
            nodes: 节点ID集合
            initial_nodes: 初始节点ID列表（用于设置reset probability）
            graph: Neo4j图数据库连接对象
            
        Returns:
            Dict[str, float]: 节点ID到PageRank分数的映射
        """
        if not nodes:
            return {}
        
        # 计算reset probability
        # 初始节点的reset probability较高，其他节点较低
        reset_prob = {}
        initial_nodes_set = set(initial_nodes)
        
        # 初始节点的reset probability（可以根据需要调整权重）
        initial_weight = 1.0 / max(len(initial_nodes_set), 1) if initial_nodes_set else 0.0
        non_initial_weight = 0.0  # 非初始节点的reset probability为0（或可以设置一个很小的值）
        
        for node_id in nodes:
            if node_id in initial_nodes_set:
                reset_prob[node_id] = initial_weight
            else:
                reset_prob[node_id] = non_initial_weight
        
        # 归一化reset probability
        total_reset_prob = sum(reset_prob.values())
        if total_reset_prob > 0:
            reset_prob = {node_id: prob / total_reset_prob for node_id, prob in reset_prob.items()}
        else:
            # 如果没有初始节点，则均匀分布
            uniform_prob = 1.0 / len(nodes)
            reset_prob = {node_id: uniform_prob for node_id in nodes}
        
        logger.info(f'Personalized PageRank: {len(initial_nodes_set)} 个初始节点，'
                   f'reset probability总和: {sum(reset_prob.values()):.6f}')
        
        # 初始化PageRank分数
        pagerank = {node_id: 1.0 / len(nodes) for node_id in nodes}
        
        # 获取所有边的信息
        edges = self._get_edges(nodes, graph)
        
        # 计算每个节点的出度
        out_degrees = {}
        for source, target in edges:
            out_degrees[source] = out_degrees.get(source, 0) + 1
        
        # Personalized PageRank迭代
        for iteration in range(self.max_iterations):
            new_pagerank = {}
            
            # 计算新的PageRank分数
            for node_id in nodes:
                # 来自其他节点的贡献
                incoming_sum = 0.0
                
                # 找到所有指向当前节点的边
                for source, target in edges:
                    if target == node_id:
                        source_out_degree = out_degrees.get(source, 1)
                        if source_out_degree > 0:
                            incoming_sum += pagerank.get(source, 0) / source_out_degree
                
                # Personalized PageRank公式: 
                # PR(A) = (1-d) * reset_prob(A) + d * sum(PR(B) / L(B))
                # 其中d是阻尼系数，L(B)是节点B的出度，reset_prob(A)是节点A的reset probability
                new_pagerank[node_id] = (1 - self.damping_factor) * reset_prob.get(node_id, 0) + \
                                       self.damping_factor * incoming_sum
            
            # 检查收敛
            max_diff = max(abs(new_pagerank[node_id] - pagerank.get(node_id, 0)) 
                          for node_id in nodes)
            
            pagerank = new_pagerank
            
            if max_diff < self.tolerance:
                logger.info(f'Personalized PageRank在第 {iteration + 1} 次迭代后收敛')
                break
            
            if iteration % 5 == 0:
                logger.debug(f'Personalized PageRank迭代 {iteration + 1}/{self.max_iterations}, 最大差异: {max_diff:.6f}')
        
        # 归一化PageRank分数
        total_score = sum(pagerank.values())
        if total_score > 0:
            pagerank = {node_id: score / total_score for node_id, score in pagerank.items()}
        
        logger.info(f'Personalized PageRank计算完成，计算了 {len(pagerank)} 个节点的分数')
        
        return pagerank
    
    def _get_edges(self, nodes: Set[str], graph: Driver) -> List[tuple]:
        """
        获取子图中所有边的信息
        
        Args:
            nodes: 节点ID集合
            graph: Neo4j图数据库连接对象
            
        Returns:
            List[tuple]: (source_id, target_id) 元组列表
        """
        edges = []
        
        query_str = """
        UNWIND $node_ids as node_id
        MATCH (n:Entity)
        WHERE elementId(n) = node_id
        MATCH (n)-[r]->(target:Entity)
        WHERE elementId(target) IN $node_ids
        RETURN elementId(n) as source_id, elementId(target) as target_id
        """
        
        try:
            with graph.session() as session:
                result = session.run(query_str, {"node_ids": list(nodes)})
                for record in result:
                    source_id = record['source_id']
                    target_id = record['target_id']
                    edges.append((source_id, target_id))
        except Exception as e:
            logger.error(f'获取边信息时发生错误: {e}')
        
        return edges
    
    def _get_top_nodes_by_pagerank(self, pagerank_scores: Dict[str, float], 
                                   graph: Driver, max_results: int = None) -> List[Dict]:
        """
        根据PageRank分数获取top-k节点
        
        Args:
            pagerank_scores: 节点ID到PageRank分数的映射
            graph: Neo4j图数据库连接对象
            max_results: 最大返回结果数（如果为None则使用self.max_results）
            
        Returns:
            List[Dict]: 节点信息列表，按PageRank分数降序排列
        """
        # 按PageRank分数排序
        sorted_nodes = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 获取top-k节点
        effective_max_results = max_results if max_results is not None else self.max_results
        top_k = min(effective_max_results, len(sorted_nodes))
        top_node_ids = [node_id for node_id, _ in sorted_nodes[:top_k]]
        
        # 查询节点详细信息
        nodes_info = []
        
        if not top_node_ids:
            return nodes_info
        
        query_str = """
        UNWIND $node_ids as node_id
        MATCH (n:Entity)
        WHERE elementId(n) = node_id
        RETURN elementId(n) as element_id, n.id as id, n.name as name, 
               n.entity_type as entity_type, n.CUI as cui, n.namespace as namespace,
               properties(n) as properties
        """
        
        try:
            with graph.session() as session:
                result = session.run(query_str, {"node_ids": top_node_ids})
                for record in result:
                    node_id = record['element_id']
                    pagerank_score = pagerank_scores.get(node_id, 0.0)
                    
                    # 获取实体类型的人类可读名称
                    entity_type_id = record.get('entity_type', 'T071')
                    entity_type_name = UMLS_SEMANTIC_TYPE_MAPPING.get(entity_type_id, entity_type_id)
                    
                    # 构建节点数据
                    node_data = {
                        "internal_id": record.get('id') or f"neo4j_{node_id}",
                        "element_id": node_id,
                        "type": entity_type_name,
                        "entity_type": entity_type_id,
                        "name": record.get('name', 'Unknown'),
                        "cui": record.get('cui'),
                        "namespace": record.get('namespace', 'umls_kg'),
                        "pagerank_score": pagerank_score,
                        "properties": record.get('properties', {})
                    }
                    
                    nodes_info.append(node_data)
        except Exception as e:
            logger.error(f'获取节点信息时发生错误: {e}')
        
        return nodes_info
    
    def _get_relationships(self, nodes: List[Dict], graph: Driver) -> List[Dict]:
        """
        获取节点之间的关系
        
        Args:
            nodes: 节点信息列表
            graph: Neo4j图数据库连接对象
            
        Returns:
            List[Dict]: 关系信息列表
        """
        relationships = []
        
        if not nodes:
            return relationships
        
        node_ids = [node['element_id'] for node in nodes]
        
        query_str = """
        UNWIND $node_ids as node_id
        MATCH (n:Entity)
        WHERE elementId(n) = node_id
        MATCH (n)-[r]->(target:Entity)
        WHERE elementId(target) IN $node_ids
        RETURN elementId(n) as source_id, elementId(target) as target_id,
               type(r) as rel_type, properties(r) as rel_properties
        """
        
        try:
            with graph.session() as session:
                result = session.run(query_str, {"node_ids": node_ids})
                for record in result:
                    source_id = record['source_id']
                    target_id = record['target_id']
                    
                    # 找到对应的节点信息
                    source_node = next((n for n in nodes if n['element_id'] == source_id), None)
                    target_node = next((n for n in nodes if n['element_id'] == target_id), None)
                    
                    if source_node and target_node:
                        rel_data = {
                            "source": source_node['internal_id'],
                            "target": target_node['internal_id'],
                            "source_name": source_node.get('name', source_node['internal_id']),  # 添加实体名称
                            "target_name": target_node.get('name', target_node['internal_id']),  # 添加实体名称
                            "type": record.get('rel_type', 'RELATED_TO'),
                            "properties": record.get('rel_properties', {})
                        }
                        relationships.append(rel_data)
        except Exception as e:
            logger.error(f'获取关系信息时发生错误: {e}')
        
        return relationships

