#!/usr/bin/env python3
"""Agentic reasoning-chain evaluation over the UMLS knowledge graph."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:  # pragma: no cover - path setup
    sys.path.append(str(ROOT_DIR))

from src.core.database import Neo4jManager
from src.utils.deepseek_client import DeepseekClient
from src.utils.entity_extraction import extract_medical_entities
from src.utils.graph_tools import (
    GraphEntityMatcher,
    SubgraphRetriever,
    format_subgraph_as_text,
)

LOGGER = logging.getLogger("reasoning_eval")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def format_options(options: Dict[str, str]) -> str:
    if not options:
        return "(no options provided)"
    return "\n".join(f"{key}: {value}" for key, value in sorted(options.items()))


def truncate(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def build_agent_payload(
    question: str,
    options: Dict[str, str],
    subgraph_text: str,
    iteration: int,
    previous_requests: List[str],
) -> str:
    option_block = format_options(options)
    needed_block = "\n".join(previous_requests) if previous_requests else "none"

    return f"""
You are an agentic medical QA analyst. Inspect the provided knowledge-graph context and decide
whether you can answer the question.

Context summary:
{subgraph_text}

Step-by-step expectations:
1. Retain only graph elements that are relevant to answering the question.
2. Build a reasoning chain that references node ids or CUIs.
3. If the retained context is sufficient, choose the most likely answer option.
4. If the context is insufficient, list the additional entities/relations you still need.

Question: {question}
Options:\n{option_block}
Iteration: {iteration}
Previously requested entities: {needed_block}

Respond ONLY in JSON with the following schema:
{{
  "status": "ANSWER" | "NEED_MORE_CONTEXT",
  "reasoning_chain": "string",
  "filtered_entities": [{{"node_name": str, "node_id": str | null, "reason": str}}],
  "answer": {{"option": str, "text": str, "confidence": float}} | null,
  "missing_information": ["entity or relation names"]
}}
"""


def parse_agent_response(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {}


class AgenticRAGEvaluator:
    def __init__(
        self,
        client: DeepseekClient,
        matcher: GraphEntityMatcher,
        retriever: SubgraphRetriever,
        max_iterations: int = 3,
    ) -> None:
        self.client = client
        self.matcher = matcher
        self.retriever = retriever
        self.max_iterations = max_iterations

    def evaluate_question(self, record: Dict[str, Any]) -> Dict[str, Any]:
        question = record.get("question", "")
        options = record.get("options", {}) or {}

        entities = extract_medical_entities(self.client, question)
        match_map = self.matcher.batch_match([entity["name"] for entity in entities])

        seed_ids: List[str] = []
        for match in match_map.values():
            for node in match.matches:
                node_id = node.get("id")
                if node_id and node_id not in seed_ids:
                    seed_ids.append(node_id)

        if not seed_ids:
            return {
                "question": question,
                "status": "NO_MATCHING_ENTITIES",
                "entities": entities,
                "agent_trace": [],
                "final_answer": None,
            }

        previous_requests: List[str] = []
        agent_trace: List[Dict[str, Any]] = []
        final_answer: Optional[Dict[str, Any]] = None
        final_status = "INCOMPLETE"

        for iteration in range(1, self.max_iterations + 1):
            subgraph = self.retriever.fetch_subgraph(seed_ids)
            subgraph_text = format_subgraph_as_text(subgraph)
            user_prompt = build_agent_payload(
                question,
                options,
                subgraph_text,
                iteration,
                previous_requests,
            )

            try:
                agent_output = self.client.run_json_prompt(
                    system_prompt="You are a structured reasoning engine.",
                    user_prompt=user_prompt,
                    max_output_tokens=1200,
                )
            except Exception as err:  # noqa: BLE001
                LOGGER.error("Agent iteration failed: %s", err)
                break

            parsed = parse_agent_response(agent_output)
            agent_trace.append(
                {
                    "iteration": iteration,
                    "seed_ids": list(seed_ids),
                    "subgraph_preview": truncate(subgraph_text, 1000),
                    "raw_response": agent_output,
                }
            )

            status = (parsed.get("status") or "").upper()
            if status == "ANSWER":
                final_status = "ANSWERED"
                final_answer = parsed.get("answer")
                agent_trace[-1]["reasoning_chain"] = parsed.get("reasoning_chain")
                agent_trace[-1]["filtered_entities"] = parsed.get("filtered_entities")
                break

            missing_info = parsed.get("missing_information") or []
            needed = [item for item in missing_info if isinstance(item, str)]
            previous_requests = needed

            if not needed:
                final_status = "INSUFFICIENT_CONTEXT"
                break

            matches = self.matcher.batch_match(needed)
            new_ids = []
            for result in matches.values():
                for node in result.matches:
                    node_id = node.get("id")
                    if node_id and node_id not in seed_ids:
                        seed_ids.append(node_id)
                        new_ids.append(node_id)

            if not new_ids:
                final_status = "NO_ADDITIONAL_CONTEXT"
                break

        return {
            "question": question,
            "meta": {
                key: record.get(key)
                for key in ("answer", "options", "meta_info", "answer_idx")
            },
            "entities": entities,
            "initial_seed_ids": seed_ids,
            "agent_trace": agent_trace,
            "final_status": final_status,
            "final_answer": final_answer,
        }


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT_DIR / "eval_data/fast_test_medqa_20.jsonl",
        help="Path to the MedQA JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "zxz/match_results",
        help="Directory where JSONL evaluation logs will be stored.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of questions to process.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum number of agentic refinement iterations.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    dataset = load_jsonl(args.dataset)
    if args.limit:
        dataset = dataset[: args.limit]

    client = DeepseekClient()
    neo_manager = Neo4jManager()
    matcher = GraphEntityMatcher(neo_manager, namespace="umls_kg", max_candidates=5)
    retriever = SubgraphRetriever(neo_manager)
    evaluator = AgenticRAGEvaluator(
        client=client,
        matcher=matcher,
        retriever=retriever,
        max_iterations=args.max_iterations,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"reasoning_chain_eval_{timestamp}.jsonl"

    answered = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for idx, record in enumerate(dataset, start=1):
            LOGGER.info("Evaluating reasoning chain for question %s/%s", idx, len(dataset))
            result = evaluator.evaluate_question(record)
            if result.get("final_status") == "ANSWERED":
                answered += 1
            handle.write(json.dumps(result, ensure_ascii=True) + "\n")

    LOGGER.info(
        "Reasoning logs written to %s | Answered %s/%s (%.2f%%)",
        output_path,
        answered,
        len(dataset),
        (answered / len(dataset) * 100) if dataset else 0,
    )


if __name__ == "__main__":
    main()
