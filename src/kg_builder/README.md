# 知识图谱构建模块 (kg_builder/)

本模块负责构建和管理医疗知识图谱，包括私有知识图谱、UMLS知识图谱、实体连接和动态更新等功能。

## 文件说明

### `private_kg.py`
- **功能**: 私有知识图谱构建
- **特性**:
  - 从Notepad数据构建私有图谱
  - 支持增量更新
  - 实体和关系提取
  - 向量化处理

### `umls_kg.py`
- **功能**: UMLS知识图谱构建
- **特性**:
  - 从UMLS数据构建标准医疗概念图谱
  - 支持多种UMLS数据格式
  - 概念层次结构处理
  - 语义类型映射

### `entity_connector.py`
- **功能**: 实体关联处理
- **特性**:
  - 连接私有和公有层实体
  - 基于语义相似度的匹配
  - 关系推理
  - 置信度计算

### `graph_updater.py`
- **功能**: 动态图谱更新
- **特性**:
  - 增量添加新数据
  - 图谱结构更新
  - 冲突检测和解决
  - 版本管理

## 核心类说明

### 私有知识图谱构建器 (private_kg.py)

#### `PrivateKGBuilder`
```python
class PrivateKGBuilder:
    """私有知识图谱构建器"""
    
    def build_kg(self, notepad_file: str, hospital_number: str = None) -> bool:
        """构建私有知识图谱"""
        
    def add_new_data(self, notepad_content: str, hospital_number: str = None) -> bool:
        """添加新数据到现有图谱"""
        
    def clear_existing_data(self) -> bool:
        """清除现有私有图谱数据"""
```

### UMLS知识图谱构建器 (umls_kg.py)

#### `UMLSKGBuilder`
```python
class UMLSKGBuilder:
    """UMLS知识图谱构建器"""
    
    def build_umls_kg(self) -> bool:
        """构建UMLS知识图谱"""
        
    def load_concepts(self) -> List[Concept]:
        """加载UMLS概念"""
        
    def create_relationships(self) -> bool:
        """创建概念间关系"""
```

### 实体连接器 (entity_connector.py)

#### `EntityConnector`
```python
class EntityConnector:
    """实体连接器"""
    
    def connect_entities(self, similarity_threshold: float = 0.5) -> bool:
        """连接私有和公有层实体"""
        
    def find_similar_entities(self, private_entity: Entity) -> List[Entity]:
        """查找相似实体"""
        
    def create_connections(self, matches: List[Match]) -> bool:
        """创建实体连接"""
```

### 图谱更新器 (graph_updater.py)

#### `GraphUpdater`
```python
class GraphUpdater:
    """图谱更新器"""
    
    def add_new_data_from_notepad(self, notepad_content: str, hospital_number: str = None) -> GraphData:
        """从Notepad添加新数据"""
        
    def update_existing_entities(self, entities: List[Entity]) -> bool:
        """更新现有实体"""
        
    def resolve_conflicts(self, conflicts: List[Conflict]) -> bool:
        """解决数据冲突"""
```

## 使用方法

### 1. 构建私有知识图谱
```python
from src.kg_builder.private_kg import PrivateKGBuilder

builder = PrivateKGBuilder()

# 构建新的私有图谱
success = builder.build_kg(
    notepad_file="data/notepad.txt",
    hospital_number="12345"
)

# 添加新数据
success = builder.add_new_data(
    notepad_content="新的患者数据...",
    hospital_number="12345"
)
```

### 2. 构建UMLS知识图谱
```python
from src.kg_builder.umls_kg import UMLSKGBuilder

builder = UMLSKGBuilder()

# 构建UMLS图谱
success = builder.build_umls_kg()
```

### 3. 连接实体
```python
from src.kg_builder.entity_connector import EntityConnector

connector = EntityConnector()

# 连接私有和公有层实体
success = connector.connect_entities(similarity_threshold=0.6)
```

### 4. 动态更新图谱
```python
from src.kg_builder.graph_updater import GraphUpdater

updater = GraphUpdater()

# 添加新数据
graph_data = updater.add_new_data_from_notepad(
    notepad_content="患者新数据...",
    hospital_number="12345"
)
```

## 数据格式

### Notepad数据格式
```json
{
  "patients": [
    {
      "name": "Lin",
      "age": 7,
      "gender": "female",
      "symptoms": ["发热", "咳嗽"],
      "diagnosis": "上呼吸道感染",
      "medications": ["布洛芬", "阿莫西林"]
    }
  ]
}
```

### UMLS数据格式
- **MRCONSO**: 概念标识符和字符串
- **MRREL**: 概念间关系
- **MRSTY**: 语义类型
- **SRDEF**: 语义类型定义

## 配置要求

### 数据路径配置
```python
# 在settings.py中配置
UMLS_DATA_DIR = "/path/to/umls/data"
SRDEF_PATH = "/path/to/srdef"
```

### 处理参数配置
```python
SIMILARITY_THRESHOLD = 0.5
BATCH_SIZE = 1000
MAX_ENTITIES_PER_BATCH = 100
```

## 性能优化

### 1. 批处理优化
- 使用批量操作减少数据库交互
- 合理设置批处理大小
- 并行处理独立任务

### 2. 内存管理
- 流式处理大文件
- 及时释放不需要的对象
- 使用生成器处理大数据集

### 3. 数据库优化
- 使用事务批量提交
- 创建适当的索引
- 优化Cypher查询

## 错误处理

### 数据格式错误
```python
try:
    builder.build_kg(notepad_file)
except DataFormatError as e:
    logger.error(f"数据格式错误: {e}")
    # 处理错误
```

### 数据库错误
```python
try:
    connector.connect_entities()
except DatabaseError as e:
    logger.error(f"数据库操作失败: {e}")
    # 处理错误
```

## 扩展指南

### 添加新的实体类型
1. 在相应的构建器中添加解析逻辑
2. 定义新的实体属性
3. 更新关系创建逻辑
4. 添加单元测试

### 支持新的数据格式
1. 创建新的数据解析器
2. 实现格式转换逻辑
3. 添加配置选项
4. 更新文档

### 优化连接算法
1. 实现新的相似度计算方法
2. 添加机器学习模型支持
3. 优化匹配性能
4. 添加评估指标

## 监控和日志

### 构建进度监控
- 记录处理进度
- 监控内存使用
- 跟踪错误率
- 性能指标统计

### 日志记录
```python
logger.info(f"开始构建私有知识图谱: {notepad_file}")
logger.info(f"处理了 {count} 个实体")
logger.error(f"构建失败: {error}")
```

## 注意事项

1. **数据质量**: 确保输入数据格式正确
2. **内存使用**: 大文件处理时注意内存管理
3. **并发安全**: 避免同时修改同一图谱
4. **备份**: 重要操作前备份数据
5. **验证**: 构建完成后验证图谱完整性

## 故障排除

### 常见问题

1. **构建失败**
   - 检查数据文件格式
   - 验证数据库连接
   - 查看错误日志

2. **连接质量差**
   - 调整相似度阈值
   - 检查向量化质量
   - 优化匹配算法

3. **性能问题**
   - 减少批处理大小
   - 优化数据库查询
   - 增加系统内存
