
#!/usr/bin/env python3
"""
针对 fast_test_medqa_20.jsonl 的实体提取与UMLS图谱比对脚本。

功能：
1. 读取评测集问题；
2. 调用 DeepSeek 模型抽取医学实体；
3. 将实体与 UMLS Neo4j 图谱中的节点比对；
4. 以 JSONL 形式输出覆盖率与匹配详情。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
sys.path.append(str(PROJECT_ROOT))

from src.config.settings import settings  # noqa: E402
from src.core.database import Neo4jManager  # noqa: E402


LOGGER = logging.getLogger("fast_test_entity_match")


SYSTEM_PROMPT = (
    "You are a medical NLP assistant. Extract clinically relevant entities from the "
    "given board-style multiple choice question. Focus on diagnoses, findings, "
    "symptoms, labs, treatments, patient descriptors, anatomy, and risk factors. "
    "Return a strict JSON object with the schema:\n"
    "{\n"
    '  "entities": [\n'
    '    {\n'
    '      "name": "<short canonical entity text>",\n'
    '      "type": "<coarse category>",\n'
    '      "evidence": "<supporting span or rationale>",\n'
    '      "confidence": <float between 0 and 1>\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Always include at least the key diagnosis concepts mentioned in the question."
)


@dataclass
class EntityExtraction:
    name: str
    type: str
    evidence: str
    confidence: float


@dataclass
class EntityMatchResult:
    entity: EntityExtraction
    matched: bool
    matches: List[Dict[str, Any]]


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def load_questions(jsonl_path: Path) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            questions.append(json.loads(line))
    LOGGER.info("读取题目数量: %d", len(questions))
    return questions


def build_completion_payload(question: str, model: str) -> Dict[str, Any]:
    user_prompt = (
        "Extract structured medical entities from the following question. "
        "Only respond with JSON.\n\n"
        f"Question:\n{question}"
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "response_format": {"type": "json_object"},
    }


def call_deepseek(question: str, retries: int = 3, backoff: float = 2.0) -> Dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "vImU74dwxL2352vLOZnR60cJBwkJz0heZE8BAFZbjJ8vO46y2HnOjh_lPuv5T7nf_sX4gEpNoaJPHRAZ2bSj1Q")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.modelarts-maas.com/v1")
    model = os.getenv("DEEPSEEK_MODEL", os.getenv("MODEL", "Deepseek-V3"))
    endpoint = os.getenv("DEEPSEEK_COMPLETIONS_ENDPOINT", "/chat/completions")

    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量，无法调用模型。")

    url = base_url.rstrip("/") + endpoint
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_completion_payload(question, model)

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"调用 DeepSeek 失败: HTTP {response.status_code} - {response.text}"
                )
            data = response.json()
            content = extract_message_content(data)
            return json.loads(content)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            LOGGER.warning("调用 DeepSeek 失败 (第 %d 次): %s", attempt, exc)
            if attempt == retries:
                raise
            time.sleep(backoff * attempt)
    raise RuntimeError("DeepSeek 调用失败且超过最大重试次数。")


def extract_message_content(response_json: Dict[str, Any]) -> str:
    """
    通用地解析 OpenAI/DeepSeek 风格的响应，返回 message content。
    """
    if "choices" in response_json:
        messages = response_json["choices"]
        if messages:
            content = messages[0].get("message", {}).get("content")
            if content:
                return strip_code_fence(content)
    # 兼容其他返回格式
    if "output" in response_json:
        return strip_code_fence(response_json["output"])
    raise ValueError(f"无法解析模型返回: {response_json}")


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # 移除第一行 ```json / ``` 等
        if lines:
            lines = lines[1:]
        # 如果最后一行还是 ``` 则去掉
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def ensure_entities(data: Dict[str, Any]) -> List[EntityExtraction]:
    entities = data.get("entities", [])
    cleaned: List[EntityExtraction] = []
    for item in entities:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        ent = EntityExtraction(
            name=name,
            type=(item.get("type") or "unknown").strip(),
            evidence=(item.get("evidence") or "").strip(),
            confidence=float(item.get("confidence") or 0.0),
        )
        cleaned.append(ent)
    return cleaned


def find_umls_matches(db: Neo4jManager, entity_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    exact_query = """
    MATCH (n:Entity)
    WHERE toLower(n.name) = toLower($name)
    RETURN n.name AS name, n.cui AS cui, n.entity_type AS entity_type, n.namespace AS namespace
    LIMIT $limit
    """
    results = db.execute_query(exact_query, {"name": entity_name, "limit": limit})
    if results:
        return results

    fuzzy_query = """
    MATCH (n:Entity)
    WHERE toLower(n.name) CONTAINS toLower($name) OR toLower($name) CONTAINS toLower(n.name)
    RETURN n.name AS name, n.cui AS cui, n.entity_type AS entity_type, n.namespace AS namespace
    LIMIT $limit
    """
    return db.execute_query(fuzzy_query, {"name": entity_name, "limit": limit})


def process_question(
    question: Dict[str, Any],
    db: Neo4jManager,
) -> Dict[str, Any]:
    question_text = question.get("question", "")
    extraction = call_deepseek(question_text)
    entities = ensure_entities(extraction)

    match_details: List[EntityMatchResult] = []
    for entity in entities:
        matches = find_umls_matches(db, entity.name)
        match_details.append(
            EntityMatchResult(
                entity=entity,
                matched=bool(matches),
                matches=matches,
            )
        )

    total_entities = len(entities)
    matched_entities = sum(1 for item in match_details if item.matched)
    coverage = matched_entities / total_entities if total_entities else 0.0

    return {
        "question": question_text,
        "meta": {k: v for k, v in question.items() if k != "question"},
        "extracted_entities": [asdict(ent) for ent in entities],
        "match_results": [
            {
                "entity": asdict(item.entity),
                "matched": item.matched,
                "matched_nodes": item.matches,
            }
            for item in match_details
        ],
        "coverage": {
            "total_entities": total_entities,
            "matched_entities": matched_entities,
            "coverage_ratio": coverage,
        },
    }


def run_pipeline(input_path: Path, output_dir: Path, limit: Optional[int] = None) -> Path:
    questions = load_questions(input_path)
    if limit:
        questions = questions[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"fast_test_medqa_match_{timestamp}.jsonl"

    db = Neo4jManager()
    db.connect()

    try:
        with output_path.open("w", encoding="utf-8") as out_f:
            for idx, question in enumerate(questions, start=1):
                LOGGER.info("处理题目 %d / %d", idx, len(questions))
                try:
                    result = process_question(question, db)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    LOGGER.error("处理题目失败 (index=%d): %s", idx, exc)
                    result = {
                        "question": question.get("question", ""),
                        "meta": {k: v for k, v in question.items() if k != "question"},
                        "error": str(exc),
                    }
                out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                out_f.flush()
                time.sleep(0.5)  # 轻微节流，避免触发速率限制
    finally:
        db.close()

    LOGGER.info("输出结果: %s", output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="fast_test_medqa 实体覆盖率检查脚本")
    parser.add_argument(
        "--input-file",
        type=Path,
        default=PROJECT_ROOT / "eval_data" / "fast_test_medqa_20.jsonl",
        help="评测集 JSONL 文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CURRENT_DIR / "match_results",
        help="输出结果目录",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅处理前 N 条数据 (调试用)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出调试日志",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    output_path = run_pipeline(args.input_file, args.output_dir, args.limit)
    LOGGER.info("全部处理完成，结果文件: %s", output_path)


if __name__ == "__main__":
    main()

