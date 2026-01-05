#!/usr/bin/env python3
"""
公有层知识图谱构建脚本
基于UMLS数据构建医疗概念知识图谱
使用正确的关系类型，关系将显示为具体的UMLS关系类型
"""
import os
import sys
import logging
import time
import gc
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import db_manager
from src.kg_builder.umls_kg import UMLSKGBuilder
from src.config.settings import settings

# 配置日志
import time
from datetime import datetime

# 创建详细的日志格式
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
detailed_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

# 确保logs目录存在
os.makedirs('./logs', exist_ok=True)

# 配置控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(log_format))

# 配置文件输出
file_handler = logging.FileHandler('./logs/build_public_kg_v2.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(detailed_format))

# 配置根日志器
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)

class PublicKGBuilder:
    """公有层知识图谱构建器"""
    
    def __init__(self, skip_embeddings=False):
        self.skip_embeddings = skip_embeddings
        self.builder = UMLSKGBuilder(skip_embeddings=skip_embeddings)
    
    def build_public_kg(self):
        """构建公有层知识图谱"""
        logger.info("🚀 开始构建UMLS公有层知识图谱")
        logger.info(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        start_time = time.time()
        
        try:
            # 连接数据库
            logger.info("🔗 正在连接数据库...")
            db_manager.connect()
            logger.info("✅ 数据库连接成功")
            
            # 清除现有数据
            logger.info("🧹 清除现有UMLS数据...")
            clear_start = time.time()
            db_manager.clear_namespace("umls_kg")
            clear_duration = time.time() - clear_start
            logger.info(f"✅ 数据清理完成 (耗时: {clear_duration:.2f}秒)")
            
            # 创建索引
            logger.info("📊 创建数据库索引...")
            index_start = time.time()
            db_manager.create_indexes()
            index_duration = time.time() - index_start
            logger.info(f"✅ 索引创建完成 (耗时: {index_duration:.2f}秒)")
            
            # 加载数据
            logger.info("📥 加载UMLS数据...")
            load_start = time.time()
            nodes, edges = self.builder.load_umls_data()
            load_duration = time.time() - load_start
            
            if not nodes or not edges:
                logger.error("❌ 数据加载失败")
                return False
            
            logger.info(f"✅ 数据加载成功: {len(nodes)} 个节点, {len(edges)} 条边 (耗时: {load_duration:.2f}秒)")
            
            # 加载关系定义
            logger.info("📚 加载关系定义...")
            rel_start = time.time()
            rel_def_map = self.builder.load_srdef()
            rel_duration = time.time() - rel_start
            logger.info(f"✅ 关系定义加载成功: {len(rel_def_map)} 个定义 (耗时: {rel_duration:.2f}秒)")
            
            # 分批处理实体
            logger.info(f"🏗️  开始分批处理 {len(nodes)} 个实体...")
            entity_start = time.time()
            total_entities_created = self._process_entities_batch(nodes)
            entity_duration = time.time() - entity_start
            
            if total_entities_created == 0:
                logger.error("❌ 实体创建失败")
                return False
            
            logger.info(f"✅ 实体创建完成: {total_entities_created} 个实体 (耗时: {entity_duration/60:.1f}分钟)")
            
            # 分批处理关系
            logger.info(f"🔗 开始分批处理 {len(edges)} 条关系...")
            rel_process_start = time.time()
            total_relationships_created = self._process_relationships_batch(edges, rel_def_map)
            rel_process_duration = time.time() - rel_process_start
            
            if total_relationships_created == 0:
                logger.error("❌ 关系创建失败")
                return False
            
            logger.info(f"✅ 关系创建完成: {total_relationships_created} 个关系 (耗时: {rel_process_duration/60:.1f}分钟)")
            
            # 验证关系类型
            logger.info("🔍 验证关系类型...")
            self._validate_relationship_types()
            
            # 最终统计
            logger.info("📊 获取最终统计信息...")
            entity_count = db_manager.get_entity_count("umls_kg")
            relationship_count = db_manager.get_relationship_count("umls_kg")
            
            total_duration = time.time() - start_time
            
            logger.info("🎉 UMLS公有层知识图谱构建完成!")
            logger.info(f"📈 总计: {entity_count} 个实体, {relationship_count} 个关系")
            logger.info(f"⏱️  总耗时: {total_duration/60:.1f}分钟")
            logger.info("💡 现在关系将显示为具体的UMLS关系类型，而不是统一的RELATIONSHIP")
            
            return True
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"❌ 构建失败: {e}")
            logger.error(f"⏱️  失败前耗时: {total_duration/60:.1f}分钟")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _process_entities_batch(self, nodes):
        """分批处理实体"""
        total_entities_created = 0
        entity_batch_size = 5000
        total_batches = (len(nodes) - 1) // entity_batch_size + 1
        
        logger.info(f"📦 实体批处理配置: 批次大小={entity_batch_size}, 总批次数={total_batches}")
        
        for i in range(0, len(nodes), entity_batch_size):
            batch_start_time = time.time()
            batch_nodes = nodes[i:i + entity_batch_size]
            batch_num = i // entity_batch_size + 1
            
            logger.info(f"🏗️  处理实体批次 {batch_num}/{total_batches} ({len(batch_nodes)} 个节点)")
            
            # 创建实体
            create_start = time.time()
            entities = self.builder.create_umls_entities(batch_nodes)
            create_duration = time.time() - create_start
            
            # 批量保存实体
            save_start = time.time()
            created_count = db_manager.create_entities_batch(entities, batch_size=1000)
            save_duration = time.time() - save_start
            total_entities_created += created_count
            
            batch_duration = time.time() - batch_start_time
            progress = (total_entities_created / len(nodes)) * 100
            
            logger.info(f"✅ 批次 {batch_num} 完成: 创建={created_count}个, 总计={total_entities_created}/{len(nodes)} ({progress:.1f}%)")
            logger.info(f"⏱️  批次耗时: 创建={create_duration:.2f}s, 保存={save_duration:.2f}s, 总计={batch_duration:.2f}s")
            
            # 清理内存
            del entities
            gc.collect()
        
        logger.info(f"🎯 实体批处理完成: 总计创建 {total_entities_created} 个实体")
        return total_entities_created
    
    def _process_relationships_batch(self, edges, rel_def_map):
        """分批处理关系"""
        total_relationships_created = 0
        relationship_batch_size = 1000  # 使用较小的批次大小
        total_batches = (len(edges) - 1) // relationship_batch_size + 1
        
        logger.info(f"📦 关系批处理配置: 批次大小={relationship_batch_size}, 总批次数={total_batches}")
        
        for i in range(0, len(edges), relationship_batch_size):
            batch_start_time = time.time()
            batch_edges = edges[i:i + relationship_batch_size]
            batch_num = i // relationship_batch_size + 1
            
            logger.info(f"🔗 处理关系批次 {batch_num}/{total_batches} ({len(batch_edges)} 条边)")
            
            # 创建关系
            create_start = time.time()
            relationships = self.builder.create_umls_relationships(batch_edges, rel_def_map)
            create_duration = time.time() - create_start
            
            # 批量保存关系
            save_start = time.time()
            created_count = db_manager.create_relationships_batch(relationships, batch_size=200)
            save_duration = time.time() - save_start
            total_relationships_created += created_count
            
            batch_duration = time.time() - batch_start_time
            progress = (total_relationships_created / len(edges)) * 100
            
            logger.info(f"✅ 批次 {batch_num} 完成: 创建={created_count}个, 总计={total_relationships_created}/{len(edges)} ({progress:.1f}%)")
            logger.info(f"⏱️  批次耗时: 创建={create_duration:.2f}s, 保存={save_duration:.2f}s, 总计={batch_duration:.2f}s")
            
            # 清理内存
            del relationships
            gc.collect()
            
            # 每10个批次暂停一下，让系统休息
            if batch_num % 10 == 0:
                logger.info("😴 暂停2秒，让系统休息...")
                time.sleep(2)
        
        logger.info(f"🎯 关系批处理完成: 总计创建 {total_relationships_created} 个关系")
        return total_relationships_created
    
    def _validate_relationship_types(self):
        """验证关系类型"""
        logger.info("🔍 验证关系类型...")
        validate_start = time.time()
        
        query = """
        MATCH ()-[r]->()
        WHERE r.namespace = 'umls_kg'
        RETURN DISTINCT type(r) as relationship_type, count(r) as count
        ORDER BY count DESC
        LIMIT 20
        """
        
        results = db_manager.execute_query(query)
        validate_duration = time.time() - validate_start
        
        logger.info(f"📊 数据库中的关系类型统计（前20种） (耗时: {validate_duration:.2f}秒):")
        for i, result in enumerate(results, 1):
            logger.info(f"  {i:2d}. {result['relationship_type']}: {result['count']:,} 个")
        
        total_relationships = sum(result['count'] for result in results)
        logger.info(f"📈 前20种关系类型总计: {total_relationships:,} 个关系")

def run_build_public_kg(argv=None):
    """主函数（可被外部调用）
    argv: 可选的参数列表；当为None时，默认读取当前进程的sys.argv[1:]
    注意：当在主进程（如 main.py）内调用时，应传入空列表或自定义参数，避免与上层 --mode 等参数冲突。
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="构建UMLS公有层知识图谱", add_help=True)
    parser.add_argument("--skip-embeddings", action="store_true", 
                       help="跳过embedding生成（默认生成embedding）")
    parser.add_argument("--batch-size", type=int, default=5000,
                       help="实体批处理大小（默认5000）")
    
    # 当作为库被调用时，允许显式传入空argv以避免解析上层参数
    if argv is None:
        argv = sys.argv[1:]
    # 仅解析本模块参数，忽略未知参数，避免与主程序参数冲突
    args, _unknown = parser.parse_known_args(argv)
    
    logger.info("=" * 80)
    logger.info("🏥 构建UMLS公有层知识图谱")
    logger.info("=" * 80)
    logger.info(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔧 配置参数: skip_embeddings={args.skip_embeddings}, batch_size={args.batch_size}")
    
    if args.skip_embeddings:
        logger.info("⚠️  跳过embedding生成 - 图谱连接功能将不可用")
    else:
        logger.info("✅ 将生成embedding向量 - 支持图谱连接功能")
    
    start_time = time.time()
    
    # 创建构建器
    logger.info("🏗️  创建构建器...")
    builder = PublicKGBuilder(skip_embeddings=args.skip_embeddings)
    
    # 构建图谱
    logger.info("🚀 开始构建图谱...")
    success = builder.build_public_kg()
    
    total_time = time.time() - start_time
    
    if success:
        logger.info("🎉 构建成功!")
        logger.info(f"⏱️  总耗时: {total_time/60:.1f}分钟 ({total_time:.2f}秒)")
        if not args.skip_embeddings:
            logger.info("✅ embedding向量已生成，可以进行图谱连接")
        logger.info("💡 现在可以运行连接脚本或查询系统")
        return True
    else:
        logger.error("❌ 构建失败")
        logger.error(f"⏱️  失败前耗时: {total_time/60:.1f}分钟")
        return False

def main():
    """主函数 - 用于直接运行脚本"""
    # 直接运行脚本时，使用命令行参数
    success = run_build_public_kg(sys.argv[1:])
    
    # 关闭数据库连接
    logger.info("🔌 正在关闭数据库连接...")
    try:
        db_manager.close()
        logger.info("✅ 数据库连接已关闭")
    except Exception as e:
        logger.warning(f"⚠️  关闭数据库连接时出现警告: {e}")
    
    logger.info("=" * 80)
    logger.info(f"🏁 构建完成 - 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
