"""
动态图谱更新模块
"""
import re
import uuid
import logging
import numpy as np
import ast
from typing import List, Dict, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity

from ..core.models import Entity, Relationship, GraphData
from ..core.database import db_manager
from ..core.embeddings import embedding_manager
from ..config.settings import settings

logger = logging.getLogger(__name__)

class GraphUpdater:
    """动态图谱更新器"""
    
    def __init__(self, namespace: str = "private_kg"):
        self.namespace = namespace
        self.excluded_types = ["Patient", "Encounter"]  # 这些类型不建立UMLS链接
    
    def find_existing_patient(self, patient_name: str, hospital_number: str = None) -> Optional[str]:
        """查找现有的患者节点"""
        try:
            if hospital_number:
                # 优先通过hospital_number查找
                query = """
                MATCH (e:Entity {entity_type: 'Patient', namespace: $namespace})
                WHERE e.properties.hospital_number = $hospital_number
                RETURN e.id as id
                """
                result = db_manager.execute_query(query, {
                    "namespace": self.namespace,
                    "hospital_number": hospital_number
                })
                if result:
                    return result[0]["id"]
            
            # 通过姓名查找
            query = """
            MATCH (e:Entity {entity_type: 'Patient', namespace: $namespace})
            WHERE e.name = $name
            RETURN e.id as id, e.properties.hospital_number as hospital_number
            ORDER BY e.properties.hospital_number DESC
            LIMIT 1
            """
            result = db_manager.execute_query(query, {
                "namespace": self.namespace,
                "name": patient_name
            })
            if result:
                return result[0]["id"]
            
            return None
        except Exception as e:
            logger.error(f"查找现有患者失败: {e}")
            return None
    
    def update_patient_attributes(self, patient_id: str, new_properties: Dict):
        """更新现有患者节点的属性"""
        try:
            query = """
            MATCH (e:Entity {id: $patient_id, namespace: $namespace})
            SET e.properties = e.properties + $new_props,
                e.updated_at = datetime()
            """
            db_manager.execute_query(query, {
                "patient_id": patient_id,
                "namespace": self.namespace,
                "new_props": new_properties
            })
            logger.info(f"更新患者节点 {patient_id} 的属性")
        except Exception as e:
            logger.error(f"更新患者属性失败: {e}")
    
    def update_relationship_references(self, graph_data: GraphData, existing_patient_id: str, new_patient_id: str):
        """更新关系中的患者ID引用"""
        for rel in graph_data.relationships:
            if rel.source == new_patient_id:
                rel.source = existing_patient_id
                logger.info(f"更新关系源ID: {new_patient_id} -> {existing_patient_id}")
            if rel.target == new_patient_id:
                rel.target = existing_patient_id
                logger.info(f"更新关系目标ID: {new_patient_id} -> {existing_patient_id}")
    
    def parse_notepad_content_to_graph(self, notepad_content: str, hospital_number: str = "Unknown") -> GraphData:
        """解析notepad内容并生成知识图谱"""
        entities = []
        relationships = []
        
        try:
            # 解析患者信息
            patient_match = re.search(r'Lin\s*\{\s*"gender":\s*"([^"]+)",\s*"age":\s*(\d+)\s*\}', notepad_content)
            if patient_match:
                gender = patient_match.group(1)
                age = int(patient_match.group(2))
                
                patient_properties = {
                    "name": "Lin",
                    "gender": gender,
                    "age": age,
                    "hospital_number": hospital_number
                }
                
                # 为患者生成embedding
                combined_text = f"Lin {gender} {age} years old"
                embedding = embedding_manager.generate_embedding(combined_text)
                patient_properties["embedding"] = embedding
                
                patient_entity = Entity(
                    id=str(uuid.uuid4()),
                    name="Lin",
                    entity_type="Patient",
                    properties=patient_properties,
                    embedding=embedding,
                    namespace=self.namespace
                )
                entities.append(patient_entity)
                patient_id = patient_entity.id
            
            # 解析就诊记录
            encounter_match = re.search(r'Encounter_(\d{4}-\d{2}-\d{2})\s*\{\s*"date":\s*"([^"]+)"\s*\}', notepad_content)
            if encounter_match:
                encounter_date = encounter_match.group(2)
                
                encounter_properties = {
                    "name": f"Encounter_{encounter_date}",
                    "date": encounter_date
                }
                
                # 为就诊记录生成embedding
                combined_text = f"Encounter {encounter_date} medical visit"
                embedding = embedding_manager.generate_embedding(combined_text)
                encounter_properties["embedding"] = embedding
                
                encounter_entity = Entity(
                    id=str(uuid.uuid4()),
                    name=f"Encounter_{encounter_date}",
                    entity_type="Encounter",
                    properties=encounter_properties,
                    embedding=embedding,
                    namespace=self.namespace
                )
                entities.append(encounter_entity)
                encounter_id = encounter_entity.id
                
                # 添加患者与就诊记录的关系
                if 'patient_id' in locals():
                    relationships.append(Relationship(
                        id=str(uuid.uuid4()),
                        source=patient_id,
                        target=encounter_id,
                        relationship_type="has_encountered",
                        namespace=self.namespace
                    ))
            
            # 解析实验室检查
            lab_tests_match = re.search(r'(Laboratory_Tests(?:_\w+)?)', notepad_content)
            if lab_tests_match:
                lab_tests_name = lab_tests_match.group(1)
                lab_tests_properties = {
                    "name": lab_tests_name
                }
                
                # 为实验室检查生成embedding
                combined_text = f"{lab_tests_name} blood work analysis"
                embedding = embedding_manager.generate_embedding(combined_text)
                lab_tests_properties["embedding"] = embedding
                
                lab_tests_entity = Entity(
                    id=str(uuid.uuid4()),
                    name=lab_tests_name,
                    entity_type="Laboratory_Tests",
                    properties=lab_tests_properties,
                    embedding=embedding,
                    namespace=self.namespace
                )
                entities.append(lab_tests_entity)
                lab_tests_id = lab_tests_entity.id
                
                # 添加就诊记录与实验室检查的关系
                if 'encounter_id' in locals():
                    relationships.append(Relationship(
                        id=str(uuid.uuid4()),
                        source=encounter_id,
                        target=lab_tests_id,
                        relationship_type="includes",
                        namespace=self.namespace
                    ))
            
            # 解析具体的检查结果
            test_patterns = [
                (r'White_Blood_Cell_Count', "white blood cell count"),
                (r'Lymphocyte_Count', "lymphocyte count"),
                (r'Lymphocyte_Percent_Differential_Count', "lymphocyte percent differential count"),
                (r'C_Reactive_Protein', "C-reactive protein"),
                (r'Erythrocyte_Sedimentation_Rate', "erythrocyte sedimentation rate")
            ]
            
            for test_pattern, test_name in test_patterns:
                pattern = test_pattern + r'[^}]*has_result[^}]*\{[^}]*"name":\s*"([^"]+)"[^}]*"value":\s*([0-9.]+)[^}]*"unit":\s*"([^"]+)"[^}]*"reference":\s*"([^"]+)"'
                test_match = re.search(pattern, notepad_content)
                if test_match:
                    result_name = test_match.group(1)
                    value = float(test_match.group(2))
                    unit = test_match.group(3)
                    reference = test_match.group(4)
                    
                    # 创建测试类型节点
                    test_type_properties = {
                        "name": test_pattern
                    }
                    
                    combined_text = f"{test_pattern} laboratory test"
                    embedding = embedding_manager.generate_embedding(combined_text)
                    test_type_properties["embedding"] = embedding
                    
                    test_type_entity = Entity(
                        id=str(uuid.uuid4()),
                        name=test_pattern,
                        entity_type="Test_Type",
                        properties=test_type_properties,
                        embedding=embedding,
                        namespace=self.namespace
                    )
                    entities.append(test_type_entity)
                    test_type_id = test_type_entity.id
                    
                    # 创建测试结果节点
                    test_result_properties = {
                        "name": result_name,
                        "test_name": result_name,
                        "value": value,
                        "unit": unit,
                        "reference_range": reference
                    }
                    
                    combined_text = f"{result_name} {value} {unit} {reference}"
                    embedding = embedding_manager.generate_embedding(combined_text)
                    test_result_properties["embedding"] = embedding
                    
                    test_result_entity = Entity(
                        id=str(uuid.uuid4()),
                        name=result_name,
                        entity_type="Test_Result",
                        properties=test_result_properties,
                        embedding=embedding,
                        namespace=self.namespace
                    )
                    entities.append(test_result_entity)
                    test_result_id = test_result_entity.id
                    
                    # 添加关系
                    if 'lab_tests_id' in locals():
                        relationships.append(Relationship(
                            id=str(uuid.uuid4()),
                            source=lab_tests_id,
                            target=test_type_id,
                            relationship_type="has_test_type",
                            namespace=self.namespace
                        ))
                    
                    relationships.append(Relationship(
                        id=str(uuid.uuid4()),
                        source=test_type_id,
                        target=test_result_id,
                        relationship_type="has_result",
                        namespace=self.namespace
                    ))
            
            # 解析评估/评分
            assessment_match = re.search(r'(Juvenile_Arthritis_Activity(?:_\w+)?)', notepad_content)
            if assessment_match:
                assessment_name = assessment_match.group(1)
                
                # 提取评分信息
                score_match = re.search(r'"score":\s*(\d+)', notepad_content)
                activity_match = re.search(r'"activity_level":\s*"([^"]+)"', notepad_content)
                note_match = re.search(r'"assessment_note":\s*"([^"]+)"', notepad_content)
                
                assessment_properties = {
                    "name": assessment_name,
                    "score": int(score_match.group(1)) if score_match else 0,
                    "activity_level": activity_match.group(1) if activity_match else "unknown",
                    "scoring_system_mild": "0-10",
                    "scoring_system_moderate": "11-20", 
                    "scoring_system_severe": "≥21",
                    "assessment_note": note_match.group(1) if note_match else ""
                }
                
                # 为评估生成embedding
                combined_text = f"{assessment_name} {assessment_properties['activity_level']} score {assessment_properties['score']} assessment"
                embedding = embedding_manager.generate_embedding(combined_text)
                assessment_properties["embedding"] = embedding
                
                assessment_entity = Entity(
                    id=str(uuid.uuid4()),
                    name=assessment_name,
                    entity_type="Assessment",
                    properties=assessment_properties,
                    embedding=embedding,
                    namespace=self.namespace
                )
                entities.append(assessment_entity)
                assessment_id = assessment_entity.id
                
                # 添加就诊记录与评估的关系
                if 'encounter_id' in locals():
                    relationships.append(Relationship(
                        id=str(uuid.uuid4()),
                        source=encounter_id,
                        target=assessment_id,
                        relationship_type="includes",
                        namespace=self.namespace
                    ))
            
            return GraphData(entities=entities, relationships=relationships)
            
        except Exception as e:
            logger.error(f"解析notepad内容失败: {e}")
            return GraphData(entities=[], relationships=[])
    
    def insert_graph_into_neo4j(self, graph_data: GraphData):
        """插入图谱数据到Neo4j"""
        if not graph_data or not graph_data.entities:
            logger.warning("没有有效的图谱数据可插入")
            return
        
        try:
            # 插入实体
            for entity in graph_data.entities:
                if not db_manager.create_entity(entity):
                    logger.error(f"插入实体失败: {entity.name}")
            
            # 插入关系
            for rel in graph_data.relationships:
                if not db_manager.create_relationship(rel):
                    logger.error(f"插入关系失败: {rel.relationship_type}")
            
            logger.info(f"成功插入 {len(graph_data.entities)} 个实体和 {len(graph_data.relationships)} 个关系")
            
        except Exception as e:
            logger.error(f"插入图谱数据失败: {e}")
    
    def connect_new_entities_to_umls(self, new_entities: List[Entity], similarity_threshold: float = None):
        """为新添加的实体建立与UMLS的语义链接"""
        if similarity_threshold is None:
            similarity_threshold = settings.CROSS_GRAPH_SIMILARITY_THRESHOLD
            
        logger.info(f"为新添加的 {len(new_entities)} 个实体建立UMLS链接...")
        
        # 过滤出需要建立链接的实体
        entities_to_connect = [
            entity for entity in new_entities 
            if entity.entity_type not in self.excluded_types and entity.embedding is not None
        ]
        
        if not entities_to_connect:
            logger.info("没有需要建立UMLS链接的新实体")
            return
        
        try:
            # 获取新实体的embedding
            new_embeddings = np.array([entity.embedding for entity in entities_to_connect])
            
            # 批量获取UMLS概念
            batch_size = 5000
            total_connections = 0
            
            # 获取UMLS概念总数
            count_query = """
            MATCH (c:Entity {entity_type: 'Concept', namespace: 'umls_kg'})
            WHERE c.embedding IS NOT NULL
            RETURN count(c) as count
            """
            result = db_manager.execute_query(count_query)
            total_concepts = result[0]["count"] if result else 0
            
            total_batches = (total_concepts + batch_size - 1) // batch_size
            
            for batch_idx in range(total_batches):
                batch_start = batch_idx * batch_size
                
                # 获取当前批次的UMLS概念
                umls_query = f"""
                MATCH (c:Entity {entity_type: 'Concept', namespace: 'umls_kg'})
                WHERE c.embedding IS NOT NULL
                RETURN c.name AS name, c.properties.CUI AS cui, c.embedding AS embedding
                SKIP {batch_start} LIMIT {batch_size}
                """
                umls_nodes = db_manager.execute_query(umls_query)
                
                if not umls_nodes:
                    continue
                
                # 解析UMLS embeddings
                umls_embeddings = []
                valid_umls_nodes = []
                
                for node in umls_nodes:
                    try:
                        emb = np.array(ast.literal_eval(node['embedding']) if isinstance(node['embedding'], str) else node['embedding'])
                        if len(emb) == 768:
                            umls_embeddings.append(emb)
                            valid_umls_nodes.append(node)
                    except Exception as e:
                        logger.warning(f"解析UMLS概念 {node['cui']} 的embedding失败: {e}")
                        continue
                
                if not umls_embeddings:
                    continue
                
                umls_embeddings = np.array(umls_embeddings)
                
                # 计算相似度
                similarities = cosine_similarity(new_embeddings, umls_embeddings)
                
                # 创建语义链接
                batch_connections = 0
                for i, entity in enumerate(entities_to_connect):
                    for j, umls_node in enumerate(valid_umls_nodes):
                        sim_score = similarities[i, j]
                        if sim_score >= similarity_threshold:
                            try:
                                # 创建跨图谱关系
                                cross_rel = Relationship(
                                    id=str(uuid.uuid4()),
                                    source=entity.id,
                                    target=umls_node["cui"],
                                    relationship_type="REFERENCE_OF",
                                    properties={"similarity": float(sim_score)},
                                    namespace="cross_graph"
                                )
                                db_manager.create_relationship(cross_rel)
                                batch_connections += 1
                            except Exception as e:
                                logger.warning(f"创建关系失败 {entity.id} -> {umls_node['cui']}: {e}")
                                continue
                
                total_connections += batch_connections
                logger.info(f"批次 {batch_idx + 1}/{total_batches} 完成: {batch_connections} 个连接")
            
            logger.info(f"新实体UMLS链接建立完成，总共 {total_connections} 个连接")
            
        except Exception as e:
            logger.error(f"建立UMLS链接失败: {e}")
    
    def add_new_data_from_notepad(self, notepad_content: str, hospital_number: str = None, merge_existing_patient: bool = True) -> GraphData:
        """从notepad内容添加新数据到现有图谱"""
        if not hospital_number:
            hospital_number = f"Auto_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"添加新数据到私有图谱，医院编号: {hospital_number}")
        
        try:
            # 解析notepad内容
            graph_data = self.parse_notepad_content_to_graph(notepad_content, hospital_number)
            
            # 如果启用患者合并，查找现有患者
            if merge_existing_patient:
                existing_patient_id = self.find_existing_patient("Lin", hospital_number)
                if existing_patient_id:
                    logger.info(f"找到现有患者节点: {existing_patient_id}，将合并新数据")
                    # 更新患者节点的属性（如年龄等）
                    self.update_patient_attributes(existing_patient_id, graph_data.entities[0].properties)
                    
                    # 找到新创建的患者节点ID
                    new_patient_id = None
                    for entity in graph_data.entities:
                        if entity.entity_type == "Patient":
                            new_patient_id = entity.id
                            break
                    
                    # 更新关系中的患者ID引用（在移除患者节点之前）
                    if new_patient_id:
                        self.update_relationship_references(graph_data, existing_patient_id, new_patient_id)
                    
                    # 移除新创建的患者节点，使用现有节点
                    graph_data.entities = [e for e in graph_data.entities if e.entity_type != "Patient"]
                else:
                    logger.info("未找到现有患者节点，将创建新的患者节点")
            
            # 插入到Neo4j（不清除现有数据）
            self.insert_graph_into_neo4j(graph_data)
            
            # 为新实体建立与UMLS的语义链接
            self.connect_new_entities_to_umls(graph_data.entities)
            
            logger.info(f"成功添加 {len(graph_data.entities)} 个实体和 {len(graph_data.relationships)} 个关系")
            
            return graph_data
            
        except Exception as e:
            logger.error(f"添加新数据失败: {e}")
            return GraphData(entities=[], relationships=[])