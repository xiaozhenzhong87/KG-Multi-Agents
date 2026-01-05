"""
医疗知识图谱系统主入口
支持模块化的图谱构建系统

本系统提供以下主要功能：
1. 构建多层级医疗知识图谱（公有层 + 私有层）
2. 动态添加新的医疗数据
3. 智能检索和推理
4. 图谱连接和更新

注意：API功能目前处于开发阶段，仅供参考
"""
import logging
import argparse
from pathlib import Path
import subprocess
import sys
from typing import Optional, List

from src.core.database import db_manager
from src.kg_builder.private_kg import PrivateKGBuilder
from src.kg_builder.umls_kg import UMLSKGBuilder
from src.kg_builder.entity_connector import EntityConnector
from src.kg_builder.graph_updater import GraphUpdater
from src.retrieval.retriever import MedicalRetriever
from src.config.settings import settings

# 配置日志
import time
from datetime import datetime

# 创建更详细的日志格式
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
detailed_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

# 配置控制台输出（简化格式）
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
console_handler.setFormatter(logging.Formatter(log_format))

# 配置文件输出（详细格式）
file_handler = None
if settings.LOG_FILE:
    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(detailed_format))

# 配置根日志器
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    handlers=[console_handler] + ([file_handler] if file_handler else [])
)

logger = logging.getLogger(__name__)

def setup_database():
    """初始化数据库连接"""
    try:
        db_manager.connect()
        logger.info("数据库连接成功")
        return True
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return False

def build_private_kg_legacy(notepad_content: str, hospital_number: str = None):
    """构建私有知识图谱（Legacy模式）"""
    logger.info("开始构建私有知识图谱（Legacy模式）")
    builder = PrivateKGBuilder()
    success = builder.build_kg_from_content(notepad_content, hospital_number)
    if success:
        logger.info("私有知识图谱构建完成")
    else:
        logger.error("私有知识图谱构建失败")
    return success

def build_public_kg_direct():
    """直接调用构建UMLS知识图谱的函数"""
    from scripts.build_public_kg import run_build_public_kg
    logger.info("直接调用函数构建UMLS知识图谱")
    # 传入空参数列表，避免与主程序 --mode 等参数冲突
    return run_build_public_kg([])

def connect_entities():
    """连接私有和UMLS实体"""
    logger.info("开始连接实体")
    connector = EntityConnector()
    success = connector.connect_entities()
    if success:
        logger.info("实体连接完成")
    else:
        logger.error("实体连接失败")
    return success

def add_new_data(notepad_content: str, hospital_number: str = None):
    """添加新数据到图谱"""
    logger.info("开始添加新数据")
    updater = GraphUpdater()
    graph_data = updater.add_new_data_from_notepad(notepad_content, hospital_number)
    if graph_data.entities:
        logger.info(f"成功添加 {len(graph_data.entities)} 个实体和 {len(graph_data.relationships)} 个关系")
        return True
    else:
        logger.error("添加新数据失败")
        return False

def query_system(query: str = None):
    """
    查询系统 - 使用PageRank算法进行检索
    
    Args:
        query: 查询字符串（如果为None，则使用配置中的默认查询）
    """
    # 如果query为None，尝试从配置中获取
    if query is None:
        query = settings.QUERY
        if query is None:
            logger.error("未提供查询，且配置中也没有默认查询")
            print("❌ 错误: 未提供查询，请在命令行中使用--query参数或在配置中设置QUERY")
            return None
    
    logger.info(f"开始查询: {query}")
    retriever = MedicalRetriever()
    result = retriever.retrieve(query)
    
    print(f"\n=== 查询结果 ===")
    print(f"查询: {query}")
    print(f"检索方法: {result.metadata.get('retrieval_method', 'Unknown')}")
    print(f"找到 {len(result.entities)} 个实体, {len(result.relationships)} 个关系")
    
    if result.entities:
        print("\n--- 相关实体 ---")
        for entity in result.entities[:10]:  # 显示前10个
            # 显示PageRank分数（如果有）
            pagerank_info = ""
            if result.metadata and 'pagerank_score' in str(entity.properties):
                pagerank_info = f" (PageRank: {entity.properties.get('pagerank_score', 0):.4f})"
            print(f"- {entity.entity_type}: {entity.name}{pagerank_info}")
    
    if result.relationships:
        print("\n--- 相关关系 ---")
        for rel in result.relationships[:10]:  # 显示前10个
            print(f"- {rel.relationship_type}: {rel.source} -> {rel.target}")
    
    if result.reasoning_chain:
        print(f"\n--- 推理链 ---")
        print(result.reasoning_chain)
    
    return result

def run_script_command(script_name: str, args: list):
    """运行脚本命令"""
    try:
        script_path = Path(__file__).parent / "scripts" / script_name
        cmd = [sys.executable, str(script_path)] + args
        
        logger.info(f"🚀 执行命令: {' '.join(cmd)}")
        logger.info(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            logger.info(f"✅ {script_name} 执行成功")
            logger.info(f"⏱️  执行时间: {duration:.2f}秒 ({duration/60:.1f}分钟)")
            if result.stdout:
                # 输出关键信息到控制台
                stdout_lines = result.stdout.strip().split('\n')
                for line in stdout_lines[-10:]:  # 显示最后10行
                    if line.strip():
                        print(f"📄 {line}")
        else:
            logger.error(f"❌ {script_name} 执行失败 (返回码: {result.returncode})")
            logger.error(f"⏱️  执行时间: {duration:.2f}秒")
            if result.stderr:
                logger.error(f"错误输出: {result.stderr}")
                print(f"❌ 错误: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"❌ 执行{script_name}失败: {e}")
        return False

def print_banner():
    """打印系统横幅"""
    print("=" * 60)
    print("🏥 医疗知识图谱系统 v2.0")
    print("=" * 60)
    print("📋 功能：多层级知识图谱构建、智能检索、动态更新")
    print("⚠️  注意：API功能目前处于开发阶段，仅供参考")
    print("=" * 60)

def validate_args(args) -> bool:
    """验证命令行参数"""
    if args.mode in ["build_private", "add_private"] and not args.notepad_file:
        logger.error("❌ 构建/添加私有图谱需要指定 --notepad-file 参数")
        return False
    
    # query参数现在是可选的，如果未提供则使用配置中的默认查询
    # if args.mode == "query" and not args.query:
    #     logger.error("❌ 查询模式需要提供 --query 参数或在配置中设置QUERY")
    #     return False
    
    if args.mode == "add_legacy" and not args.notepad:
        logger.error("❌ 添加数据模式需要提供 --notepad 参数")
        return False
    
    return True

def main():
    """主函数"""
    print_banner()
    
    parser = argparse.ArgumentParser(
        description="医疗知识图谱系统 - 支持多层级图谱构建和智能检索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 构建完整知识图谱系统
  python main.py --mode build_all --notepad-file data/notepad.txt --hospital-number 12345
  
  # 仅构建公有层图谱
  python main.py --mode build_public
  
  # 仅构建私有层图谱
  python main.py --mode build_private --notepad-file data/notepad.txt --hospital-number 12345
  
  # 添加新数据到私有图谱
  python main.py --mode add_private --notepad-file data/new_data.txt --hospital-number 12345
  
  # 连接图谱
  python main.py --mode connect --similarity-threshold 0.6
  
  # 查询系统
  python main.py --mode query --query "患者Lin的实验室检查结果"
  
  # 使用legacy模式构建
  python main.py --mode build_legacy --notepad "notepad_content" --hospital-number 12345
        """
    )
    
    parser.add_argument("--mode", choices=[
        "build_all", "build_public", "build_private", "add_private", "connect", 
        "query", "build_legacy", "add_legacy"
    ], required=True,
                       help="运行模式")
    parser.add_argument("--notepad", type=str, help="Notepad内容（仅用于legacy模式）")
    parser.add_argument("--notepad-file", type=str, help="Notepad内容文件路径")
    parser.add_argument("--hospital-number", type=str, help="医院编号")
    parser.add_argument("--query", type=str, help="查询内容")
    parser.add_argument("--clear-existing", action="store_true", help="清除现有数据")
    parser.add_argument("--similarity-threshold", type=float, default=0.5, 
                       help="相似度阈值 (默认: 0.5)")
    
    args = parser.parse_args()
    
    # 验证参数
    if not validate_args(args):
        return 1
    
    # 初始化数据库
    logger.info("🔗 正在连接数据库...")
    if not setup_database():
        logger.error("❌ 数据库连接失败，程序退出")
        return 1
    
    try:
        if args.mode == "build_all":
            # 构建完整系统：公有层 + 私有层 + 连接
            logger.info("🚀 开始构建完整知识图谱系统")
            print("\n📊 构建进度:")
            
            # 1. 构建公有层图谱
            print("  [1/3] 构建公有层图谱...")
            logger.info("步骤1: 构建公有层图谱")
            if not build_public_kg_direct():
                logger.error("❌ 公有层图谱构建失败")
                return 1
            print("  ✅ 公有层图谱构建完成")
            
            # 2. 构建私有层图谱
            if args.notepad_file:
                print("  [2/3] 构建私有层图谱...")
                logger.info("步骤2: 构建私有层图谱")
                private_args = ["--mode", "build", "--notepad-file", args.notepad_file]
                if args.hospital_number:
                    private_args.extend(["--hospital-number", args.hospital_number])
                if args.clear_existing:
                    private_args.append("--clear-existing")
                
                if not run_script_command("build_private_kg.py", private_args):
                    logger.error("❌ 私有层图谱构建失败")
                    return 1
                print("  ✅ 私有层图谱构建完成")
            else:
                logger.warning("⚠️  未指定notepad文件，跳过私有层图谱构建")
                print("  ⏭️  跳过私有层图谱构建")
            
            # 3. 连接图谱
            print("  [3/3] 连接图谱...")
            logger.info("步骤3: 连接图谱")
            connect_args = ["--similarity-threshold", str(args.similarity_threshold)]
            if not run_script_command("connect_graphs.py", connect_args):
                logger.error("❌ 图谱连接失败")
                return 1
            print("  ✅ 图谱连接完成")
            
            print("\n🎉 完整知识图谱系统构建完成！")
            logger.info("✓ 完整知识图谱系统构建完成！")
            
        elif args.mode == "build_public":
            # 仅构建公有层图谱
            logger.info("🏗️  开始构建公有层图谱")
            print("📊 正在构建公有层图谱...")
            print("⏰ 开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            start_time = time.time()
            success = build_public_kg_direct()
            end_time = time.time()
            total_duration = end_time - start_time
            
            if success:
                print("✅ 公有层图谱构建完成")
                logger.info(f"✅ 公有层图谱构建完成 - 总耗时: {total_duration/60:.1f}分钟")
                print(f"⏱️  总耗时: {total_duration/60:.1f}分钟")
            else:
                print("❌ 公有层图谱构建失败")
                logger.error(f"❌ 公有层图谱构建失败 - 耗时: {total_duration/60:.1f}分钟")
                return 1
            
        elif args.mode == "build_private":
            # 仅构建私有层图谱
            logger.info("🏗️  构建私有层图谱")
            print("📊 正在构建私有层图谱...")
            
            private_args = ["--mode", "build", "--notepad-file", args.notepad_file]
            if args.hospital_number:
                private_args.extend(["--hospital-number", args.hospital_number])
            if args.clear_existing:
                private_args.append("--clear-existing")
            
            success = run_script_command("build_private_kg.py", private_args)
            if success:
                print("✅ 私有层图谱构建完成")
            else:
                print("❌ 私有层图谱构建失败")
                return 1
            
        elif args.mode == "add_private":
            # 添加新数据到私有层图谱
            logger.info("➕ 添加新数据到私有层图谱")
            print("📊 正在添加新数据...")
            
            private_args = ["--mode", "add", "--notepad-file", args.notepad_file]
            if args.hospital_number:
                private_args.extend(["--hospital-number", args.hospital_number])
            
            success = run_script_command("build_private_kg.py", private_args)
            if success:
                print("✅ 新数据添加完成")
            else:
                print("❌ 新数据添加失败")
                return 1
            
        elif args.mode == "connect":
            # 仅连接图谱
            logger.info("🔗 连接图谱")
            print("📊 正在连接图谱...")
            connect_args = ["--similarity-threshold", str(args.similarity_threshold)]
            success = run_script_command("connect_graphs.py", connect_args)
            if success:
                print("✅ 图谱连接完成")
            else:
                print("❌ 图谱连接失败")
                return 1
            
        elif args.mode == "build_legacy":
            # 使用旧的构建系统
            logger.info("🔄 使用旧的构建系统")
            print("📊 正在使用legacy模式构建知识图谱...")
            
            # 1. 构建私有知识图谱
            if args.notepad:
                print("  [1/3] 构建私有知识图谱...")
                if not build_private_kg_legacy(args.notepad, args.hospital_number):
                    print("  ❌ 私有知识图谱构建失败")
                    return 1
                print("  ✅ 私有知识图谱构建完成")
            else:
                logger.warning("⚠️  未指定notepad内容，跳过私有知识图谱构建")
                print("  ⏭️  跳过私有知识图谱构建")
            
            # 2. 构建UMLS知识图谱
            print("  [2/3] 构建UMLS知识图谱...")
            if not build_public_kg_direct():
                print("  ❌ UMLS知识图谱构建失败")
                return 1
            print("  ✅ UMLS知识图谱构建完成")
            
            # 3. 连接实体
            print("  [3/3] 连接实体...")
            if not connect_entities():
                print("  ❌ 实体连接失败")
                return 1
            print("  ✅ 实体连接完成")
            
            print("\n🎉 知识图谱系统构建完成！")
            logger.info("✓ 知识图谱系统构建完成！")
            
        elif args.mode == "add_legacy":
            # 使用旧的添加数据系统
            logger.info("➕ 使用旧的添加数据系统")
            print("📊 正在添加新数据...")
            
            if not add_new_data(args.notepad, args.hospital_number):
                print("❌ 新数据添加失败")
                return 1
            
            print("✅ 新数据添加完成！")
            logger.info("✓ 新数据添加完成！")
            
        elif args.mode == "query":
            # 查询系统 - 使用PageRank算法
            query = args.query if args.query else settings.QUERY
            if query:
                logger.info(f"🔍 查询系统: {query}")
                print(f"\n🔍 正在查询: {query}")
                result = query_system(query)
                if result:
                    print("\n✅ 查询完成")
                else:
                    print("\n❌ 查询失败")
                    return 1
            else:
                logger.error("❌ 查询模式需要提供 --query 参数或在配置中设置QUERY")
                print("❌ 错误: 请使用 --query 参数指定查询，或在配置文件中设置 QUERY 环境变量")
                return 1
    
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        logger.info("用户中断操作")
        return 1
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        logger.error(f"运行出错: {e}")
        return 1
    finally:
        logger.info("🔌 正在关闭数据库连接...")
        db_manager.close()
        print("👋 程序结束")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
