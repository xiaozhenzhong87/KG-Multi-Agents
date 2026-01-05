#!/usr/bin/env python3
"""
运行评估脚本
用于评估医疗知识图谱系统在测试数据上的表现
"""
import sys
import logging
import argparse
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from evaluation.evaluator import TestDataEvaluator
from src.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="医疗知识图谱系统评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 评估所有测试数据
  python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl
  
  # 评估前10条数据
  python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --max-items 10
  
  # 从第5条开始评估
  python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --start-from 5
  
  # 保存结果到指定文件
  python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --output results.json
  
  # 生成报告
  python evaluation/run_evaluation.py --data-file eval_data/test_data.jsonl --report report.txt
        """
    )
    
    parser.add_argument(
        "--data-file",
        type=str,
        required=True,
        help="测试数据文件路径（JSONL格式）"
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="最大评估数量（默认：评估所有数据）"
    )
    parser.add_argument(
        "--start-from",
        type=int,
        default=0,
        help="从第几条开始评估（默认：0）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="结果输出文件路径（JSON格式）"
    )
    parser.add_argument(
        "--output-jsonl",
        type=str,
        default=None,
        help="结果输出文件路径（JSONL格式）"
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="评估报告输出文件路径"
    )
    
    args = parser.parse_args()
    
    # 验证数据文件
    data_file = Path(args.data_file)
    if not data_file.exists():
        logger.error(f"测试数据文件不存在: {data_file}")
        return 1
    
    logger.info("=" * 80)
    logger.info("医疗知识图谱系统评估")
    logger.info("=" * 80)
    logger.info(f"测试数据文件: {data_file}")
    logger.info(f"最大评估数量: {args.max_items or '全部'}")
    logger.info(f"起始位置: {args.start_from}")
    logger.info("=" * 80)
    
    try:
        # 创建评估器
        evaluator = TestDataEvaluator(data_file=str(data_file))
        
        # 执行评估
        evaluation_summary = evaluator.evaluate(
            max_items=args.max_items,
            start_from=args.start_from
        )
        
        # 保存结果
        if args.output:
            evaluator.save_results(args.output, format='json')
            logger.info(f"评估结果已保存到: {args.output}")
        
        if args.output_jsonl:
            evaluator.save_results(args.output_jsonl, format='jsonl')
            logger.info(f"评估结果已保存到: {args.output_jsonl}")
        
        # 生成报告
        if args.report:
            report = evaluator.generate_report(output_file=args.report)
            logger.info(f"评估报告已保存到: {args.report}")
        else:
            # 如果没有指定报告文件，输出到控制台
            report = evaluator.generate_report()
            print("\n" + report)
        
        # 输出摘要
        metrics = evaluation_summary.get('metrics', {})
        logger.info("\n" + "=" * 80)
        logger.info("评估完成")
        logger.info("=" * 80)
        logger.info(f"总问题数: {metrics.get('total_items', 0)}")
        logger.info(f"正确答案数: {metrics.get('correct_items', 0)}")
        logger.info(f"错误答案数: {metrics.get('incorrect_items', 0)}")
        logger.info(f"准确率: {metrics.get('accuracy', 0.0):.2%}")
        logger.info(f"耗时: {evaluation_summary.get('duration_seconds', 0):.2f}秒")
        logger.info("=" * 80)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n用户中断评估")
        return 1
    except Exception as e:
        logger.error(f"评估过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())

