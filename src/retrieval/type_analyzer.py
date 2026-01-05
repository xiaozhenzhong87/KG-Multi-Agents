"""
节点类型和关系类型分析模块
使用LLM先改写query，然后根据改写后的query从merged_types.csv筛选相关类型
"""
import logging
import requests
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config.settings import settings

logger = logging.getLogger(__name__)


class TypeAnalyzer:
    """类型分析器"""
    
    def __init__(self, 
                 query_rewrite_prompt_path: Optional[str] = None,
                 type_analysis_prompt_path: Optional[str] = None):
        """
        初始化类型分析器
        
        Args:
            query_rewrite_prompt_path: Query改写prompt配置文件路径（如果为None，则使用settings中的配置）
            type_analysis_prompt_path: 类型分析prompt配置文件路径（如果为None，则使用settings中的配置）
        """
        self.ollama_url = settings.OLLAMA_URL
        self.ollama_model = settings.OLLAMA_MODEL
        
        # 加载query改写prompt配置
        if query_rewrite_prompt_path is None:
            query_rewrite_prompt_path = settings.QUERY_REWRITE_PROMPT_CONFIG
        
        # 加载类型分析prompt配置
        if type_analysis_prompt_path is None:
            type_analysis_prompt_path = settings.TYPE_ANALYSIS_PROMPT_CONFIG
        
        # 转换为绝对路径
        project_root = Path(__file__).resolve().parent.parent.parent
        
        if not Path(query_rewrite_prompt_path).is_absolute():
            query_rewrite_prompt_path = project_root / query_rewrite_prompt_path
        
        if not Path(type_analysis_prompt_path).is_absolute():
            type_analysis_prompt_path = project_root / type_analysis_prompt_path
        
        self.query_rewrite_prompt_config = self._load_prompt_config(query_rewrite_prompt_path)
        self.type_analysis_prompt_config = self._load_prompt_config(type_analysis_prompt_path)
        
        # 加载节点类型和关系类型列表
        self._load_type_list()
    
    def _load_prompt_config(self, config_path: Path) -> Dict[str, Any]:
        """加载prompt配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载prompt配置: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载prompt配置失败: {e}")
            return {}
    
    def _load_type_list(self):
        """加载节点类型和关系类型列表"""
        try:
            # 加载merged_types.csv
            csv_path = Path(__file__).parent.parent.parent / "docs" / "merged_types.csv"
            
            entity_types = set()
            relationship_types = set()
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[1:]:  # 跳过标题行
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            entity_type = parts[0].strip().strip('"')
                            relationship_type = parts[1].strip().strip('"')
                            if entity_type:
                                entity_types.add(entity_type)
                            if relationship_type and relationship_type != "RELATIONSHIP":
                                relationship_types.add(relationship_type)
            
            self.entity_types = sorted(list(entity_types))
            self.relationship_types = sorted(list(relationship_types))
            
            logger.info(f"加载了 {len(self.entity_types)} 个节点类型和 {len(self.relationship_types)} 个关系类型")
            
        except Exception as e:
            logger.error(f"加载类型列表失败: {e}")
            self.entity_types = []
            self.relationship_types = []
    
    def analyze_query_types(self, query: str) -> Dict[str, Any]:
        """
        分析查询涉及的节点类型和关系类型
        步骤：
        1. 先使用LLM改写query
        2. 根据改写的query，从merged_types.csv中筛选相关的实体类型和关系类型
        
        Args:
            query: 用户查询
            
        Returns:
            Dict[str, Any]: 包含rewritten_query、entity_types和relationship_types的字典
        """
        if not settings.ENABLE_TYPE_ANALYSIS:
            logger.info("类型分析已禁用，跳过分析")
            return {"rewritten_query": query, "entity_types": [], "relationship_types": []}
        
        logger.info(f"开始分析查询类型: {query}")
        
        # 第一步：改写query
        rewritten_query = self._rewrite_query(query)
        if not rewritten_query:
            rewritten_query = query
        
        logger.info(f"改写后的query: {rewritten_query}")
        
        # 第二步：根据改写后的query筛选类型
        result = self._select_types(rewritten_query)
        
        # 添加改写后的query到结果中
        result['rewritten_query'] = rewritten_query
        
        logger.info(f"筛选结果 - 节点类型: {len(result.get('entity_types', []))} 个, "
                   f"关系类型: {len(result.get('relationship_types', []))} 个")
        logger.info(f"筛选出的节点类型: {result.get('entity_types', [])}")
        logger.info(f"筛选出的关系类型: {result.get('relationship_types', [])}")
        
        return result
    
    def _rewrite_query(self, query: str) -> str:
        """
        使用LLM改写query
        
        Args:
            query: 原始查询
            
        Returns:
            str: 改写后的查询
        """
        logger.info("步骤1: 使用LLM改写query...")
        
        # 构建改写prompt
        prompt = self._build_rewrite_prompt(query)
        
        try:
            # 调用LLM
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0}
                },
                timeout=60
            )
            response.raise_for_status()
            
            raw_response = response.json().get("response", "").strip()
            logger.debug(f"LLM改写响应: {raw_response}")
            
            # 解析响应
            rewritten_query = self._parse_rewrite_response(raw_response, query)
            
            return rewritten_query
            
        except Exception as e:
            logger.error(f"Query改写失败: {e}")
            return query
    
    def _select_types(self, rewritten_query: str) -> Dict[str, List[str]]:
        """
        根据改写后的query从merged_types.csv筛选相关类型
        
        Args:
            rewritten_query: 改写后的查询
            
        Returns:
            Dict[str, List[str]]: 包含entity_types和relationship_types的字典
        """
        logger.info("步骤2: 根据改写后的query筛选类型...")
        
        # 构建类型筛选prompt
        prompt = self._build_select_types_prompt(rewritten_query)
        
        try:
            # 调用LLM
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0}
                },
                timeout=60
            )
            response.raise_for_status()
            
            raw_response = response.json().get("response", "").strip()
            logger.debug(f"LLM类型筛选响应: {raw_response}")
            
            # 解析响应
            result = self._parse_select_types_response(raw_response)
            
            return result
            
        except Exception as e:
            logger.error(f"类型筛选失败: {e}")
            return {"entity_types": [], "relationship_types": []}
    
    def _build_rewrite_prompt(self, query: str) -> str:
        """构建query改写prompt"""
        parts = []
        
        # 添加系统prompt
        if 'system_prompt' in self.query_rewrite_prompt_config:
            parts.append(self.query_rewrite_prompt_config['system_prompt'])
            parts.append("")
        
        # 添加few shot examples
        if 'few_shot_examples' in self.query_rewrite_prompt_config:
            parts.append("Here are some examples:")
            parts.append("")
            for example in self.query_rewrite_prompt_config['few_shot_examples']:
                parts.append(f"Original query: {example['original_query']}")
                parts.append(f"Rewritten query: {example['rewritten_query']}")
                parts.append("")
        
        # 添加输出格式说明
        if 'output_format' in self.query_rewrite_prompt_config:
            output_format = self.query_rewrite_prompt_config['output_format']
            if 'description' in output_format:
                parts.append(output_format['description'])
            if 'example' in output_format:
                parts.append("Example output:")
                parts.append(output_format['example'])
            parts.append("")
        
        # 添加指令
        if 'instructions' in self.query_rewrite_prompt_config:
            parts.append("Please follow these steps:")
            parts.append(self.query_rewrite_prompt_config['instructions'])
            parts.append("")
        
        # 添加当前查询
        parts.append(f"Original query: {query}")
        parts.append("")
        parts.append("Please rewrite this query and output in JSON format:")
        
        return "\n".join(parts)
    
    def _build_select_types_prompt(self, rewritten_query: str) -> str:
        """构建类型筛选prompt"""
        parts = []
        
        # 添加系统prompt
        if 'system_prompt' in self.type_analysis_prompt_config:
            parts.append(self.type_analysis_prompt_config['system_prompt'])
            parts.append("")
        
        # 添加few shot examples
        if 'few_shot_examples' in self.type_analysis_prompt_config:
            parts.append("Here are some examples:")
            parts.append("")
            for example in self.type_analysis_prompt_config['few_shot_examples']:
                parts.append(f"Rewritten query: {example['query']}")
                parts.append(f"Selected entity types: {', '.join(example['entity_types'])}")
                parts.append(f"Selected relationship types: {', '.join(example['relationship_types'])}")
                parts.append("")
        
        # 添加所有可用的类型列表
        parts.append("=" * 80)
        parts.append("Available Entity Types (from merged_types.csv):")
        parts.append("=" * 80)
        parts.append(", ".join(self.entity_types))
        parts.append("")
        parts.append("=" * 80)
        parts.append("Available Relationship Types (from merged_types.csv):")
        parts.append("=" * 80)
        parts.append(", ".join(self.relationship_types))
        parts.append("")
        
        # 添加输出格式说明
        if 'output_format' in self.type_analysis_prompt_config:
            output_format = self.type_analysis_prompt_config['output_format']
            if 'description' in output_format:
                parts.append(output_format['description'])
            if 'example' in output_format:
                parts.append("Example output:")
                parts.append(output_format['example'])
            parts.append("")
        
        # 添加指令
        if 'instructions' in self.type_analysis_prompt_config:
            parts.append("Please follow these steps for selection:")
            parts.append(self.type_analysis_prompt_config['instructions'])
            parts.append("")
        
        # 添加当前查询
        parts.append(f"Rewritten query: {rewritten_query}")
        parts.append("")
        parts.append("Please select the relevant node types and relationship types from the lists above and output in JSON format:")
        
        return "\n".join(parts)
    
    def _parse_rewrite_response(self, raw_response: str, fallback_query: str) -> str:
        """解析query改写响应"""
        try:
            # 尝试提取JSON部分
            json_start = raw_response.find('{')
            json_end = raw_response.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = raw_response[json_start:json_end+1]
                parsed = json.loads(json_str)
                
                if 'rewritten_query' in parsed:
                    rewritten_query = parsed['rewritten_query'].strip()
                    if rewritten_query:
                        return rewritten_query
                
                logger.warning("JSON响应中没有找到rewritten_query字段")
            else:
                logger.warning("无法找到JSON格式，使用原始query")
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"原始响应: {raw_response}")
        
        return fallback_query
    
    def _parse_select_types_response(self, raw_response: str) -> Dict[str, List[str]]:
        """解析类型筛选响应"""
        result = {"entity_types": [], "relationship_types": []}
        
        try:
            # 尝试提取JSON部分
            json_start = raw_response.find('{')
            json_end = raw_response.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = raw_response[json_start:json_end+1]
                parsed = json.loads(json_str)
                
                # 提取节点类型和关系类型
                if 'entity_types' in parsed:
                    result['entity_types'] = parsed['entity_types']
                if 'relationship_types' in parsed:
                    result['relationship_types'] = parsed['relationship_types']
                
                logger.debug(f"成功解析JSON响应")
            else:
                logger.warning("无法找到JSON格式，尝试按行解析")
                # 可以添加按行解析的逻辑，但通常不需要
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"原始响应: {raw_response}")
        
        # 验证类型是否在允许的列表中
        result['entity_types'] = [t for t in result['entity_types'] if t in self.entity_types]
        result['relationship_types'] = [t for t in result['relationship_types'] if t in self.relationship_types]
        
        return result
