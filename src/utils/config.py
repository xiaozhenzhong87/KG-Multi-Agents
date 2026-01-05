"""
配置管理工具模块
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """配置错误异常"""
    pass

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._configs: Dict[str, Any] = {}
    
    def load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """加载YAML配置文件"""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise ConfigError(f"配置文件不存在: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {config_path}")
            return config
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML解析错误: {e}")
        except Exception as e:
            raise ConfigError(f"加载配置文件失败: {e}")
    
    def load_env_config(self, prefix: str = "") -> Dict[str, str]:
        """加载环境变量配置"""
        env_config = {}
        prefix = prefix.upper() + "_" if prefix else ""
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                env_config[config_key] = value
        
        logger.info(f"加载了 {len(env_config)} 个环境变量配置")
        return env_config
    
    def validate_config(self, config: Dict[str, Any], schema: BaseModel) -> BaseModel:
        """验证配置数据"""
        try:
            validated_config = schema(**config)
            logger.info("配置验证通过")
            return validated_config
        except ValidationError as e:
            raise ConfigError(f"配置验证失败: {e}")
    
    def get_config(self, name: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._configs.get(name, default)
    
    def set_config(self, name: str, value: Any) -> None:
        """设置配置值"""
        self._configs[name] = value
        logger.debug(f"设置配置: {name} = {value}")
    
    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """合并多个配置字典"""
        merged = {}
        for config in configs:
            merged.update(config)
        return merged
    
    def save_config(self, config: Dict[str, Any], filename: str) -> None:
        """保存配置到文件"""
        config_path = self.config_dir / filename
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"配置已保存到: {config_path}")
        except Exception as e:
            raise ConfigError(f"保存配置文件失败: {e}")

# 全局配置管理器实例
config_manager = ConfigManager()
