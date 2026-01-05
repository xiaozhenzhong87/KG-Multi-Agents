# 上下文拼接流程说明

## 概述

本文档说明如何将检索到的实体和关系拼接成推理链并格式化为上下文，用于传递给LLM。

## 核心流程

### 1. PageRank检索结果获取

**文件位置**: `healthcare-modeling/src/retrieval/pagerank_retriever.py`

**关键方法**: `retrieve()` (第49-102行)

流程：
1. 查找初始节点 (`_find_initial_nodes`)
2. 构建子图 (`_build_subgraph`)
3. 计算PageRank分数 (`_calculate_pagerank`)
4. 获取top-k节点 (`_get_top_nodes_by_pagerank`)
5. **获取节点之间的关系** (`_get_relationships`) - **关键步骤**

```python
# 第93-94行
result.nodes = top_nodes
result.relationships = self._get_relationships(top_nodes, graph)
```

### 2. 关系获取 (_get_relationships)

**文件位置**: `healthcare-modeling/src/retrieval/pagerank_retriever.py`

**关键方法**: `_get_relationships()` (第497-547行)

**代码位置**: 第497-547行

**关系数据结构**:
```python
rel_data = {
    "source": source_node['internal_id'],    # 源实体的内部ID（保留用于内部处理）
    "target": target_node['internal_id'],      # 目标实体的内部ID（保留用于内部处理）
    "source_name": source_node.get('name', source_node['internal_id']),  # 源实体名称（用于显示）
    "target_name": target_node.get('name', target_node['internal_id']),  # 目标实体名称（用于显示）
    "type": record.get('rel_type', 'RELATED_TO'),  # 关系类型
    "properties": record.get('rel_properties', {})  # 关系属性
}
```

**Cypher查询** (第515-523行):
```cypher
UNWIND $node_ids as node_id
MATCH (n:Entity)
WHERE elementId(n) = node_id
MATCH (n)-[r]->(target:Entity)
WHERE elementId(target) IN $node_ids
RETURN elementId(n) as source_id, elementId(target) as target_id,
       type(r) as rel_type, properties(r) as rel_properties
```

**说明**: 
- 只获取top-k节点之间的直接关系
- 关系格式为：`(source实体) -[关系类型]-> (target实体)`
- 返回的是**三元组形式**：`(source_id, target_id, rel_type)`

### 3. 上下文格式化

**文件位置**: `healthcare-modeling/src/retrieval/formatter.py`

**关键方法**: `format_pagerank_result_for_prompt()` (第184-249行)

#### 3.1 实体格式化 (第209-228行)

按PageRank分数排序，显示实体信息：
```
1. 实体名称
   - Type: 实体类型
   - CUI: UMLS概念唯一标识符
   - PageRank Score: 分数
   - Definition: 定义（如果有）
```

#### 3.2 关系格式化 (第230-247行)

**代码位置**: 第230-247行

**格式化逻辑**:
```python
# 按关系类型分组
rel_groups = {}
for rel in pagerank_result.relationships[:30]:
    rel_type = rel.get('type', 'RELATED_TO')
    if rel_type not in rel_groups:
        rel_groups[rel_type] = []
    rel_groups[rel_type].append(rel)

# 按关系类型显示
for rel_type, rels in list(rel_groups.items())[:10]:
    # 将关系类型转换为更可读的格式
    rel_type_display = rel_type.replace('_', ' ').title()
    parts.append(f"**{rel_type_display}:**")
    for rel in rels[:5]:
        # 优先使用实体名称，如果没有则使用ID作为后备
        source_name = rel.get('source_name', rel.get('source', 'Unknown'))
        target_name = rel.get('target_name', rel.get('target', 'Unknown'))
        parts.append(f"  - {source_name} --[{rel_type_display}]--> {target_name}")
```

**输出格式**:
```
**Key Relationships:**
**Related To:**
  - Hypertension --[Related To]--> High Blood Pressure
  - Diabetes --[Related To]--> Insulin
**Treats:**
  - Medication A --[Treats]--> Hypertension
  - Medication B --[Treats]--> Diabetes
```

### 4. 最终上下文拼接

**文件位置**: `healthcare-modeling/src/retrieval/formatter.py`

**关键方法**: `format_structured_context_from_pagerank()` (第251-273行)

**代码位置**: 第251-273行

**拼接逻辑**:
```python
context_parts = []

# 1. 添加查询信息
context_parts.append(f"**User Query:** {query}")
context_parts.append("")

# 2. 添加PageRank检索结果（包含实体和关系）
pagerank_formatted = self.format_pagerank_result_for_prompt(pagerank_result)
context_parts.append(pagerank_formatted)

# 3. 拼接成最终字符串
return "\n".join(context_parts)
```

### 5. 传递给LLM

**文件位置**: `healthcare-modeling/src/retrieval/retriever.py`

**关键方法**: `retrieve()` (第51-97行)

**代码位置**: 第86-94行

```python
# 步骤3: 生成结构化上下文
structured_context = self.formatter.format_structured_context_from_pagerank(
    query, pagerank_result
)

# 步骤4: 调用LLM生成响应
llm_response = self.llm_integration.generate_response_with_context_v5(
    query, structured_context
)
```

## 关键发现

### ✅ 关系确实是以三元组形式存储的

在 `_get_relationships()` 方法中，关系以字典形式存储：
```python
{
    "source": source_node['internal_id'],  # 源实体ID（用于内部处理）
    "target": target_node['internal_id'],  # 目标实体ID（用于内部处理）
    "source_name": source_node.get('name', ...),  # 源实体名称（用于显示）
    "target_name": target_node.get('name', ...),  # 目标实体名称（用于显示）
    "type": rel_type                       # 关系类型
}
```

这构成了**实体-关系-实体**的三元组结构，并且同时存储了ID和名称。

### ✅ 格式化时使用实体名称

**当前实现** (第241-249行):
- 格式化时优先使用 `source_name` 和 `target_name`（实体名称）
- 如果没有名称，则回退使用 `source` 和 `target`（ID）
- 关系类型被格式化为更可读的形式（下划线替换为空格，首字母大写）

### 📊 当前输出格式示例

```
**PageRank Retrieval Results:**
- Total Entities: 50
- Total Relationships: 120

**Top Relevant Entities (sorted by PageRank score):**
1. Hypertension
   - Type: Disease or Syndrome
   - CUI: C0020538
   - PageRank Score: 0.023456

**Key Relationships:**
**Treats:**
  - Aspirin --[Treats]--> Hypertension
  - Metformin --[Treats]--> Diabetes
**Related To:**
  - Hypertension --[Related To]--> High Blood Pressure
  - Diabetes --[Related To]--> Insulin Resistance
```

**注意**: 现在关系显示使用的是**实体名称**而不是CUI/ID，使得上下文更易读，更适合传递给LLM。

## 总结

1. **检索阶段**: PageRank检索器从Neo4j图谱中获取实体和关系
2. **关系获取**: 通过Cypher查询获取top-k节点之间的直接关系，以三元组形式存储 `(source_id, target_id, rel_type)`
3. **格式化阶段**: 将实体和关系格式化为文本，关系按类型分组显示
4. **上下文拼接**: 将查询、实体列表、关系列表拼接成结构化上下文
5. **传递给LLM**: 将格式化后的上下文传递给LLM生成响应

**关于三元组**: 是的，关系确实是以**实体-关系-实体**的三元组形式存储的。现在在格式化时使用**实体名称**而不是ID，使得上下文更易读，更适合传递给LLM进行推理。

