"""
答案预测器
根据检索结果使用LLM预测答案
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import re

from src.core.models import QueryResult
from src.retrieval.llm_integration import LLMIntegration

logger = logging.getLogger(__name__)


class AnswerPredictor:
    """答案预测器"""
    
    def __init__(self, prompt_file: Optional[str] = None):
        """
        初始化答案预测器
        
        Args:
            prompt_file: Prompt文件路径（如果为None，使用默认路径）
        """
        self.llm_integration = LLMIntegration()
        
        # 加载prompt文件
        if prompt_file is None:
            # 默认路径：evaluation/prompts/answer_prediction_prompt.yaml
            current_dir = Path(__file__).parent
            prompt_file = current_dir / "prompts" / "answer_prediction_prompt.yaml"
        
        self.prompt_file = Path(prompt_file)
        self.prompt_config = self._load_prompt_config()
    
    def _load_prompt_config(self) -> Dict[str, Any]:
        """加载prompt配置文件"""
        if not self.prompt_file.exists():
            logger.warning(f"Prompt文件不存在: {self.prompt_file}，使用默认prompt")
            return {}
        
        try:
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载prompt配置: {self.prompt_file}")
            return config
        except Exception as e:
            logger.error(f"加载prompt配置失败: {e}")
            return {}
    
    def _build_prompt(self, question: str, options: Dict[str, str], structured_context: str) -> str:
        """
        构建用于LLM的prompt
        
        Args:
            question: 问题文本
            options: 选项字典
            structured_context: 结构化上下文（从检索结果构建）
            
        Returns:
            str: 完整的prompt文本
        """
        # 构建选项文本
        options_text = "\n".join([f"{idx}. {text}" for idx, text in options.items()])
        
        # 从配置文件构建prompt
        system_prompt = self.prompt_config.get('system_prompt', '')
        premises = self.prompt_config.get('premises', '')
        core_tasks = self.prompt_config.get('core_tasks', '')
        output_format = self.prompt_config.get('output_format', '')
        data_source = self.prompt_config.get('data_source', '')
        
        # 如果没有配置文件，使用默认prompt
        if not system_prompt:
            system_prompt = """You are a professional physician proficient in clinical case analysis and medical exam question-solving (focusing on Step2&3 logic). Your core task is to analyze the patient's case, deduce the suspected diagnosis, evaluate each option based on clinical evidence, and select the most accurate answer."""
            premises = """- All information is based solely on the provided patient report, structured background, and question context (no external information added).
- Adhere to authoritative clinical guidelines (referenced from UMLS) to match "suspected diagnosis → confirmatory examination" core logic.
- Prioritize practicality: focus on "which examination can directly confirm the disease" rather than irrelevant indicator analysis."""
            core_tasks = """1. Extract key clinical information from the patient's report (symptoms, history, physical signs, exposure factors) and list it concisely.
2. Deduce 1-2 most likely suspected diagnoses based on key information.
3. Analyze each option one by one: explain why it is the correct answer (if applicable) or why it is excluded (clinical rationality, sensitivity/specificity, invasiveness, etc.).
4. Clearly output the final answer (specify option letter + name) and summarize the core reasoning chain."""
            output_format = """Your response must follow this structure:

0. Key Clinical Information Extraction
- List core symptoms, medical history, travel/exposure factors, and critical physical signs (only relevant to the diagnosis).

I. Suspected Diagnosis
- Propose the most likely diagnosis(es) and briefly explain the matching basis with clinical information.

II. Option-by-Option Analysis
- For each option (A-E), write 1-2 sentences explaining:
  - If it is the correct answer: Why it is the gold standard / 首选 confirmatory examination for the suspected diagnosis.
  - If it is an incorrect answer: Why it is not suitable (e.g., low sensitivity, auxiliary only, irrelevant to diagnosis).

III. Final Answer
Explicitly state: "The most likely answer is [Option Letter]: [Option Name]."

IMPORTANT: The final answer must be in the format: "Answer: [A-E]" or "The answer is [A-E]"

IV. Core Reasoning Chain Summary
Connect "clinical information → suspected diagnosis → confirmatory examination (correct option)" in a logical line."""
            data_source = """The analysis references the Unified Medical Language System (UMLS), a comprehensive and authoritative biomedical terminology database developed by the U.S. National Library of Medicine. UMLS integrates various health and biomedical vocabularies and standards to enable interoperability between computer systems and support advanced medical data analysis."""
        
        prompt = f"""{system_prompt}

**Premises:**
{premises}

**Core Tasks:**
{core_tasks}

**Structured Background Information:**
{structured_context}

**Question:**
{question}

**Options:**
{options_text}

**Output Format:**
{output_format}

**Data Source:**
{data_source}
"""
        return prompt
    
    def _build_structured_context(self, query_result: QueryResult) -> str:
        """
        从检索结果构建结构化上下文
        
        Args:
            query_result: 检索结果
            
        Returns:
            str: 结构化的上下文文本
        """
        context_parts = []
        
        # 添加实体信息
        if query_result.entities:
            context_parts.append("**Entities (Retrieved):**")
            for entity in query_result.entities[:30]:  # 限制数量
                entity_info = f"- {entity.name}"
                if hasattr(entity, 'entity_type') and entity.entity_type:
                    entity_info += f" (Type: {entity.entity_type})"
                context_parts.append(entity_info)
        
        # 添加关系信息
        if query_result.relationships:
            context_parts.append("\n**Relationships (Retrieved):**")
            for rel in query_result.relationships[:30]:  # 限制数量
                source_name = rel.source if isinstance(rel.source, str) else getattr(rel.source_entity, 'name', str(rel.source))
                target_name = rel.target if isinstance(rel.target, str) else getattr(rel.target_entity, 'name', str(rel.target))
                rel_info = f"- {source_name} --[{rel.relationship_type}]--> {target_name}"
                context_parts.append(rel_info)
        
        # 添加推理链（如果有）
        if query_result.reasoning_chain:
            context_parts.append("\n**Reasoning Chain (from retrieval):**")
            context_parts.append(query_result.reasoning_chain)
        
        return "\n".join(context_parts) if context_parts else "No additional context available."
    
    def _extract_answer_from_llm_response(self, llm_response: str, options: Dict[str, str]) -> Dict[str, Any]:
        """
        从LLM响应中提取答案
        
        Args:
            llm_response: LLM的响应文本
            options: 选项字典
            
        Returns:
            Dict: 包含answer_idx, answer, confidence的字典
        """
        if not llm_response:
            return {
                'answer': '',
                'answer_idx': '',
                'confidence': 0.0,
                'llm_response': llm_response
            }
        
        # 从配置文件中获取答案提取模式
        answer_patterns_config = self.prompt_config.get('answer_extraction_patterns', [])
        
        # 构建模式列表
        answer_patterns = []
        if answer_patterns_config:
            for pattern_config in answer_patterns_config:
                pattern = pattern_config.get('pattern', '')
                if pattern:
                    answer_patterns.append(pattern)
        
        # 如果没有配置文件，使用默认模式
        if not answer_patterns:
            answer_patterns = [
                r'(?:答案|Answer|The answer|The most likely answer)[是:：]?\s*([A-E])',
                r'(?:选择|Select|Option)\s*([A-E])',
                r'^([A-E])\s*[.:：]',  # 单独一行开头的A-E
                r'\b([A-E])\b\s*[是最佳选择|是正确答案|is the correct answer]',
                r'Final Answer[:\s]*([A-E])',
                r'III\.\s*Final Answer[:\s]*([A-E])',
            ]
        
        answer_idx = None
        for pattern in answer_patterns:
            matches = re.findall(pattern, llm_response, re.IGNORECASE | re.MULTILINE)
            if matches:
                answer_idx = matches[-1].upper()  # 使用最后一个匹配
                if answer_idx in options:
                    break
        
        # 如果没找到，尝试从选项名称中匹配
        if not answer_idx:
            for idx, option_text in options.items():
                # 检查选项文本是否在响应的最后部分出现
                if option_text in llm_response[-500:]:  # 检查最后500字符
                    # 检查是否有明确的答案指示
                    if re.search(rf'(?:答案|Answer|选择|Select).*{re.escape(idx)}', llm_response[-500:], re.IGNORECASE):
                        answer_idx = idx
                        break
        
        # 如果找到答案
        if answer_idx and answer_idx in options:
            return {
                'answer': options[answer_idx],
                'answer_idx': answer_idx,
                'confidence': 0.8,  # LLM预测的置信度
                'llm_response': llm_response,
                'method': 'llm_prediction'
            }
        
        # 如果没找到，返回空答案
        return {
            'answer': '',
            'answer_idx': '',
            'confidence': 0.0,
            'llm_response': llm_response,
            'method': 'llm_prediction',
            'warning': '无法从LLM响应中提取答案'
        }
    
    def predict_answer(self, 
                      question: str,
                      options: Dict[str, str],
                      query_result: QueryResult) -> Dict[str, Any]:
        """
        根据检索结果使用LLM预测答案
        
        Args:
            question: 问题文本
            options: 选项字典（如 {"A": "选项1", "B": "选项2", ...}）
            query_result: 检索结果
            
        Returns:
            Dict: 预测结果，包含 answer, answer_idx, confidence, llm_response
        """
        if not options:
            logger.warning("没有选项，无法预测答案")
            return {
                'answer': '',
                'answer_idx': '',
                'confidence': 0.0,
                'error': 'No options provided'
            }
        
        try:
            # 构建结构化上下文
            structured_context = self._build_structured_context(query_result)
            
            # 构建prompt
            prompt = self._build_prompt(question, options, structured_context)
            
            # 调用LLM
            logger.info("调用LLM进行答案预测...")
            llm_response = self.llm_integration.call_llm(prompt)
            
            if not llm_response:
                logger.warning("LLM返回空响应")
                return {
                    'answer': '',
                    'answer_idx': '',
                    'confidence': 0.0,
                    'llm_response': '',
                    'error': 'LLM returned empty response'
                }
            
            # 从LLM响应中提取答案
            result = self._extract_answer_from_llm_response(llm_response, options)
            result['llm_response'] = llm_response
            
            logger.info(f"LLM预测答案: {result.get('answer_idx', 'N/A')}")
            
            return result
            
        except Exception as e:
            logger.error(f"预测答案时发生错误: {e}", exc_info=True)
            return {
                'answer': '',
                'answer_idx': '',
                'confidence': 0.0,
                'error': str(e)
            }
