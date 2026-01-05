"""
实体关联模块
"""
import logging
from typing import List, Tuple, Dict, Any
from tqdm import tqdm

from ..core.models import Entity, Relationship
from ..core.database import db_manager
from ..core.embeddings import embedding_manager
from ..config.settings import settings

logger = logging.getLogger(__name__)

class EntityConnector:
    """实体关联器"""
    
    def __init__(self):
        self.similarity_threshold = settings.CROSS_GRAPH_SIMILARITY_THRESHOLD
    
    def find_similar_entities(self, private_entities: List[Entity], 
                            umls_entities: List[Entity]) -> List[Tuple[Entity, Entity, float]]:
        """查找相似的实体对"""
        similar_pairs = []
        
        logger.info("开始查找相似实体")
        
        for private_entity in tqdm(private_entities, desc="匹配私有实体"):
            if not private_entity.embedding:
                continue
            
            best_match = None
            best_similarity = 0.0
            
            for umls_entity in umls_entities:
                if not umls_entity.embedding:
                    continue
                
                similarity = embedding_manager.calculate_similarity(
                    private_entity.embedding, 
                    umls_entity.embedding
                )
                
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = umls_entity
            
            if best_match:
                similar_pairs.append((private_entity, best_match, best_similarity))
                logger.info(f"找到匹配: {private_entity.name} <-> {best_match.name} (相似度: {best_similarity:.3f})")
        
        return similar_pairs
    
    def create_cross_graph_relationships(self, similar_pairs: List[Tuple[Entity, Entity, float]]) -> List[Relationship]:
        """创建跨图谱关系"""
        relationships = []
        
        for private_entity, umls_entity, similarity in similar_pairs:
            try:
                relationship = Relationship(
                    source_id=private_entity.id,
                    target_id=umls_entity.id,
                    relationship_type="REFERENCE_OF",
                    properties={
                        'similarity': similarity,
                        'connection_type': 'semantic_similarity'
                    },
                    confidence=similarity,
                    namespace='cross_graph'
                )
                relationships.append(relationship)
                
            except Exception as e:
                logger.error(f"创建跨图谱关系失败: {e}")
                continue
        
        return relationships
    
    def connect_entities(self) -> bool:
        """连接私有和UMLS实体"""
        try:
            logger.info("开始连接实体")
            
            # 获取私有实体
            private_entities = db_manager.find_entities_by_type("", "private_kg")
            logger.info(f"找到 {len(private_entities)} 个私有实体")
            
            # 获取UMLS实体
            umls_entities = db_manager.find_entities_by_type("Entity", "umls_kg")
            logger.info(f"找到 {len(umls_entities)} 个UMLS实体")
            
            # 查找相似实体
            similar_pairs = self.find_similar_entities(private_entities, umls_entities)
            logger.info(f"找到 {len(similar_pairs)} 对相似实体")
            
            # 创建跨图谱关系
            relationships = self.create_cross_graph_relationships(similar_pairs)
            logger.info(f"创建了 {len(relationships)} 个跨图谱关系")
            
            # 保存关系
            total_relationships = 0
            for relationship in relationships:
                if db_manager.create_relationship(relationship):
                    total_relationships += 1
            
            logger.info(f"实体连接完成: {total_relationships} 个跨图谱关系")
            return True
            
        except Exception as e:
            logger.error(f"连接实体失败: {e}")
            return False