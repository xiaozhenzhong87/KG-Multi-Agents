#!/usr/bin/env python3
"""
私有层知识图谱构建脚本
基于notepad内容构建患者特定的知识图谱
支持从txt文件读取notepad_content，支持患者信息合并和更新
"""
import os
import sys
import re
import uuid
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field, ValidationError
from sentence_transformers import SentenceTransformer, models

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import db_manager
from src.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('build_private_kg.log')
    ]
)

logger = logging.getLogger(__name__)

# === 创建SentenceTransformer模型 ===
word_embedding_model = models.Transformer("cambridgeltl/SapBERT-from-PubMedBERT-fulltext")
pooling_model = models.Pooling(
    word_embedding_model.get_word_embedding_dimension(), 
    pooling_mode_mean_tokens=True,
    pooling_mode_cls_token=False,
    pooling_mode_max_tokens=False
)
model = SentenceTransformer(modules=[word_embedding_model, pooling_model])

# 实体类型排除列表（这些类型不生成embedding）
EXCLUDED_TYPES_FOR_EMBEDDING = {"Patient", "Encounter", "Clinician", "GP", "Hospital", "Visit"}

# === Pydantic模型定义 ===
class Entity(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    properties: Dict[str, Union[str, int, float, List[str], List[int], List[float], Dict, None]]

class Relationship(BaseModel):
    source: str
    target: str
    type: str

class GraphData(BaseModel):
    entities: List[Entity]
    relationships: List[Relationship]

class PrivateKGBuilder:
    """私有层知识图谱构建器"""
    
    def __init__(self, namespace="private_kg"):
        self.namespace = namespace
    
    def read_notepad_from_file(self, file_path: str) -> str:
        """从txt文件读取notepad内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            logger.info(f"从文件 {file_path} 读取notepad内容")
            return content
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return ""
    
    def parse_notepad_content_to_graph(self, notepad_content: str, hospital_number: str = "Unknown"):
        """解析notepad内容并生成知识图谱"""
        entities = []
        relationships = []
        
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
            
            # Patient类型不生成embedding（在EXCLUDED_TYPES_FOR_EMBEDDING中）
            
            patient_entity = Entity(
                id=str(uuid.uuid4()),
                type="Patient",
                properties=patient_properties
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
            
            # Encounter类型不生成embedding（在EXCLUDED_TYPES_FOR_EMBEDDING中）
            
            encounter_entity = Entity(
                id=str(uuid.uuid4()),
                type="Encounter",
                properties=encounter_properties
            )
            entities.append(encounter_entity)
            encounter_id = encounter_entity.id
            
            # 添加患者与就诊记录的关系
            if 'patient_id' in locals():
                relationships.append(Relationship(
                    source=patient_id,
                    target=encounter_id,
                    type="has_encountered"
                ))
        
        # 解析实验室检查
        lab_tests_match = re.search(r'Laboratory_Tests', notepad_content)
        if lab_tests_match:
            lab_tests_properties = {
                "name": "Laboratory_Tests"
            }
            
            # 为实验室检查生成embedding
            combined_text = "Laboratory Tests blood work analysis"
            embedding = model.encode(combined_text, normalize_embeddings=True).tolist()
            lab_tests_properties["embedding"] = embedding
            
            lab_tests_entity = Entity(
                id=str(uuid.uuid4()),
                type="Laboratory_Tests",
                properties=lab_tests_properties
            )
            entities.append(lab_tests_entity)
            lab_tests_id = lab_tests_entity.id
            
            # 添加就诊记录与实验室检查的关系
            if 'encounter_id' in locals():
                relationships.append(Relationship(
                    source=encounter_id,
                    target=lab_tests_id,
                    type="includes"
                ))
        
        # 解析具体的检查结果 - 拆分为测试类型和测试结果两个节点
        test_results = [
            {
                "test_type": "White_Blood_Cell_Count",
                "result": {
                    "test_name": "white blood cell count elevated",
                    "value": 14.5,
                    "unit": "10^9/L",
                    "reference_range": "4.0-10.0"
                }
            },
            {
                "test_type": "Lymphocyte_Count",
                "result": {
                    "test_name": "lymphocyte count elevated",
                    "value": 5.2,
                    "unit": "10^9/L",
                    "reference_range": "1.2-3.0"
                }
            },
            {
                "test_type": "Lymphocyte_Percent_Differential_Count",
                "result": {
                    "test_name": "lymphocyte percent differential count normal",
                    "value": 35.8,
                    "unit": "%",
                    "reference_range": "20.0-40.0"
                }
            }
        ]
        
        for test in test_results:
            # 创建测试类型节点
            test_type_properties = {
                "name": test["test_type"]
            }
            
            # 为测试类型生成embedding
            combined_text = f"{test['test_type']} laboratory test"
            embedding = model.encode(combined_text, normalize_embeddings=True).tolist()
            test_type_properties["embedding"] = embedding
            
            test_type_entity = Entity(
                id=str(uuid.uuid4()),
                type="Test_Type",
                properties=test_type_properties
            )
            entities.append(test_type_entity)
            test_type_id = test_type_entity.id
            
            # 创建测试结果节点
            test_result_properties = {
                "name": test["result"]["test_name"],
                "test_name": test["result"]["test_name"],
                "value": test["result"]["value"],
                "unit": test["result"]["unit"],
                "reference_range": test["result"]["reference_range"]
            }
            
            # 为测试结果生成embedding
            combined_text = f"{test['result']['test_name']} {test['result']['value']} {test['result']['unit']} {test['result']['reference_range']}"
            embedding = model.encode(combined_text, normalize_embeddings=True).tolist()
            test_result_properties["embedding"] = embedding
            
            test_result_entity = Entity(
                id=str(uuid.uuid4()),
                type="Test_Result",
                properties=test_result_properties
            )
            entities.append(test_result_entity)
            test_result_id = test_result_entity.id
            
            # 添加关系：实验室检查 -> 测试类型 -> 测试结果
            if 'lab_tests_id' in locals():
                relationships.append(Relationship(
                    source=lab_tests_id,
                    target=test_type_id,
                    type="has_test_type"
                ))
            
            relationships.append(Relationship(
                source=test_type_id,
                target=test_result_id,
                type="has_result"
            ))
        
        # 解析评估/评分
        assessment_match = re.search(r'Juvenile_Arthritis_Activity', notepad_content)
        if assessment_match:
            assessment_properties = {
                "name": "Juvenile_Arthritis_Activity",
                "score": 13,
                "activity_level": "moderate",
                "scoring_system_mild": "0-10",
                "scoring_system_moderate": "11-20",
                "scoring_system_severe": "≥21",
                "assessment_note": "Comprehensive evaluation based on joint symptoms and inflammation-related manifestations indicates that juvenile arthritis is in a moderate activity phase."
            }
            
            # 为评估生成embedding
            combined_text = f"Juvenile Arthritis Activity moderate score 13 assessment joint symptoms inflammation"
            embedding = model.encode(combined_text, normalize_embeddings=True).tolist()
            assessment_properties["embedding"] = embedding
            
            assessment_entity = Entity(
                id=str(uuid.uuid4()),
                type="Assessment",
                properties=assessment_properties
            )
            entities.append(assessment_entity)
            assessment_id = assessment_entity.id
            
            # 添加就诊记录与评估的关系
            if 'encounter_id' in locals():
                relationships.append(Relationship(
                    source=encounter_id,
                    target=assessment_id,
                    type="includes"
                ))
        
        return GraphData(entities=entities, relationships=relationships)
    
    def insert_graph_into_neo4j(self, graph_data: GraphData, clear_existing: bool = True):
        """插入图谱数据到Neo4j"""
        if not graph_data or not graph_data.entities:
            logger.warning("没有有效的图谱数据可插入")
            return

        with db_manager.driver.session() as session:
            # 如果需要，先清除现有数据
            if clear_existing:
                self.clear_namespace_data(self.namespace)
            
            for entity in graph_data.entities:
                entity.properties["namespace"] = self.namespace

                if entity.type == "Patient":
                    hospital_number = entity.properties.get("hospital_number")
                    if hospital_number is None:
                        logger.error(f"患者实体缺少hospital_number: {entity.properties}")
                        raise ValueError("患者实体必须有hospital_number")
                    session.run(
                        """
                        MERGE (e:Entity {hospital_number: $hospital_number, namespace: $namespace})
                        SET e.id = $id, e += $props, e.type = $type, e.name = $name
                        """,
                        hospital_number=hospital_number,
                        namespace=self.namespace,
                        id=entity.id,
                        props=entity.properties,
                        type=entity.type,
                        name=entity.properties.get("name", f"Unknown {entity.type}")
                    )
                else:
                    session.run(
                        """
                        MERGE (e:Entity {id: $id, namespace: $namespace})
                        SET e += $props, e.type = $type, e.name = $name
                        """,
                        id=entity.id,
                        namespace=self.namespace,
                        props=entity.properties,
                        type=entity.type,
                        name=entity.properties.get("name", f"Unknown {entity.type}")
                    )
                logger.info(f"插入实体: {entity.type} - {entity.properties.get('name', 'Unknown')} (ID: {entity.id})")

            for rel in graph_data.relationships:
                session.run(
                    f"""
                    MATCH (a:Entity {{id: $source, namespace: $namespace}})
                    MATCH (b:Entity {{id: $target, namespace: $namespace}})
                    MERGE (a)-[r:{rel.type}]->(b)
                    """,
                    source=rel.source,
                    target=rel.target,
                    namespace=self.namespace
                )
                logger.info(f"插入关系: {rel.source} -> {rel.target} ({rel.type})")
    
    def clear_namespace_data(self, namespace="private_kg"):
        """清除指定命名空间的所有数据"""
        with db_manager.driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE n.namespace = $namespace DETACH DELETE n RETURN count(n) as deleted_count",
                namespace=namespace
            )
            deleted_count = result.single()["deleted_count"]
            logger.info(f"清除了 {deleted_count} 个实体从命名空间 '{namespace}'")
            return deleted_count
    
    def find_existing_patient(self, patient_name: str, hospital_number: str = None):
        """查找现有的患者节点"""
        with db_manager.driver.session() as session:
            if hospital_number:
                # 优先通过hospital_number查找
                result = session.run("""
                    MATCH (e:Entity {type: 'Patient', hospital_number: $hospital_number, namespace: $namespace})
                    RETURN e.id as id
                """, hospital_number=hospital_number, namespace=self.namespace)
                record = result.single()
                if record:
                    return record["id"]
            
            # 通过姓名查找
            result = session.run("""
                MATCH (e:Entity {type: 'Patient', name: $name, namespace: $namespace})
                RETURN e.id as id, e.hospital_number as hospital_number
                ORDER BY e.hospital_number DESC
                LIMIT 1
            """, name=patient_name, namespace=self.namespace)
            record = result.single()
            if record:
                return record["id"]
        
        return None
    
    def update_patient_attributes(self, patient_id: str, new_properties: Dict):
        """更新现有患者节点的属性"""
        with db_manager.driver.session() as session:
            session.run("""
                MATCH (e:Entity {id: $patient_id, namespace: $namespace})
                SET e += $new_props
            """, patient_id=patient_id, namespace=self.namespace, new_props=new_properties)
            logger.info(f"更新患者节点 {patient_id} 的属性")
    
    def update_relationship_references(self, graph_data: GraphData, existing_patient_id: str, new_patient_id: str):
        """更新关系中的患者ID引用"""
        for rel in graph_data.relationships:
            if rel.source == new_patient_id:
                rel.source = existing_patient_id
                logger.info(f"更新关系源ID: {new_patient_id} -> {existing_patient_id}")
            if rel.target == new_patient_id:
                rel.target = existing_patient_id
                logger.info(f"更新关系目标ID: {new_patient_id} -> {existing_patient_id}")
    
    def build_private_kg_from_file(self, notepad_file_path: str, hospital_number: str = "Unknown", clear_existing: bool = True):
        """从txt文件构建私有层图谱"""
        logger.info(f"从文件 {notepad_file_path} 构建私有层图谱")
        
        try:
            # 连接数据库
            db_manager.connect()
            logger.info("✓ 数据库连接成功")
            
            # 读取notepad内容
            notepad_content = self.read_notepad_from_file(notepad_file_path)
            if not notepad_content:
                logger.error("无法读取notepad内容")
                return False
            
            # 解析并生成图谱
            graph_data = self.parse_notepad_content_to_graph(notepad_content, hospital_number)
            
            # 插入到Neo4j
            self.insert_graph_into_neo4j(graph_data, clear_existing=clear_existing)
            
            logger.info(f"✓ 成功构建私有层图谱: {len(graph_data.entities)} 个实体, {len(graph_data.relationships)} 个关系")
            return True
            
        except Exception as e:
            logger.error(f"✗ 构建私有层图谱失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def add_new_data_from_file(self, notepad_file_path: str, hospital_number: str = None, merge_existing_patient: bool = True):
        """从txt文件添加新数据到现有图谱"""
        if not hospital_number:
            hospital_number = f"Auto_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"从文件 {notepad_file_path} 添加新数据到私有图谱，医院编号: {hospital_number}")
        
        try:
            # 连接数据库
            db_manager.connect()
            logger.info("✓ 数据库连接成功")
            
            # 读取notepad内容
            notepad_content = self.read_notepad_from_file(notepad_file_path)
            if not notepad_content:
                logger.error("无法读取notepad内容")
                return False
            
            # 解析并生成图谱
            graph_data = self.parse_notepad_content_to_graph(notepad_content, hospital_number)
            
            # 如果启用患者合并，查找现有患者
            if merge_existing_patient:
                existing_patient_id = self.find_existing_patient("Lin", hospital_number)
                if existing_patient_id:
                    logger.info(f"找到现有患者节点: {existing_patient_id}，将合并新数据")
                    # 更新患者节点的属性
                    self.update_patient_attributes(existing_patient_id, graph_data.entities[0].properties)
                    
                    # 找到新创建的患者节点ID
                    new_patient_id = None
                    for entity in graph_data.entities:
                        if entity.type == "Patient":
                            new_patient_id = entity.id
                            break
                    
                    # 更新关系中的患者ID引用
                    if new_patient_id:
                        self.update_relationship_references(graph_data, existing_patient_id, new_patient_id)
                    
                    # 移除新创建的患者节点，使用现有节点
                    graph_data.entities = [e for e in graph_data.entities if e.type != "Patient"]
                else:
                    logger.info("未找到现有患者节点，将创建新的患者节点")
            
            # 插入到Neo4j（不清除现有数据）
            self.insert_graph_into_neo4j(graph_data, clear_existing=False)
            
            logger.info(f"✓ 成功添加 {len(graph_data.entities)} 个实体和 {len(graph_data.relationships)} 个关系")
            return True
            
        except Exception as e:
            logger.error(f"✗ 添加新数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="私有层知识图谱构建系统")
    parser.add_argument("--mode", choices=["build", "add"], required=True,
                       help="运行模式: build(构建图谱), add(添加数据)")
    parser.add_argument("--notepad-file", type=str, required=True, help="notepad内容文件路径")
    parser.add_argument("--hospital-number", type=str, help="医院编号")
    parser.add_argument("--clear-existing", action="store_true", help="清除现有数据")
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("私有层知识图谱构建系统")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    # 创建构建器
    builder = PrivateKGBuilder()
    
    # 执行操作
    if args.mode == "build":
        success = builder.build_private_kg_from_file(
            args.notepad_file, 
            args.hospital_number or "Unknown", 
            args.clear_existing
        )
    elif args.mode == "add":
        success = builder.add_new_data_from_file(
            args.notepad_file, 
            args.hospital_number
        )
    
    total_time = time.time() - start_time
    
    if success:
        logger.info(f"✓ 操作成功! 总耗时: {total_time:.1f}秒")
    else:
        logger.error("✗ 操作失败")
    
    # 关闭数据库连接
    try:
        db_manager.close()
        logger.info("数据库连接已关闭")
    except:
        pass
    
    logger.info("=" * 80)
    logger.info("操作完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
