"""
向量化处理模块
"""
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer, models
import numpy as np

from ..config.settings import settings

logger = logging.getLogger(__name__)

class EmbeddingManager:
    """向量化管理器"""
    
    def __init__(self):
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """加载嵌入模型"""
        try:
            # 创建模型组件
            word_embedding_model = models.Transformer(settings.EMBEDDING_MODEL)
            pooling_model = models.Pooling(
                word_embedding_model.get_word_embedding_dimension(),
                pooling_mode_mean_tokens=True,
                pooling_mode_cls_token=False,
                pooling_mode_max_tokens=False
            )
            
            # 构建SentenceTransformer模型
            self.model = SentenceTransformer(modules=[word_embedding_model, pooling_model])
            logger.info(f"成功加载嵌入模型: {settings.EMBEDDING_MODEL}")
        except Exception as e:
            logger.error(f"加载嵌入模型失败: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        try:
            if not self.model:
                raise ValueError("模型未加载")
            
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量"""
        try:
            if not self.model:
                raise ValueError("模型未加载")
            
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"批量生成嵌入向量失败: {e}")
            raise
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """计算两个嵌入向量的余弦相似度"""
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # 计算余弦相似度
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
        except Exception as e:
            logger.error(f"计算相似度失败: {e}")
            return 0.0
    
    def find_similar_entities(self, query_embedding: List[float], 
                            entity_embeddings: List[tuple], 
                            threshold: float = None) -> List[tuple]:
        """查找相似实体"""
        try:
            if threshold is None:
                threshold = settings.CROSS_GRAPH_SIMILARITY_THRESHOLD
                
            similar_entities = []
            
            for entity_id, entity_embedding in entity_embeddings:
                if entity_embedding is None:
                    continue
                
                similarity = self.calculate_similarity(query_embedding, entity_embedding)
                if similarity >= threshold:
                    similar_entities.append((entity_id, similarity))
            
            # 按相似度排序
            similar_entities.sort(key=lambda x: x[1], reverse=True)
            return similar_entities
        except Exception as e:
            logger.error(f"查找相似实体失败: {e}")
            return []

# 全局嵌入管理器实例
embedding_manager = EmbeddingManager()