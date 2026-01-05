# Reasoning Chain Evaluation Scripts

这个目录包含三个版本的推理链评估脚本，用于在UMLS知识图谱上进行代理式推理链评估。

## 文件概述

### 1. `run_reasoning_chain_eval-2512291605.py` (1047行) - 基础版本
**发布时间**: 2025-12-29

**主要特性**:
- 基础的代理式RAG评估框架
- 固定3跳图谱检索
- 简单的迭代逻辑（最多3轮）
- 不支持RAG开关

**AgenticRAGEvaluator参数**:
- `max_iterations: int = 3` - 最大迭代次数

**命令行参数**:
- `--dataset` - 数据集路径
- `--output-dir` - 输出目录
- `--limit` - 问题数量限制
- `--max-iterations` - 最大迭代次数
- `--verbose` - 启用调试日志

### 2. `run_reasoning_chain_eval-2512301019.py` (1108行) - 中间版本
**发布时间**: 2025-12-30

**主要特性**:
- 添加了RAG开关功能
- 支持迭代控制
- 当RAG禁用时仍会尝试实体扩展
- 推理链格式更严格（强制使用图谱风格格式）

**AgenticRAGEvaluator参数**:
- `max_iterations: int = 3` - 最大迭代次数
- `use_rag: bool = True` - 是否启用RAG
- `enable_iteration: bool = True` - 是否启用迭代

**新增命令行参数**:
- `--use-rag` / `--no-rag` - 启用/禁用RAG检索
- `--enable-iteration` / `--no-iteration` - 启用/禁用迭代

### 3. `run_reasoning_chain_eval.py` (1196行) - 最新版本
**发布时间**: 最新版本

**主要特性**:
- **当RAG禁用时，直接跳过实体扩展，立即强制LLM回答**（核心改进）
- 更灵活的推理链格式（非RAG模式下使用自然语言）
- 更多可配置参数
- 更好的错误处理

**AgenticRAGEvaluator参数**:
- `max_iterations: int = 3` - 最大迭代次数
- `use_rag: bool = True` - 是否启用RAG
- `enable_iteration: bool = True` - 是否启用迭代
- `max_hops: int = 3` - 图谱检索最大跳数
- `max_output_tokens: int = 8192` - LLM最大输出token数

**新增命令行参数**:
- `--max-hops` - 图谱检索最大跳数
- `--max-candidates` - 实体匹配最大候选数
- `--max-output-tokens` - LLM最大输出token数

## 关键区别说明

### RAG禁用时的行为差异

1. **基础版本** (`-2512291605.py`):
   - 不支持RAG开关，始终启用RAG

2. **中间版本** (`-2512301019.py`):
   - 支持RAG开关
   - 当RAG禁用时，LLM仍会收到严格的图谱格式提示词
   - 会尝试实体扩展（可能匹配到不相关实体）

3. **最新版本** (`run_reasoning_chain_eval.py`):
   - **核心改进**：当RAG禁用时，直接跳过实体扩展，避免不相关匹配
   - 强制回答模式使用更自由的推理链格式
   - 推理链可以是自然语言描述，而非强制图谱格式

### 使用建议

- **如果需要严格的图谱风格推理链** → 使用中间版本 (`-2512301019.py`)
- **如果需要灵活的自然语言推理** → 使用最新版本 (`run_reasoning_chain_eval.py`)
- **如果只需要基础功能** → 使用基础版本 (`-2512291605.py`)

## 输出文件

- 评估结果保存在 `match_results/` 目录中
- 日志文件保存在 `logs/` 目录中
- 关键结果文件保存在 `match_results/key_results/` 目录中

## 运行示例

```bash
# 使用最新版本，禁用RAG，单次迭代
python run_reasoning_chain_eval.py --no-rag --no-iteration --limit 10

# 使用中间版本，启用RAG，3次迭代
python run_reasoning_chain_eval-2512301019.py --use-rag --enable-iteration --max-iterations 3

# 使用基础版本
python run_reasoning_chain_eval-2512291605.py --limit 50
```
