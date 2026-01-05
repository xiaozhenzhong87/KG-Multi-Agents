# 创建 src/retrieval/llm_integration.py
"""
LLM集成模块
"""
import logging
import requests
import json
from typing import Optional

from ..config.settings import settings

logger = logging.getLogger(__name__)

class LLMIntegration:
    """LLM集成器"""
    
    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.ollama_model = settings.OLLAMA_MODEL
    
    def generate_response_with_context_v5(self, query: str, structured_context: str) -> str:
        """
        使用LLM和结构化上下文生成响应
        
        Args:
            query (str): 用户问题
            structured_context (str): 结构化的上下文字符串
            
        Returns:
            str: LLM生成的响应
        """
#         prompt = f"""You are a professional physician specializing in the analysis of medical examination reports.

# **Premises:**
# - All information retrieved from the private layer represents authentic and factual reports.
# - Entities and relationships from the public layer constitute authoritative knowledge bases.

# 1. Your task is to comprehensively analyze the report based solely on the provided background information and the user's report;
# 2. You are required to predict potential (undiscovered) disease risks for indicators, including risk alerts [over/under alert, trend change alert], reasoning chain, and comprehensive information;
# 3. Please provide the basis for your judgments and the reasoning chain;
# 4. Use only the available sources of information, and do not add any content that is not included in the background information;
# 5. If an answer cannot be found in the background information or the necessary sources are unavailable, please indicate that this information cannot be obtained from the provided background information or based on the current configuration.

# **Structured Background Information:**
# {structured_context}

# **User Report:**
# {query} 

# **Output Format**
# 0. Overall Analysis of the Patient's Medical/Physical Examination Report  
# - List all the indicators detected in all reports (private layer) and write down the corresponding detection time. 
# - Clearly present the specific numerical changes for each indicator (e.g., the value increased from 12 mm/h on the 12th to 30 mm/h).
# I. Risk Warning for Indicators (over/under alert, trend change alert); describe specific numerical changes for each indicator;
# II. Disease Attribution (reasoning chain)
# III. Prediction of Potential Disease Risks (comprehensive information)
# IV. Basis for Judgments and Reasoning Chain
# V. Final Addition as follows:
# **Disclaimer**: This analysis is based solely on the information provided and should not replace professional medical advice. Please consult a qualified healthcare professional for diagnosis and treatment.

# **Data Source**: The analysis references the Unified Medical Language System (UMLS), a comprehensive and authoritative biomedical terminology database developed by the U.S. National Library of Medicine. UMLS integrates various health and biomedical vocabularies and standards to enable interoperability between computer systems and support advanced medical data analysis.
# """

        prompt = f"""You are a professional physician proficient in clinical case analysis and medical exam question-solving (focusing on Step2&3 logic). Your core task is to analyze the patient’s case, deduce the suspected diagnosis, evaluate each option based on clinical evidence, and select the most accurate answer to confirm the diagnosis.
**Premises**:
- All information is based solely on the provided patient report and structured background (no external information added).
- Adhere to authoritative clinical guidelines (referenced from UMLS) to match "suspected diagnosis → confirmatory examination" core logic.
- Prioritize practicality: focus on "which examination can directly confirm the disease" rather than irrelevant indicator analysis.
**Core Tasks**:
 - Extract key clinical information from the patient’s report (symptoms, history, physical signs, exposure factors) and list it concisely.
 - Deduce 1-2 most likely suspected diagnoses based on key information.
 - Analyze each option one by one: explain why it is the correct answer (if applicable) or why it is excluded (clinical rationality, sensitivity/specificity, invasiveness, etc.).
 - Clearly output the final answer (specify option letter + name) and summarize the core reasoning chain.

**Structured Background Information:**
{structured_context}

**User Report:**
{query} 

**Output Format (Strictly Follow)**:
0. Key Clinical Information Extraction
- List core symptoms, medical history, travel/exposure factors, and critical physical signs (only relevant to the rash/diagnosis).
I. Suspected Diagnosis
- Propose the most likely diagnosis(es) and briefly explain the matching basis with clinical information.
II. Option-by-Option Analysis
- For each option (A-E), write 1-2 sentences explaining:
  - If it is the correct answer: Why it is the gold standard / 首选 confirmatory examination for the suspected diagnosis.
  - If it is an incorrect answer: Why it is not suitable (e.g., low sensitivity, auxiliary only, irrelevant to diagnosis).
III. Final Answer
Explicitly state: "The most likely answer is [Option Letter]: [Option Name]."
IV. Core Reasoning Chain Summary
Connect "clinical information → suspected diagnosis → confirmatory examination (correct option)" in a logical line.
Data Source: The analysis references the Unified Medical Language System (UMLS), a comprehensive and authoritative biomedical terminology database developed by the U.S. National Library of Medicine. UMLS integrates various health and biomedical vocabularies and standards to enable interoperability between computer systems and support advanced medical data analysis.
"""
        logger.info("=" * 80)
        logger.info("发送完整prompt到LLM")
        logger.info("=" * 80)
        logger.info(prompt)
        logger.info("=" * 80)
        logger.info(f"Prompt总长度: {len(prompt)} 字符")
        logger.info(f"结构化上下文长度: {len(structured_context)} 字符")
        logger.info("=" * 80)

        try:
            response = requests.post(self.ollama_url, json={
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            })
            response.raise_for_status()
            llm_response = response.json().get("response", "").strip()
            logging.info("LLM成功生成响应。")
            return llm_response
        except requests.exceptions.RequestException as e:
            logging.error(f"生成过程中联系Ollama API时出错: {e}")
            return f"错误: 由于API连接问题无法生成响应。{e}"
        except json.JSONDecodeError as e:
            logging.error(f"生成过程中解码Ollama API响应时出错: {e}")
            logging.error(f"原始响应文本: {response.text}")
            return f"错误: 由于API解码问题无法生成响应。{e}"
        except Exception as e:
            logging.error(f"LLM生成过程中发生意外错误: {e}")
            return f"错误: 生成响应时发生意外问题。{e}"

    def call_llm(self, prompt: str) -> Optional[str]:
        """
        调用LLM
        
        Args:
            prompt: 提示文本
            
        Returns:
            Optional[str]: LLM响应
        """
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            else:
                logging.error(f"LLM API返回错误状态码: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logging.error("LLM API请求超时")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"LLM API请求失败: {e}")
            return None
        except Exception as e:
            logging.error(f"调用LLM时发生意外错误: {e}")
            return None