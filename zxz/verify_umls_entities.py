#!/usr/bin/env python3
"""验证MedQA题目中识别到的实体是否存在于UMLS中"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# 直接导入需要的模块
from src.core.database import Neo4jManager
from src.utils.graph_tools import GraphEntityMatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def verify_entities_in_umls(
    entities: List[str],
    db_manager: Neo4jManager,
    namespace: str = "umls_kg",
    max_candidates: int = 5,
) -> Dict[str, Any]:
    """
    验证实体列表是否存在于UMLS中
    
    Args:
        entities: 要验证的实体名称列表
        db_manager: Neo4j数据库管理器
        namespace: UMLS命名空间，默认为'umls_kg'
        max_candidates: 每个实体最多返回的匹配候选数
    
    Returns:
        包含验证结果的字典
    """
    # 创建实体匹配器，专门查找UMLS命名空间的实体
    matcher = GraphEntityMatcher(
        manager=db_manager,
        namespace=namespace,
        max_candidates=max_candidates,
    )
    
    results = []
    matched_count = 0
    unmatched_count = 0
    
    logger.info(f"开始验证 {len(entities)} 个实体...")
    
    for entity_name in entities:
        entity_name = entity_name.strip()
        if not entity_name:
            continue
            
        logger.info(f"验证实体: {entity_name}")
        
        # 使用匹配器查找UMLS中的匹配
        match_result = matcher.match_entity(entity_name)
        
        entity_result = {
            "entity_name": entity_name,
            "matched": match_result.matched,
            "match_count": len(match_result.matches),
            "matches": match_result.matches,
        }
        
        results.append(entity_result)
        
        if match_result.matched:
            matched_count += 1
            logger.info(f"  ✓ 找到 {len(match_result.matches)} 个匹配")
            # 打印前3个匹配的详细信息
            for i, match in enumerate(match_result.matches[:3], 1):
                logger.info(f"    {i}. {match.get('name')} (CUI: {match.get('cui')}, Type: {match.get('entity_type')})")
        else:
            unmatched_count += 1
            logger.warning(f"  ✗ 未找到匹配")
    
    # 计算覆盖率
    total = len(results)
    coverage_ratio = matched_count / total if total > 0 else 0.0
    
    summary = {
        "total_entities": total,
        "matched_entities": matched_count,
        "unmatched_entities": unmatched_count,
        "coverage_ratio": round(coverage_ratio, 4),
    }
    
    return {
        "summary": summary,
        "results": results,
    }


def main():
    """主函数"""
    # 用户提供的实体列表
    initial_seed = [
        "Carpal gland",
        "carpal spasm",
        "Carpal groove",
        "6 metacarpals",
        "Carpal hygroma",
        "Entire flexor tendon",
        "FLEXOR TENDON REPAIR",
        "Flexor tendon of thumb",
        "FLEXOR TENDON LACERATION",
    ]
    
    logger.info("=" * 80)
    logger.info("UMLS实体验证工具")
    logger.info("=" * 80)
    
    # 连接数据库
    db_manager = Neo4jManager()
    try:
        logger.info("正在连接Neo4j数据库...")
        db_manager.connect()
        logger.info("成功连接到Neo4j数据库")
        
        # 检查数据库健康状态
        if not db_manager.health_check():
            logger.error("数据库健康检查失败，请确保Neo4j服务正在运行")
            sys.exit(1)
        
        # 执行验证
        verification_result = verify_entities_in_umls(
            entities=initial_seed,
            db_manager=db_manager,
            namespace="umls_kg",
            max_candidates=5,
        )
        
        # 打印摘要
        logger.info("=" * 80)
        logger.info("验证摘要")
        logger.info("=" * 80)
        logger.info(f"总实体数: {verification_result['summary']['total_entities']}")
        logger.info(f"匹配实体数: {verification_result['summary']['matched_entities']}")
        logger.info(f"未匹配实体数: {verification_result['summary']['unmatched_entities']}")
        logger.info(f"覆盖率: {verification_result['summary']['coverage_ratio'] * 100:.2f}%")
        
        # 打印详细结果
        logger.info("=" * 80)
        logger.info("详细结果")
        logger.info("=" * 80)
        
        for result in verification_result["results"]:
            status = "✓" if result["matched"] else "✗"
            logger.info(f"\n{status} {result['entity_name']}")
            if result["matched"]:
                logger.info(f"  找到 {result['match_count']} 个匹配:")
                for i, match in enumerate(result["matches"], 1):
                    logger.info(f"    {i}. 名称: {match.get('name')}")
                    logger.info(f"       CUI: {match.get('cui', 'N/A')}")
                    logger.info(f"       类型: {match.get('entity_type', 'N/A')}")
                    logger.info(f"       命名空间: {match.get('namespace', 'N/A')}")
                    if match.get('definition'):
                        logger.info(f"       定义: {match.get('definition')[:100]}...")
            else:
                logger.info("  未在UMLS中找到匹配")
        
        # 保存结果到JSON文件
        output_file = Path(__file__).parent / "umls_verification_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(verification_result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n结果已保存到: {output_file}")
        
    except Exception as e:
        logger.error(f"验证过程中出错: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_manager.close()


if __name__ == "__main__":
    main()

