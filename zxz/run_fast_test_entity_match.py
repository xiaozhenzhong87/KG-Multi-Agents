#!/usr/bin/env python3
"""Run oracle-style entity coverage analysis for the MedQA fast test."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:  # pragma: no cover - path setup
	sys.path.append(str(ROOT_DIR))

from src.core.database import Neo4jManager
from src.utils.deepseek_client import DeepseekClient
from src.utils.entity_extraction import extract_medical_entities
from src.utils.graph_tools import GraphEntityMatcher

LOGGER = logging.getLogger("oracle_coverage")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
	records: List[Dict[str, Any]] = []
	with path.open("r", encoding="utf-8") as handle:
		for line in handle:
			if line.strip():
				records.append(json.loads(line))
	return records


def process_question(
	client: DeepseekClient,
	matcher: GraphEntityMatcher,
	question_record: Dict[str, Any],
) -> Dict[str, Any]:
	question = question_record.get("question", "")
	entities = extract_medical_entities(client, question)

	match_summaries = []
	for entity in entities:
		match = matcher.match_entity(entity["name"])
		match_summaries.append(
			{
				"entity": entity,
				"matched": match.matched,
				"matched_nodes": match.matches,
			}
		)

	total = len(entities)
	matched = sum(1 for summary in match_summaries if summary["matched"])
	coverage = {
		"total_entities": total,
		"matched_entities": matched,
		"coverage_ratio": round(matched / total, 4) if total else None,
	}

	return {
		"question": question,
		"meta": {
			key: question_record.get(key)
			for key in ("answer", "options", "meta_info", "answer_idx")
		},
		"extracted_entities": entities,
		"match_results": match_summaries,
		"coverage": coverage,
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
		help="Directory where JSONL results will be stored.",
	)
	parser.add_argument(
		"--limit",
		type=int,
		default=None,
		help="Optional limit on the number of questions to process.",
	)
	parser.add_argument(
		"--max-candidates",
		type=int,
		default=5,
		help="Maximum number of matched KG nodes recorded per entity.",
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
	matcher = GraphEntityMatcher(
		neo_manager,
		namespace="umls_kg",
		max_candidates=args.max_candidates,
	)

	timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
	output_dir = args.output_dir
	output_dir.mkdir(parents=True, exist_ok=True)
	output_path = output_dir / f"fast_test_medqa_match_{timestamp}.jsonl"

	overall_matches = 0
	overall_entities = 0

	with output_path.open("w", encoding="utf-8") as handle:
		for idx, record in enumerate(dataset, start=1):
			LOGGER.info("Processing question %s/%s", idx, len(dataset))
			processed = process_question(client, matcher, record)
			handle.write(json.dumps(processed, ensure_ascii=True) + "\n")

			coverage = processed["coverage"]
			overall_matches += coverage.get("matched_entities") or 0
			overall_entities += coverage.get("total_entities") or 0

	LOGGER.info("Results written to %s", output_path)
	if overall_entities:
		LOGGER.info(
			"Aggregate coverage: %.2f%% (%s/%s entities)",
			(overall_matches / overall_entities) * 100,
			overall_matches,
			overall_entities,
		)
	else:
		LOGGER.warning("No entities were extracted; coverage cannot be computed.")


if __name__ == "__main__":
	main()

