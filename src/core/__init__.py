"""
核心模块
"""
from .database import Neo4jManager, get_db_manager, db_manager
# 延迟导入embeddings，避免触发不必要的依赖
try:
    from .embeddings import EmbeddingManager
except ImportError:
    EmbeddingManager = None
from .models import (
    Entity, Relationship, MedicalConcept, QueryResult, 
    Document, GraphData, PrivateLayerResult, PublicLayerResult
)

__all__ = [
    'Neo4jManager',
    'get_db_manager', 
    'db_manager',
    'EmbeddingManager',
    'Entity',
    'Relationship', 
    'MedicalConcept',
    'QueryResult',
    'Document',
    'GraphData',
    'PrivateLayerResult',
    'PublicLayerResult'
]