# 创建 src/retrieval/multi_layer_retriever.py
"""
多层级检索模块
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from neo4j import Driver

from ..core.database import db_manager
from ..config.settings import settings
from ..core.umls_mapping import UMLS_SEMANTIC_TYPE_MAPPING

logger = logging.getLogger(__name__)

@dataclass
class PrivateLayerResult:
    """私有层检索结果"""
    nodes: List[Dict] = None
    reasoning_chains: List[Dict] = None
    relationships: List[Dict] = None
    raw_records: List[Dict] = None  # 添加原始记录
    
    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []
        if self.reasoning_chains is None:
            self.reasoning_chains = []
        if self.relationships is None:
            self.relationships = []
        if self.raw_records is None:
            self.raw_records = []

@dataclass
class PublicLayerResult:
    """公有层检索结果"""
    nodes: List[Dict] = None
    concepts: List[Dict] = None
    reasoning_chains: List[Dict] = None
    relationships: List[Dict] = None
    
    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []
        if self.concepts is None:
            self.concepts = []
        if self.reasoning_chains is None:
            self.reasoning_chains = []
        if self.relationships is None:
            self.relationships = []

class MultiLayerRetriever:
    """多层级检索器"""
    
    def __init__(self):
        self.private_max_depth = getattr(settings, 'PRIVATE_GRAPH_MAX_DEPTH', 5)
        self.private_max_entities = getattr(settings, 'PRIVATE_GRAPH_MAX_ENTITIES', 50)
        self.umls_max_depth = getattr(settings, 'UMLS_GRAPH_MAX_DEPTH', 3)
        self.umls_max_concepts = getattr(settings, 'UMLS_GRAPH_MAX_CONCEPTS', 50)
    
    def _get_semantic_type_name(self, semantic_type_id: str) -> str:
        """获取UMLS语义类型的人类可读名称"""
        return UMLS_SEMANTIC_TYPE_MAPPING.get(semantic_type_id, semantic_type_id)
        self.similarity_threshold = getattr(settings, 'CROSS_GRAPH_SIMILARITY_THRESHOLD', 0.5)
    
    def retrieve_private_layer_complete(self, graph: Driver, patient_id: str, 
                                      max_depth: int = None, max_entities: int = None) -> PrivateLayerResult:
        """
        私有层完整遍历函数
        返回分离的推理链和节点属性
        
        Args:
            graph: Neo4j图数据库连接对象
            patient_id (str): 患者ID
            max_depth (int): 最大跳数深度
            max_entities (int): 最大实体数量
            
        Returns:
            PrivateLayerResult: 包含推理链和节点属性的私有层结果
        """
        if max_depth is None:
            max_depth = self.private_max_depth
        if max_entities is None:
            max_entities = self.private_max_entities
            
        logging.info(f'=== 私有层完整遍历 (最大跳数: {max_depth}, 最大实体数: {max_entities}) ===')
        
        result = PrivateLayerResult()
        
        if max_depth < 1:
            return result
        
        all_results = []
        seen_entities = set()
        
        # 为每个跳数分别查询
        for hop in range(1, max_depth + 1):
            # 修改查询策略：分别获取Test_Result、Test_Type和其他类型节点
            hop_query = f"""
            MATCH (patient:Entity)
            WHERE elementId(patient) = $patient_id
            WITH patient
            
            // 首先获取Test_Result类型的节点，确保获取所有属性
            MATCH path = (patient)-[*{hop}]-(related)
            WHERE related <> patient AND related.type = 'Test_Result'
            WITH related, length(path) as path_length, path
            ORDER BY path_length, related.name
            LIMIT $max_test_results
            
            // 获取每个Test_Result的直接关系
            OPTIONAL MATCH (related)-[r]-(neighbor)
            WHERE neighbor <> related
            
            WITH related, path_length, path, 
                 collect(DISTINCT {{rel: coalesce(r.relationship_type, type(r)), target: neighbor}})[0..5] as connections
            
            // 确保返回所有属性，特别是数值相关的属性
            RETURN related as n, connections, path_length, 'Test_Result' as priority_type,
                   related.value as test_value,
                   related.reference_range as reference_range,
                   related.unit as unit,
                   related.test_name as test_name
            
            UNION ALL
            
            // 然后获取Test_Type类型的节点
            MATCH (patient:Entity)
            WHERE elementId(patient) = $patient_id
            WITH patient
            
            MATCH path = (patient)-[*{hop}]-(related)
            WHERE related <> patient AND related.type = 'Test_Type'
            WITH related, length(path) as path_length, path
            ORDER BY path_length, related.name
            LIMIT $max_test_types
            
            // 获取每个Test_Type的直接关系
            OPTIONAL MATCH (related)-[r]-(neighbor)
            WHERE neighbor <> related
            
            WITH related, path_length, path, 
                 collect(DISTINCT {{rel: coalesce(r.relationship_type, type(r)), target: neighbor}})[0..5] as connections
            
            RETURN related as n, connections, path_length, 'Test_Type' as priority_type,
                   null as test_value,
                   null as reference_range,
                   null as unit,
                   null as test_name
            
            UNION ALL
            
            // 最后获取其他类型的节点
            MATCH (patient:Entity)
            WHERE elementId(patient) = $patient_id
            WITH patient
            
            MATCH path = (patient)-[*{hop}]-(related)
            WHERE related <> patient AND related.type <> 'Test_Result' AND related.type <> 'Test_Type'
            WITH related, length(path) as path_length, path
            ORDER BY path_length, related.name
            LIMIT $max_other_entities
            
            // 获取每个实体的直接关系
            OPTIONAL MATCH (related)-[r]-(neighbor)
            WHERE neighbor <> related
            
            WITH related, path_length, path, 
                 collect(DISTINCT {{rel: coalesce(r.relationship_type, type(r)), target: neighbor}})[0..5] as connections
            
            RETURN related as n, connections, path_length, 'Other' as priority_type,
                   null as test_value,
                   null as reference_range,
                   null as unit,
                   null as test_name
            """
            
            try:
                # 重新分配配额：Test_Result 40%，Test_Type 30%，其他 30%
                max_test_results = min(max_entities * 4 // 10, 20)  # 40%
                max_test_types = min(max_entities * 3 // 10, 15)    # 30%
                max_other_entities = max_entities - max_test_results - max_test_types  # 30%
                
                logging.info(f'跳数 {hop} 配额分配: Test_Result={max_test_results}, Test_Type={max_test_types}, Other={max_other_entities}')
                
                with graph.session() as session:
                    hop_result = session.run(
                        hop_query,
                        patient_id=patient_id,
                        max_test_results=max_test_results,
                        max_test_types=max_test_types,
                        max_other_entities=max_other_entities
                    ).data()
                
                if hop_result:
                    logging.info(f'私有层跳数 {hop} 找到 {len(hop_result)} 个实体')
                    
                    # 按优先级类型分组统计
                    type_counts = {}
                    for record in hop_result:
                        priority_type = record.get('priority_type', 'Unknown')
                        type_counts[priority_type] = type_counts.get(priority_type, 0) + 1
                    
                    logging.info(f'跳数 {hop} 类型分布: {type_counts}')
                    
                    for record in hop_result:
                        # 从字典中获取entity_id，而不是从节点对象
                        entity_id = record.get('entity_id') or record.get('id') or str(record.get('n', {}).get('id', ''))
                        if entity_id and entity_id not in seen_entities:
                            seen_entities.add(entity_id)
                            all_results.append(record)
                else:
                    logging.info(f'私有层跳数 {hop} 未找到实体')
                    
            except Exception as e:
                logging.error(f"私有层跳数 {hop} 查询错误: {e}")
        
        # 限制总数量
        if len(all_results) > max_entities:
            all_results = all_results[:max_entities]
            logging.info(f'限制私有层总实体数量为 {max_entities}')
        
        # 分离推理链和节点属性
        result = self._separate_private_chains_and_nodes(all_results)
        
        # 保存原始记录
        result.raw_records = all_results
        
        logging.info(f'私有层完整遍历总共找到 {len(result.nodes)} 个节点和 {len(result.reasoning_chains)} 个推理链')
        return result

    def _separate_private_chains_and_nodes(self, records: List[Dict]) -> PrivateLayerResult:
        """
        将私有层记录分离为推理链和节点属性
        
        Args:
            records: 私有层查询记录列表
            
        Returns:
            PrivateLayerResult: 分离后的结果
        """
        result = PrivateLayerResult()
        seen_entities = set()
        
        for record in records:
            entity = record['n']
            entity_id = entity.get('id') if isinstance(entity, dict) else str(entity.get('id', ''))
            path_length = record.get('path_length', 1)
            connections = record.get('connections', [])
            priority_type = record.get('priority_type', 'Other')
            
            # 构建推理链
            reasoning_chain = {
                "chain_id": f"private_{entity_id}_{path_length}",
                "path_length": path_length,
                "entity_name": entity.get('name', 'Unknown'),
                "entity_type": self._get_semantic_type_name(entity.get('type', 'Entity')) if entity.get('type', 'Entity') in UMLS_SEMANTIC_TYPE_MAPPING else entity.get('type', 'Entity'),
                "priority_type": priority_type,
                "connections": connections,
                "test_value": record.get('test_value'),
                "reference_range": record.get('reference_range'),
                "unit": record.get('unit'),
                "test_name": record.get('test_name')
            }
            result.reasoning_chains.append(reasoning_chain)
            
            # 构建节点属性（如果未处理过）
            if entity_id not in seen_entities:
                seen_entities.add(entity_id)
                node_props = dict(entity)
                
                # 获取所有属性，包括从查询结果中直接获取的属性
                all_properties = {}
                
                # 首先从节点属性中获取
                for k, v in node_props.items():
                    if k not in ["embedding", "id", "CUI", "name", "type", "full_name"] and v is not None:
                        all_properties[k] = v
                
                # 然后从查询结果中获取额外的属性
                additional_props = [
                    'value', 'reference_range', 'unit', 'test_name', 'hospital_number',
                    'age', 'gender', 'activity_level', 'assessment_note', 'score',
                    'scoring_system_mild', 'scoring_system_moderate', 'scoring_system_severe',
                    'date', 'description', 'definition', 'namespace'
                ]
                
                for prop in additional_props:
                    if record.get(prop) is not None:
                        all_properties[prop] = record.get(prop)
                
                # 获取实体类型的人类可读名称
                entity_type = node_props.get("type", "Entity")
                if entity_type in UMLS_SEMANTIC_TYPE_MAPPING:
                    display_type = self._get_semantic_type_name(entity_type)
                else:
                    display_type = entity_type
                
                node_data = {
                    "internal_id": node_props.get("id") or f"neo4j_{entity_id}",
                    "element_id": entity_id,
                    "type": display_type,
                    "name": node_props.get("name", node_props.get("full_name", "Unknown")),
                    "properties": all_properties
                }
                
                # 确保基本属性被正确设置
                node_data["properties"]["name"] = node_data["name"]
                node_data["properties"]["type"] = node_data["type"]
                
                result.nodes.append(node_data)
                
                # 处理关系
                for conn in connections:
                    if conn.get("target") and conn.get("rel"):
                        target = conn["target"]
                        rel_type = conn["rel"]
                        target_id = target.get('id') if isinstance(target, dict) else str(target.get('id', ''))
                        target_props = dict(target) if hasattr(target, 'items') else {}
                        target_internal_id = target_props.get("id") or f"neo4j_{target_id}"
                        
                        # 添加目标节点（如果未处理过）
                        if target_id not in seen_entities:
                            seen_entities.add(target_id)
                            target_all_properties = {}
                            for k, v in target_props.items():
                                if k not in ["embedding", "id", "CUI", "name", "type", "full_name"] and v is not None:
                                    target_all_properties[k] = v
                            
                            # 获取目标节点实体类型的人类可读名称
                            target_entity_type = target_props.get("type", "Entity")
                            if target_entity_type in UMLS_SEMANTIC_TYPE_MAPPING:
                                target_display_type = self._get_semantic_type_name(target_entity_type)
                            else:
                                target_display_type = target_entity_type
                            
                            target_node_data = {
                                "internal_id": target_internal_id,
                                "element_id": target_id,
                                "type": target_display_type,
                                "name": target_props.get("name", target_props.get("full_name", "Unknown")),
                                "properties": target_all_properties
                            }
                            target_node_data["properties"]["name"] = target_node_data["name"]
                            target_node_data["properties"]["type"] = target_node_data["type"]
                            
                            result.nodes.append(target_node_data)
                        
                        # 添加关系
                        result.relationships.append({
                            "source": node_data["internal_id"],
                            "target": target_internal_id,
                            "type": str(rel_type)
                        })
        
        return result

    def retrieve_public_layer_complete(self, graph: Driver, private_entities: List[Dict], 
                                     max_depth: int = None, max_concepts: int = None) -> PublicLayerResult:
        """
        公有层完整遍历函数
        基于私有层结果进行UMLS图谱遍历
        
        Args:
            graph: Neo4j图数据库连接对象
            private_entities: 私有层实体列表
            max_depth (int): UMLS图谱最大跳数
            max_concepts (int): UMLS图谱最大概念数
            
        Returns:
            PublicLayerResult: 包含推理链和节点属性的公有层结果
        """
        if max_depth is None:
            max_depth = self.umls_max_depth
        if max_concepts is None:
            max_concepts = self.umls_max_concepts
            
        logging.info(f'=== 公有层完整遍历 (最大跳数: {max_depth}, 最大概念数: {max_concepts}) ===')
        
        result = PublicLayerResult()
        
        if not private_entities or max_depth < 1:
            return result
        
        # 步骤1：通过REFERENCE_OF关系找到UMLS概念
        umls_concept_ids = set()
        for entity_record in private_entities:
            # 处理已经处理过的节点数据格式
            if 'internal_id' in entity_record:
                # 这是已经处理过的节点数据
                entity_id = entity_record.get('internal_id', '')
            elif 'n' in entity_record:
                # 这是原始的Neo4j记录
                entity_id = entity_record['n'].get('id') if isinstance(entity_record['n'], dict) else str(entity_record['n'].get('id', ''))
            else:
                # 其他格式，尝试获取id
                entity_id = entity_record.get('id', '')
            
            logging.info(f"实体ID类型: {type(entity_id)}, 值: {entity_id}")
            concept_query = '''
            MATCH (entity:Entity)-[r:REFERENCE_OF]-(concept:Entity)
            WHERE entity.id = $entity_id
            AND concept.CUI IS NOT NULL
            AND r.similarity >= $similarity_threshold
            RETURN elementId(concept) as concept_id, r.similarity as similarity, concept.name as concept_name
            ORDER BY r.similarity DESC
            LIMIT 10
            '''
            
            try:
                with graph.session() as session:
                    concept_result = session.run(
                        concept_query, 
                        entity_id=entity_id,
                        similarity_threshold=self.similarity_threshold
                    ).data()
                
                logging.info(f'为实体查询REFERENCE_OF关系，相似度阈值: {self.similarity_threshold}')
                logging.info(f'查询结果数量: {len(concept_result)}')
                for concept_record in concept_result:
                    umls_concept_ids.add(concept_record['concept_id'])
                    logging.info(f'找到UMLS概念关联: {concept_record["concept_name"]} (相似度: {concept_record["similarity"]})')
                    
            except Exception as e:
                logging.error(f"查找UMLS概念关联错误: {e}")
        
        if not umls_concept_ids:
            logging.info('未找到UMLS概念关联')
            return result
        
        logging.info(f'总共找到 {len(umls_concept_ids)} 个UMLS概念ID，开始多跳遍历')
        
        # 步骤2：在UMLS图谱中进行多跳检索
        all_results = []
        seen_concepts = set()
        
        # 为每个跳数分别进行检索，确保真正的多跳遍历
        for hop in range(1, max_depth + 1):
            hop_query = f"""
            UNWIND $concept_ids as concept_id
            MATCH (start_concept:Entity)
            WHERE elementId(start_concept) = concept_id
            
            WITH start_concept
            
            // 使用可变长度路径进行多跳检索，暂时不限制关系类型
            MATCH path = (start_concept)-[*1..{hop}]-(related:Entity)
            WHERE related.CUI IS NOT NULL 
            AND related <> start_concept
            AND length(path) = {hop}
            WITH related, length(path) as path_length, path
            ORDER BY path_length, related.name
            LIMIT $max_concepts_per_hop
            
            // 获取每个概念的语义关系
            OPTIONAL MATCH (related)-[r]-(semantic_concept:Entity)
            WHERE semantic_concept.CUI IS NOT NULL 
            AND semantic_concept <> related
            
            WITH related, path_length, path,
                 collect(DISTINCT {{rel: coalesce(r.relationship_type, type(r)), target: semantic_concept}})[0..8] as semantic_relations
            
            RETURN related as n, semantic_relations, path_length, path
            """
            
            try:
                max_concepts_per_hop = max_concepts // max_depth  # 平均分配每个跳数的概念数
                
                with graph.session() as session:
                    hop_result = session.run(
                        hop_query,
                        concept_ids=list(umls_concept_ids),
                        max_concepts_per_hop=max_concepts_per_hop
                    ).data()
                
                if hop_result:
                    logging.info(f'公有层跳数 {hop} 找到 {len(hop_result)} 个概念')
                    for record in hop_result:
                        # 从字典中获取concept_id，而不是从节点对象
                        concept_id = record.get('concept_id') or record.get('id') or str(record.get('n', {}).get('id', ''))
                        if concept_id and concept_id not in seen_concepts:
                            seen_concepts.add(concept_id)
                            all_results.append(record)
                        else:
                            # 即使concept_id重复，也要添加到all_results中，因为推理链需要所有记录
                            all_results.append(record)
                else:
                    logging.info(f'公有层跳数 {hop} 未找到概念')
                    
            except Exception as e:
                logging.error(f"公有层跳数 {hop} 查询错误: {e}")
        
        # 限制总数量
        if len(all_results) > max_concepts:
            all_results = all_results[:max_concepts]
            logging.info(f'限制公有层总概念数量为 {max_concepts}')
        
        # 分离推理链和节点属性
        result = self._separate_public_chains_and_nodes(all_results)
        
        logging.info(f'公有层完整遍历总共找到 {len(result.nodes)} 个节点和 {len(result.reasoning_chains)} 个推理链')
        return result

    def _separate_public_chains_and_nodes(self, records: List[Dict]) -> PublicLayerResult:
        """
        将公有层记录分离为推理链和节点属性
        
        Args:
            records: 公有层查询记录列表
            
        Returns:
            PublicLayerResult: 分离后的结果
        """
        result = PublicLayerResult()
        seen_concepts = set()
        
        for record in records:
            # 添加调试信息
            logging.debug(f"处理记录: {record.keys()}")
            if 'n' not in record:
                logging.warning(f"记录中缺少'n'字段: {record}")
                continue
                
            concept = record['n']
            # 添加调试信息
            logging.debug(f"concept类型: {type(concept)}, 内容: {concept}")
            
            if isinstance(concept, dict):
                concept_id = concept.get('id', '')
            else:
                # 如果是Neo4j节点对象，尝试获取id
                concept_id = str(getattr(concept, 'id', ''))
            
            path_length = record.get('path_length', 0)
            semantic_relations = record.get('semantic_relations', [])
            path = record.get('path', [])
            
            # 构建推理链
            if isinstance(concept, dict):
                concept_name = concept.get('name', 'Unknown')
                concept_cui = concept.get('CUI', 'Unknown')
            else:
                concept_name = getattr(concept, 'name', 'Unknown')
                concept_cui = getattr(concept, 'CUI', 'Unknown')
            
            reasoning_chain = {
                "chain_id": f"public_{concept_id}_{path_length}",
                "path_length": path_length,
                "concept_name": concept_name,
                "cui": concept_cui,
                "semantic_relations": semantic_relations,
                "path_info": self._extract_path_info(path)
            }
            result.reasoning_chains.append(reasoning_chain)
            
            # 构建节点属性（如果未处理过）
            if concept_id not in seen_concepts:
                seen_concepts.add(concept_id)
                
                if isinstance(concept, dict):
                    concept_props = concept
                else:
                    # 如果是Neo4j节点对象，转换为字典
                    concept_props = dict(concept)
                
                # 获取所有属性
                all_properties = {}
                for k, v in concept_props.items():
                    if k not in ["embedding", "id", "CUI", "name", "type"] and v is not None:
                        all_properties[k] = v
                
                # 获取实体类型，使用entity_type字段
                entity_type_id = concept_props.get("entity_type") or "T071"
                
                # 将语义类型ID转换为人类可读的名称
                entity_type_name = UMLS_SEMANTIC_TYPE_MAPPING.get(entity_type_id, entity_type_id)
                
                node_data = {
                    "internal_id": concept_props.get("CUI") or f"neo4j_{concept_id}",
                    "element_id": concept_id,
                    "type": entity_type_name,  # 使用人类可读的语义类型名称
                    "entity_type": entity_type_id,  # 保留原始ID用于其他用途
                    "name": concept_props.get("name", "Unknown"),
                    "cui": concept_props.get("CUI"),
                    "properties": all_properties
                }
                
                # 确保基本属性被正确设置
                node_data["properties"]["name"] = node_data["name"]
                node_data["properties"]["type"] = node_data["type"]
                if node_data["cui"]:
                    node_data["properties"]["CUI"] = node_data["cui"]
                
                result.nodes.append(node_data)
                result.concepts.append(node_data)  # 添加到concepts列表
                
                # 处理语义关系
                for sem_rel in semantic_relations:
                    if sem_rel.get("target") and sem_rel.get("rel"):
                        target = sem_rel["target"]
                        rel_type = sem_rel["rel"]
                        target_id = target.get('id') if isinstance(target, dict) else str(target.get('id', ''))
                        target_props = dict(target) if hasattr(target, 'items') else {}
                        target_internal_id = target_props.get("CUI") or f"neo4j_{target_id}"
                        
                        # 添加目标节点（如果未处理过）
                        if target_id not in seen_concepts:
                            seen_concepts.add(target_id)
                            target_all_properties = {}
                            for k, v in target_props.items():
                                if k not in ["embedding", "id", "CUI", "name", "type"] and v is not None:
                                    target_all_properties[k] = v
                            
                            # 获取目标节点的实体类型
                            target_entity_type_id = target_props.get("entity_type") or "T071"
                            target_entity_type_name = UMLS_SEMANTIC_TYPE_MAPPING.get(target_entity_type_id, target_entity_type_id)
                            
                            target_node_data = {
                                "internal_id": target_internal_id,
                                "element_id": target_id,
                                "type": target_entity_type_name,  # 使用人类可读的语义类型名称
                                "entity_type": target_entity_type_id,  # 保留原始ID
                                "name": target_props.get("name", "Unknown"),
                                "cui": target_props.get("CUI"),
                                "properties": target_all_properties
                            }
                            target_node_data["properties"]["name"] = target_node_data["name"]
                            target_node_data["properties"]["type"] = target_node_data["type"]
                            if target_node_data["cui"]:
                                target_node_data["properties"]["CUI"] = target_node_data["cui"]
                            
                            result.nodes.append(target_node_data)
                            result.concepts.append(target_node_data)  # 添加到concepts列表
                        
                        # 添加关系
                        result.relationships.append({
                            "source": node_data["internal_id"],
                            "target": target_internal_id,
                            "type": str(rel_type)
                        })
        
        return result

    def _extract_path_info(self, path) -> List[Dict]:
        """
        提取路径信息，用于知识链分析
        
        Args:
            path: Neo4j路径对象或列表
            
        Returns:
            List[Dict]: 路径信息列表
        """
        path_info = []
        if path:
            # 检查path的类型
            if hasattr(path, 'nodes') and hasattr(path, 'relationships'):
                # Neo4j Path对象
                for i, node in enumerate(path.nodes):
                    if i < len(path.nodes) - 1:  # 不是最后一个节点
                        rel_type = path.relationships[i].type if i < len(path.relationships) else "RELATED_TO"
                        path_info.append({
                            'node': node.get('name', 'Unknown'),
                            'rel_type': rel_type
                        })
            elif isinstance(path, list):
                # 如果是列表，尝试解析
                for i, item in enumerate(path):
                    if i < len(path) - 1:  # 不是最后一个节点
                        if isinstance(item, dict):
                            node_name = item.get('name', 'Unknown')
                        else:
                            node_name = getattr(item, 'name', 'Unknown')
                        path_info.append({
                            'node': node_name,
                            'rel_type': 'RELATED_TO'  # 默认关系类型
                        })
            else:
                # 其他类型，记录警告
                logging.warning(f"未知的path类型: {type(path)}")
        return path_info