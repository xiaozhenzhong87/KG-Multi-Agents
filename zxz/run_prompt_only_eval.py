#!/usr/bin/env python3
"""Prompt-only MedQA evaluation for ablation experiments."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:  # pragma: no cover - environment bootstrap
    sys.path.append(str(ROOT_DIR))

from src.utils.model_client import ModelClient

LOGGER = logging.getLogger("prompt_eval")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def format_options(options: Dict[str, str]) -> str:
    if not options:
        return "(no options provided)"
    return "\n".join(f"{key}. {value}" for key, value in sorted(options.items()))


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


PROMPT_INSTRUCTIONS = """You are an experienced medical board-style QA analyst.
Read the multiple-choice question and think critically.

Requirements:
1. Reason through the clinical facts before selecting an option.
2. Always choose the single best option, even if unsure (provide best guess).
3. Return JSON only, following the schema below.

JSON schema:
{{
  "status": "ANSWER",
  "reasoning": "Step-by-step justification in plain text.",
  "answer": {{"option": "A", "text": "Option text", "confidence": 0.0}}
}}

Confidence should be between 0 and 1.
"""


def build_user_prompt(question: str, options: Dict[str, str], meta: Optional[str] = None) -> str:
    meta_block = f"\nContext: {meta}" if meta else ""
    return f"""Question:{meta_block}
{question}

Options:
{format_options(options)}
"""


def safe_extract_answer(
    response: Dict[str, Any],
    options: Dict[str, str],
) -> Dict[str, Any]:
    status = (response.get("status") or "").upper()
    reasoning = response.get("reasoning")
    answer = response.get("answer") or {}
    option = answer.get("option")
    text = answer.get("text") or (options.get(option) if option else None)
    confidence = answer.get("confidence")

    if status != "ANSWER":
        raise ValueError(f"Model did not return ANSWER status: {status}")
    if option not in options:
        raise ValueError(f"Model returned invalid option '{option}'")

    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0

    return {
        "status": status,
        "reasoning": reasoning or "",
        "answer": {
            "option": option,
            "text": text or options[option],
            "confidence": max(0.0, min(confidence_val, 1.0)),
        },
    }


class PromptOnlyEvaluator:
    def __init__(
        self,
        client: ModelClient,
        temperature: float = 0.0,
        max_output_tokens: int = 900,
    ) -> None:
        self.client = client
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def evaluate_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        question = record.get("question", "")
        options = record.get("options", {}) or {}
        meta = record.get("meta_info")

        user_prompt = build_user_prompt(question, options, meta)
        system_prompt = PROMPT_INSTRUCTIONS

        result: Dict[str, Any] = {
            "question": question,
            "options": options,
            "ground_truth": record.get("answer"),
            "answer_idx": record.get("answer_idx"),
            "meta_info": meta,
            "raw_response": None,
            "parsed": None,
            "status": "ERROR",
            "prediction": None,
            "is_correct": None,
            "error": None,
        }

        try:
            raw_response = self.client.run_json_prompt(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
            result["raw_response"] = raw_response
            parsed = safe_extract_answer(raw_response, options)
            result["parsed"] = parsed
            result["status"] = parsed["status"]
            prediction = parsed["answer"]["option"]
            result["prediction"] = prediction
            if record.get("answer_idx"):
                result["is_correct"] = prediction == record["answer_idx"]
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to evaluate question: %s", exc)
            result["error"] = str(exc)

        return result


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
        default=ROOT_DIR / "zxz/prompt_results",
        help="Directory to store evaluation logs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on the number of questions.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the model.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=900,
        help="Maximum tokens for model response.",
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

    client = ModelClient()
    evaluator = PromptOnlyEvaluator(
        client=client,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"prompt_eval_{timestamp}.jsonl"

    answered = 0
    total = len(dataset)

    with output_path.open("w", encoding="utf-8") as handle:
        for idx, record in enumerate(dataset, start=1):
            LOGGER.info("Evaluating question %s/%s", idx, total)
            result = evaluator.evaluate_record(record)
            if result.get("is_correct") is True:
                answered += 1
            handle.write(json.dumps(result, ensure_ascii=True) + "\n")

    accuracy = (answered / total * 100) if total else 0.0
    LOGGER.info(
        "Prompt-only evaluation finished | %s/%s correct (%.2f%%) | Output: %s",
        answered,
        total,
        accuracy,
        output_path,
    )


if __name__ == "__main__":
    main()


