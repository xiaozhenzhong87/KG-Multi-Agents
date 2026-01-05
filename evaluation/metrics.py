"""
评估指标计算
"""
import logging
from typing import List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class EvaluationMetrics:
    """评估指标计算器"""
    
    def __init__(self):
        """初始化评估指标计算器"""
        pass
    
    def calculate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算评估指标
        
        Args:
            results: 评估结果列表
            
        Returns:
            Dict: 评估指标
        """
        if not results:
            return {
                'accuracy': 0.0,
                'total_items': 0,
                'correct_items': 0,
                'incorrect_items': 0,
                'error_items': 0
            }
        
        # 基础指标
        total_items = len(results)
        correct_items = sum(1 for r in results if r.get('is_correct', False))
        incorrect_items = total_items - correct_items
        error_items = sum(1 for r in results if 'error' in r)
        
        # 准确率
        accuracy = correct_items / total_items if total_items > 0 else 0.0
        
        # 按meta_info分组统计
        meta_info_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
        for result in results:
            meta_info = result.get('meta_info', 'unknown')
            meta_info_stats[meta_info]['total'] += 1
            if result.get('is_correct', False):
                meta_info_stats[meta_info]['correct'] += 1
        
        # 计算每个meta_info的准确率
        meta_info_accuracy = {}
        for meta_info, stats in meta_info_stats.items():
            meta_info_accuracy[meta_info] = {
                'total': stats['total'],
                'correct': stats['correct'],
                'accuracy': stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0
            }
        
        # 置信度统计
        confidences = [r.get('confidence', 0.0) for r in results if 'confidence' in r]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # 正确和错误答案的置信度
        correct_confidences = [
            r.get('confidence', 0.0) 
            for r in results 
            if r.get('is_correct', False) and 'confidence' in r
        ]
        incorrect_confidences = [
            r.get('confidence', 0.0) 
            for r in results 
            if not r.get('is_correct', True) and 'confidence' in r
        ]
        
        avg_correct_confidence = (
            sum(correct_confidences) / len(correct_confidences) 
            if correct_confidences else 0.0
        )
        avg_incorrect_confidence = (
            sum(incorrect_confidences) / len(incorrect_confidences) 
            if incorrect_confidences else 0.0
        )
        
        # 检索结果统计
        retrieval_stats = {
            'avg_entities_count': 0.0,
            'avg_relationships_count': 0.0,
            'retrieval_methods': {}
        }
        
        entity_counts = []
        relationship_counts = []
        retrieval_methods = defaultdict(int)
        
        for result in results:
            metadata = result.get('retrieval_metadata', {})
            entity_count = metadata.get('entities_count', 0)
            relationship_count = metadata.get('relationships_count', 0)
            retrieval_method = metadata.get('retrieval_method', 'Unknown')
            
            entity_counts.append(entity_count)
            relationship_counts.append(relationship_count)
            retrieval_methods[retrieval_method] += 1
        
        if entity_counts:
            retrieval_stats['avg_entities_count'] = sum(entity_counts) / len(entity_counts)
        if relationship_counts:
            retrieval_stats['avg_relationships_count'] = sum(relationship_counts) / len(relationship_counts)
        retrieval_stats['retrieval_methods'] = dict(retrieval_methods)
        
        # 答案分布统计
        true_answer_distribution = defaultdict(int)
        predicted_answer_distribution = defaultdict(int)
        
        for result in results:
            true_idx = result.get('true_answer_idx', '')
            predicted_idx = result.get('predicted_answer_idx', '')
            if true_idx:
                true_answer_distribution[true_idx] += 1
            if predicted_idx:
                predicted_answer_distribution[predicted_idx] += 1
        
        # 构建最终指标
        metrics = {
            'accuracy': accuracy,
            'total_items': total_items,
            'correct_items': correct_items,
            'incorrect_items': incorrect_items,
            'error_items': error_items,
            'meta_info_accuracy': meta_info_accuracy,
            'confidence_stats': {
                'avg_confidence': avg_confidence,
                'avg_correct_confidence': avg_correct_confidence,
                'avg_incorrect_confidence': avg_incorrect_confidence,
                'max_confidence': max(confidences) if confidences else 0.0,
                'min_confidence': min(confidences) if confidences else 0.0
            },
            'retrieval_stats': retrieval_stats,
            'answer_distribution': {
                'true_answers': dict(true_answer_distribution),
                'predicted_answers': dict(predicted_answer_distribution)
            }
        }
        
        return metrics
    
    def calculate_confusion_matrix(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算混淆矩阵
        
        Args:
            results: 评估结果列表
            
        Returns:
            Dict: 混淆矩阵
        """
        # 获取所有可能的答案索引
        all_indices = set()
        for result in results:
            all_indices.add(result.get('true_answer_idx', ''))
            all_indices.add(result.get('predicted_answer_idx', ''))
        all_indices = sorted([idx for idx in all_indices if idx])
        
        # 构建混淆矩阵
        confusion_matrix = {}
        for true_idx in all_indices:
            confusion_matrix[true_idx] = {}
            for pred_idx in all_indices:
                confusion_matrix[true_idx][pred_idx] = 0
        
        # 填充矩阵
        for result in results:
            true_idx = result.get('true_answer_idx', '')
            pred_idx = result.get('predicted_answer_idx', '')
            if true_idx and pred_idx:
                confusion_matrix[true_idx][pred_idx] = confusion_matrix[true_idx].get(pred_idx, 0) + 1
        
        return {
            'indices': all_indices,
            'matrix': confusion_matrix
        }

