"""
文本处理工具模块
"""
import re
import string
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class TextProcessor:
    """文本处理器"""
    
    def __init__(self):
        # 医疗相关停用词
        self.medical_stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '里', '个', '为', '对', '下', '过', '他', '她', '它', '们',
            '可以', '能', '会', '要', '应该', '可能', '或者', '但是', '因为', '所以',
            '如果', '虽然', '然后', '而且', '还有', '另外', '此外', '同时', '首先',
            '其次', '最后', '总之', '因此', '然而', '不过', '可是', '只是', '只是',
            '就是', '就是', '就是', '就是', '就是', '就是', '就是', '就是'
        }
        
        # 医疗实体模式
        self.medical_patterns = {
            'age': r'(\d+)\s*岁',
            'gender': r'(男|女|男性|女性)',
            'hospital_number': r'医院编号[：:]\s*(\d+)',
            'date': r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            'time': r'(\d{1,2}[:：]\d{2})',
            'temperature': r'(\d+\.?\d*)\s*[°℃度]',
            'blood_pressure': r'(\d+/\d+)\s*mmHg',
            'heart_rate': r'心率[：:]\s*(\d+)\s*次/分',
            'weight': r'体重[：:]\s*(\d+\.?\d*)\s*kg',
            'height': r'身高[：:]\s*(\d+\.?\d*)\s*cm'
        }
    
    def clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符但保留中文、英文、数字和基本标点
        text = re.sub(r'[^\u4e00-\u9fff\w\s.,;:!?()（）【】\[\]""''""''—–-]', '', text)
        
        # 标准化引号
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()
    
    def extract_medical_entities(self, text: str) -> Dict[str, List[str]]:
        """提取医疗实体"""
        entities = {}
        
        for entity_type, pattern in self.medical_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                entities[entity_type] = matches
        
        return entities
    
    def segment_text(self, text: str) -> List[str]:
        """简单中文分词（基于空格和标点）"""
        if not text:
            return []
        
        # 按空格和标点分割
        words = re.split(r'[\s,，。！？；：]', text)
        return [word.strip() for word in words if word.strip()]
    
    def remove_stopwords(self, words: List[str]) -> List[str]:
        """移除停用词"""
        return [word for word in words if word not in self.medical_stopwords and len(word) > 1]
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """提取关键词"""
        # 分词
        words = self.segment_text(text)
        words = self.remove_stopwords(words)
        
        # 简单的词频统计
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按频率排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_words[:top_k]
    
    def normalize_medical_term(self, term: str) -> str:
        """标准化医疗术语"""
        if not term:
            return ""
        
        # 转换为小写
        term = term.lower()
        
        # 移除多余空格
        term = re.sub(r'\s+', ' ', term).strip()
        
        # 标准化常见医疗术语
        term_mappings = {
            '血压': 'blood_pressure',
            '心率': 'heart_rate',
            '体温': 'temperature',
            '体重': 'weight',
            '身高': 'height',
            '年龄': 'age',
            '性别': 'gender'
        }
        
        return term_mappings.get(term, term)
    
    def extract_sentences(self, text: str) -> List[str]:
        """提取句子"""
        if not text:
            return []
        
        # 按句号、问号、感叹号分割
        sentences = re.split(r'[。！？]', text)
        
        # 清理和过滤
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        
        return sentences
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简单版本）"""
        if not text1 or not text2:
            return 0.0
        
        # 分词
        words1 = set(self.segment_text(text1))
        words2 = set(self.segment_text(text2))
        
        # 计算Jaccard相似度
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def extract_medical_relationships(self, text: str) -> List[Dict[str, str]]:
        """提取医疗关系"""
        relationships = []
        
        # 症状-疾病关系模式
        symptom_disease_patterns = [
            r'(\w+症状)\s*(?:可能|提示|表明|说明)\s*(\w+疾病)',
            r'(\w+疾病)\s*(?:伴有|伴随|出现)\s*(\w+症状)',
            r'(\w+症状)\s*(?:与|和)\s*(\w+疾病)\s*(?:相关|有关)'
        ]
        
        for pattern in symptom_disease_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                relationships.append({
                    'source': match.group(1),
                    'target': match.group(2),
                    'relationship_type': 'symptom_disease',
                    'confidence': 0.8
                })
        
        return relationships
    
    def preprocess_for_embedding(self, text: str) -> str:
        """为嵌入模型预处理文本"""
        if not text:
            return ""
        
        # 清理文本
        text = self.clean_text(text)
        
        # 移除停用词
        words = self.segment_text(text)
        words = self.remove_stopwords(words)
        
        # 重新组合
        processed_text = ' '.join(words)
        
        return processed_text

# 全局文本处理器实例
text_processor = TextProcessor()
