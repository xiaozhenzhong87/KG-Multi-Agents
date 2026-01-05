"""
配置设置
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings  # 使用新版本

class Settings(BaseSettings):
    """应用配置"""
    
    # 项目基础配置
    PROJECT_NAME: str = "Healthcare Modeling"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # 数据库配置
    NEO4J_URI: str = "bolt://localhost:7688"  # 使用新的端口7688
    NEO4J_USER: str = "neo4j"  # 统一使用NEO4J_USER
    NEO4J_PASSWORD: str = "12345678"  # 使用新的密码
    
    # Ollama配置
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "llama3.1:8b-instruct-fp16"
    # OLLAMA_MODEL: str = "gemma3:27b"
    
    # LLM/DeepSeek API配置（可通过环境变量覆盖）
    # LLM_PROVIDER: str = "siliconflow"  # 标识当前使用的LLM服务商
    LLM_PROVIDER: str = "ollama"  # 标识当前使用的LLM服务商，设置为"ollama"使用Ollama，设置为其他值使用OpenAI兼容API
    LLM_API_KEY: Optional[str] = "sk-cenriggjfnjesxtbfokbnmefixldctjoevwmhhjkqixehqxk"  # 推荐通过环境变量 LLM_API_KEY 设置
    LLM_BASE_URL: Optional[str] = "https://api.siliconflow.cn/v1"  # 推荐通过环境变量 LLM_BASE_URL 设置
    LLM_MODEL: Optional[str] = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"  # 推荐通过环境变量 LLM_MODEL 设置

    # 向后兼容的DeepSeek专用字段（如未提供通用字段，将回退到这些值）
    DEEPSEEK_API_KEY: Optional[str] = "sk-ef9dba25a3334335ab43ad4daf923bdb"
    DEEPSEEK_BASE_URL: Optional[str] = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 数据路径配置
    PDF_DIR: str = "/home/ymkj/zxz/OrthoGraphRAG/zxz/clinic-letter-data/test/"
    # UMLS_DATA_DIR: str = "/home/ymkj/zxz-new/OrthoGraphRAG/zxz/nodes-and-edges/v1-UMLS/concat-batch/processed/"
    # UMLS_DATA_DIR: str = "/home/ymkj/zxz-new/OrthoGraphRAG/zxz/nodes-and-edges/v1-UMLS/comprehensive/"
    UMLS_DATA_DIR: str = "/home/inspur/zxz/orthographrag/data/v4-UMLS/no_self_loops/"
    SRDEF_PATH: str = "/home/inspur/zxz/orthographrag/data/UMLS/2025AA-full-extracted/2025AA/NET/SRDEF"
    
    # 嵌入配置
    EMBEDDING_MODEL: str = "/home/inspur/zxz/models/SapBERT-from-PubMedBERT-fulltext"
    EMBEDDING_DIMENSION: int = 768
    
    # 检索配置
    MAX_MEDICAL_CONCEPTS: int = 20
    MAX_GENERAL_ENTITIES: int = 20
    MAX_RELATIONSHIPS: int = 20
    MAX_PARTIAL_NAME_RESULTS: int = 20
    MAX_GENERAL_ENTITY_RESULTS: int = 20
    MAX_CROSS_GRAPH_CONCEPTS: int = 50
    CROSS_GRAPH_SIMILARITY_THRESHOLD: float = 0.5
    
    # 新增：原项目的配置参数（保留但不使用）
    PRIVATE_GRAPH_MAX_DEPTH: int = 5
    PRIVATE_GRAPH_MAX_ENTITIES: int = 50
    UMLS_GRAPH_MAX_DEPTH: int = 3
    UMLS_GRAPH_MAX_CONCEPTS: int = 50
    
    # PageRank检索配置
    PAGERANK_DAMPING_FACTOR: float = 0.85  # PageRank阻尼系数
    PAGERANK_MAX_ITERATIONS: int = 20  # 最大迭代次数
    PAGERANK_TOLERANCE: float = 1e-6  # 收敛容差
    PAGERANK_MAX_RESULTS: int = 50  # 最大返回结果数，原定50
    PAGERANK_USE_GDS: bool = False  # 是否使用GDS库（如果可用）
    
    # PageRank和Personalized PageRank开关
    USE_PERSONALIZED_PAGERANK: bool = True  # 是否使用Personalized PageRank (PPR)，False则使用标准PageRank (PR)
    USE_PAGERANK_RETRIEVAL: bool = True  # 是否启用PageRank检索（包括PPR和PR）
    
    # 知识图谱检索开关（用于评估和正常RAG）
    ENABLE_KNOWLEDGE_GRAPH_RETRIEVAL: bool = False  # 是否启用知识图谱检索（True=启用，False=禁用）。当禁用时，将跳过PageRank检索步骤，仅使用LLM提取的实体进行后续处理
    
    # 子图构建配置
    PAGERANK_ENABLE_SUBGRAPH_LIMIT: bool = True  # 是否启用子图限制（True=启用限制，False=不限制）
    PAGERANK_SUBGRAPH_MAX_DEPTH: int = 2  # 子图最大深度（跳数），默认2跳（原为3跳），仅在启用限制时生效
    PAGERANK_SUBGRAPH_MAX_NODES_PER_LEVEL: int = 1000  # 每层最大节点数，避免图过大，仅在启用限制时生效，原定1000
    PAGERANK_SUBGRAPH_MAX_TOTAL_NODES: int = 5000  # 子图最大总节点数，仅在启用限制时生效，原定5000
    
    # 初始节点查找配置
    PAGERANK_INITIAL_NODES_PER_ENTITY: int = 5  # 每个实体最多匹配的节点数
    PAGERANK_INITIAL_NODES_MAX_TOTAL: int = 15  # 初始节点总数上限（原为无限制）
    PAGERANK_USE_QUERY_FALLBACK: bool = True  # 如果通过实体找到的节点太少，是否使用原始query作为补充
    
    # 查询配置（在config中可以配置query）
    # QUERY: Optional[str] = "I have hypertension and lately have [symptoms, e.g., headaches/dizziness]. What should I do? Do I need urgent care?"  # 默认查询（可通过环境变量或配置文件设置）
    QUERY: Optional[str] = "A 21-year-old man comes to the physician because of pruritus and a hypopigmented rash on his upper body for 5 days. He first noticed the symptoms after returning from a business trip last week in the Bahamas. While he was there, he visited a couple of beaches and went hiking with some coworkers. The rash initially started as a single lesion on his upper back but since then has extended to his shoulders. He has a history of type 1 diabetes mellitus controlled with an insulin pump. He works as an office manager and has no known exposure to melanocytotoxic chemicals. He has been sexually active with three female partners over the past year and uses condoms inconsistently. He is 183 cm (6 ft) tall and weighs 80 kg (176 lb); BMI is 23.9 kg/m2. His temperature is 37.2°C (99°F), pulse is 78/min, and blood pressure is 130/84 mm Hg. A photograph of the rash is shown. One month ago, his hemoglobin A1C was 7.8%. Which of the following is most likely to confirm the diagnosis?\n options:A: Wood lamp examination, B: Skin culture, C: Potassium hydroxide preparation, D: Skin biopsy, E: Antinuclear antibody testing"
    # UMLS_ENABLED_RELATIONSHIPS: List[str] = [
    #     "is_a", "part_of", "causes", "indicates", "manifestation_of",
    #     "is_broader_than", "is_narrower_than", "is_child_of", "is_parent_of",
    #     "location_of", "occurs_in", "produces", "brings_about", "result_of"
    # ]
    UMLS_ENABLED_RELATIONSHIPS: List[str] = [
        "refers_to", "manifestation_of", "causes", "result_of", "associated_with", "has_quantified_form", "was_a",
        "produces", "location_of", "associated_with", " has_conceptual_part", "is_a", "part_of", "property_of", "form_of"
    ]
    UMLS_RELATIONSHIP_FILTER_ENABLED: bool = False
    
    # 节点类型和关系类型分析配置
    ENABLE_TYPE_ANALYSIS: bool = True  # 是否启用LLM分析节点类型和关系类型
    QUERY_REWRITE_PROMPT_CONFIG: str = "src/retrieval/prompts/query_rewrite_prompt.yaml"  # Query改写的prompt配置文件路径
    TYPE_ANALYSIS_PROMPT_CONFIG: str = "src/retrieval/prompts/type_analysis_prompt.yaml"  # 类型分析的prompt配置文件路径
    
    # UMLS实体类型过滤配置
    UMLS_ENABLED_ENTITY_TYPES: List[str] = [
        "T047",  # Disease or Syndrome
        "T048",  # Mental or Behavioral Dysfunction
        "T049",  # Cell or Molecular Dysfunction
        "T019",  # Congenital Abnormality
        "T020",  # Acquired Abnormality
        "T033",  # Finding
        "T184",  # Sign or Symptom
        "T037",  # Injury or Poisoning
        "T046",  # Pathologic Function
        "T191",  # Neoplastic Process
        "T121",  # Pharmacologic Substance
        "T109",  # Organic Chemical
        "T103",  # Chemical
        "T125",  # Hormone
        "T126",  # Enzyme
        "T127",  # Vitamin
        "T129",  # Immunologic Factor
        "T130",  # Indicator, Reagent, or Diagnostic Aid
        "T131",  # Hazardous or Poisonous Substance
        "T007",  # Bacterium
        "T002",  # Plant
        "T004",  # Fungus
        "T005",  # Virus
        "T001",  # Organism
        "T017",  # Anatomical Structure
        "T023",  # Body Part, Organ, or Organ Component
        "T024",  # Tissue
        "T025",  # Cell
        "T026",  # Cell Component
        "T018",  # Embryonic Structure
        "T022",  # Body System
        "T021",  # Body Region
        "T031",  # Body Substance
        "T060",  # Diagnostic Procedure
        "T061",  # Therapeutic or Preventive Procedure
        "T062",  # Research Activity
        "T063",  # Molecular Biology Research Technique
        "T064",  # Laboratory Procedure
        "T065",  # Educational Activity
        "T066",  # Governmental or Regulatory Activity
        "T067",  # Health Care Activity
        "T068",  # Individual Behavior
        "T069",  # Social Behavior
        "T070",  # Human-caused Phenomenon or Process
        "T071",  # Entity
        "T072",  # Physical Object
        "T073",  # Manufactured Object
        "T074",  # Medical Device
        "T075",  # Research Device
        "T076",  # Conceptual Entity
        "T077",  # Intellectual Product
        "T078",  # Mental Process
        "T079",  # Temporal Concept
        "T080",  # Qualitative Concept
        "T081",  # Quantitative Concept
        "T082",  # Spatial Concept
        "T083",  # Geographic Area
        "T084",  # Group
        "T085",  # Group Attribute
        "T086",  # Population Group
        "T087",  # Professional or Occupational Group
        "T088",  # Family Group
        "T089",  # Age Group
        "T090",  # Patient or Disabled Group
        "T091",  # Professional Society
        "T092",  # Organization"
    ]
    UMLS_ENTITY_TYPE_FILTER_ENABLED: bool = False
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = None
    
    @property
    def resolved_llm_api_key(self) -> Optional[str]:
        """返回当前生效的LLM API Key"""
        return self.LLM_API_KEY or self.DEEPSEEK_API_KEY

    @property
    def resolved_llm_base_url(self) -> Optional[str]:
        """返回当前生效的LLM Base URL"""
        return self.LLM_BASE_URL or self.DEEPSEEK_BASE_URL

    @property
    def resolved_llm_model(self) -> Optional[str]:
        """返回当前生效的LLM模型名称"""
        return self.LLM_MODEL or self.DEEPSEEK_MODEL

    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局设置实例
settings = Settings()