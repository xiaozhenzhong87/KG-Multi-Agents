"""
API服务启动脚本 - 简化版
"""
import sys
import argparse
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_system():
    """检查系统状态"""
    try:
        db_manager.connect()
        if not db_manager.health_check():
            logger.error("✗ 数据库连接异常")
            return False
        
        entity_count = db_manager.get_entity_count()
        if entity_count == 0:
            logger.error("✗ 数据库中没有数据，请先构建知识图谱")
            return False
        
        logger.info("✓ 系统就绪")
        return True
    except Exception as e:
        logger.error(f"✗ 系统检查失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动API服务")
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--skip-check", action="store_true", help="跳过系统检查")
    
    args = parser.parse_args()
    
    try:
        if not args.skip_check:
            if not check_system():
                return False
        
        logger.info(f"启动API服务器: http://{args.host}:{args.port}")
        
        uvicorn.run(
            "src.api.main:app",
            host=args.host,
            port=args.port,
            reload=False,
            log_level="info"
        )
        
        return True
        
    except KeyboardInterrupt:
        logger.info("API服务器已停止")
        return True
    except Exception as e:
        logger.error(f"✗ 启动API服务失败: {e}")
        return False
    finally:
        db_manager.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)