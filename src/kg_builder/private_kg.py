"""
私有知识图谱构建模块
"""
import os
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from tqdm import tqdm

from ..core.models import Entity, Relationship, Document
from ..core.database import db_manager
from ..core.embeddings import embedding_manager
from ..utils.text_processor import TextProcessor
from ..config.settings import settings

logger = logging.getLogger(__name__)

class PrivateKGBuilder:
    """私有知识图谱构建器"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.excluded_types = {"Patient", "Clinician", "GP", "Hospital", "Visit"}
    
    def process_documents(self, pdf_dir: str) -> List[Document]:
        """处理PDF文档"""
        documents = []
        pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        
        logger.info(f"找到 {len(pdf_files)} 个PDF文件")
        
        for filename in tqdm(pdf_files, desc="处理PDF文档"):
            try:
                file_path = os.path.join(pdf_dir, filename)
                document = self._process_single_pdf(file_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"处理文件 {filename} 失败: {e}")
                continue
        
        return documents
    
    def _process_single_pdf(self, file_path: str) -> Optional[Document]:
        """处理单个PDF文件"""
        try:
            filename = os.path.basename(file_path)
            
            # 提取文本内容
            content = self._extract_text_from_pdf(file_path)
            if not content:
                return None
            
            # 创建文档对象
            document = Document(
                filename=filename,
                content=content,
                file_type="pdf"
            )
            
            # 提取实体和关系
            entities, relationships = self._extract_entities_and_relationships(content)
            document.entities = entities
            document.relationships = relationships
            
            return document
            
        except Exception as e:
            logger.error(f"处理PDF文件失败 {file_path}: {e}")
            return None
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF提取文本"""
        try:
            # 首先尝试使用pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            # 如果pdfplumber提取失败，尝试OCR
            if not text.strip():
                logger.info(f"使用OCR处理文件: {file_path}")
                images = convert_from_path(file_path)
                text = ""
                for image in images:
                    text += pytesseract.image_to_string(image, lang='eng') + "\n"
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"提取PDF文本失败 {file_path}: {e}")
            return ""
    
    def _extract_entities_and_relationships(self, content: str) -> tuple[List[Entity], List[Relationship]]:
        """从文本中提取实体和关系"""
        entities = []
        relationships = []
        
        try:
            # 使用LLM提取实体和关系
            llm_response = self._call_llm_for_extraction(content)
            if not llm_response:
                return entities, relationships
            
            # 解析LLM响应
            entities, relationships = self._parse_llm_response(llm_response)
            
            # 为实体生成嵌入向量
            for entity in entities:
                if entity.entity_type not in self.excluded_types:
                    entity.embedding = embedding_manager.generate_embedding(entity.name)
                    entity.namespace = "private_kg"
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"提取实体和关系失败: {e}")
            return entities, relationships
    
    def _call_llm_for_extraction(self, content: str) -> Optional[str]:
        """调用LLM进行实体和关系提取"""
        try:
            import requests
            
            prompt = f"""
            请从以下医疗文档中提取实体和关系，并以JSON格式返回：
            
            文档内容：
            {content}
            
            请提取以下类型的实体：
            - Patient: 患者信息
            - Clinician: 临床医生
            - Disease: 疾病
            - Symptom: 症状
            - Treatment: 治疗方案
            - Anatomy: 解剖结构
            - Procedure: 医疗程序
            
            关系类型：
            - HAS_SYMPTOM: 患者有症状
            - DIAGNOSED_WITH: 诊断为疾病
            - TREATED_WITH: 接受治疗
            - LOCATED_IN: 位于解剖结构
            - PERFORMED: 执行程序
            
            返回格式：
            {{
                "entities": [
                    {{"name": "实体名称", "entity_type": "实体类型", "properties": {{"key": "value"}}}}
                ],
                "relationships": [
                    {{"source": "源实体名称", "target": "目标实体名称", "relationship_type": "关系类型"}}
                ]
            }}
            """
            
            response = requests.post(
                settings.OLLAMA_URL,
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                logger.error(f"LLM调用失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"调用LLM失败: {e}")
            return None
    
    def _parse_llm_response(self, response: str) -> tuple[List[Entity], List[Relationship]]:
        """解析LLM响应"""
        entities = []
        relationships = []
        
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return entities, relationships
            
            data = json.loads(json_match.group())
            
            # 解析实体
            for entity_data in data.get("entities", []):
                entity = Entity(
                    name=entity_data.get("name", ""),
                    entity_type=entity_data.get("entity_type", ""),
                    properties=entity_data.get("properties", {}),
                    namespace="private_kg"
                )
                entities.append(entity)
            
            # 解析关系
            for rel_data in data.get("relationships", []):
                # 查找源实体和目标实体
                source_entity = next((e for e in entities if e.name == rel_data.get("source")), None)
                target_entity = next((e for e in entities if e.name == rel_data.get("target")), None)
                
                if source_entity and target_entity:
                    relationship = Relationship(
                        source_id=source_entity.id,
                        target_id=target_entity.id,
                        relationship_type=rel_data.get("relationship_type", ""),
                        namespace="private_kg"
                    )
                    relationships.append(relationship)
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return entities, relationships
    
    def build_kg(self, pdf_dir: str) -> bool:
        """构建私有知识图谱"""
        try:
            logger.info("开始构建私有知识图谱")
            
            # 清除现有数据
            db_manager.clear_namespace("private_kg")
            
            # 处理文档
            documents = self.process_documents(pdf_dir)
            logger.info(f"处理了 {len(documents)} 个文档")
            
            # 保存到数据库
            total_entities = 0
            total_relationships = 0
            
            for document in documents:
                # 保存实体
                for entity in document.entities:
                    if db_manager.create_entity(entity):
                        total_entities += 1
                
                # 保存关系
                for relationship in document.relationships:
                    if db_manager.create_relationship(relationship):
                        total_relationships += 1
            
            logger.info(f"知识图谱构建完成: {total_entities} 个实体, {total_relationships} 个关系")
            return True
            
        except Exception as e:
            logger.error(f"构建知识图谱失败: {e}")
            return False