# 脚本目录 (scripts/)

本目录包含各种实用脚本，用于系统管理、数据构建、测试和部署等操作。

## 文件说明

### `build_public_kg.py`
- **功能**: 构建公有层知识图谱
- **用途**: 从UMLS数据构建标准医疗概念图谱
- **参数**: 无特殊参数，使用默认配置

### `build_private_kg.py`
- **功能**: 构建私有层知识图谱
- **用途**: 从Notepad数据构建私有医疗数据图谱
- **参数**: 
  - `--mode`: 操作模式（build/add）
  - `--notepad-file`: Notepad文件路径
  - `--hospital-number`: 医院编号
  - `--clear-existing`: 清除现有数据

### `connect_graphs.py`
- **功能**: 连接公有层和私有层图谱
- **用途**: 建立两层图谱之间的语义连接
- **参数**:
  - `--similarity-threshold`: 相似度阈值

### `setup_database.py`
- **功能**: 数据库初始化
- **用途**: 设置Neo4j数据库和索引
- **参数**: 无特殊参数

### `run_retrieval.py`
- **功能**: 运行检索系统
- **用途**: 交互式查询和检索测试
- **参数**:
  - `--interactive`: 交互式模式
  - `--query`: 直接查询

### `add_data.py`
- **功能**: 添加数据到图谱
- **用途**: 增量添加新的医疗数据
- **参数**:
  - `--notepad-file`: 数据文件路径
  - `--hospital-number`: 医院编号

### `manage.py`
- **功能**: 系统管理脚本
- **用途**: 系统维护和管理操作
- **参数**: 根据具体操作而定

### `start_api.py`
- **功能**: 启动API服务
- **用途**: 启动RESTful API服务
- **参数**:
  - `--host`: 服务主机
  - `--port`: 服务端口
  - `--debug`: 调试模式

## 使用方法

### 1. 构建公有层知识图谱
```bash
# 构建UMLS知识图谱
python scripts/build_public_kg.py
```

### 2. 构建私有层知识图谱
```bash
# 构建新的私有图谱
python scripts/build_private_kg.py --mode build --notepad-file data/notepad.txt --hospital-number 12345

# 添加数据到现有图谱
python scripts/build_private_kg.py --mode add --notepad-file data/new_data.txt --hospital-number 12345

# 清除现有数据后构建
python scripts/build_private_kg.py --mode build --notepad-file data/notepad.txt --clear-existing
```

### 3. 连接图谱
```bash
# 使用默认相似度阈值连接
python scripts/connect_graphs.py

# 使用自定义相似度阈值
python scripts/connect_graphs.py --similarity-threshold 0.6
```

### 4. 数据库初始化
```bash
# 初始化数据库
python scripts/setup_database.py
```

### 5. 运行检索系统
```bash
# 交互式查询
python scripts/run_retrieval.py --interactive

# 直接查询
python scripts/run_retrieval.py --query "患者Lin的实验室检查结果"
```

### 6. 添加数据
```bash
# 添加新数据
python scripts/add_data.py --notepad-file data/new_data.txt --hospital-number 12345
```

### 7. 系统管理
```bash
# 查看系统状态
python scripts/manage.py status

# 清理系统
python scripts/manage.py cleanup

# 备份数据
python scripts/manage.py backup
```

### 8. 启动API服务
```bash
# 启动API服务（开发中）
python scripts/start_api.py --host 0.0.0.0 --port 8000

# 调试模式
python scripts/start_api.py --debug
```

## 脚本详细说明

### build_public_kg.py
```python
"""
构建公有层知识图谱脚本
从UMLS数据构建标准医疗概念图谱
"""

# 主要功能：
# 1. 加载UMLS数据
# 2. 创建概念节点
# 3. 建立概念关系
# 4. 生成向量嵌入
# 5. 创建索引
```

### build_private_kg.py
```python
"""
构建私有层知识图谱脚本
从Notepad数据构建私有医疗数据图谱
"""

# 支持的操作模式：
# - build: 构建新的私有图谱
# - add: 添加数据到现有图谱

# 主要功能：
# 1. 解析Notepad数据
# 2. 提取实体和关系
# 3. 创建图谱节点
# 4. 建立关系连接
# 5. 生成向量嵌入
```

### connect_graphs.py
```python
"""
连接图谱脚本
建立公有层和私有层图谱之间的语义连接
"""

# 主要功能：
# 1. 计算实体相似度
# 2. 建立跨层连接
# 3. 创建推理路径
# 4. 更新图谱结构
```

### setup_database.py
```python
"""
数据库初始化脚本
设置Neo4j数据库和必要的索引
"""

# 主要功能：
# 1. 连接数据库
# 2. 创建约束
# 3. 建立索引
# 4. 验证设置
```

### run_retrieval.py
```python
"""
检索系统运行脚本
提供交互式查询和检索测试功能
"""

# 主要功能：
# 1. 初始化检索器
# 2. 处理用户查询
# 3. 显示检索结果
# 4. 生成推理链
```

## 配置要求

### 环境变量
```bash
# 数据库配置
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"

# 数据路径
export UMLS_DATA_DIR="/path/to/umls/data"
export SRDEF_PATH="/path/to/srdef"

# 模型配置
export OLLAMA_MODEL="gemma3:27b"
export OLLAMA_URL="http://localhost:11434/api/generate"
```

### 文件结构
```
data/
├── notepad.txt          # Notepad数据文件
├── umls/               # UMLS数据目录
│   ├── MRCONSO.RRF
│   ├── MRREL.RRF
│   └── ...
└── srdef               # SRDEF文件
```

## 错误处理

### 常见错误
1. **数据库连接失败**
   - 检查Neo4j服务状态
   - 验证连接参数
   - 确认网络连通性

2. **数据文件不存在**
   - 检查文件路径
   - 验证文件权限
   - 确认文件格式

3. **内存不足**
   - 减少批处理大小
   - 增加系统内存
   - 优化处理流程

### 错误日志
```bash
# 查看错误日志
tail -f logs/error.log

# 查看系统日志
tail -f logs/system.log
```

## 性能优化

### 1. 批处理优化
- 调整批处理大小
- 使用并行处理
- 优化内存使用

### 2. 数据库优化
- 创建适当索引
- 使用事务批量提交
- 优化Cypher查询

### 3. 系统资源
- 监控内存使用
- 调整并发数
- 优化I/O操作

## 监控和日志

### 进度监控
```bash
# 查看构建进度
python scripts/manage.py progress

# 查看系统状态
python scripts/manage.py status
```

### 日志管理
```bash
# 查看日志
python scripts/manage.py logs

# 清理日志
python scripts/manage.py cleanup-logs
```

## 扩展指南

### 添加新脚本
1. 创建新的Python脚本
2. 添加命令行参数解析
3. 实现主要功能
4. 添加错误处理
5. 更新此README

### 脚本模板
```python
#!/usr/bin/env python3
"""
脚本描述
"""

import argparse
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="脚本描述")
    parser.add_argument("--param", type=str, help="参数说明")
    
    args = parser.parse_args()
    
    try:
        # 主要逻辑
        logger.info("开始执行...")
        
        # 执行操作
        
        logger.info("执行完成")
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
```

## 注意事项

1. **权限**: 确保脚本有足够的文件系统权限
2. **资源**: 注意脚本的资源使用情况
3. **安全**: 验证输入参数的安全性
4. **备份**: 重要操作前备份数据
5. **测试**: 在生产环境使用前充分测试

## 故障排除

### 常见问题

1. **脚本执行失败**
   - 检查Python环境
   - 验证依赖包
   - 查看错误日志

2. **参数错误**
   - 检查参数格式
   - 验证参数值
   - 查看帮助信息

3. **性能问题**
   - 监控资源使用
   - 优化处理流程
   - 调整配置参数