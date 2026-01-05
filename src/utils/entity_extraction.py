"""Utility helpers to extract medical entities with an LLM client."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .model_client import ModelClient

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a biomedical entity extraction assistant. Given a clinical question,
identify up to {max_entities} salient medical concepts (symptoms, diseases, labs,
and treatments). Return the result strictly as JSON."""

_USER_PROMPT_TEMPLATE = (
    "Extract up to {max_entities} distinct medical entities mentioned in the question.\n"
    "Provide the answer in the following JSON schema:\n"
        "{{\n"
        "  \"entities\": [\n"
        "    {{\n"
        "      \"name\": string,\n"
        "      \"type\": string (Disease or Syndrome|Laboratory or Test Result|Clinical Drug|Individual Behavior|other),\n"
        "      \"confidence\": number between 0 and 1,\n"
        "      \"evidence\": short phrase from the question\n"
        "    }}\n"
        "  ]\n"
        "}}\n\n"
    "Question: {question}\n"
    "Remember: respond with JSON only."
)


def _normalize_confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, score))


def _normalize_type(value: Any) -> str:
    if not value:
        return "other"
    text = str(value).strip().lower()
    if not text:
        return "other"
    return text


def _to_entity(entry: Dict[str, Any]) -> Dict[str, Any] | None:
    name = str(entry.get("name") or entry.get("entity") or "").strip()
    if not name:
        return None

    return {
        "name": name,
        "type": _normalize_type(entry.get("type") or entry.get("category")),
        "confidence": _normalize_confidence(entry.get("confidence")),
        "evidence": str(entry.get("evidence") or entry.get("source") or "").strip(),
    }


def extract_medical_entities(
    client: ModelClient,
    question: str,
    max_entities: int = 6,
    max_output_tokens: int = 512,
) -> List[Dict[str, Any]]:
    """Call the configured LLM to extract structured medical entities."""

    if not question.strip():
        return []

    system_prompt = _SYSTEM_PROMPT.format(max_entities=max_entities)
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        max_entities=max_entities,
        question=question.strip(),
    )

    try:
        raw = client.run_json_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Entity extraction failed: %s", exc)
        return []

    if isinstance(raw, dict):
        candidates = raw.get("entities") or raw.get("items") or []
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = []

    entities: List[Dict[str, Any]] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        normalized = _to_entity(entry)
        if normalized:
            entities.append(normalized)

    return entities
