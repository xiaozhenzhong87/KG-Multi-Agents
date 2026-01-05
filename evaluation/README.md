# 评估模块使用说明

## 概述

评估模块用于评估医疗知识图谱系统在测试数据上的表现。该模块支持加载JSONL格式的测试数据，对每个问题进行检索和答案预测，并生成详细的评估报告。

## 模块结构

```
evaluation/
├── __init__.py              # 模块初始化
├── evaluator.py             # 核心评估器
├── answer_predictor.py       # 答案预测器
├── metrics.py                # 评估指标计算
├── report_generator.py       # 报告生成器
├── run_evaluation.py         # 评估脚本
└── README.md                 # 本文档
```

## 主要类和方法

### TestDataEvaluator

核心评估类，负责加载测试数据并执行评估。

**主要方法：**
- `load_test_data(data_file)`: 加载测试数据文件
- `evaluate(data_file, max_items, start_from)`: 执行评估
- `save_results(output_file, format)`: 保存评估结果
- `generate_report(output_file)`: 生成评估报告

### AnswerPredictor

答案预测器，根据检索结果预测答案。

**主要方法：**
- `predict_answer(question, options, query_result)`: 预测答案

**预测方法：**
1. 基于LLM推理链的答案提取
2. 基于实体匹配的答案选择
3. 基于关键词匹配的答案选择（备用方法）

### EvaluationMetrics

评估指标计算器。

**主要方法：**
- `calculate_metrics(results)`: 计算评估指标
- `calculate_confusion_matrix(results)`: 计算混淆矩阵

### ReportGenerator

评估报告生成器。

**主要方法：**
- `generate_report(results, metrics)`: 生成评估报告
- `generate_detailed_report(results, metrics)`: 生成详细报告

## 测试数据格式

测试数据文件应为JSONL格式，每行一个JSON对象，包含以下字段：

```json
{
  "question": "问题文本",
  "answer": "正确答案文本",
  "options": {
    "A": "选项A",
    "B": "选项B",
    "C": "选项C",
    "D": "选项D",
    "E": "选项E"
  },
  "meta_info": "step1",
  "answer_idx": "E"
}
```

**字段说明：**
- `question`: 问题文本（必需）
- `answer`: 正确答案文本（必需）
- `options`: 选项字典，键为选项标识符（A-E），值为选项文本
- `meta_info`: 元信息，如"step1"、"step2&3"等
- `answer_idx`: 正确答案的索引（A-E）

## 使用方法

### 1. 使用命令行脚本

```bash
# 评估所有测试数据
python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl

# 评估前10条数据
python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --max-items 10

# 从第5条开始评估
python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --start-from 5

# 保存结果到JSON文件
python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --output results.json

# 保存结果到JSONL文件
python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --output-jsonl results.jsonl

# 生成评估报告
python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --report report.txt
```

### 2. 在代码中使用

```python
from evaluation.evaluator import TestDataEvaluator

# 创建评估器
evaluator = TestDataEvaluator(data_file="eval_data/test_data.jsonl")

# 执行评估
evaluation_summary = evaluator.evaluate(max_items=10)

# 保存结果
evaluator.save_results("results.json", format="json")

# 生成报告
report = evaluator.generate_report(output_file="report.txt")

# 查看指标
metrics = evaluation_summary['metrics']
print(f"准确率: {metrics['accuracy']:.2%}")
```

## 评估指标

评估模块会计算以下指标：

1. **总体指标**
   - 总问题数
   - 正确答案数
   - 错误答案数
   - 准确率

2. **按meta_info分组统计**
   - 每个meta_info的准确率

3. **置信度统计**
   - 平均置信度
   - 正确答案平均置信度
   - 错误答案平均置信度

4. **检索统计**
   - 平均实体数量
   - 平均关系数量
   - 检索方法分布

5. **答案分布**
   - 正确答案分布
   - 预测答案分布

## 评估结果格式

评估结果可以保存为JSON或JSONL格式。

### JSON格式

包含所有评估结果和指标：

```json
{
  "metrics": {
    "accuracy": 0.75,
    "total_items": 10,
    "correct_items": 8,
    "incorrect_items": 2,
    ...
  },
  "results": [
    {
      "line_number": 1,
      "question": "问题文本",
      "true_answer": "正确答案",
      "true_answer_idx": "E",
      "predicted_answer": "预测答案",
      "predicted_answer_idx": "E",
      "is_correct": true,
      "confidence": 0.85,
      ...
    },
    ...
  ]
}
```

### JSONL格式

每行一个评估结果：

```jsonl
{"line_number": 1, "question": "...", "is_correct": true, ...}
{"line_number": 2, "question": "...", "is_correct": false, ...}
```

## 评估报告

评估报告包含以下内容：

1. 总体评估指标
2. 按meta_info分组的准确率
3. 置信度统计
4. 检索统计
5. 答案分布
6. 错误案例分析（前10个）
7. 错误记录

## 注意事项

1. **数据库连接**: 评估前需要确保数据库连接正常
2. **LLM服务**: 答案预测依赖于LLM服务，需要确保Ollama等LLM服务运行正常
3. **测试数据格式**: 确保测试数据文件格式正确，包含必要字段
4. **性能考虑**: 评估大量数据可能需要较长时间，建议使用`--max-items`参数限制数量

## 依赖模块

评估模块依赖以下模块：

- `src.retrieval.retriever`: 检索器
- `src.core.database`: 数据库管理
- `src.core.models`: 数据模型

## 扩展

如需扩展评估功能，可以：

1. **自定义答案预测器**: 继承`AnswerPredictor`类并实现自定义预测方法
2. **自定义评估指标**: 在`EvaluationMetrics`类中添加新的指标计算方法
3. **自定义报告格式**: 在`ReportGenerator`类中添加新的报告生成方法

