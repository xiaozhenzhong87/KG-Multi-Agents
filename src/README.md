# 源代码目录 (src/)

本目录包含医疗知识图谱系统的核心源代码，采用模块化设计，便于维护和扩展。

## 目录结构

```
src/
├── api/                    # API接口模块
│   └── endpoints.py       # FastAPI端点定义
├── config/                # 配置管理模块
│   └── settings.py        # 系统配置设置
├── core/                  # 核心功能模块
│   ├── database.py        # 数据库连接管理
│   ├── embeddings.py      # 向量化处理
│   └── models.py          # 数据模型定义
├── kg_builder/            # 知识图谱构建模块
│   ├── private_kg.py      # 私有知识图谱构建
│   ├── umls_kg.py         # UMLS知识图谱构建
│   ├── entity_connector.py # 实体关联处理
│   └── graph_updater.py   # 动态图谱更新
├── retrieval/             # 检索系统模块
│   ├── retriever.py       # 主检索器
│   ├── query_processor.py # 查询处理
│   ├── formatter.py       # 结果格式化
│   ├── identifier.py      # 实体识别
│   ├── llm_integration.py # LLM集成
│   ├── multi_layer_retriever.py # 多层级检索
│   └── cross_layer_connector.py # 跨层连接
└── utils/                 # 工具模块
    ├── config.py          # 配置工具
    ├── file_processor.py  # 文件处理
    ├── logging_config.py  # 日志配置
    └── text_processor.py  # 文本处理
```

## 模块说明

### 🔌 API模块 (api/)
- **状态**: 开发中，仅供参考
- **功能**: 提供RESTful API接口
- **注意**: 当前版本主要使用命令行接口

### ⚙️ 配置模块 (config/)
- **功能**: 管理系统配置和设置
- **核心文件**: `settings.py` - 包含所有系统配置项

### 🏗️ 核心模块 (core/)
- **功能**: 提供系统核心功能
- **包含**: 数据库管理、向量化处理、数据模型

### 🧠 知识图谱构建模块 (kg_builder/)
- **功能**: 负责构建和管理知识图谱
- **支持**: 私有图谱、UMLS图谱、实体连接、动态更新

### 🔍 检索模块 (retrieval/)
- **功能**: 提供智能检索和推理能力
- **特性**: 多层级检索、语义搜索、推理链生成

### 🛠️ 工具模块 (utils/)
- **功能**: 提供各种辅助工具和实用函数
- **包含**: 配置管理、文件处理、日志记录、文本处理

## 开发指南

### 添加新功能
1. 在相应模块中创建新的类或函数
2. 更新模块的`__init__.py`文件
3. 在`main.py`中添加相应的命令行选项
4. 编写单元测试

### 模块依赖
- 各模块应保持相对独立
- 避免循环依赖
- 通过接口进行模块间通信

### 代码规范
- 遵循PEP 8编码规范
- 添加详细的文档字符串
- 使用类型提示
- 编写单元测试

## 注意事项

⚠️ **API功能目前处于开发阶段，未来会拓展这部分的代码，提供的代码仅供参考。**

当前系统主要通过命令行接口进行操作，各模块的设计考虑了未来API扩展的需求。
