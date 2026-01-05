#!/usr/bin/env python3
"""Agentic reasoning-chain evaluation over the UMLS knowledge graph."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import math
from collections import Counter

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:  # pragma: no cover - path setup
    sys.path.append(str(ROOT_DIR))

from src.core.database import Neo4jManager
from src.core.umls_mapping import get_semantic_type_name
from src.utils.model_client import ModelClient
from src.utils.entity_extraction import extract_medical_entities
from src.utils.graph_tools import (
    GraphEntityMatcher,
    SubgraphRetriever,
)

LOGGER = logging.getLogger("reasoning_eval")

UNLS_FILTERS_PATH = ROOT_DIR / "docs/unls_filters.yaml"
_UNLS_FILTERS_CACHE: Optional[Dict[str, Any]] = None


def load_unls_filters(path: Path = UNLS_FILTERS_PATH) -> Dict[str, Any]:
    """Load UNLS filter/scoring configuration (cached)."""
    global _UNLS_FILTERS_CACHE
    if _UNLS_FILTERS_CACHE is None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                _UNLS_FILTERS_CACHE = yaml.safe_load(handle) or {}
        except FileNotFoundError:
            LOGGER.warning("UNLS filters file not found at %s, using empty config", path)
            _UNLS_FILTERS_CACHE = {}
    return _UNLS_FILTERS_CACHE


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


def _tokenize(text: str) -> List[str]:
    """Very simple tokenizer for similarity scoring."""
    tokens: List[str] = []
    current: List[str] = []
    for ch in text.lower():
        if ch.isalnum():
            current.append(ch)
        else:
            if current:
                token = "".join(current)
                if len(token) >= 3:
                    tokens.append(token)
                current = []
    if current:
        token = "".join(current)
        if len(token) >= 3:
            tokens.append(token)
    return tokens


def jaccard_similarity(a: Sequence[str], b: Sequence[str]) -> float:
    """Compute Jaccard similarity between two token lists."""
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def normalize_relation_type(rel_type: Optional[str], cfg: Dict[str, Any]) -> Optional[str]:
    """Normalize relation direction using inverse_unify map."""
    if not rel_type:
        return None
    mapping = (cfg.get("inverse_unify") or {}) if cfg else {}
    return mapping.get(rel_type, rel_type)


def build_question_type_keys(question: str) -> List[str]:
    """Heuristic question-type detector to enable conditional entity types."""
    q = question.lower()
    keys: List[str] = []
    if any(k in q for k in ["infection", "pathogen", "bacter", "viral", "fungal", "sepsis"]):
        keys.append("INFECTION")
    if any(k in q for k in ["mechanism", "receptor", "enzyme", "gene", "pathway"]):
        keys.append("MECHANISM")
    if any(k in q for k in ["monitoring", "follow-up", "follow up", "nursing", "care plan"]):
        keys.append("WORKFLOW")
    if any(k in q for k in ["age group", "population", "risk group"]):
        keys.append("EPI")
    if any(k in q for k in ["catheter", "stent", "pacemaker", "device"]):
        keys.append("DEVICE")
    return keys


def build_entity_type_policy(
    question: str,
    filters_cfg: Dict[str, Any],
) -> Tuple[set, set, Dict[str, float]]:
    """Build allowed / blacklisted entity-type names and weights.

    Returns:
        (allow_types, blacklist_types, type_weights) where types are semantic-type *names*.
    """
    entity_cfg = filters_cfg.get("entity_types") or {}
    core_allow = set(entity_cfg.get("core_allowlist") or [])
    blacklist = set(entity_cfg.get("blacklist") or [])
    cond_allow_cfg = entity_cfg.get("conditional_allowlist") or {}
    enabled_cond = set(filters_cfg.get("conditional_types_enabled") or [])

    # Enable conditional groups based on both config and question keywords
    q_keys = set(build_question_type_keys(question))
    cond_allowed_types: set = set()
    for key in q_keys:
        if key in enabled_cond and key in cond_allow_cfg:
            cond_allowed_types.update(cond_allow_cfg.get(key) or [])

    allow_types = core_allow | cond_allowed_types
    type_weights = filters_cfg.get("entity_type_weights") or filters_cfg.get("entity_types", {}).get("entity_type_weights") or {}
    # If weights are nested under entity_types, prefer that
    if not isinstance(type_weights, dict):
        type_weights = {}
    return allow_types, blacklist, type_weights  # type: ignore[return-value]


def is_entity_type_allowed(
    entity_type_id: Optional[str],
    allow_types: set,
    blacklist_types: set,
) -> bool:
    """Check if a node's semantic type is allowed based on config.

    entity_type_id is the UMLS semantic type ID (e.g., 'T047'); we map it to a name.
    """
    if not entity_type_id:
        return False
    type_name = get_semantic_type_name(entity_type_id)
    if not type_name:
        return False
    if type_name in blacklist_types:
        return False
    if allow_types and type_name not in allow_types:
        return False
    return True


def compute_node_degrees(subgraph: Dict[str, Any]) -> Counter:
    """Approximate node degrees from the local subgraph."""
    degrees: Counter = Counter()
    for edge in subgraph.get("edges") or []:
        src = (edge.get("source") or {}).get("id")
        dst = (edge.get("target") or {}).get("id")
        if src:
            degrees[src] += 1
        if dst:
            degrees[dst] += 1
    for path in subgraph.get("paths") or []:
        if "sequence" in path:
            path_edges = path.get("sequence") or []
        else:
            path_edges = [path.get("first"), path.get("second")]
        for edge in path_edges:
            if not isinstance(edge, dict):
                continue
            src = (edge.get("source") or {}).get("id")
            dst = (edge.get("target") or {}).get("id")
            if src:
                degrees[src] += 1
            if dst:
                degrees[dst] += 1
    return degrees


def score_edge(
    edge: Dict[str, Any],
    question_tokens: Sequence[str],
    filters_cfg: Dict[str, Any],
    type_policy: Tuple[set, set, Dict[str, float]],
    degrees: Counter,
    relax: bool = False,
) -> Optional[float]:
    """Compute edge score s_edge; return None if filtered out."""
    rel_type_raw = edge.get("type")
    rel_type = normalize_relation_type(rel_type_raw, filters_cfg)
    if not rel_type:
        return None

    hard_exact = set(filters_cfg.get("hard_blacklist_exact") or [])
    hard_prefixes = list(filters_cfg.get("hard_blacklist_prefix") or [])
    if rel_type in hard_exact or any(rel_type.startswith(p) for p in hard_prefixes):
        return None

    relation_whitelist = set(filters_cfg.get("relation_whitelist") or [])
    if relation_whitelist and not relax and rel_type not in relation_whitelist:
        return None

    rel_groups = filters_cfg.get("relation_whitelist_groups") or {}
    w_rel = 0.0
    for group in rel_groups.values():
        if not isinstance(group, dict):
            continue
        weight = float(group.get("weight", 0.0))
        relations = group.get("relations") or []
        if rel_type in relations:
            w_rel = max(w_rel, weight)

    allow_types, blacklist_types, type_weights = type_policy
    allow_types_use = set() if relax else allow_types
    target = edge.get("target") or {}
    target_type_id = target.get("entity_type")
    if not is_entity_type_allowed(target_type_id, allow_types_use, blacklist_types):
        return None

    type_name = get_semantic_type_name(target_type_id) if target_type_id else None
    w_type = float(type_weights.get(type_name, 0.0)) if type_name else 0.0

    alias_map = filters_cfg.get("relation_alias") or {}
    rel_alias = alias_map.get(rel_type, rel_type)
    dst_text = f"{target.get('name') or ''} {rel_alias or ''}"
    dst_tokens = _tokenize(dst_text)
    text_sim = jaccard_similarity(question_tokens, dst_tokens)

    scoring_cfg = filters_cfg.get("scoring") or {}
    lam = float(scoring_cfg.get("text_sim_lambda", 0.5))
    mu = float(scoring_cfg.get("degree_penalty_mu", 0.6))
    tau = float(scoring_cfg.get("type_weight_tau", 0.2))

    dst_id = target.get("id")
    degree = float(degrees.get(dst_id, 0)) if dst_id else 0.0

    s_edge = w_rel + lam * text_sim + tau * w_type - mu * math.log(1.0 + degree)
    min_edge_weight = float(scoring_cfg.get("min_edge_weight", 0.2))
    if relax:
        min_edge_weight = max(0.05, min_edge_weight * 0.75)
    if s_edge < min_edge_weight:
        return None
    return s_edge


def score_and_filter_paths(
    subgraph: Dict[str, Any],
    question: str,
    filters_cfg: Dict[str, Any],
    type_policy: Tuple[set, set, Dict[str, float]],
    relax: bool = False,
    base_threshold: float = 0.6,
) -> Dict[str, Any]:
    """Apply Typed Beam-style scoring to edges/paths and return a filtered subgraph."""
    if not subgraph:
        return {"nodes": [], "edges": [], "paths": []}

    question_tokens = _tokenize(question)
    degrees = compute_node_degrees(subgraph)
    scoring_cfg = filters_cfg.get("scoring") or {}
    path_penalty = float(scoring_cfg.get("path_length_penalty", 0.4))
    path_threshold = base_threshold if not relax else max(0.3, base_threshold - 0.2)

    # Score and filter direct edges (treated as 1-hop paths)
    filtered_edges: List[Dict[str, Any]] = []
    for edge in subgraph.get("edges") or []:
        s_edge = score_edge(edge, question_tokens, filters_cfg, type_policy, degrees, relax=relax)
        if s_edge is None:
            continue
        # 1-hop path score等于该边得分
        if s_edge >= path_threshold:
            edge = dict(edge)
            edge["score"] = s_edge
            filtered_edges.append(edge)

    # Score and filter two-hop paths
    filtered_paths: List[Dict[str, Any]] = []
    for raw_path in subgraph.get("paths") or []:
        if "sequence" in raw_path:
            path_edges = [edge for edge in raw_path.get("sequence", []) if isinstance(edge, dict)]
        else:
            first = raw_path.get("first")
            second = raw_path.get("second")
            path_edges = [edge for edge in (first, second) if isinstance(edge, dict)]
        if len(path_edges) < 2:
            continue

        scored_edges: List[Dict[str, Any]] = []
        s_total = 0.0
        valid = True
        for edge in path_edges:
            s_edge = score_edge(edge, question_tokens, filters_cfg, type_policy, degrees, relax=relax)
            if s_edge is None:
                valid = False
                break
            scored_edge = dict(edge)
            scored_edge["score"] = s_edge
            scored_edges.append(scored_edge)
            s_total += s_edge
        if not valid:
            continue

        s_path = s_total - path_penalty * (len(scored_edges) - 1)
        if s_path < path_threshold:
            continue

        if "sequence" in raw_path or len(scored_edges) > 2:
            filtered_paths.append({"sequence": scored_edges, "score": s_path})
        else:
            filtered_paths.append(
                {"first": scored_edges[0], "second": scored_edges[1], "score": s_path}
            )

    # Rebuild node set from surviving edges/paths
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    for edge in filtered_edges:
        for key in ("source", "target"):
            node = edge.get(key) or {}
            node_id = node.get("id")
            if node_id:
                nodes_by_id[node_id] = node
    for path in filtered_paths:
        if "sequence" in path:
            path_edges = path.get("sequence") or []
        else:
            path_edges = [path.get("first"), path.get("second")]
        for edge in path_edges:
            if not isinstance(edge, dict):
                continue
            for key in ("source", "target"):
                node = edge.get(key) or {}
                node_id = node.get("id")
                if node_id:
                    nodes_by_id[node_id] = node

    return {
        "nodes": list(nodes_by_id.values()),
        "edges": filtered_edges,
        "paths": filtered_paths,
    }


def build_reasoning_chains(subgraph: Dict[str, Any]) -> List[str]:
    """Build reasoning chains from subgraph in format: node1[SemanticType]-(relationship1)->node2[SemanticType]-(relationship2)->node3[SemanticType]
    
    Each node includes its semantic type (not entity, but the actual semantic type) in brackets.
    """
    chains: List[str] = []
    
    def _format_node_ref(node: Dict[str, Any]) -> str:
        """Format node reference with semantic type in brackets."""
        name = node.get("name", "")
        if not name or name == "Unknown":
            return ""
        
        # Get semantic type (entity_type field contains semantic type ID)
        entity_type = node.get("entity_type")
        if entity_type and entity_type != "Entity":
            # Convert semantic type ID to name (e.g., "T047" -> "Disease or Syndrome")
            semantic_type_name = get_semantic_type_name(entity_type)
            return f"{name}[{semantic_type_name}]"
        return name
    
    # Process direct edges (one-hop chains)
    edges = subgraph.get("edges") or []
    for edge in edges:
        source = edge.get("source", {})
        target = edge.get("target", {})
        rel_type = edge.get("type")
        
        source_ref = _format_node_ref(source)
        target_ref = _format_node_ref(target)
        rel_name = rel_type or "RELATED_TO"
        
        # Only add chain if both nodes have valid references
        if source_ref and target_ref:
            chain = f"{source_ref}-({rel_name})->{target_ref}"
            chains.append(chain)
    
    # Process multi-hop paths (2-hop legacy + 3-hop sequence)
    paths = subgraph.get("paths") or []
    for path in paths:
        if "sequence" in path:
            edges = [edge for edge in path.get("sequence", []) if isinstance(edge, dict)]
        else:
            first_edge = path.get("first")
            second_edge = path.get("second")
            edges = [edge for edge in (first_edge, second_edge) if isinstance(edge, dict)]
        if len(edges) < 2:
            continue

        node_refs: List[str] = []
        rel_names: List[str] = []
        for idx, edge in enumerate(edges):
            rel_names.append(edge.get("type") or "RELATED_TO")
            if idx == 0:
                node_refs.append(_format_node_ref(edge.get("source", {})))
            node_refs.append(_format_node_ref(edge.get("target", {})))

        if any(not ref for ref in node_refs):
            continue

        parts: List[str] = []
        for idx, rel in enumerate(rel_names):
            parts.append(f"{node_refs[idx]}-({rel})->")
        parts.append(node_refs[-1])
        chains.append("".join(parts))
    
    return chains


def build_graph_snapshot(subgraph: Dict[str, Any]) -> Dict[str, Any]:
    """Build graph snapshot with reasoning chains in text format.
    
    Only includes reasoning chains and statistics to reduce output size.
    Full node/edge/path details are not included in the snapshot.
    """
    reasoning_chains = build_reasoning_chains(subgraph)
    nodes = subgraph.get("nodes") or []
    edges = subgraph.get("edges") or []
    paths = subgraph.get("paths") or []
    
    return {
        "reasoning_chains": reasoning_chains,
        "reasoning_chains_text": "\n".join(reasoning_chains) if reasoning_chains else "(no reasoning chains found)",
        # Only include statistics, not full node/edge/path lists to reduce output size
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "path_count": len(paths),
            "chain_count": len(reasoning_chains),
        },
    }


def enrich_filtered_entities(
    filtered: Optional[List[Dict[str, Any]]],
    subgraph: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not filtered:
        return []

    node_index = {
        (node.get("id") or node.get("cui")): node 
        for node in subgraph.get("nodes", []) 
        if node.get("id") or node.get("cui")
    }
    name_index: Dict[str, Dict[str, Any]] = {}
    for node in subgraph.get("nodes", []):
        name = (node.get("name") or "").lower()
        if name and name not in name_index:
            name_index[name] = node

    enriched: List[Dict[str, Any]] = []
    for raw in filtered:
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        candidate = None
        node_id = entry.get("node_id")
        if node_id:
            candidate = node_index.get(node_id)
        if not candidate:
            node_name = (entry.get("node_name") or "").lower()
            candidate = name_index.get(node_name)
        if candidate:
            entry.setdefault("node_id", candidate.get("id"))
            entry.setdefault("node_name", candidate.get("name"))
            entry["cui"] = candidate.get("cui")
            entry["entity_type"] = candidate.get("entity_type")
            entry["namespace"] = candidate.get("namespace")
        enriched.append(entry)
    return enriched


def build_agent_payload(
    question: str,
    options: Dict[str, str],
    reasoning_chains_text: str,
    iteration: int,
    previous_requests: List[str],
) -> str:
    option_block = format_options(options)
    needed_block = "\n".join(previous_requests) if previous_requests else "none"

    return f"""
You are an agentic medical QA analyst. Inspect the provided knowledge-graph context and decide
whether you can answer the question.

**Graph Context - Retrieved Reasoning Chains:**
The following reasoning chains are retrieved from the knowledge graph to support your answer. 
Each chain shows the relationships between entities in the format: entity1[SemanticType]-(relationship)->entity2[SemanticType]-(relationship)->entity3[SemanticType]
Each entity includes its semantic type in brackets (e.g., "Fever[Sign or Symptom]") for reference.
Please reference these reasoning chains when building your response.

Reasoning Chains:
{reasoning_chains_text}

Step-by-step expectations:
1. Use the reasoning chains above to understand the relationships between medical entities.
2. Build a reasoning chain that **explicitly references** the semantic types from the chains above.
3. For each entity mentioned in your reasoning, include its semantic type in parentheses or brackets, matching the format in the reasoning chains.
4. If the reasoning chains provide sufficient context, choose the most likely answer option.
5. If the context is insufficient, list the additional entities/relations you still need.
6. **IMPORTANT**: If you cannot find new context after multiple iterations, you MUST provide your best guess answer based on the available information, even if confidence is lower.

Question: {question}
Options:\n{option_block}
Iteration: {iteration}
Previously requested entities: {needed_block}

Respond ONLY in JSON with the following schema:
{{
  "status": "ANSWER" | "NEED_MORE_CONTEXT",
  "reasoning_chain": "string (must include semantic type references for each entity)",
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
        client: ModelClient,
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

        filters_cfg = load_unls_filters()
        allow_types, blacklist_types, type_weights = build_entity_type_policy(
            question, filters_cfg
        )

        seed_ids: List[str] = []
        seed_name_map: Dict[str, str] = {}

        def _register_seed(node: Dict[str, Any]) -> Optional[str]:
            """Register a seed node if its entity type passes the policy."""
            entity_type_id = node.get("entity_type")
            if not is_entity_type_allowed(entity_type_id, allow_types, blacklist_types):
                return None
            node_id = node.get("cui") or node.get("id")
            if not node_id:
                return None
            if node_id not in seed_ids:
                seed_ids.append(node_id)
            node_name = node.get("name")
            if node_name:
                seed_name_map.setdefault(node_id, node_name)
            return node_id

        for match in match_map.values():
            for node in match.matches:
                _register_seed(node)

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
        retrieval_failures = 0
        
        def resolve_seed_names(values: List[str]) -> List[str]:
            return [seed_name_map.get(value, value) for value in values]

        # Get initial seed names instead of IDs
        initial_seed: List[str] = []
        for match in match_map.values():
            for node in match.matches:
                node_id = node.get("cui") or node.get("id")
                node_name = node.get("name")
                if node_id and node_name and node_name not in initial_seed and node_id in seed_ids:
                    initial_seed.append(node_name)

        for iteration in range(1, self.max_iterations + 1):
            relax_mode = iteration > 1 or retrieval_failures > 0
            max_hops = 3 if relax_mode else 2

            # 2. 基于种子做 1-hop / 2-hop（或 3-hop）搜索（Typed Beam 前的原始子图）
            raw_subgraph = self.retriever.fetch_subgraph(seed_ids, max_hops=max_hops)

            # 3. 基于关系黑名单、实体类型与打分规则做路径筛选
            type_policy = (allow_types, blacklist_types, type_weights)
            subgraph = score_and_filter_paths(
                raw_subgraph,
                question=question,
                filters_cfg=filters_cfg,
                type_policy=type_policy,
                relax=relax_mode,
            )

            # 4. 构建给 LLM 的图快照（下游生成逻辑保持不变）
            graph_snapshot = build_graph_snapshot(subgraph)
            reasoning_chains_text = graph_snapshot.get("reasoning_chains_text", "(no reasoning chains found)")
            if not reasoning_chains_text or reasoning_chains_text == "(no reasoning chains found)":
                reasoning_chains_text = "(graph retriever did not return any reasoning chains)"
            user_prompt = build_agent_payload(
                question,
                options,
                reasoning_chains_text,
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
            seeds_before = list(seed_ids)
            chain_count = graph_snapshot.get("stats", {}).get("chain_count", 0)
            if chain_count == 0:
                retrieval_failures += 1

            trace_entry: Dict[str, Any] = {
                "iteration": iteration,
                "seed_ids_before": seeds_before,
                "seed_names_before": resolve_seed_names(seeds_before),
                "graph_context": graph_snapshot,
                "reasoning_chains_preview": truncate(reasoning_chains_text, 1200),
                "raw_response": agent_output,
                "retrieval_mode": "relaxed" if relax_mode else "strict",
                "max_hops": max_hops,
                "retrieval_failure": chain_count == 0,
                "retrieval_failure_count": retrieval_failures,
            }
            status = (parsed.get("status") or "").upper()
            filtered_entities = enrich_filtered_entities(
                parsed.get("filtered_entities"), subgraph
            )
            trace_entry["reasoning_chain"] = parsed.get("reasoning_chain")
            trace_entry["filtered_entities"] = filtered_entities
            trace_entry["status"] = status or "UNKNOWN"
            agent_trace.append(trace_entry)

            if status == "ANSWER":
                final_status = "ANSWERED"
                final_answer = parsed.get("answer")
                agent_trace[-1]["missing_information"] = []
                agent_trace[-1]["seed_ids_after"] = list(seed_ids)
                agent_trace[-1]["seed_names_after"] = resolve_seed_names(seed_ids)
                break

            missing_info = parsed.get("missing_information") or []
            needed = [item for item in missing_info if isinstance(item, str)]
            trace_entry["missing_information"] = needed
            previous_requests = needed

            if not needed:
                final_status = "INSUFFICIENT_CONTEXT"
                trace_entry["seed_ids_after"] = list(seed_ids)
                trace_entry["seed_names_after"] = resolve_seed_names(seed_ids)
                break

            matches = self.matcher.batch_match(needed)
            new_ids = []
            expansion_entities: List[Dict[str, Any]] = []
            for query_name, result in matches.items():
                for node in result.matches:
                    seeds_snapshot = set(seed_ids)
                    node_id = _register_seed(node)
                    if node_id and node_id not in seeds_snapshot:
                        new_ids.append(node_id)
                        expansion_entities.append(
                            {
                                "requested": query_name,
                                "node_id": node_id,
                                "node_name": node.get("name"),
                                "cui": node.get("cui"),
                                "entity_type": node.get("entity_type"),
                            }
                        )

            if not new_ids:
                # Force agent to provide best guess answer when no new context can be found
                final_status = "NO_ADDITIONAL_CONTEXT"
                trace_entry["seed_ids_after"] = list(seed_ids)
                trace_entry["seed_names_after"] = resolve_seed_names(seed_ids)
                
                # Build a prompt to force answer
                option_block = format_options(options)
                force_answer_prompt = f"""
You have reached the maximum number of iterations and no new context can be found.
You MUST provide your best guess answer based on the available reasoning chains, even if confidence is lower.

**Available Reasoning Chains:**
{reasoning_chains_text}

**Question:** {question}
**Options:**\n{option_block}

Respond ONLY in JSON with the following schema:
{{
  "status": "ANSWER",
  "reasoning_chain": "string (explain your reasoning based on available information)",
  "filtered_entities": [],
  "answer": {{"option": str, "text": str, "confidence": float}},
  "missing_information": []
}}
"""
                try:
                    agent_output = self.client.run_json_prompt(
                        system_prompt="You are a structured reasoning engine. Provide your best answer based on available information.",
                        user_prompt=force_answer_prompt,
                        max_output_tokens=1200,
                    )
                    parsed = parse_agent_response(agent_output)
                    if parsed.get("status") == "ANSWER":
                        final_status = "ANSWERED"
                        final_answer = parsed.get("answer")
                        trace_entry["forced_answer"] = True
                        trace_entry["lack_of_evidence"] = True
                        trace_entry["raw_response"] = agent_output
                        trace_entry["reasoning_chain"] = parsed.get("reasoning_chain")
                        trace_entry["status"] = "ANSWER"
                        if isinstance(final_answer, dict):
                            confidence = final_answer.get("confidence")
                            if isinstance(confidence, (int, float)):
                                final_answer["confidence"] = min(float(confidence), 0.25)
                            else:
                                final_answer["confidence"] = 0.2
                            final_answer["confidence_flag"] = "LackOfEvidence"
                        LOGGER.warning(
                            "LackOfEvidence | Forced answer with limited context for question: %s",
                            truncate(question, 120),
                        )
                except Exception as err:  # noqa: BLE001
                    LOGGER.error("Forced answer attempt failed: %s", err)
                
                break

            trace_entry["new_seed_ids"] = new_ids
            trace_entry["new_seed_names"] = resolve_seed_names(new_ids)
            trace_entry["graph_expansion"] = expansion_entities
            trace_entry["seed_ids_after"] = list(seed_ids)
            trace_entry["seed_names_after"] = resolve_seed_names(seed_ids)

        return {
            "question": question,
            "meta": {
                key: record.get(key)
                for key in ("answer", "options", "meta_info", "answer_idx")
            },
            "entities": entities,
            "initial_seed": initial_seed,
            "final_seed_ids": seed_ids,
            "final_seed_names": resolve_seed_names(seed_ids),
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

    client = ModelClient()
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
