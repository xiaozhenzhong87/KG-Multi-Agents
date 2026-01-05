# 创建 src/retrieval/identifier.py
"""
核心标识识别模块
"""
import re
import logging
import requests
import json
from typing import List, Dict, Any, Optional

from ..config.settings import settings

logger = logging.getLogger(__name__)

class CoreIdentifier:
    """核心标识识别器"""
    
    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.ollama_model = settings.OLLAMA_MODEL
    
    def detect_patient_name(self, question: str) -> Optional[str]:
        """
        检测问题中的患者姓名
        支持格式：Lin {gender: female, age: 7} 或简单的姓名
        """
        logging.info('检测患者姓名')
        
        # 首先尝试正式格式：Lin {gender: female, age: 7}
        formal_pattern = r'\b(Lin)\s*\{[^}]*"gender"[^}]*"age"[^}]*\}'
        match = re.search(formal_pattern, question)
        if match:
            return match.group(1)
        
        # 然后尝试简单姓名模式：大写字母开头的单词
        simple_pattern = r"\b([A-Z][a-z]{2,})\b"
        matches = re.findall(simple_pattern, question)
        
        # 过滤掉常见的非姓名词汇
        common_words = {"You", "Now", "Professional", "Doctor", "Please", "Analyze", "Physical", 
                        "Examination", "Report", "Explain", "Cause", "Condition", "Potential", 
                        "Disease", "Risks", "Clinical", "Juvenile", "Arthritis", "There", "Might",
                        "Issues", "With", "Her", "White", "Blood", "Cell", "Count", "Lymphocyte",
                        "Percent", "Differential", "May", "Have"}
        
        for match in matches:
            if match not in common_words:
                logging.info(f"检测到潜在患者姓名: {match}")
                return match
        
        return None

    def detect_hospital_number(self, question: str) -> Optional[str]:
        """
        检测问题中的医院号码
        支持格式：5位以上数字，或Unknown_前缀的数字
        """
        logging.info('检测医院号码')
        # 支持5位以上的数字，包括Unknown_前缀
        pattern = r"\b(\d{5,}|Unknown_\d{5,})\b"
        match = re.search(pattern, question)
        if match:
            hospital_num = match.group(1)
            logging.info(f'检测到医院号码: {hospital_num}')
            return hospital_num
        else:
            logging.info('未检测到医院号码')
            return None

    def extract_entities_from_question(self, question: str) -> List[str]:
        """
        使用LLM从问题中提取医疗实体
        包括患者姓名、医疗术语、医院号码等
        """
        prompt = f"""
You are an entity extraction engine. Your task is to identify specific entities in the user's question.
Extract the following types of entities if present:

1.Names (e.g., Audrey Chesover, Janet Goodman)
2.Disease Names (e.g., juvenile arthritis, pneumonia)
3.Physical Examination Indicators (e.g., white blood cell count, lymphocyte count)
4.Other Medical-related Terms

Your output **MUST** be **ONLY** a comma-separated list containing the extracted entities.
**DO NOT** include any introductory text, explanations, justifications, apologies, or any conversational filler.
**Output ONLY** the comma-separated list.

Question: "{question}"

Extracted entities:
"""
        try:
            logging.info(f"发送实体提取请求，问题: {question}")
            response = requests.post(self.ollama_url, json={
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0}
            })
            response.raise_for_status()
            raw_entities_str = response.json().get("response", "").strip()
            logging.info(f'实体提取原始响应:\n{raw_entities_str}')

            lines = [line.strip() for line in raw_entities_str.split('\n') if line.strip()]
            if not lines:
                logging.warning("LLM返回空响应用于实体提取")
                return []

            potential_list_str = lines[-1]
            logging.info(f'使用最后一行进行解析: {potential_list_str}')

            # 检查该行是否更像解释而不是列表
            if len(potential_list_str.split()) > 10 and ',' not in potential_list_str:
                logging.warning("最后一行看起来像解释，不是列表。尝试解析，但可能不正确。")

            # 首先尝试按逗号分割，如提示中要求
            entities = [e.strip().strip("'\"") for e in potential_list_str.split(',') if e.strip() and len(e.strip()) > 1]

            # 如果逗号分割产生很少或没有结果，尝试按空格分割作为后备
            if not entities or len(entities) < 2:
                logging.warning("逗号分割产生很少实体，尝试空格分割作为后备。")
                space_entities = [e.strip().strip("'\"") for e in re.split(r'\s+', potential_list_str) if e.strip() and len(e.strip()) > 1]
                common_ignore = {"extracted", "entities", "question", "medical", "terms", "concepts", "patient", "names", "hospital", "numbers", "following", "types", "present", "full"}
                space_entities = [e for e in space_entities if e.lower() not in common_ignore]
                entities.extend(se for se in space_entities if se not in entities)

            # 最终清理
            entities = [e for e in entities if len(e) > 1 and not e.lower().startswith("extracted entities")]

            logging.info(f"LLM提取的实体（处理后）: {entities}")
            return list(set(entities))  # 返回唯一实体

        except requests.exceptions.RequestException as e:
            logging.error(f"联系Ollama API进行实体提取时出错: {e}")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"解码Ollama API响应进行实体提取时出错: {e}")
            logging.error(f"原始响应文本: {response.text}")
            return []
        except Exception as e:
            logging.error(f"实体提取过程中发生意外错误: {e}")
            return []

    def identify_core_identifiers(self, query: str) -> Dict[str, Any]:
        """
        识别核心标识符
        
        Args:
            query: 用户查询
            
        Returns:
            Dict: 包含核心标识符的字典
        """
        logging.info("步骤1: 识别核心标识...")
        
        # 检测医院号码
        hospital_number = self.detect_hospital_number(query)
        
        # 检测患者姓名
        patient_name = self.detect_patient_name(query)
        
        # 提取实体
        entities = self.extract_entities_from_question(query)
        
        # 重新排序实体，将患者姓名和医院号码放在前面
        if patient_name and patient_name in entities:
            entities.remove(patient_name)
            entities.insert(0, patient_name)
        
        if hospital_number and hospital_number in entities:
            entities.remove(hospital_number)
            entities.insert(0, hospital_number)
        
        logging.info(f"检测结果 - 医院号码: {hospital_number}, 患者姓名: {patient_name}, 实体: {entities}")
        
        return {
            'hospital_number': hospital_number,
            'patient_name': patient_name,
            'entities': entities
        }