"""
评估报告生成器
"""
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """评估报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        pass
    
    def generate_report(self, 
                       results: List[Dict[str, Any]],
                       metrics: Dict[str, Any]) -> str:
        """
        生成评估报告
        
        Args:
            results: 评估结果列表
            metrics: 评估指标
            
        Returns:
            str: 报告文本
        """
        report_lines = []
        
        # 报告标题
        report_lines.append("=" * 80)
        report_lines.append("医疗知识图谱系统评估报告")
        report_lines.append("=" * 80)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 总体指标
        report_lines.append("=" * 80)
        report_lines.append("总体评估指标")
        report_lines.append("=" * 80)
        report_lines.append(f"总问题数: {metrics.get('total_items', 0)}")
        report_lines.append(f"正确答案数: {metrics.get('correct_items', 0)}")
        report_lines.append(f"错误答案数: {metrics.get('incorrect_items', 0)}")
        report_lines.append(f"错误数: {metrics.get('error_items', 0)}")
        report_lines.append(f"准确率: {metrics.get('accuracy', 0.0):.2%}")
        report_lines.append("")
        
        # 正确和错误题号列表
        correct_line_numbers = []
        incorrect_line_numbers = []
        error_line_numbers = []
        
        for result in results:
            line_num = result.get('line_number', 0)
            if 'error' in result:
                error_line_numbers.append(line_num)
            elif result.get('is_correct', False):
                correct_line_numbers.append(line_num)
            else:
                incorrect_line_numbers.append(line_num)
        
        # 正确题号列表
        if correct_line_numbers:
            report_lines.append("=" * 80)
            report_lines.append(f"正确答案题号列表（共{len(correct_line_numbers)}题）")
            report_lines.append("=" * 80)
            # 每行显示10个题号
            for i in range(0, len(correct_line_numbers), 10):
                line_nums = correct_line_numbers[i:i+10]
                report_lines.append(", ".join(map(str, line_nums)))
            report_lines.append("")
        
        # 错误题号列表
        if incorrect_line_numbers:
            report_lines.append("=" * 80)
            report_lines.append(f"错误答案题号列表（共{len(incorrect_line_numbers)}题）")
            report_lines.append("=" * 80)
            # 每行显示10个题号
            for i in range(0, len(incorrect_line_numbers), 10):
                line_nums = incorrect_line_numbers[i:i+10]
                report_lines.append(", ".join(map(str, line_nums)))
            report_lines.append("")
        
        # 错误记录题号列表
        if error_line_numbers:
            report_lines.append("=" * 80)
            report_lines.append(f"错误记录题号列表（共{len(error_line_numbers)}题）")
            report_lines.append("=" * 80)
            # 每行显示10个题号
            for i in range(0, len(error_line_numbers), 10):
                line_nums = error_line_numbers[i:i+10]
                report_lines.append(", ".join(map(str, line_nums)))
            report_lines.append("")
        
        # 按meta_info分组统计
        meta_info_accuracy = metrics.get('meta_info_accuracy', {})
        if meta_info_accuracy:
            report_lines.append("=" * 80)
            report_lines.append("按meta_info分组的准确率")
            report_lines.append("=" * 80)
            for meta_info, stats in meta_info_accuracy.items():
                report_lines.append(
                    f"{meta_info}: {stats.get('accuracy', 0.0):.2%} "
                    f"({stats.get('correct', 0)}/{stats.get('total', 0)})"
                )
            report_lines.append("")
        
        # 置信度统计
        confidence_stats = metrics.get('confidence_stats', {})
        if confidence_stats:
            report_lines.append("=" * 80)
            report_lines.append("置信度统计")
            report_lines.append("=" * 80)
            report_lines.append(f"平均置信度: {confidence_stats.get('avg_confidence', 0.0):.2%}")
            report_lines.append(f"正确答案平均置信度: {confidence_stats.get('avg_correct_confidence', 0.0):.2%}")
            report_lines.append(f"错误答案平均置信度: {confidence_stats.get('avg_incorrect_confidence', 0.0):.2%}")
            report_lines.append(f"最大置信度: {confidence_stats.get('max_confidence', 0.0):.2%}")
            report_lines.append(f"最小置信度: {confidence_stats.get('min_confidence', 0.0):.2%}")
            report_lines.append("")
        
        # 检索统计
        retrieval_stats = metrics.get('retrieval_stats', {})
        if retrieval_stats:
            report_lines.append("=" * 80)
            report_lines.append("检索统计")
            report_lines.append("=" * 80)
            report_lines.append(f"平均实体数量: {retrieval_stats.get('avg_entities_count', 0.0):.1f}")
            report_lines.append(f"平均关系数量: {retrieval_stats.get('avg_relationships_count', 0.0):.1f}")
            
            retrieval_methods = retrieval_stats.get('retrieval_methods', {})
            if retrieval_methods:
                report_lines.append("检索方法分布:")
                for method, count in retrieval_methods.items():
                    report_lines.append(f"  {method}: {count}")
            report_lines.append("")
        
        # 答案分布
        answer_distribution = metrics.get('answer_distribution', {})
        if answer_distribution:
            report_lines.append("=" * 80)
            report_lines.append("答案分布")
            report_lines.append("=" * 80)
            
            true_answers = answer_distribution.get('true_answers', {})
            predicted_answers = answer_distribution.get('predicted_answers', {})
            
            if true_answers:
                report_lines.append("正确答案分布:")
                for idx, count in sorted(true_answers.items()):
                    report_lines.append(f"  {idx}: {count}")
            
            if predicted_answers:
                report_lines.append("预测答案分布:")
                for idx, count in sorted(predicted_answers.items()):
                    report_lines.append(f"  {idx}: {count}")
            report_lines.append("")
        
        # 错误案例分析
        incorrect_results = [r for r in results if not r.get('is_correct', False) and 'error' not in r]
        if incorrect_results:
            report_lines.append("=" * 80)
            report_lines.append(f"错误案例分析（前10个）")
            report_lines.append("=" * 80)
            
            for idx, result in enumerate(incorrect_results[:10], 1):
                report_lines.append(f"\n错误案例 {idx}:")
                report_lines.append(f"  问题: {result.get('question', '')[:200]}...")
                report_lines.append(f"  正确答案: {result.get('true_answer_idx', '')} - {result.get('true_answer', '')[:100]}")
                report_lines.append(f"  预测答案: {result.get('predicted_answer_idx', '')} - {result.get('predicted_answer', '')[:100]}")
                report_lines.append(f"  置信度: {result.get('confidence', 0.0):.2%}")
                if result.get('meta_info'):
                    report_lines.append(f"  meta_info: {result.get('meta_info')}")
            report_lines.append("")
        
        # 错误记录
        error_results = [r for r in results if 'error' in r]
        if error_results:
            report_lines.append("=" * 80)
            report_lines.append(f"错误记录（{len(error_results)}个）")
            report_lines.append("=" * 80)
            
            for idx, result in enumerate(error_results[:10], 1):
                report_lines.append(f"\n错误 {idx}:")
                report_lines.append(f"  问题: {result.get('question', '')[:200]}...")
                report_lines.append(f"  错误信息: {result.get('error', '')[:200]}")
            report_lines.append("")
        
        # 报告结尾
        report_lines.append("=" * 80)
        report_lines.append("报告结束")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def generate_detailed_report(self,
                                 results: List[Dict[str, Any]],
                                 metrics: Dict[str, Any]) -> str:
        """
        生成详细评估报告（包含所有结果）
        
        Args:
            results: 评估结果列表
            metrics: 评估指标
            
        Returns:
            str: 详细报告文本
        """
        # 首先生成基础报告
        report = self.generate_report(results, metrics)
        
        # 添加详细结果
        report_lines = report.split('\n')
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("详细结果列表")
        report_lines.append("=" * 80)
        
        for idx, result in enumerate(results, 1):
            report_lines.append(f"\n结果 {idx}:")
            report_lines.append(f"  行号: {result.get('line_number', idx)}")
            report_lines.append(f"  问题: {result.get('question', '')}")
            report_lines.append(f"  正确答案: {result.get('true_answer_idx', '')} - {result.get('true_answer', '')}")
            report_lines.append(f"  预测答案: {result.get('predicted_answer_idx', '')} - {result.get('predicted_answer', '')}")
            report_lines.append(f"  正确: {'是' if result.get('is_correct', False) else '否'}")
            report_lines.append(f"  置信度: {result.get('confidence', 0.0):.2%}")
            if result.get('meta_info'):
                report_lines.append(f"  meta_info: {result.get('meta_info')}")
            if 'error' in result:
                report_lines.append(f"  错误: {result.get('error', '')}")
        
        return "\n".join(report_lines)

