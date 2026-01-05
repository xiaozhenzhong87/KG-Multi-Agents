# 工具模块 (utils/)

本模块提供各种辅助工具和实用函数，为系统其他模块提供基础支持。

## 文件说明

### `config.py`
- **功能**: 配置工具
- **特性**:
  - 配置加载和验证
  - 环境变量处理
  - 配置文件解析
  - 配置合并

### `file_processor.py`
- **功能**: 文件处理
- **特性**:
  - 文件读写操作
  - 格式转换
  - 批量处理
  - 文件监控

### `logging_config.py`
- **功能**: 日志配置
- **特性**:
  - 日志系统初始化
  - 日志格式配置
  - 日志级别管理
  - 日志轮转

### `text_processor.py`
- **功能**: 文本处理
- **特性**:
  - 文本清洗
  - 分词处理
  - 编码转换
  - 文本标准化

## 核心类说明

### 配置工具 (config.py)

#### `ConfigManager`
```python
class ConfigManager:
    """配置管理器"""
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        
    def validate_config(self, config: Dict) -> bool:
        """验证配置"""
        
    def merge_configs(self, base_config: Dict, override_config: Dict) -> Dict:
        """合并配置"""
        
    def get_env_vars(self, prefix: str = "") -> Dict:
        """获取环境变量"""
```

### 文件处理器 (file_processor.py)

#### `FileProcessor`
```python
class FileProcessor:
    """文件处理器"""
    
    def read_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """读取文件"""
        
    def write_file(self, file_path: str, content: str, encoding: str = "utf-8") -> bool:
        """写入文件"""
        
    def process_batch(self, file_paths: List[str], processor_func: Callable) -> List[Any]:
        """批量处理文件"""
        
    def monitor_file(self, file_path: str, callback: Callable) -> None:
        """监控文件变化"""
```

### 日志配置 (logging_config.py)

#### `LoggingConfig`
```python
class LoggingConfig:
    """日志配置"""
    
    def setup_logging(self, level: str = "INFO", log_file: str = None) -> None:
        """设置日志系统"""
        
    def get_logger(self, name: str) -> logging.Logger:
        """获取日志器"""
        
    def set_log_level(self, level: str) -> None:
        """设置日志级别"""
        
    def add_file_handler(self, log_file: str) -> None:
        """添加文件处理器"""
```

### 文本处理器 (text_processor.py)

#### `TextProcessor`
```python
class TextProcessor:
    """文本处理器"""
    
    def clean_text(self, text: str) -> str:
        """清洗文本"""
        
    def tokenize(self, text: str) -> List[str]:
        """分词"""
        
    def normalize_text(self, text: str) -> str:
        """标准化文本"""
        
    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """提取关键词"""
```

## 使用方法

### 1. 配置管理
```python
from src.utils.config import ConfigManager

config_manager = ConfigManager()

# 加载配置文件
config = config_manager.load_config("config.yaml")

# 验证配置
is_valid = config_manager.validate_config(config)

# 合并配置
merged_config = config_manager.merge_configs(base_config, override_config)

# 获取环境变量
env_vars = config_manager.get_env_vars("NEO4J_")
```

### 2. 文件处理
```python
from src.utils.file_processor import FileProcessor

file_processor = FileProcessor()

# 读取文件
content = file_processor.read_file("data/input.txt")

# 写入文件
success = file_processor.write_file("data/output.txt", content)

# 批量处理
results = file_processor.process_batch(
    file_paths=["file1.txt", "file2.txt"],
    processor_func=process_function
)

# 监控文件
file_processor.monitor_file("data/watch.txt", callback_function)
```

### 3. 日志配置
```python
from src.utils.logging_config import LoggingConfig

logging_config = LoggingConfig()

# 设置日志系统
logging_config.setup_logging(level="DEBUG", log_file="logs/app.log")

# 获取日志器
logger = logging_config.get_logger(__name__)

# 设置日志级别
logging_config.set_log_level("INFO")

# 添加文件处理器
logging_config.add_file_handler("logs/error.log")
```

### 4. 文本处理
```python
from src.utils.text_processor import TextProcessor

text_processor = TextProcessor()

# 清洗文本
clean_text = text_processor.clean_text("原始文本...")

# 分词
tokens = text_processor.tokenize("这是一个句子")

# 标准化文本
normalized_text = text_processor.normalize_text("文本内容")

# 提取关键词
keywords = text_processor.extract_keywords("长文本内容", top_k=5)
```

## 工具函数

### 通用工具函数
```python
# 时间工具
def get_timestamp() -> str:
    """获取时间戳"""
    
def format_duration(seconds: float) -> str:
    """格式化持续时间"""

# 字符串工具
def safe_filename(filename: str) -> str:
    """生成安全的文件名"""
    
def truncate_string(text: str, max_length: int) -> str:
    """截断字符串"""

# 数据工具
def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """分块处理列表"""
    
def flatten_list(nested_list: List) -> List:
    """展平嵌套列表"""

# 验证工具
def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    
def validate_url(url: str) -> bool:
    """验证URL格式"""
```

## 配置示例

### 日志配置示例
```python
# logging_config.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False
        }
    }
}
```

### 文件处理配置
```python
# file_processor.py
SUPPORTED_FORMATS = {
    "text": [".txt", ".md"],
    "json": [".json"],
    "csv": [".csv"],
    "xml": [".xml"],
    "yaml": [".yaml", ".yml"]
}

DEFAULT_ENCODING = "utf-8"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
```

## 性能优化

### 1. 文件处理优化
- 使用流式处理大文件
- 批量操作减少I/O次数
- 异步文件操作
- 内存映射大文件

### 2. 文本处理优化
- 缓存分词结果
- 并行处理文本
- 使用高效的正则表达式
- 预编译模式

### 3. 配置管理优化
- 配置缓存
- 延迟加载
- 配置热更新
- 配置验证优化

## 错误处理

### 文件操作错误
```python
try:
    content = file_processor.read_file(file_path)
except FileNotFoundError:
    logger.error(f"文件不存在: {file_path}")
except PermissionError:
    logger.error(f"没有权限访问文件: {file_path}")
except UnicodeDecodeError:
    logger.error(f"文件编码错误: {file_path}")
```

### 配置错误
```python
try:
    config = config_manager.load_config(config_file)
except ConfigError as e:
    logger.error(f"配置加载失败: {e}")
except ValidationError as e:
    logger.error(f"配置验证失败: {e}")
```

## 扩展指南

### 添加新的文件格式支持
1. 在`FileProcessor`中添加新的解析器
2. 更新支持格式列表
3. 添加相应的测试用例
4. 更新文档

### 扩展文本处理功能
1. 实现新的文本处理算法
2. 添加语言特定处理
3. 集成外部NLP库
4. 优化处理性能

### 添加新的配置源
1. 实现新的配置加载器
2. 添加配置验证规则
3. 支持配置继承
4. 添加配置模板

## 最佳实践

### 1. 文件处理
- 使用上下文管理器处理文件
- 及时关闭文件句柄
- 处理文件编码问题
- 验证文件大小限制

### 2. 日志记录
- 使用适当的日志级别
- 避免敏感信息泄露
- 结构化日志信息
- 定期清理日志文件

### 3. 配置管理
- 使用环境变量覆盖配置
- 验证配置完整性
- 提供默认配置
- 文档化配置选项

## 注意事项

1. **文件安全**: 验证文件路径，防止路径遍历攻击
2. **内存使用**: 大文件处理时注意内存管理
3. **编码问题**: 正确处理不同编码的文件
4. **错误处理**: 提供友好的错误信息
5. **性能考虑**: 避免阻塞操作影响系统性能

## 故障排除

### 常见问题

1. **文件读取失败**
   - 检查文件路径是否正确
   - 验证文件权限
   - 确认文件编码

2. **配置加载错误**
   - 检查配置文件格式
   - 验证配置项名称
   - 确认环境变量设置

3. **日志记录问题**
   - 检查日志目录权限
   - 验证日志配置
   - 确认日志级别设置
