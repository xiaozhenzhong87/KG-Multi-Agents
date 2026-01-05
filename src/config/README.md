# 配置管理模块 (config/)

本模块负责管理系统的所有配置项，提供统一的配置管理接口。

## 文件说明

### `settings.py`
- **功能**: 系统配置设置
- **特性**: 
  - 支持环境变量覆盖
  - 类型安全的配置项
  - 默认值设置
  - 配置验证

## 主要配置项

### 数据库配置
```python
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password"
NEO4J_DATABASE = "neo4j"
```

### 数据路径配置
```python
PDF_DIR = "/path/to/pdf/files"
UMLS_DATA_DIR = "/path/to/umls/data"
SRDEF_PATH = "/path/to/srdef"
```

### 模型配置
```python
OLLAMA_MODEL = "gemma3:27b"
OLLAMA_URL = "http://localhost:11434/api/generate"
EMBEDDING_MODEL = "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"
```

### 日志配置
```python
LOG_LEVEL = "INFO"
LOG_FILE = "logs/system.log"
```

### 检索配置
```python
SIMILARITY_THRESHOLD = 0.5
MAX_RESULTS = 100
BATCH_SIZE = 1000
```

## 使用方法

### 1. 直接导入使用
```python
from src.config.settings import settings

# 使用配置
db_uri = settings.NEO4J_URI
log_level = settings.LOG_LEVEL
```

### 2. 环境变量覆盖
```bash
# 设置环境变量
export NEO4J_URI="bolt://your-server:7687"
export NEO4J_PASSWORD="your_secure_password"
export LOG_LEVEL="DEBUG"
```

### 3. 配置文件方式
```python
# 创建自定义配置
from src.config.settings import Settings

custom_settings = Settings(
    NEO4J_URI="bolt://custom-server:7687",
    LOG_LEVEL="WARNING"
)
```

## 配置验证

系统会自动验证配置项的有效性：

- **必需配置**: 检查关键配置项是否存在
- **格式验证**: 验证URL、路径等格式
- **类型检查**: 确保配置项类型正确
- **范围检查**: 验证数值范围（如阈值、端口号等）

## 环境变量列表

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j数据库连接URI |
| `NEO4J_USER` | `neo4j` | Neo4j用户名 |
| `NEO4J_PASSWORD` | - | Neo4j密码（必需） |
| `NEO4J_DATABASE` | `neo4j` | Neo4j数据库名 |
| `PDF_DIR` | - | PDF文件目录 |
| `UMLS_DATA_DIR` | - | UMLS数据目录 |
| `SRDEF_PATH` | - | SRDEF文件路径 |
| `OLLAMA_MODEL` | `gemma3:27b` | Ollama模型名称 |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama API地址 |
| `EMBEDDING_MODEL` | `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` | 嵌入模型 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_FILE` | - | 日志文件路径 |
| `SIMILARITY_THRESHOLD` | `0.5` | 相似度阈值 |
| `MAX_RESULTS` | `100` | 最大结果数 |
| `BATCH_SIZE` | `1000` | 批处理大小 |

## 最佳实践

### 1. 敏感信息管理
- 使用环境变量存储密码等敏感信息
- 不要在代码中硬编码敏感配置
- 使用配置文件时注意权限设置

### 2. 配置分层
- 开发环境：使用默认配置
- 测试环境：覆盖部分配置
- 生产环境：使用环境变量

### 3. 配置验证
- 启动时验证所有必需配置
- 提供清晰的错误信息
- 记录配置加载过程

## 扩展配置

### 添加新配置项
1. 在`settings.py`中定义新的配置项
2. 设置默认值和类型
3. 添加环境变量支持
4. 更新文档

### 示例
```python
# 在settings.py中添加
class Settings(BaseSettings):
    # 现有配置...
    
    # 新配置项
    NEW_FEATURE_ENABLED: bool = False
    NEW_FEATURE_TIMEOUT: int = 30
    
    class Config:
        env_prefix = ""
```

## 故障排除

### 常见问题

1. **配置加载失败**
   - 检查环境变量名称是否正确
   - 验证配置文件格式
   - 查看错误日志

2. **数据库连接失败**
   - 确认Neo4j服务运行状态
   - 检查连接参数
   - 验证网络连通性

3. **模型加载失败**
   - 检查模型名称是否正确
   - 确认网络连接
   - 验证模型文件存在

## 注意事项

- 配置项名称使用大写字母和下划线
- 敏感信息不要提交到版本控制
- 定期更新默认配置值
- 保持配置文档同步更新
