"""
测试数据评估器
用于加载测试数据并执行评估
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.retrieval.retriever import MedicalRetriever
from src.core.database import db_manager
from .answer_predictor import AnswerPredictor
from .metrics import EvaluationMetrics
from .report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class TestDataEvaluator:
    """测试数据评估器"""
    
    def __init__(self, data_file: Optional[str] = None):
        """
        初始化评估器
        
        Args:
            data_file: 测试数据文件路径（JSONL格式）
        """
        self.data_file = data_file
        self.retriever = MedicalRetriever()
        self.predictor = AnswerPredictor()
        self.metrics = EvaluationMetrics()
        self.report_generator = ReportGenerator()
        
        # 评估结果
        self.test_data: List[Dict[str, Any]] = []
        self.evaluation_results: List[Dict[str, Any]] = []
        
    def load_test_data(self, data_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        加载测试数据
        
        Args:
            data_file: 测试数据文件路径（如果为None，使用初始化时的路径）
            
        Returns:
            List[Dict]: 测试数据列表
        """
        if data_file is None:
            data_file = self.data_file
            
        if data_file is None:
            raise ValueError("未指定测试数据文件路径")
        
        data_file = Path(data_file)
        if not data_file.exists():
            raise FileNotFoundError(f"测试数据文件不存在: {data_file}")
        
        logger.info(f"加载测试数据: {data_file}")
        test_data = []
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        item = json.loads(line)
                        # 验证必要字段
                        if 'question' not in item or 'answer' not in item:
                            logger.warning(f"第{line_num}行缺少必要字段，跳过")
                            continue
                        
                        # 添加行号用于追踪
                        item['line_number'] = line_num
                        test_data.append(item)
                    except json.JSONDecodeError as e:
                        logger.warning(f"第{line_num}行JSON解析失败: {e}，跳过")
                        continue
            
            self.test_data = test_data
            logger.info(f"成功加载 {len(test_data)} 条测试数据")
            return test_data
            
        except Exception as e:
            logger.error(f"加载测试数据失败: {e}")
            raise
    
    def evaluate(self, 
                 data_file: Optional[str] = None,
                 max_items: Optional[int] = None,
                 start_from: int = 0) -> Dict[str, Any]:
        """
        执行评估
        
        Args:
            data_file: 测试数据文件路径（如果为None，使用初始化时的路径）
            max_items: 最大评估数量（如果为None，评估所有数据）
            start_from: 从第几条开始评估（用于断点续评）
            
        Returns:
            Dict: 评估结果
        """
        # 加载测试数据
        if not self.test_data:
            self.load_test_data(data_file)
        
        if not self.test_data:
            raise ValueError("没有可用的测试数据")
        
        # 连接数据库
        logger.info("连接数据库...")
        db_manager.connect()
        
        # 确定评估范围
        test_items = self.test_data[start_from:]
        if max_items:
            test_items = test_items[:max_items]
        
        total_items = len(test_items)
        logger.info(f"开始评估 {total_items} 条测试数据（从第 {start_from + 1} 条开始）")
        
        # 评估结果
        evaluation_results = []
        start_time = datetime.now()
        
        try:
            for idx, item in enumerate(test_items, 1):
                logger.info(f"\n{'='*80}")
                logger.info(f"评估进度: {idx}/{total_items}")
                logger.info(f"问题: {item.get('question', '')[:100]}...")
                
                try:
                    # 执行检索
                    question = item['question']
                    logger.info(f"执行检索: {question[:100]}...")
                    query_result = self.retriever.retrieve(question)
                    
                    # 预测答案
                    predicted_answer = self.predictor.predict_answer(
                        question=question,
                        options=item.get('options', {}),
                        query_result=query_result
                    )
                    
                    # 构建评估结果
                    result = {
                        'line_number': item.get('line_number', start_from + idx),
                        'question': question,
                        'true_answer': item.get('answer', ''),
                        'true_answer_idx': item.get('answer_idx', ''),
                        'predicted_answer': predicted_answer.get('answer', ''),
                        'predicted_answer_idx': predicted_answer.get('answer_idx', ''),
                        'options': item.get('options', {}),
                        'meta_info': item.get('meta_info', ''),
                        'is_correct': predicted_answer.get('answer_idx', '') == item.get('answer_idx', ''),
                        'confidence': predicted_answer.get('confidence', 0.0),
                        'retrieval_metadata': {
                            'entities_count': len(query_result.entities),
                            'relationships_count': len(query_result.relationships),
                            'retrieval_method': query_result.metadata.get('retrieval_method', 'Unknown')
                        },
                        'reasoning_chain': query_result.reasoning_chain,  # 检索阶段的推理链
                        'llm_response': predicted_answer.get('llm_response', ''),  # 答案预测的LLM响应
                        'prediction_method': predicted_answer.get('method', 'unknown'),  # 预测方法
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    evaluation_results.append(result)
                    
                    # 记录结果
                    status = "✅ 正确" if result['is_correct'] else "❌ 错误"
                    logger.info(f"{status} - 预测: {result['predicted_answer_idx']}, 正确答案: {result['true_answer_idx']}")
                    
                except Exception as e:
                    logger.error(f"评估第 {idx} 条数据时发生错误: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    # 记录错误结果
                    error_result = {
                        'line_number': item.get('line_number', start_from + idx),
                        'question': item.get('question', ''),
                        'true_answer': item.get('answer', ''),
                        'true_answer_idx': item.get('answer_idx', ''),
                        'predicted_answer': '',
                        'predicted_answer_idx': '',
                        'options': item.get('options', {}),
                        'meta_info': item.get('meta_info', ''),
                        'is_correct': False,
                        'confidence': 0.0,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    evaluation_results.append(error_result)
        
        finally:
            # 关闭数据库连接
            db_manager.close()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 计算评估指标
        metrics = self.metrics.calculate_metrics(evaluation_results)
        
        # 构建最终结果
        evaluation_summary = {
            'total_items': total_items,
            'evaluated_items': len(evaluation_results),
            'duration_seconds': duration,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'metrics': metrics,
            'results': evaluation_results
        }
        
        self.evaluation_results = evaluation_results
        
        logger.info(f"\n{'='*80}")
        logger.info("评估完成")
        logger.info(f"总耗时: {duration:.2f}秒 ({duration/60:.1f}分钟)")
        logger.info(f"准确率: {metrics.get('accuracy', 0.0):.2%}")
        logger.info(f"{'='*80}")
        
        return evaluation_summary
    
    def save_results(self, output_file: str, format: str = 'json'):
        """
        保存评估结果
        
        Args:
            output_file: 输出文件路径
            format: 输出格式 ('json' 或 'jsonl')
        """
        if not self.evaluation_results:
            logger.warning("没有评估结果可保存")
            return
        
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"保存评估结果到: {output_file}")
        
        try:
            if format == 'json':
                # 保存为JSON格式（包含所有结果和指标）
                summary = {
                    'metrics': self.metrics.calculate_metrics(self.evaluation_results),
                    'results': self.evaluation_results
                }
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
            
            elif format == 'jsonl':
                # 保存为JSONL格式（每行一个结果）
                with open(output_file, 'w', encoding='utf-8') as f:
                    for result in self.evaluation_results:
                        f.write(json.dumps(result, ensure_ascii=False) + '\n')
            
            else:
                raise ValueError(f"不支持的格式: {format}")
            
            logger.info(f"评估结果已保存到: {output_file}")
            
        except Exception as e:
            logger.error(f"保存评估结果失败: {e}")
            raise
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        生成评估报告
        
        Args:
            output_file: 输出文件路径（如果为None，仅返回报告内容）
            
        Returns:
            str: 报告内容
        """
        if not self.evaluation_results:
            raise ValueError("没有评估结果可生成报告")
        
        metrics = self.metrics.calculate_metrics(self.evaluation_results)
        report = self.report_generator.generate_report(
            self.evaluation_results,
            metrics
        )
        
        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"评估报告已保存到: {output_file}")
        
        return report

