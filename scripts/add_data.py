"""
添加新数据脚本 - 简化版
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import db_manager
from src.kg_builder.graph_updater import GraphUpdater
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_notepad_data(notepad_content: str, hospital_number: str = None):
    """添加notepad数据"""
    try:
        logger.info("添加新数据到私有层...")
        
        updater = GraphUpdater()
        graph_data = updater.add_new_data_from_notepad(
            notepad_content, 
            hospital_number, 
            merge_existing=True
        )
        
        if graph_data.entities:
            logger.info(f"✓ 成功添加 {len(graph_data.entities)} 个实体和 {len(graph_data.relationships)} 个关系")
            
            # 重新连接图谱层
            logger.info("重新连接图谱层...")
            from src.kg_builder.entity_connector import EntityConnector
            connector = EntityConnector()
            connector.connect_entities()
            
            return True
        else:
            logger.error("✗ 添加数据失败")
            return False
            
    except Exception as e:
        logger.error(f"✗ 添加数据时出错: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="添加新数据")
    parser.add_argument("--notepad", type=str, required=True, help="Notepad内容")
    parser.add_argument("--hospital-number", type=str, help="医院编号")
    
    args = parser.parse_args()
    
    try:
        db_manager.connect()
        
        if not db_manager.health_check():
            logger.error("✗ 数据库连接异常")
            return False
        
        success = add_notepad_data(args.notepad, args.hospital_number)
        
        if success:
            logger.info("✓ 新数据添加完成！")
        
        return success
        
    except Exception as e:
        logger.error(f"✗ 添加数据失败: {e}")
        return False
    finally:
        db_manager.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)