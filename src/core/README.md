# 核心模块 (core/)

本模块包含系统的核心功能，提供数据库管理、向量化处理和数据模型定义等基础服务。

## 文件说明

### `database.py`
- **功能**: 数据库连接管理
- **特性**:
  - Neo4j数据库连接池管理
  - 连接状态监控
  - 事务处理
  - 错误处理和重连机制

### `embeddings.py`
- **功能**: 向量化处理
- **特性**:
  - 文本向量化
  - 向量相似度计算
  - 批量处理支持
  - 模型缓存管理

### `models.py`
- **功能**: 数据模型定义
- **包含**:
  - 实体模型（Entity）
  - 关系模型（Relationship）
  - 查询结果模型（QueryResult）
  - 图谱数据模型（GraphData）

## 核心类说明

### 数据库管理 (database.py)

#### `DatabaseManager`
```python
class DatabaseManager:
    """数据库连接管理器"""
    
    def connect(self) -> bool:
        """建立数据库连接"""
        
    def close(self) -> None:
        """关闭数据库连接"""
        
    def execute_query(self, query: str, parameters: dict = None) -> List[dict]:
        """执行Cypher查询"""
        
    def execute_write(self, query: str, parameters: dict = None) -> bool:
        """执行写操作"""
```

### 向量化处理 (embeddings.py)

#### `EmbeddingManager`
```python
class EmbeddingManager:
    """向量化管理器"""
    
    def embed_text(self, text: str) -> np.ndarray:
        """将文本转换为向量"""
        
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """批量向量化"""
        
    def calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算向量相似度"""
```

### 数据模型 (models.py)

#### 实体模型
```python
@dataclass
class Entity:
    """实体模型"""
    name: str
    entity_type: str
    properties: Dict[str, Any]
    embedding: Optional[np.ndarray] = None
```

#### 关系模型
```python
@dataclass
class Relationship:
    """关系模型"""
    source: str
    target: str
    relationship_type: str
    properties: Dict[str, Any]
```

#### 查询结果模型
```python
@dataclass
class QueryResult:
    """查询结果模型"""
    entities: List[Entity]
    relationships: List[Relationship]
    confidence: float
    reasoning_chain: Optional[str] = None
```

## 使用方法

### 1. 数据库操作
```python
from src.core.database import db_manager

# 连接数据库
db_manager.connect()

# 执行查询
results = db_manager.execute_query(
    "MATCH (n:Entity) RETURN n LIMIT 10"
)

# 执行写操作
success = db_manager.execute_write(
    "CREATE (n:Entity {name: $name})",
    {"name": "新实体"}
)

# 关闭连接
db_manager.close()
```

### 2. 向量化处理
```python
from src.core.embeddings import embedding_manager

# 单个文本向量化
vector = embedding_manager.embed_text("患者症状描述")

# 批量向量化
texts = ["文本1", "文本2", "文本3"]
vectors = embedding_manager.embed_batch(texts)

# 计算相似度
similarity = embedding_manager.calculate_similarity(vector1, vector2)
```

### 3. 数据模型使用
```python
from src.core.models import Entity, Relationship, QueryResult

# 创建实体
entity = Entity(
    name="患者Lin",
    entity_type="Patient",
    properties={"age": 7, "gender": "female"}
)

# 创建关系
relationship = Relationship(
    source="患者Lin",
    target="发热",
    relationship_type="HAS_SYMPTOM",
    properties={"severity": "high"}
)

# 创建查询结果
result = QueryResult(
    entities=[entity],
    relationships=[relationship],
    confidence=0.95,
    reasoning_chain="基于症状匹配的推理"
)
```

## 配置要求

### 数据库配置
```python
# 在settings.py中配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password"
```

### 模型配置
```python
# 嵌入模型配置
EMBEDDING_MODEL = "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"
BATCH_SIZE = 1000
```

## 性能优化

### 1. 数据库优化
- 使用连接池管理连接
- 批量执行操作
- 合理使用索引
- 优化Cypher查询

### 2. 向量化优化
- 批量处理文本
- 模型缓存
- 异步处理
- 内存管理

### 3. 内存管理
- 及时释放大对象
- 使用生成器处理大数据
- 监控内存使用

## 错误处理

### 数据库错误
```python
try:
    db_manager.execute_query(query)
except Neo4jError as e:
    logger.error(f"数据库查询失败: {e}")
    # 处理错误
```

### 向量化错误
```python
try:
    vector = embedding_manager.embed_text(text)
except Exception as e:
    logger.error(f"向量化失败: {e}")
    # 处理错误
```

## 扩展指南

### 添加新的数据模型
1. 在`models.py`中定义新的数据类
2. 使用`@dataclass`装饰器
3. 添加类型提示
4. 更新文档

### 扩展数据库功能
1. 在`DatabaseManager`中添加新方法
2. 处理异常情况
3. 添加日志记录
4. 编写单元测试

### 添加新的向量化模型
1. 在`EmbeddingManager`中添加新模型支持
2. 实现模型加载和缓存
3. 添加配置选项
4. 测试性能影响

## 注意事项

1. **线程安全**: 数据库连接管理器是线程安全的
2. **资源管理**: 及时关闭数据库连接
3. **内存使用**: 注意向量化过程中的内存使用
4. **错误处理**: 所有操作都应包含适当的错误处理
5. **日志记录**: 重要操作都应记录日志

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查Neo4j服务状态
   - 验证连接参数
   - 检查网络连通性

2. **向量化失败**
   - 检查模型是否正确加载
   - 验证输入文本格式
   - 检查内存使用情况

3. **性能问题**
   - 监控数据库查询性能
   - 优化批处理大小
   - 检查索引使用情况
