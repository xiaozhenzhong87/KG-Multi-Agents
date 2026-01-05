# API模块 (api/)

## ⚠️ 重要说明

**API功能目前处于开发阶段，未来会拓展这部分的代码，提供的代码仅供参考。**

本模块旨在提供RESTful API接口，但目前主要功能通过命令行接口实现。

## 文件说明

### `endpoints.py`
- **功能**: 定义FastAPI端点
- **状态**: 开发中
- **包含**: 
  - 系统信息端点
  - 健康检查端点
  - 查询端点
  - 数据添加端点
  - 统计信息端点

## 计划中的API端点

### 基础端点
- `GET /` - 系统信息和状态
- `GET /health` - 健康检查
- `GET /docs` - API文档（Swagger UI）

### 知识图谱操作
- `POST /query` - 查询知识图谱
- `POST /add_data` - 添加新数据到图谱
- `GET /stats` - 获取图谱统计信息
- `POST /build_kg` - 构建知识图谱
- `POST /connect_graphs` - 连接图谱

### 数据管理
- `GET /entities` - 获取实体列表
- `GET /relationships` - 获取关系列表
- `POST /upload` - 上传数据文件
- `DELETE /clear` - 清除图谱数据

## 技术栈

- **框架**: FastAPI
- **文档**: Swagger UI / OpenAPI
- **验证**: Pydantic
- **异步**: 支持异步操作

## 开发计划

### 第一阶段（当前）
- [x] 基础端点框架
- [x] 基本查询功能
- [ ] 完善错误处理
- [ ] 添加认证机制

### 第二阶段
- [ ] 完整的CRUD操作
- [ ] 批量操作支持
- [ ] 实时数据更新
- [ ] WebSocket支持

### 第三阶段
- [ ] 高级查询功能
- [ ] 数据可视化接口
- [ ] 性能优化
- [ ] 监控和日志

## 使用示例（未来）

```python
# 启动API服务
uvicorn src.api.endpoints:app --host 0.0.0.0 --port 8000

# 查询示例
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{"query": "患者Lin的实验室检查结果"}'

# 添加数据示例
curl -X POST "http://localhost:8000/add_data" \
     -H "Content-Type: application/json" \
     -d '{"notepad_content": "...", "hospital_number": "12345"}'
```

## 注意事项

1. **当前状态**: API功能仍在开发中，建议使用命令行接口
2. **兼容性**: 未来版本可能不向后兼容
3. **性能**: 当前实现未进行性能优化
4. **安全**: 暂未实现认证和授权机制

## 贡献指南

如果您想为API模块贡献代码：

1. 遵循FastAPI最佳实践
2. 添加完整的类型提示
3. 编写API文档字符串
4. 添加单元测试
5. 更新此README文档
