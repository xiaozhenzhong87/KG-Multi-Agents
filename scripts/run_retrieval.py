"""
检索系统脚本 - 核心功能
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import get_db_manager
from src.retrieval.retriever import MedicalRetriever
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_system():
    """检查系统状态"""
    try:
        get_db_manager().connect()
        if not get_db_manager().health_check():
            logger.error("✗ 数据库连接异常")
            return False
        
        entity_count = get_db_manager().get_entity_count()
        if entity_count == 0:
            logger.error("✗ 数据库中没有数据，请先构建知识图谱")
            return False
        
        logger.info("✓ 系统就绪")
        return True
    except Exception as e:
        logger.error(f"✗ 系统检查失败: {e}")
        return False

def interactive_query():
    """交互式查询"""
    print("=== 医疗知识图谱检索系统 ===")
    print("输入 'quit' 或 'exit' 退出")
    print()
    
    retriever = MedicalRetriever()
    
    while True:
        try:
            query = input("请输入查询内容: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            print(f"\n正在查询: {query}")
            result = retriever.retrieve(query)
            
            print("\n" + "="*50)
            print(f"查询: {query}")
            print(f"置信度: {result.confidence:.3f}")
            print(f"找到 {len(result.entities)} 个实体, {len(result.relationships)} 个关系")
            
            if result.entities:
                print("\n--- 相关实体 ---")
                for i, entity in enumerate(result.entities[:10], 1):
                    print(f"{i}. {entity.entity_type}: {entity.name}")
            
            if result.relationships:
                print("\n--- 相关关系 ---")
                for i, rel in enumerate(result.relationships[:10], 1):
                    print(f"{i}. {rel.relationship_type}: {rel.source} -> {rel.target}")
            
            if result.reasoning_chain:
                print(f"\n--- 推理链 ---")
                print(result.reasoning_chain)
            
            # 显示LLM的完整响应
            if result.metadata and 'llm_response' in result.metadata:
                print(f"\n--- LLM分析报告 ---")
                print(result.metadata['llm_response'])
            
            print("="*50 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n退出检索系统")
            break
        except Exception as e:
            print(f"查询出错: {e}")

def single_query(query: str):
    """单次查询"""
    retriever = MedicalRetriever()
    result = retriever.retrieve(query)
    
    print(f"查询: {query}")
    print(f"置信度: {result.confidence:.3f}")
    print(f"找到 {len(result.entities)} 个实体, {len(result.relationships)} 个关系")
    
    if result.entities:
        print("\n--- 相关实体 ---")
        for i, entity in enumerate(result.entities[:10], 1):
            print(f"{i}. {entity.entity_type}: {entity.name}")
    
    if result.relationships:
        print("\n--- 相关关系 ---")
        for i, rel in enumerate(result.relationships[:10], 1):
            print(f"{i}. {rel.relationship_type}: {rel.source} -> {rel.target}")
    
    if result.reasoning_chain:
        print(f"\n--- 推理链 ---")
        print(result.reasoning_chain)
    
    # 显示LLM的完整响应
    if result.metadata and 'llm_response' in result.metadata:
        print(f"\n--- LLM分析报告 ---")
        print(result.metadata['llm_response'])

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="医疗知识图谱检索系统")
    parser.add_argument("--query", type=str, help="查询内容")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    
    args = parser.parse_args()
    
    try:
        if not check_system():
            return False
        
        if args.interactive:
            interactive_query()
        elif args.query:
            single_query(args.query)
        else:
            logger.error("请指定查询模式: --query 或 --interactive")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 检索系统运行失败: {e}")
        return False
    finally:
        get_db_manager().close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)