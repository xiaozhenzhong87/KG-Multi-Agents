# 修复 src/retrieval/retriever.py
"""
检索核心逻辑 - 完整版本
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import requests
import json
import re

from ..core.models import Entity, Relationship, QueryResult
from ..core.database import db_manager
from ..core.embeddings import embedding_manager
from ..config.settings import settings

# 导入新的模块
from .identifier import CoreIdentifier
from .multi_layer_retriever import MultiLayerRetriever, PrivateLayerResult, PublicLayerResult
from .cross_layer_connector import CrossLayerConnector
from .formatter import ContextFormatter
from .llm_integration import LLMIntegration
from .pagerank_retriever import PageRankRetriever, PageRankResult
from .type_analyzer import TypeAnalyzer
from .result_filter import ResultFilter

logger = logging.getLogger(__name__)

class MedicalRetriever:
    """医疗信息检索器 - 完整版本"""
    
    def __init__(self):
        # 基础配置
        self.max_medical_concepts = settings.MAX_MEDICAL_CONCEPTS
        self.max_general_entities = settings.MAX_GENERAL_ENTITIES
        self.max_relationships = settings.MAX_RELATIONSHIPS
        self.max_cross_graph_concepts = settings.MAX_CROSS_GRAPH_CONCEPTS
        
        # 新增配置参数
        self.private_max_depth = getattr(settings, 'PRIVATE_GRAPH_MAX_DEPTH', 5)
        self.private_max_entities = getattr(settings, 'PRIVATE_GRAPH_MAX_ENTITIES', 50)
        self.umls_max_depth = getattr(settings, 'UMLS_GRAPH_MAX_DEPTH', 3)
        self.umls_max_concepts = getattr(settings, 'UMLS_GRAPH_MAX_CONCEPTS', 50)
        self.similarity_threshold = getattr(settings, 'CROSS_GRAPH_SIMILARITY_THRESHOLD', 0.5)
        
        # 初始化各个模块
        self.identifier = CoreIdentifier()
        self.multi_layer_retriever = MultiLayerRetriever()  # 保留但不使用私有层逻辑
        self.cross_layer_connector = CrossLayerConnector()
        self.formatter = ContextFormatter()
        self.llm_integration = LLMIntegration()
        self.pagerank_retriever = PageRankRetriever()  # 新增：PageRank检索器
        self.type_analyzer = TypeAnalyzer()  # 新增：类型分析器
        self.result_filter = ResultFilter()  # 新增：结果过滤器
    
    def retrieve(self, query: str = None, max_results: int = None) -> QueryResult:
        """
        执行完整检索流程 - 按照7个步骤执行
        
        步骤1: 使用LLM提取查询中的医疗实体
        步骤2: 使用提取的实体作为种子，进行Personal PageRank检索（PPR或PR）
        步骤3: 生成结构化上下文Context
        步骤4: LLM分析QUERY涉及的节点类型和关系类型
        步骤5: 通过节点类型和关系类型的list对步骤2或步骤3的输出进行过滤
        步骤6: 生成结构化上下文Context（过滤后）
        步骤7: 根据query和context结合以及预先设定的prompt使LLM进行分析生成
        
        Args:
            query: 用户查询（如果为None，则使用配置中的默认查询）
            max_results: 最大返回结果数（如果为None则使用配置文件中的PAGERANK_MAX_RESULTS）
            
        Returns:
            QueryResult: 检索结果
        """
        try:
            # 如果query为None，使用配置中的默认查询
            if query is None:
                query = settings.QUERY
                if query is None:
                    logger.warning("未提供查询，且配置中也没有默认查询")
                    return QueryResult()
            
            logger.info(f"开始完整检索流程: {query}")
            logger.info("=" * 80)
            
            # 步骤1: 使用LLM提取查询中的医疗实体
            logger.info("步骤1: 使用LLM提取查询中的医疗实体...")
            extracted_entities = self.identifier.extract_entities_from_question(query)
            logger.info(f"LLM提取的实体: {extracted_entities}")
            logger.info("=" * 80)
            
            # 连接数据库
            db_manager.connect()
            driver = db_manager.driver
            
            # 步骤2: 使用提取的实体作为种子，进行Personal PageRank检索（PPR或PR）
            # 检查是否启用知识图谱检索（优先使用新配置项，向后兼容旧配置项）
            enable_kg_retrieval = getattr(settings, 'ENABLE_KNOWLEDGE_GRAPH_RETRIEVAL', None)
            if enable_kg_retrieval is None:
                # 如果新配置项不存在，使用旧配置项
                enable_kg_retrieval = settings.USE_PAGERANK_RETRIEVAL
            
            if not enable_kg_retrieval:
                logger.warning("知识图谱检索已禁用（ENABLE_KNOWLEDGE_GRAPH_RETRIEVAL=False），跳过步骤2（PageRank检索）")
                pagerank_result = PageRankResult()
            else:
                logger.info("步骤2: 使用提取的实体作为种子，进行知识图谱检索（PageRank）...")
                pagerank_result = self.pagerank_retriever.retrieve(
                    query, driver, seed_entities=extracted_entities, max_results=max_results
                )
                logger.info(f"步骤2完成: 找到 {len(pagerank_result.nodes)} 个节点, {len(pagerank_result.relationships)} 个关系")
            logger.info("=" * 80)
            
            # 步骤3: 生成结构化上下文Context
            logger.info("步骤3: 生成结构化上下文Context...")
            structured_context_step3 = self.formatter.format_structured_context_from_pagerank(
                query, pagerank_result
            )
            logger.info(f"步骤3完成: 上下文长度 {len(structured_context_step3)} 字符")
            logger.info("=" * 80)
            
            # 步骤4: LLM分析QUERY涉及的节点类型和关系类型
            type_analysis_result = {"rewritten_query": query, "entity_types": [], "relationship_types": []}
            if settings.ENABLE_TYPE_ANALYSIS:
                logger.info("步骤4: LLM改写query并分析涉及的节点类型和关系类型...")
                type_analysis_result = self.type_analyzer.analyze_query_types(query)
                if 'rewritten_query' in type_analysis_result and type_analysis_result['rewritten_query'] != query:
                    logger.info(f"改写后的query: {type_analysis_result['rewritten_query']}")
                logger.info(f"步骤4完成: 识别出 {len(type_analysis_result['entity_types'])} 个节点类型, "
                           f"{len(type_analysis_result['relationship_types'])} 个关系类型")
            else:
                logger.info("步骤4: 类型分析已禁用，跳过")
            logger.info("=" * 80)
            
            # 步骤5: 通过节点类型和关系类型的list对步骤2或步骤3的输出进行过滤
            filtered_result = pagerank_result
            if settings.ENABLE_TYPE_ANALYSIS and type_analysis_result:
                logger.info("步骤5: 根据节点类型和关系类型过滤结果...")
                filtered_result = self.result_filter.filter_by_types(
                    pagerank_result,
                    type_analysis_result.get('entity_types', []),
                    type_analysis_result.get('relationship_types', [])
                )
                logger.info(f"步骤5完成: 过滤后剩余 {len(filtered_result.nodes)} 个节点, "
                           f"{len(filtered_result.relationships)} 个关系")
            else:
                logger.info("步骤5: 类型分析未启用，跳过过滤")
            logger.info("=" * 80)
            
            # 步骤6: 生成结构化上下文Context（过滤后）
            logger.info("步骤6: 生成结构化上下文Context（过滤后）...")
            structured_context = self.formatter.format_structured_context_from_pagerank(
                query, filtered_result
            )
            logger.info(f"步骤6完成: 上下文长度 {len(structured_context)} 字符")
            
            # 记录最终格式化后的上下文（用于调试）
            logger.info("=" * 80)
            logger.info("最终格式化后的上下文（将传递给LLM的prompt）:")
            logger.info("=" * 80)
            logger.info(structured_context)
            logger.info("=" * 80)
            logger.info(f"上下文长度: {len(structured_context)} 字符")
            logger.info("=" * 80)
            
            # 步骤7: 根据query和context结合以及预先设定的prompt使LLM进行分析生成
            logger.info("步骤7: 使用LLM生成最终响应...")
            llm_response = self.llm_integration.generate_response_with_context_v5(
                query, structured_context
            )
            logger.info(f"步骤7完成: LLM响应长度 {len(llm_response) if llm_response else 0} 字符")
            logger.info("=" * 80)
            
            # 构建最终结果
            result = self._build_result_from_pagerank(filtered_result, llm_response)
            
            # 添加类型分析结果到元数据
            if type_analysis_result:
                result.metadata['type_analysis'] = type_analysis_result
                result.metadata['filtered'] = len(filtered_result.nodes) < len(pagerank_result.nodes)
            
            logger.info("完整检索流程完成")
            return result
            
        except Exception as e:
            logger.error(f"检索过程中发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return QueryResult()
    
    def retrieve_legacy(self, query: str) -> QueryResult:
        """
        原有的检索方法（保留但不使用，用于向后兼容）
        使用固定跳数的多层级检索
        
        Args:
            query: 用户查询
            
        Returns:
            QueryResult: 检索结果
        """
        try:
            logger.info(f"开始完整检索流程（Legacy模式）: {query}")
            
            # 步骤1: 识别核心标识符
            core_identifiers = self.identifier.identify_core_identifiers(query)
            logger.info(f"核心标识符识别完成: {core_identifiers}")
            
            # 步骤2: 获取患者ID
            patient_id = self._get_patient_id(core_identifiers)
            if not patient_id:
                logger.warning("未找到患者ID，无法进行检索")
                return QueryResult()
            
            # 步骤3: 执行多层级检索（私有层逻辑，保留但不使用）
            # private_result, public_result = self._execute_multi_layer_retrieval(
            #     patient_id, core_identifiers
            # )
            
            # 由于不再使用私有层，直接返回空结果或使用公有层检索
            private_result = PrivateLayerResult()
            public_result = PublicLayerResult()
            
            # 步骤4: 构建跨层关联
            cross_chains = self.cross_layer_connector.build_cross_layer_chains(
                private_result, public_result
            )
            
            # 步骤5: 生成结构化上下文
            structured_context = self.formatter.format_structured_context(
                query, private_result, public_result, cross_chains
            )
            
            # 记录最终格式化后的上下文（用于调试）
            logger.info("=" * 80)
            logger.info("最终格式化后的上下文（将传递给LLM的prompt）:")
            logger.info("=" * 80)
            logger.info(structured_context)
            logger.info("=" * 80)
            logger.info(f"上下文长度: {len(structured_context)} 字符")
            
            # 步骤6: 调用LLM生成响应
            llm_response = self.llm_integration.generate_response_with_context_v5(
                query, structured_context
            )
            
            # 步骤7: 构建最终结果
            result = self._build_final_result(
                private_result, public_result, cross_chains, llm_response
            )
            
            logger.info("完整检索流程完成（Legacy模式）")
            return result
            
        except Exception as e:
            logger.error(f"检索过程中发生错误: {e}")
            return QueryResult()
    
    def _get_patient_id(self, core_identifiers: Dict[str, Any]) -> Optional[str]:
        """
        根据核心标识符获取患者ID
        
        Args:
            core_identifiers: 核心标识符字典
            
        Returns:
            Optional[str]: 患者ID
        """
        try:
            # 首先尝试通过医院号码查找
            hospital_number = core_identifiers.get('hospital_number')
            if hospital_number:
                patient_query = """
                MATCH (p:Entity)
                WHERE p.hospital_number = $hospital_number
                RETURN elementId(p) as patient_id
                LIMIT 1
                """
                
                with db_manager.get_session() as session:
                    result = session.run(patient_query, hospital_number=hospital_number)
                    record = result.single()
                    if record:
                        patient_id = record['patient_id']
                        logger.info(f"通过医院号码找到患者ID: {patient_id}")
                        return patient_id
            
            # 然后尝试通过患者姓名查找
            patient_name = core_identifiers.get('patient_name')
            if patient_name:
                patient_query = """
                MATCH (p:Entity)
                WHERE p.name = $patient_name OR p.full_name = $patient_name
                RETURN elementId(p) as patient_id
                LIMIT 1
                """
                
                with db_manager.get_session() as session:
                    result = session.run(patient_query, patient_name=patient_name)
                    record = result.single()
                    if record:
                        patient_id = record['patient_id']
                        logger.info(f"通过患者姓名找到患者ID: {patient_id}")
                        return patient_id
            
            logger.warning("未找到患者ID")
            return None
            
        except Exception as e:
            logger.error(f"获取患者ID时发生错误: {e}")
            return None
    
    def _execute_multi_layer_retrieval(self, patient_id: str, 
                                     core_identifiers: Dict[str, Any]) -> Tuple[PrivateLayerResult, PublicLayerResult]:
        """
        执行多层级检索
        
        Args:
            patient_id: 患者ID
            core_identifiers: 核心标识符
            
        Returns:
            Tuple[PrivateLayerResult, PublicLayerResult]: 私有层和公有层结果
        """
        try:
            # 修复：传递driver而不是session
            db_manager.connect()
            driver = db_manager.driver
            
            # 私有层检索
            logger.info("开始私有层检索")
            private_result = self.multi_layer_retriever.retrieve_private_layer_complete(
                driver, patient_id, self.private_max_depth, self.private_max_entities
            )
            
            # 公有层检索
            logger.info("开始公有层检索")
            # 传递原始的私有层记录，而不是处理后的节点
            public_result = self.multi_layer_retriever.retrieve_public_layer_complete(
                driver, private_result.raw_records, self.umls_max_depth, self.umls_max_concepts
            )
            
            return private_result, public_result
                
        except Exception as e:
            logger.error(f"多层级检索过程中发生错误: {e}")
            return PrivateLayerResult(), PublicLayerResult()
    
    def _build_result_from_pagerank(self, pagerank_result: PageRankResult, 
                                   llm_response: str = None) -> QueryResult:
        """
        从PageRank结果构建QueryResult
        
        Args:
            pagerank_result: PageRank检索结果
            llm_response: LLM生成的响应（可选）
            
        Returns:
            QueryResult: 最终结果
        """
        result = QueryResult()
        
        # 添加节点实体
        for node in pagerank_result.nodes:
            entity = Entity(
                id=node['internal_id'],
                name=node['name'],
                entity_type=node['type'],
                properties=node.get('properties', {})
            )
            # 如果节点有PageRank分数，添加到properties中
            if 'pagerank_score' in node:
                entity.properties['pagerank_score'] = node['pagerank_score']
            result.entities.append(entity)
        
        # 添加关系
        for rel in pagerank_result.relationships:
            relationship = Relationship(
                source=rel['source'],
                target=rel['target'],
                relationship_type=rel['type']
            )
            result.relationships.append(relationship)
        
        # 添加LLM响应到推理链
        if llm_response:
            result.reasoning_chain = llm_response
        
        # 添加元数据
        result.metadata = {
            'nodes_count': len(pagerank_result.nodes),
            'relationships_count': len(pagerank_result.relationships),
            'retrieval_method': 'PageRank',
            'llm_response': llm_response if llm_response else None
        }
        
        return result
    
    def _build_final_result(self, private_result: PrivateLayerResult, 
                          public_result: PublicLayerResult, 
                          cross_chains: List[Dict], 
                          llm_response: str) -> QueryResult:
        """
        构建最终检索结果
        
        Args:
            private_result: 私有层结果
            public_result: 公有层结果
            cross_chains: 跨层推理链
            llm_response: LLM响应
            
        Returns:
            QueryResult: 最终结果
        """
        result = QueryResult()
        
        # 添加私有层实体
        for node in private_result.nodes:
            entity = Entity(
                id=node['internal_id'],
                name=node['name'],
                entity_type=node['type'],
                properties=node.get('properties', {})
            )
            result.entities.append(entity)
        
        # 添加公有层实体
        for concept in public_result.concepts:
            entity = Entity(
                id=concept['internal_id'],
                name=concept['name'],
                entity_type=concept['type'],
                properties=concept.get('properties', {})
            )
            result.entities.append(entity)
        
        # 添加关系
        all_relationships = private_result.relationships + public_result.relationships
        for rel in all_relationships:
            relationship = Relationship(
                source=rel['source'],
                target=rel['target'],
                relationship_type=rel['type']
            )
            result.relationships.append(relationship)
        
        # 添加LLM响应
        result.metadata = {
            'llm_response': llm_response,
            'private_nodes_count': len(private_result.nodes),
            'public_concepts_count': len(public_result.concepts),
            'cross_chains_count': len(cross_chains),
            'reasoning_chains_count': len(private_result.reasoning_chains) + len(public_result.reasoning_chains)
        }
        
        return result
    
    # 保留原有的简化检索方法作为备用
    def retrieve_simple(self, query: str) -> QueryResult:
        """执行简化检索（原有方法）"""
        try:
            logger.info(f"开始简化检索: {query}")
            
            # 生成查询嵌入
            query_embedding = embedding_manager.generate_embedding(query)
            
            # 多层级检索
            result = QueryResult()
            
            # 1. 私有层检索
            private_entities, private_relationships = self._retrieve_private_layer(query, query_embedding)
            result.entities.extend(private_entities)
            result.relationships.extend(private_relationships)
            
            # 2. UMLS层检索
            umls_entities, umls_relationships = self._retrieve_umls_layer(query, query_embedding)
            result.entities.extend(umls_entities)
            result.relationships.extend(umls_relationships)
            
            # 3. 跨图谱检索
            cross_entities, cross_relationships = self._retrieve_cross_graph(query, query_embedding)
            result.entities.extend(cross_entities)
            result.relationships.extend(cross_relationships)
            
            logger.info(f"简化检索完成，找到 {len(result.entities)} 个实体和 {len(result.relationships)} 个关系")
            return result
            
        except Exception as e:
            logger.error(f"简化检索过程中发生错误: {e}")
            return QueryResult()
    
    def _retrieve_private_layer(self, query: str, query_embedding: List[float]) -> Tuple[List[Entity], List[Relationship]]:
        """检索私有层（修复版）"""
        entities = []
        relationships = []
        
        try:
            # 修复：使用正确的数据库查询方法
            with db_manager.get_session() as session:
                # 基于名称的模糊匹配
                name_query = """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query AND e.namespace = 'private_kg'
                RETURN e
                LIMIT $limit
                """
                
                result = session.run(name_query, {"query": query, "limit": self.max_general_entities})
                for record in result:
                    entity_data = dict(record['e'])
                    entity = Entity(
                        id=entity_data.get('id', ''),
                        name=entity_data.get('name', ''),
                        entity_type=entity_data.get('type', 'Entity'),
                        properties=entity_data
                    )
                    entities.append(entity)
                
                # 基于嵌入的语义匹配（简化版）
                all_entities_query = """
                MATCH (e:Entity)
                WHERE e.namespace = 'private_kg'
                RETURN e
                LIMIT $limit
                """
                
                result = session.run(all_entities_query, {"limit": self.max_medical_concepts})
                for record in result:
                    entity_data = dict(record['e'])
                    if entity_data.get('embedding'):
                        # 这里可以添加相似度计算逻辑
                        entity = Entity(
                            id=entity_data.get('id', ''),
                            name=entity_data.get('name', ''),
                            type=entity_data.get('type', 'Entity'),
                            properties=entity_data
                        )
                        entities.append(entity)
                
                # 获取相关关系
                for entity in entities[:10]:  # 限制关系查询数量
                    rel_query = """
                    MATCH (e:Entity {id: $entity_id})-[r:RELATIONSHIP]->(target:Entity)
                    RETURN r, target
                    UNION
                    MATCH (source:Entity)-[r:RELATIONSHIP]->(e:Entity {id: $entity_id})
                    RETURN r, source
                    LIMIT $limit
                    """
                    
                    rel_result = session.run(rel_query, {"entity_id": entity.id, "limit": self.max_relationships})
                    for rel_record in rel_result:
                        if 'r' in rel_record:
                            rel_data = dict(rel_record['r'])
                            relationship = Relationship(
                                source=rel_data.get('source', ''),
                                target=rel_data.get('target', ''),
                                relationship_type=rel_data.get('type', 'RELATIONSHIP')
                            )
                            relationships.append(relationship)
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"私有层检索失败: {e}")
            return entities, relationships
    
    def _retrieve_umls_layer(self, query: str, query_embedding: List[float]) -> Tuple[List[Entity], List[Relationship]]:
        """检索UMLS层（修复版）"""
        entities = []
        relationships = []
        
        try:
            with db_manager.get_session() as session:
                # 基于名称的模糊匹配
                name_query = """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query AND e.namespace = 'umls_kg'
                RETURN e
                LIMIT $limit
                """
                
                result = session.run(name_query, {"query": query, "limit": self.max_medical_concepts})
                for record in result:
                    entity_data = dict(record['e'])
                    # 获取实体类型，使用entity_type字段
                    entity_type = entity_data.get('entity_type', 'T071')
                    
                    entity = Entity(
                        id=entity_data.get('id', ''),
                        name=entity_data.get('name', ''),
                        type=entity_type,  # 使用具体的语义类型
                        properties=entity_data
                    )
                    entities.append(entity)
                
                # 获取相关关系
                for entity in entities[:10]:  # 限制关系查询数量
                    rel_query = """
                    MATCH (e:Entity {id: $entity_id})-[r:RELATIONSHIP]->(target:Entity)
                    RETURN r, target
                    UNION
                    MATCH (source:Entity)-[r:RELATIONSHIP]->(e:Entity {id: $entity_id})
                    RETURN r, source
                    LIMIT $limit
                    """
                    
                    rel_result = session.run(rel_query, {"entity_id": entity.id, "limit": self.max_relationships})
                    for rel_record in rel_result:
                        if 'r' in rel_record:
                            rel_data = dict(rel_record['r'])
                            relationship = Relationship(
                                source=rel_data.get('source', ''),
                                target=rel_data.get('target', ''),
                                relationship_type=rel_data.get('type', 'RELATIONSHIP')
                            )
                            relationships.append(relationship)
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"UMLS层检索失败: {e}")
            return entities, relationships
    
    def _retrieve_cross_graph(self, query: str, query_embedding: List[float]) -> Tuple[List[Entity], List[Relationship]]:
        """检索跨图谱关系（修复版）"""
        entities = []
        relationships = []
        
        try:
            with db_manager.get_session() as session:
                # 查找跨图谱关系
                cross_query = """
                MATCH (p:Entity {namespace: 'private_kg'})-[r:RELATIONSHIP {namespace: 'cross_graph'}]->(u:Entity {namespace: 'umls_kg'})
                WHERE p.name CONTAINS $query OR u.name CONTAINS $query
                RETURN p, r, u
                LIMIT $limit
                """
                
                result = session.run(cross_query, {"query": query, "limit": self.max_cross_graph_concepts})
                
                for record in result:
                    if 'p' in record:
                        entity_data = dict(record['p'])
                        entity = Entity(
                            id=entity_data.get('id', ''),
                            name=entity_data.get('name', ''),
                            type=entity_data.get('type', 'Entity'),
                            properties=entity_data
                        )
                        entities.append(entity)
                    
                    if 'u' in record:
                        entity_data = dict(record['u'])
                        entity = Entity(
                            id=entity_data.get('id', ''),
                            name=entity_data.get('name', ''),
                            type=entity_data.get('type', 'Entity'),
                            properties=entity_data
                        )
                        entities.append(entity)
                    
                    if 'r' in record:
                        rel_data = dict(record['r'])
                        relationship = Relationship(
                            source=rel_data.get('source', ''),
                            target=rel_data.get('target', ''),
                            relationship_type=rel_data.get('type', 'RELATIONSHIP')
                        )
                        relationships.append(relationship)
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"跨图谱检索失败: {e}")
            return entities, relationships
    
    def _find_similar_entities(self, query_embedding: List[float], entities: List[Entity]) -> List[Entity]:
        """查找相似实体"""
        similar_entities = []
        
        for entity in entities:
            if not entity.embedding:
                continue
            
            similarity = embedding_manager.calculate_similarity(query_embedding, entity.embedding)
            if similarity >= 0.5:  # 相似度阈值
                similar_entities.append((entity, similarity))
        
        # 按相似度排序
        similar_entities.sort(key=lambda x: x[1], reverse=True)
        return [entity for entity, _ in similar_entities]
    
    def _get_entity_relationships(self, entity_id: str, namespace: str) -> List[Relationship]:
        """获取实体的关系"""
        try:
            with db_manager.get_session() as session:
                query = """
                MATCH (e:Entity {id: $entity_id, namespace: $namespace})-[r:RELATIONSHIP]->(target:Entity)
                RETURN r
                UNION
                MATCH (source:Entity)-[r:RELATIONSHIP]->(e:Entity {id: $entity_id, namespace: $namespace})
                RETURN r
                LIMIT $limit
                """
                
                result = session.run(query, {"entity_id": entity_id, "namespace": namespace, "limit": self.max_relationships})
                
                relationships = []
                for record in result:
                    if 'r' in record:
                        rel_data = dict(record['r'])
                        relationship = Relationship(
                            source=rel_data.get('source', ''),
                            target=rel_data.get('target', ''),
                            relationship_type=rel_data.get('type', 'RELATIONSHIP')
                        )
                        relationships.append(relationship)
                
                return relationships
                
        except Exception as e:
            logger.error(f"获取实体关系失败: {e}")
            return []
    
    def _generate_reasoning_chain(self, result: QueryResult) -> List[str]:
        """生成推理链"""
        reasoning_chain = []
        
        try:
            # 使用LLM生成推理链
            entities_text = ", ".join([f"{e.name} ({e.type})" for e in result.entities[:10]])
            relationships_text = ", ".join([f"{r.type}" for r in result.relationships[:10]])
            
            prompt = f"""
            基于以下医疗实体和关系，生成推理链：
            
            实体: {entities_text}
            关系: {relationships_text}
            
            请生成简洁的推理步骤，说明这些实体和关系如何关联。
            """
            
            llm_response = self._call_llm(prompt)
            if llm_response:
                reasoning_chain = [llm_response]
            
        except Exception as e:
            logger.error(f"生成推理链失败: {e}")
        
        return reasoning_chain
    
    def _calculate_confidence(self, result: QueryResult) -> float:
        """计算检索结果置信度"""
        try:
            if not result.entities and not result.relationships:
                return 0.0
            
            # 基于实体数量和关系数量计算置信度
            entity_score = min(len(result.entities) / 20.0, 1.0)
            relationship_score = min(len(result.relationships) / 20.0, 1.0)
            
            confidence = (entity_score + relationship_score) / 2.0
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"计算置信度失败: {e}")
            return 0.0
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """调用LLM"""
        try:
            response = requests.post(
                settings.OLLAMA_URL,
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                logger.error(f"LLM调用失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"调用LLM失败: {e}")
            return None