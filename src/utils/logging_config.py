"""
日志配置模块
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

class LoggingConfig:
    """日志配置管理器"""
    
    def __init__(self):
        self.log_formats = {
            'detailed': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            'simple': '%(asctime)s - %(levelname)s - %(message)s',
            'minimal': '%(levelname)s: %(message)s'
        }
    
    def setup_logging(self, 
                     level: str = 'INFO',
                     log_file: Optional[str] = None,
                     format_style: str = 'detailed',
                     max_file_size: int = 10 * 1024 * 1024,  # 10MB
                     backup_count: int = 5,
                     console_output: bool = True) -> None:
        """设置日志配置"""
        
        # 获取日志级别
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # 获取日志格式
        log_format = self.log_formats.get(format_style, self.log_formats['detailed'])
        
        # 创建格式化器
        formatter = logging.Formatter(log_format)
        
        # 清除现有的处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 设置根日志级别
        root_logger.setLevel(log_level)
        
        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # 文件处理器
        if log_file:
            self._setup_file_handler(log_file, log_level, formatter, max_file_size, backup_count)
        
        # 设置第三方库的日志级别
        self._setup_third_party_loggers()
    
    def _setup_file_handler(self, log_file: str, level: int, formatter: logging.Formatter,
                           max_file_size: int, backup_count: int) -> None:
        """设置文件处理器"""
        log_path = Path(log_file)
        
        # 确保日志目录存在
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建轮转文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        
        # 添加到根日志器
        logging.getLogger().addHandler(file_handler)
    
    def _setup_third_party_loggers(self) -> None:
        """设置第三方库的日志级别"""
        third_party_loggers = {
            'neo4j': logging.WARNING,
            'urllib3': logging.WARNING,
            'requests': logging.WARNING,
            'sentence_transformers': logging.WARNING,
            'transformers': logging.WARNING,
            'torch': logging.WARNING,
            'numpy': logging.WARNING,
            'sklearn': logging.WARNING
        }
        
        for logger_name, level in third_party_loggers.items():
            logging.getLogger(logger_name).setLevel(level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        return logging.getLogger(name)
    
    def set_logger_level(self, logger_name: str, level: str) -> None:
        """设置指定日志器的级别"""
        logger = logging.getLogger(logger_name)
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(log_level)
    
    def add_file_handler(self, logger_name: str, log_file: str, 
                        level: str = 'INFO', format_style: str = 'detailed') -> None:
        """为指定日志器添加文件处理器"""
        logger = logging.getLogger(logger_name)
        log_level = getattr(logging, level.upper(), logging.INFO)
        log_format = self.log_formats.get(format_style, self.log_formats['detailed'])
        
        formatter = logging.Formatter(log_format)
        
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
    
    def create_structured_log(self, level: str, message: str, 
                            extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建结构化日志条目"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level.upper(),
            'message': message
        }
        
        if extra_data:
            log_entry.update(extra_data)
        
        return log_entry

# 全局日志配置实例
logging_config = LoggingConfig()

def setup_logging(level: str = 'INFO', 
                 log_file: Optional[str] = None,
                 format_style: str = 'detailed') -> None:
    """便捷的日志设置函数"""
    logging_config.setup_logging(
        level=level,
        log_file=log_file,
        format_style=format_style
    )

def get_logger(name: str) -> logging.Logger:
    """便捷的日志器获取函数"""
    return logging_config.get_logger(name)
