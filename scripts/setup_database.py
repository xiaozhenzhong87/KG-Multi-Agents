"""
数据库初始化脚本 - 简化版
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_database():
    """初始化数据库"""
    try:
        logger.info("初始化数据库...")
        db_manager.connect()
        db_manager.create_indexes()
        
        if db_manager.health_check():
            logger.info("✓ 数据库初始化完成")
            return True
        else:
            logger.error("✗ 数据库初始化失败")
            return False
    except Exception as e:
        logger.error(f"✗ 数据库初始化失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库初始化")
    parser.add_argument("--check", action="store_true", help="仅检查数据库连接")
    
    args = parser.parse_args()
    
    try:
        if args.check:
            db_manager.connect()
            if db_manager.health_check():
                logger.info("✓ 数据库连接正常")
                return True
            else:
                logger.error("✗ 数据库连接异常")
                return False
        else:
            return setup_database()
    except Exception as e:
        logger.error(f"✗ 操作失败: {e}")
        return False
    finally:
        db_manager.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)