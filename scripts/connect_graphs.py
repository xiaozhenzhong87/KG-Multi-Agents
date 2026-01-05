#!/usr/bin/env python3
"""
图谱连接脚本
实现公有层和私有层图谱的语义连接
通过余弦相似度计算建立REFERENCE_OF关系
"""
import os
import sys
import logging
import time
import gc
import numpy as np
import ast
from pathlib import Path
from typing import List, Dict, Optional
from sklearn.metrics.pairwise import cosine_similarity

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import db_manager
from src.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('connect_graphs.log')
    ]
)

logger = logging.getLogger(__name__)

# 实体类型排除列表（这些类型不建立UMLS链接）
EXCLUDED_TYPES_FOR_EMBEDDING = {"Patient", "Clinician", "GP", "Hospital", "Visit"}

class GraphConnector:
    """图谱连接器 - 链接公有层和私有层图谱"""
    
    def __init__(self, similarity_threshold: float = 0.5):
        self.similarity_threshold = similarity_threshold
        self.batch_size = 1000  # 批处理大小
    
    def connect_private_to_umls(self):
        """连接私有层和UMLS公有层图谱"""
        logger.info("开始连接私有层和UMLS公有层图谱")
        
        try:
            # 连接数据库
            db_manager.connect()
            logger.info("✓ 数据库连接成功")
            
            # 清除现有的跨图谱关系
            self.clear_existing_cross_graph_relations()
            
            # 获取私有层实体
            private_entities = self.get_private_entities()
            logger.info(f"找到 {len(private_entities)} 个私有层实体")
            
            if not private_entities:
                logger.warning("没有找到私有层实体，跳过连接")
                return True
            
            # 获取UMLS实体
            umls_entities = self.get_umls_entities()
            logger.info(f"找到 {len(umls_entities)} 个UMLS实体")
            
            if not umls_entities:
                logger.warning("没有找到UMLS实体，跳过连接")
                return True
            
            # 建立语义链接
            total_connections = self.create_semantic_links(private_entities, umls_entities)
            
            logger.info(f"✓ 图谱连接完成，总共建立了 {total_connections} 个语义链接")
            return True
            
        except Exception as e:
            logger.error(f"✗ 连接图谱失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def clear_existing_cross_graph_relations(self):
        """清除现有的跨图谱关系"""
        logger.info("清除现有的跨图谱关系...")
        with db_manager.driver.session() as session:
            result = session.run("""
                MATCH ()-[r:REFERENCE_OF]->()
                WHERE r.namespace = 'cross_graph'
                DELETE r
                RETURN count(r) as deleted_count
            """)
            deleted_count = result.single()["deleted_count"]
            logger.info(f"清除了 {deleted_count} 个现有的跨图谱关系")
    
    def get_private_entities(self):
        """获取私有层实体"""
        with db_manager.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {namespace: 'private_kg'})
                WHERE e.embedding IS NOT NULL
                AND NOT e.type IN $excluded_types
                RETURN e.id as id, e.name as name, e.type as type, e.embedding as embedding
            """, excluded_types=list(EXCLUDED_TYPES_FOR_EMBEDDING))
            
            entities = []
            for record in result:
                try:
                    # 确保embedding是列表格式
                    embedding = record['embedding']
                    if isinstance(embedding, str):
                        embedding = ast.literal_eval(embedding)
                    
                    entities.append({
                        'id': record['id'],
                        'name': record['name'],
                        'type': record['type'],
                        'embedding': embedding
                    })
                except Exception as e:
                    logger.warning(f"解析私有实体 {record['id']} 的embedding失败: {e}")
                    continue
            
            return entities
    
    def get_umls_entities(self):
        """获取UMLS实体"""
        with db_manager.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {namespace: 'umls_kg'})
                WHERE e.embedding IS NOT NULL
                RETURN e.cui as cui, e.name as name, e.embedding as embedding
            """)
            
            entities = []
            for record in result:
                try:
                    # 确保embedding是列表格式
                    embedding = record['embedding']
                    if isinstance(embedding, str):
                        embedding = ast.literal_eval(embedding)
                    
                    entities.append({
                        'cui': record['cui'],
                        'name': record['name'],
                        'embedding': embedding
                    })
                except Exception as e:
                    logger.warning(f"解析UMLS实体 {record['cui']} 的embedding失败: {e}")
                    continue
            
            return entities
    
    def create_semantic_links(self, private_entities, umls_entities):
        """创建语义链接"""
        total_connections = 0
        
        # 分批处理UMLS实体
        total_batches = (len(umls_entities) + self.batch_size - 1) // self.batch_size
        
        for i in range(0, len(umls_entities), self.batch_size):
            batch_umls = umls_entities[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            logger.info(f"处理UMLS批次 {batch_num}/{total_batches} ({len(batch_umls)} 个实体)")
            
            batch_connections = self.process_batch_similarity(private_entities, batch_umls)
            total_connections += batch_connections
            
            logger.info(f"批次 {batch_num} 完成: {batch_connections} 个连接")
            
            # 清理内存
            gc.collect()
            
            # 每10个批次暂停一下
            if batch_num % 10 == 0:
                logger.info("暂停1秒，让系统休息...")
                time.sleep(1)
        
        return total_connections
    
    def process_batch_similarity(self, private_entities, umls_entities):
        """处理批次相似度计算"""
        batch_connections = 0
        
        # 准备私有层embedding矩阵
        private_embeddings = []
        valid_private_entities = []
        
        for entity in private_entities:
            try:
                emb = np.array(entity['embedding'])
                if len(emb) == 768:  # 确保是768维
                    private_embeddings.append(emb)
                    valid_private_entities.append(entity)
            except Exception as e:
                logger.warning(f"处理私有实体 {entity['id']} 的embedding失败: {e}")
                continue
        
        if not private_embeddings:
            return 0
        
        private_embeddings = np.array(private_embeddings)
        
        # 准备UMLS embedding矩阵
        umls_embeddings = []
        valid_umls_entities = []
        
        for entity in umls_entities:
            try:
                emb = np.array(entity['embedding'])
                if len(emb) == 768:  # 确保是768维
                    umls_embeddings.append(emb)
                    valid_umls_entities.append(entity)
            except Exception as e:
                logger.warning(f"处理UMLS实体 {entity['cui']} 的embedding失败: {e}")
                continue
        
        if not umls_embeddings:
            return 0
        
        umls_embeddings = np.array(umls_embeddings)
        
        # 计算相似度
        similarities = cosine_similarity(private_embeddings, umls_embeddings)
        
        # 创建语义链接
        with db_manager.driver.session() as session:
            for i, private_entity in enumerate(valid_private_entities):
                for j, umls_entity in enumerate(valid_umls_entities):
                    sim_score = similarities[i, j]
                    if sim_score >= self.similarity_threshold:
                        try:
                            session.run("""
                                MATCH (a:Entity {id: $private_id, namespace: 'private_kg'})
                                MATCH (b:Entity {cui: $umls_cui, namespace: 'umls_kg'})
                                MERGE (a)-[r:REFERENCE_OF]->(b)
                                SET r.similarity = $score,
                                    r.namespace = 'cross_graph',
                                    r.created_at = datetime()
                            """, 
                            private_id=private_entity['id'],
                            umls_cui=umls_entity['cui'],
                            score=float(sim_score)
                            )
                            batch_connections += 1
                        except Exception as e:
                            logger.warning(f"创建关系失败 {private_entity['id']} -> {umls_entity['cui']}: {e}")
                            continue
        
        return batch_connections
    
    def get_connection_statistics(self):
        """获取连接统计信息"""
        with db_manager.driver.session() as session:
            # 统计总连接数
            result = session.run("""
                MATCH ()-[r:REFERENCE_OF]->()
                WHERE r.namespace = 'cross_graph'
                RETURN count(r) as total_connections
            """)
            total_connections = result.single()["total_connections"]
            
            # 统计相似度分布
            result = session.run("""
                MATCH ()-[r:REFERENCE_OF]->()
                WHERE r.namespace = 'cross_graph'
                RETURN 
                    count(CASE WHEN r.similarity >= 0.9 THEN 1 END) as high_similarity,
                    count(CASE WHEN r.similarity >= 0.8 AND r.similarity < 0.9 THEN 1 END) as medium_high_similarity,
                    count(CASE WHEN r.similarity >= 0.7 AND r.similarity < 0.8 THEN 1 END) as medium_similarity,
                    count(CASE WHEN r.similarity >= 0.6 AND r.similarity < 0.7 THEN 1 END) as low_medium_similarity,
                    count(CASE WHEN r.similarity >= 0.5 AND r.similarity < 0.6 THEN 1 END) as low_similarity
            """)
            stats = result.single()
            
            logger.info("连接统计信息:")
            logger.info(f"  总连接数: {total_connections}")
            logger.info(f"  高相似度 (≥0.9): {stats['high_similarity']}")
            logger.info(f"  中高相似度 (0.8-0.9): {stats['medium_high_similarity']}")
            logger.info(f"  中等相似度 (0.7-0.8): {stats['medium_similarity']}")
            logger.info(f"  中低相似度 (0.6-0.7): {stats['low_medium_similarity']}")
            logger.info(f"  低相似度 (0.5-0.6): {stats['low_similarity']}")
            
            return total_connections, stats

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="图谱连接系统")
    parser.add_argument("--similarity-threshold", type=float, default=0.5,
                       help="相似度阈值 (默认: 0.5)")
    parser.add_argument("--batch-size", type=int, default=1000,
                       help="批处理大小 (默认: 1000)")
    parser.add_argument("--stats-only", action="store_true",
                       help="仅显示连接统计信息")
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("图谱连接系统")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    # 创建连接器
    connector = GraphConnector(similarity_threshold=args.similarity_threshold)
    connector.batch_size = args.batch_size
    
    if args.stats_only:
        # 仅显示统计信息
        try:
            db_manager.connect()
            logger.info("✓ 数据库连接成功")
            connector.get_connection_statistics()
        except Exception as e:
            logger.error(f"✗ 获取统计信息失败: {e}")
        finally:
            db_manager.close()
    else:
        # 执行连接
        success = connector.connect_private_to_umls()
        
        total_time = time.time() - start_time
        
        if success:
            logger.info(f"✓ 连接成功! 总耗时: {total_time/60:.1f}分钟")
            
            # 显示统计信息
            connector.get_connection_statistics()
        else:
            logger.error("✗ 连接失败")
        
        # 关闭数据库连接
        try:
            db_manager.close()
            logger.info("数据库连接已关闭")
        except:
            pass
    
    logger.info("=" * 80)
    logger.info("操作完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
