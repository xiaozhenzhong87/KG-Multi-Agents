# 检索系统模块 (retrieval/)

本模块提供智能检索和推理功能，支持多层级检索、语义搜索、推理链生成等高级功能。

## 文件说明

### `retriever.py`
- **功能**: 主检索器
- **特性**:
  - 统一检索接口
  - 多层级检索支持
  - 结果聚合和排序
  - 置信度计算

### `query_processor.py`
- **功能**: 查询处理
- **特性**:
  - 自然语言查询解析
  - 查询意图识别
  - 查询优化
  - 多语言支持

### `formatter.py`
- **功能**: 结果格式化
- **特性**:
  - 结果结构化输出
  - 多种输出格式支持
  - 结果摘要生成
  - 可视化数据准备

### `identifier.py`
- **功能**: 实体识别
- **特性**:
  - 命名实体识别
  - 医疗实体识别
  - 实体链接
  - 实体消歧

### `llm_integration.py`
- **功能**: LLM集成
- **特性**:
  - 大语言模型集成
  - 推理链生成
  - 自然语言生成
  - 上下文管理

### `multi_layer_retriever.py`
- **功能**: 多层级检索
- **特性**:
  - 跨层检索
  - 层级融合
  - 结果去重
  - 相关性排序

### `cross_layer_connector.py`
- **功能**: 跨层连接
- **特性**:
  - 层间关系发现
  - 跨层推理
  - 连接路径分析
  - 关系强度计算

## 核心类说明

### 主检索器 (retriever.py)

#### `MedicalRetriever`
```python
class MedicalRetriever:
    """医疗检索器"""
    
    def retrieve(self, query: str) -> QueryResult:
        """执行检索查询"""
        
    def retrieve_entities(self, query: str) -> List[Entity]:
        """检索相关实体"""
        
    def retrieve_relationships(self, query: str) -> List[Relationship]:
        """检索相关关系"""
        
    def generate_reasoning_chain(self, entities: List[Entity], relationships: List[Relationship]) -> str:
        """生成推理链"""
```

### 查询处理器 (query_processor.py)

#### `QueryProcessor`
```python
class QueryProcessor:
    """查询处理器"""
    
    def parse_query(self, query: str) -> ParsedQuery:
        """解析自然语言查询"""
        
    def identify_intent(self, query: str) -> QueryIntent:
        """识别查询意图"""
        
    def optimize_query(self, parsed_query: ParsedQuery) -> OptimizedQuery:
        """优化查询"""
```

### 结果格式化器 (formatter.py)

#### `ResultFormatter`
```python
class ResultFormatter:
    """结果格式化器"""
    
    def format_result(self, result: QueryResult, format_type: str = "structured") -> str:
        """格式化查询结果"""
        
    def generate_summary(self, result: QueryResult) -> str:
        """生成结果摘要"""
        
    def prepare_visualization_data(self, result: QueryResult) -> Dict:
        """准备可视化数据"""
```

### 实体识别器 (identifier.py)

#### `EntityIdentifier`
```python
class EntityIdentifier:
    """实体识别器"""
    
    def identify_entities(self, text: str) -> List[Entity]:
        """识别文本中的实体"""
        
    def link_entities(self, entities: List[Entity]) -> List[LinkedEntity]:
        """链接实体到知识图谱"""
        
    def disambiguate_entities(self, entities: List[Entity]) -> List[Entity]:
        """实体消歧"""
```

### LLM集成 (llm_integration.py)

#### `LLMIntegration`
```python
class LLMIntegration:
    """LLM集成"""
    
    def generate_reasoning(self, context: str, query: str) -> str:
        """生成推理链"""
        
    def answer_question(self, context: str, question: str) -> str:
        """回答问题"""
        
    def summarize_results(self, results: List[dict]) -> str:
        """总结结果"""
```

### 多层级检索器 (multi_layer_retriever.py)

#### `MultiLayerRetriever`
```python
class MultiLayerRetriever:
    """多层级检索器"""
    
    def retrieve_across_layers(self, query: str) -> MultiLayerResult:
        """跨层检索"""
        
    def fuse_results(self, results: List[QueryResult]) -> QueryResult:
        """融合多层级结果"""
        
    def rank_results(self, results: List[QueryResult]) -> List[QueryResult]:
        """结果排序"""
```

### 跨层连接器 (cross_layer_connector.py)

#### `CrossLayerConnector`
```python
class CrossLayerConnector:
    """跨层连接器"""
    
    def find_cross_layer_paths(self, source_entity: Entity, target_entity: Entity) -> List[Path]:
        """查找跨层路径"""
        
    def analyze_connections(self, entities: List[Entity]) -> ConnectionAnalysis:
        """分析连接关系"""
        
    def calculate_connection_strength(self, path: Path) -> float:
        """计算连接强度"""
```

## 使用方法

### 1. 基本检索
```python
from src.retrieval.retriever import MedicalRetriever

retriever = MedicalRetriever()

# 执行检索
result = retriever.retrieve("患者Lin的实验室检查结果")

# 获取实体和关系
entities = result.entities
relationships = result.relationships
confidence = result.confidence
reasoning = result.reasoning_chain
```

### 2. 查询处理
```python
from src.retrieval.query_processor import QueryProcessor

processor = QueryProcessor()

# 解析查询
parsed_query = processor.parse_query("患者Lin的实验室检查结果")

# 识别意图
intent = processor.identify_intent("患者Lin的实验室检查结果")

# 优化查询
optimized_query = processor.optimize_query(parsed_query)
```

### 3. 结果格式化
```python
from src.retrieval.formatter import ResultFormatter

formatter = ResultFormatter()

# 格式化结果
formatted_result = formatter.format_result(result, "json")

# 生成摘要
summary = formatter.generate_summary(result)

# 准备可视化数据
viz_data = formatter.prepare_visualization_data(result)
```

### 4. 实体识别
```python
from src.retrieval.identifier import EntityIdentifier

identifier = EntityIdentifier()

# 识别实体
entities = identifier.identify_entities("患者Lin出现发热症状")

# 链接实体
linked_entities = identifier.link_entities(entities)

# 实体消歧
disambiguated_entities = identifier.disambiguate_entities(entities)
```

### 5. LLM集成
```python
from src.retrieval.llm_integration import LLMIntegration

llm = LLMIntegration()

# 生成推理链
reasoning = llm.generate_reasoning(context, query)

# 回答问题
answer = llm.answer_question(context, question)

# 总结结果
summary = llm.summarize_results(results)
```

## 检索策略

### 1. 多层级检索
- **公有层检索**: 基于UMLS标准概念
- **私有层检索**: 基于具体患者数据
- **跨层检索**: 结合两层信息

### 2. 语义检索
- **向量相似度**: 基于嵌入向量的相似度计算
- **语义匹配**: 考虑语义关系的匹配
- **上下文理解**: 结合上下文信息

### 3. 推理检索
- **路径推理**: 基于图谱路径的推理
- **规则推理**: 基于医疗规则的推理
- **LLM推理**: 基于大语言模型的推理

## 配置要求

### 模型配置
```python
# 在settings.py中配置
OLLAMA_MODEL = "gemma3:27b"
OLLAMA_URL = "http://localhost:11434/api/generate"
EMBEDDING_MODEL = "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"
```

### 检索参数
```python
SIMILARITY_THRESHOLD = 0.5
MAX_RESULTS = 100
REASONING_ENABLED = True
CROSS_LAYER_ENABLED = True
```

## 性能优化

### 1. 缓存策略
- 查询结果缓存
- 实体嵌入缓存
- 推理结果缓存

### 2. 并行处理
- 多层级并行检索
- 批量实体处理
- 异步LLM调用

### 3. 索引优化
- 向量索引优化
- 全文搜索索引
- 关系索引优化

## 错误处理

### 查询错误
```python
try:
    result = retriever.retrieve(query)
except QueryError as e:
    logger.error(f"查询失败: {e}")
    # 处理错误
```

### LLM错误
```python
try:
    reasoning = llm.generate_reasoning(context, query)
except LLMError as e:
    logger.error(f"LLM调用失败: {e}")
    # 处理错误
```

## 扩展指南

### 添加新的检索策略
1. 实现新的检索算法
2. 集成到主检索器
3. 添加配置选项
4. 编写单元测试

### 支持新的查询类型
1. 扩展查询处理器
2. 添加新的意图识别
3. 实现相应的检索逻辑
4. 更新文档

### 集成新的LLM模型
1. 实现新的LLM接口
2. 添加模型配置
3. 处理模型特定参数
4. 测试兼容性

## 评估指标

### 检索质量
- **精确率**: 相关结果的比例
- **召回率**: 找到的相关结果比例
- **F1分数**: 精确率和召回率的调和平均

### 推理质量
- **推理准确性**: 推理链的正确性
- **推理完整性**: 推理链的完整性
- **推理可解释性**: 推理过程的可解释性

## 注意事项

1. **查询理解**: 确保正确理解用户查询意图
2. **结果质量**: 平衡检索速度和结果质量
3. **推理准确性**: 验证推理链的正确性
4. **性能优化**: 注意检索性能优化
5. **错误处理**: 提供友好的错误信息

## 故障排除

### 常见问题

1. **检索结果不准确**
   - 调整相似度阈值
   - 优化查询处理
   - 检查实体识别质量

2. **推理链错误**
   - 验证LLM模型状态
   - 检查上下文信息
   - 优化推理提示

3. **性能问题**
   - 启用缓存机制
   - 优化索引
   - 减少并发查询
