"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
from dataclasses import dataclass
import uuid

class Entity(BaseModel):
    """实体模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    entity_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    namespace: str = "default"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class Relationship(BaseModel):
    """关系模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    relationship_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    namespace: str = "default"
    created_at: datetime = Field(default_factory=datetime.now)

class MedicalConcept(BaseModel):
    """医疗概念模型"""
    cui: str
    name: str
    definition: Optional[str] = None
    semantic_type: Optional[str] = None
    embedding: Optional[List[float]] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

class QueryResult(BaseModel):
    """查询结果模型"""
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    concepts: List[MedicalConcept] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning_chain: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class Document(BaseModel):
    """文档模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content: str
    file_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processed_at: datetime = Field(default_factory=datetime.now)
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)

class GraphData(BaseModel):
    """图谱数据模型"""
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)

@dataclass
class PrivateLayerResult:
    """私有层检索结果"""
    nodes: List[Dict] = None
    reasoning_chains: List[Dict] = None
    relationships: List[Dict] = None
    
    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []
        if self.reasoning_chains is None:
            self.reasoning_chains = []
        if self.relationships is None:
            self.relationships = []

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
