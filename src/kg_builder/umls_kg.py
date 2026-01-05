"""
UMLS知识图谱集成模块
"""
import os
import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Any
from tqdm import tqdm

from ..core.models import Entity, Relationship, MedicalConcept
from ..core.database import db_manager
from ..core.embeddings import embedding_manager
from ..config.settings import settings

logger = logging.getLogger(__name__)

class UMLSKGBuilder:
    """UMLS知识图谱构建器"""
    
    def __init__(self, skip_embeddings: bool = True):
        self.skip_embeddings = skip_embeddings
        self.rel_label_map = {
            # ========== REL字段映射 - 10种基础关系类型 ==========
            "SY": "synonym_of",              # Synonym - 同义词关系
            "PAR": "is_parent_of",           # Parent - 父级关系
            "CHD": "is_child_of",            # Child - 子级关系
            "RB": "is_broader_than",         # Broader - 更广泛关系
            "RN": "is_narrower_than",        # Narrower - 更狭窄关系
            "RO": "other_relation",          # Other - 其他关系
            "RQ": "related_to",              # Related and possibly synonymous - 相关关系
            "RL": "similar_or_like",         # Similar or "like" - 相似关系
            "AQ": "allowed_qualifier",       # Allowed qualifier - 允许的限定词
            "QB": "qualified_by",            # Qualified by - 被限定
            
            # ========== RELA字段映射 - 具体关系类型 ==========
            
            # 层级关系 (Hierarchical)
            "isa": "is_a",
            "inverse_isa": "has_subtype",
            "classifies": "classifies",
            "classified_as": "classified_as",
            "parent_of": "parent_of",
            
            # 部分-整体关系 (Part-Whole)
            "part_of": "part_of",
            "has_part": "has_part",
            "component_of": "component_of",
            "has_component": "has_component",
            "ingredient_of": "ingredient_of",
            "has_ingredient": "has_ingredient",
            "contains": "contains",
            
            # 解剖定位 (Anatomical Location)
            "location_of": "location_of",
            "has_location": "has_location",
            "finding_site_of": "finding_site_of",
            "has_finding_site": "has_finding_site",
            "occurs_in": "occurs_in",
            "has_occurrence": "has_occurrence",
            "procedure_site_of": "procedure_site_of",
            "has_procedure_site": "has_procedure_site",
            "direct_procedure_site_of": "direct_procedure_site_of",
            "has_direct_procedure_site": "has_direct_procedure_site",
            
            # 因果关系 (Causality)
            "causes": "causes",
            "caused_by": "caused_by",
            "manifestation_of": "manifestation_of",
            "has_manifestation": "has_manifestation",
            "indicates": "indicates",
            "indicated_by": "indicated_by",
            "produces": "produces",
            "produced_by": "produced_by",
            "brings_about": "brings_about",
            "brought_about_by": "brought_about_by",
            "result_of": "result_of",
            "has_result": "has_result",
            "pathological_process_of": "pathological_process_of",
            "has_pathological_process": "has_pathological_process",
            "causative_agent_of": "causative_agent_of",
            "has_causative_agent": "has_causative_agent",
            
            # 临床关系 (Clinical)
            "may_treat": "may_treat",
            "may_be_treated_by": "may_be_treated_by",
            "may_prevent": "may_prevent",
            "may_be_prevented_by": "may_be_prevented_by",
            "may_diagnose": "may_diagnose",
            "diagnoses": "diagnoses",
            "diagnosed_by": "diagnosed_by",
            
            # 药物关系 (Pharmaceutical)
            "active_ingredient_of": "active_ingredient_of",
            "has_active_ingredient": "has_active_ingredient",
            "inactive_ingredient_of": "inactive_ingredient_of",
            "has_inactive_ingredient": "has_inactive_ingredient",
            "active_moiety_of": "active_moiety_of",
            "has_active_moiety": "has_active_moiety",
            "dose_form_of": "dose_form_of",
            "has_dose_form": "has_dose_form",
            "tradename_of": "tradename_of",
            "has_tradename": "has_tradename",
            
            # 形态学关系 (Morphology)
            "associated_morphology_of": "associated_morphology_of",
            "has_associated_morphology": "has_associated_morphology",
            
            # 方法和过程 (Method & Procedure)
            "method_of": "method_of",
            "has_method": "has_method",
            "uses": "uses",
            "used_by": "used_by",
            "used_for": "used_for",
            "usage_of": "usage_of",
            
            # 关联关系 (Association)
            "associated_with": "associated_with",
            "associated_finding_of": "associated_finding_of",
            "has_associated_finding": "has_associated_finding",
            
            # 测量和评估 (Measurement & Evaluation)
            "measures": "measures",
            "measured_by": "measured_by",
            "property_of": "property_of",
            "has_property": "has_property",
            "is_interpreted_by": "is_interpreted_by",
            "interprets": "interprets",
            
            # 分类和映射关系
            "classifies": "classifies",
            "classified_as": "classified_as",
            "mapped_from": "mapped_from",
            "mapped_to": "mapped_to",
            "same_as": "same_as",
            "possibly_equivalent_to": "possibly_equivalent_to",
            "partially_equivalent_to": "partially_equivalent_to",
            
            # 形态学关系
            "associated_morphology_of": "associated_morphology_of",
            "has_associated_morphology": "has_associated_morphology",
            "has_direct_morphology": "has_direct_morphology",
            "direct_morphology_of": "direct_morphology_of",
            "has_indirect_morphology": "has_indirect_morphology",
            "indirect_morphology_of": "indirect_morphology_of",
            
            # 药物成分关系
            "inactive_ingredient_of": "inactive_ingredient_of",
            "has_inactive_ingredient": "has_inactive_ingredient",
            "active_moiety_of": "active_moiety_of",
            "has_active_moiety": "has_active_moiety",
            "dose_form_of": "dose_form_of",
            "has_dose_form": "has_dose_form",
            "has_tradename": "has_tradename",
            "tradename_of": "tradename_of",
            "precise_ingredient_of": "precise_ingredient_of",
            "has_precise_active_ingredient": "has_precise_active_ingredient",
            
            # 过程和方法关系
            "has_method": "has_method",
            "method_of": "method_of",
            "has_finding_method": "has_finding_method",
            "finding_method_of": "finding_method_of",
            "pathological_process_of": "pathological_process_of",
            "has_pathological_process": "has_pathological_process",
            
            # 部位关系（手术/操作）
            "has_direct_procedure_site": "has_direct_procedure_site",
            "direct_procedure_site_of": "direct_procedure_site_of",
            "has_procedure_site": "has_procedure_site",
            "procedure_site_of": "procedure_site_of",
            "has_indirect_procedure_site": "has_indirect_procedure_site",
            "indirect_procedure_site_of": "indirect_procedure_site_of",
            "has_finding_site": "has_finding_site",
            "finding_site_of": "finding_site_of",
            
            # 装置关系
            "has_direct_device": "has_direct_device",
            "direct_device_of": "direct_device_of",
            "has_procedure_device": "has_procedure_device",
            "procedure_device_of": "procedure_device_of",
            "uses_device": "uses_device",
            "device_used_by": "device_used_by",
            "has_indirect_device": "has_indirect_device",
            
            # 物质关系
            "has_direct_substance": "has_direct_substance",
            "direct_substance_of": "direct_substance_of",
            "uses_substance": "uses_substance",
            "substance_used_by": "substance_used_by",
            
            # 标本关系
            "has_specimen": "has_specimen",
            "specimen_of": "specimen_of",
            "has_specimen_substance": "has_specimen_substance",
            "specimen_substance_of": "specimen_substance_of",
            "has_specimen_source_topography": "has_specimen_source_topography",
            "specimen_source_topography_of": "specimen_source_topography_of",
            
            # 临床关联
            "associated_with": "associated_with",
            "clinically_associated_with": "clinically_associated_with",
            "clinically_similar": "clinically_similar",
            "co-occurs_with": "co-occurs_with",
            "has_associated_finding": "has_associated_finding",
            "associated_finding_of": "associated_finding_of",
            "associated_procedure_of": "associated_procedure_of",
            "has_associated_procedure": "has_associated_procedure",
            
            # 禁忌症关系
            "has_contraindicated_drug": "has_contraindicated_drug",
            "contraindicated_with_disease": "contraindicated_with_disease",
            "has_contraindicated_class": "has_contraindicated_class",
            "contraindicated_class_of": "contraindicated_class_of",
            
            # 解释和上下文
            "interpretation_of": "interpretation_of",
            "has_interpretation": "has_interpretation",
            "temporal_context_of": "temporal_context_of",
            "has_temporal_context": "has_temporal_context",
            "procedure_context_of": "procedure_context_of",
            "has_procedure_context": "has_procedure_context",
            
            # 焦点和成员关系
            "has_focus": "has_focus",
            "focus_of": "focus_of",
            "has_member": "has_member",
            "member_of": "member_of",
            
            # 层次结构（补充）
            "parent_of": "parent_of",
            "has_parent": "has_parent",
            "was_a": "was_a",
            "inverse_was_a": "inverse_was_a",
            
            # 表单和显示
            "has_form": "has_form",
            "form_of": "form_of",
            "has_consumer_friendly_form": "has_consumer_friendly_form",
            "consumer_friendly_form_of": "consumer_friendly_form_of",
            "has_clinician_form": "has_clinician_form",
            "clinician_form_of": "clinician_form_of",
            
            # 其他常用关系
            "ALT": "is_alternative_to",
            "ssc": "clinically_related_to",  # SNOMED CT: may_be_qualified_by - 临床相关/限定关系
            "ddx": "differential_diagnosis_of",  # Differential Diagnosis - 鉴别诊断关系
            "used_for": "used_for",
            "uses": "uses",
            "used_by": "used_by",
            "replaces": "replaces",
            "replaced_by": "replaced_by",
            "refers_to": "refers_to",
            "referred_to_by": "referred_to_by",
        }
    
    def load_umls_data(self) -> tuple[List[Dict], List[Dict]]:
        """加载UMLS数据"""
        try:
            nodes_path = os.path.join(settings.UMLS_DATA_DIR, "umls_comprehensive_nodes_all.npy")
            edges_path = os.path.join(settings.UMLS_DATA_DIR, "umls_comprehensive_edges_all.npy")
            
            nodes = np.load(nodes_path, allow_pickle=True).tolist()
            edges = np.load(edges_path, allow_pickle=True).tolist()
            
            # 过滤有效的CUI
            valid_cuis = set(n['CUI'] for n in nodes)
            edges = [e for e in edges if e["CUI1"] in valid_cuis and e["CUI2"] in valid_cuis]
            
            logger.info(f"加载UMLS数据: {len(nodes)} 个节点, {len(edges)} 条边")
            return nodes, edges
            
        except Exception as e:
            logger.error(f"加载UMLS数据失败: {e}")
            return [], []
    
    def load_srdef(self) -> Dict[str, str]:
        """加载SRDEF关系定义"""
        try:
            df_srdef = pd.read_csv(settings.SRDEF_PATH, sep='|', header=None, dtype=str)
            df_srdef.columns = ["Type", "Code", "Name", "TreeNumber", "Definition", "5", "6", "7", "Abbrev", "9", "10"]
            
            rel_def_map = df_srdef[df_srdef["Type"] == "REL"].set_index("Code")["Definition"].to_dict()
            return rel_def_map
            
        except Exception as e:
            logger.error(f"加载SRDEF失败: {e}")
            return {}
    
    def create_umls_entities(self, nodes: List[Dict]) -> List[Entity]:
        """创建UMLS实体（批量生成嵌入向量）"""
        entities = []
        
        # 获取配置中的实体类型过滤设置
        enabled_entity_types = settings.UMLS_ENABLED_ENTITY_TYPES
        filter_enabled = settings.UMLS_ENTITY_TYPE_FILTER_ENABLED
        
        logger.info(f"实体类型过滤设置: 启用={filter_enabled}, 允许的实体类型数量={len(enabled_entity_types)}")
        
        # 先创建所有实体（不生成嵌入向量）
        for node in tqdm(nodes, desc="创建UMLS实体"):
            try:
                # 处理None值
                name = node.get('STR', '')
                if name is None or name.strip() == '':
                    name = f"Unknown_{node['CUI']}"  # 使用CUI作为备用名称
                
                # 获取语义类型，用作实体类型
                semantic_type = node.get('STN', '')
                if not semantic_type or semantic_type.strip() == '':
                    semantic_type = 'T071'  # 默认使用Entity类型
                
                # 如果启用了实体类型过滤，检查语义类型是否在允许列表中
                if filter_enabled and semantic_type not in enabled_entity_types:
                    continue
                
                entity = Entity(
                    id=node['CUI'],
                    name=name,  # 确保name不为None
                    entity_type=semantic_type,  # 使用语义类型作为实体类型
                    properties={
                        'cui': node['CUI'],
                        'definition': node.get('DEF', ''),
                        'semantic_definition': node.get('SEMDEF', ''),
                        'umls_data': node
                    },
                    namespace='umls_kg'
                )
                entities.append(entity)
                
            except Exception as e:
                logger.error(f"创建UMLS实体失败: {e}")
                continue
        
        # 根据配置决定是否生成嵌入向量
        if not self.skip_embeddings:
            logger.info("开始批量生成嵌入向量...")
            names = [entity.name for entity in entities if entity.name and entity.name != '']
            if names:
                embeddings = embedding_manager.generate_embeddings_batch(names)
                embedding_idx = 0
                for entity in entities:
                    if entity.name and entity.name != '':
                        entity.embedding = embeddings[embedding_idx]
                        embedding_idx += 1
        else:
            logger.info("跳过嵌入向量生成 - UMLS数据量过大（145万个节点）")
            logger.info("如需嵌入向量，建议使用预计算的向量或分批处理")
        
        return entities

    def create_umls_relationships(self, edges: List[Dict], rel_def_map: Dict[str, str]) -> List[Relationship]:
        """创建UMLS关系"""
        relationships = []
        
        # 获取配置中的关系过滤设置
        enabled_relationships = settings.UMLS_ENABLED_RELATIONSHIPS
        filter_enabled = settings.UMLS_RELATIONSHIP_FILTER_ENABLED
        
        logger.info(f"关系过滤设置: 启用={filter_enabled}, 允许的关系类型={enabled_relationships}")
        
        for edge in tqdm(edges, desc="创建UMLS关系"):
            try:
                # 修复字段映射：使用实际的REL和RELA字段
                rel = edge.get('REL', '')
                rela = edge.get('RELA', '')
                
                # 优先使用RELA，如果没有则使用REL
                rel_type = rela if rela else rel
                rel_label = self.rel_label_map.get(rel_type, rel_type)
                
                # 如果启用了关系过滤，检查关系类型是否在允许列表中
                if filter_enabled and rel_label not in enabled_relationships:
                    continue
                
                relationship = Relationship(
                    source=edge['CUI1'],
                    target=edge['CUI2'],
                    relationship_type=rel_label,
                    properties={
                        'original_rel': rel,
                        'original_rela': rela,
                        'original_relation': rel_type,
                        'definition': rel_def_map.get(rel_type, ''),
                        'umls_data': edge
                    },
                    namespace='umls_kg'
                )
                
                relationships.append(relationship)
                
            except Exception as e:
                logger.error(f"创建UMLS关系失败: {e}")
                continue
        
        logger.info(f"过滤后创建了 {len(relationships)} 个关系")
        
        # 统计关系类型分布
        if relationships:
            rel_type_counts = {}
            for rel in relationships:
                rel_type = rel.relationship_type
                rel_type_counts[rel_type] = rel_type_counts.get(rel_type, 0) + 1
            
            logger.info("关系类型统计:")
            for rel_type, count in sorted(rel_type_counts.items()):
                logger.info(f"  {rel_type}: {count} 个")
        
        return relationships
    
    def build_umls_kg(self) -> bool:
        """构建UMLS知识图谱"""
        try:
            logger.info("开始构建UMLS知识图谱")
            
            # 清除现有数据
            db_manager.clear_namespace("umls_kg")
            
            # 加载数据
            nodes, edges = self.load_umls_data()
            if not nodes or not edges:
                logger.error("UMLS数据加载失败")
                return False
            
            # 加载关系定义
            rel_def_map = self.load_srdef()
            
            # 创建实体
            entities = self.create_umls_entities(nodes)
            logger.info(f"创建了 {len(entities)} 个UMLS实体")
            
            # 批量保存实体到数据库
            total_entities = db_manager.create_entities_batch(entities, batch_size=10000)
            logger.info(f"批量保存了 {total_entities} 个实体")
            
            # 创建关系
            relationships = self.create_umls_relationships(edges, rel_def_map)
            logger.info(f"创建了 {len(relationships)} 个UMLS关系")
            
            # 批量保存关系到数据库
            total_relationships = db_manager.create_relationships_batch(relationships, batch_size=10000)
            logger.info(f"批量保存了 {total_relationships} 个关系")
            
            logger.info(f"UMLS知识图谱构建完成: {total_entities} 个实体, {total_relationships} 个关系")
            return True
            
        except Exception as e:
            logger.error(f"构建UMLS知识图谱失败: {e}")
            return False
