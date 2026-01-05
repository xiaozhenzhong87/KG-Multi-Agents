"""Helpers for interacting with the Neo4j healthcare graph."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..core.database import Neo4jManager

logger = logging.getLogger(__name__)


def _node_to_dict(node: object) -> Dict[str, Optional[str]]:
    """Convert a Neo4j node into a lightweight dictionary."""

    if isinstance(node, dict):
        data = node.copy()
    elif node is None:
        data = {}
    else:
        try:
            data = dict(node)
        except Exception:  # noqa: BLE001
            data = {}

    return {
        "name": data.get("name"),
        "cui": data.get("cui"),
        "entity_type": data.get("entity_type"),
        "namespace": data.get("namespace"),
        "definition": data.get("definition"),
        # Note: embedding is typically a large vector, we don't include it in the dict
        # but it's available in the node if needed
    }


def _relationship_to_dict(rel: object, rel_type: Optional[str]) -> Dict[str, Optional[str]]:
    """Convert a Neo4j relationship into a lightweight dictionary."""

    start: Dict[str, Optional[str]]
    end: Dict[str, Optional[str]]

    if isinstance(rel, dict):
        data = rel.copy()
        start = _node_to_dict(data.get("start"))
        end = _node_to_dict(data.get("end"))
    else:
        try:
            data = dict(rel)
            start = _node_to_dict(getattr(rel, "start_node", {}))
            end = _node_to_dict(getattr(rel, "end_node", {}))
        except Exception:  # noqa: BLE001
            data = {}
            start = {}
            end = {}

    return {
        "id": data.get("id"),
        "type": rel_type,
        "namespace": data.get("namespace"),
        "confidence": data.get("confidence"),
        "source": start,
        "target": end,
    }


@dataclass
class EntityMatch:
    """Represents the result of matching a single entity candidate."""

    name: str
    matched: bool
    matches: List[Dict[str, Optional[str]]]


class GraphEntityMatcher:
    """Perform simple entity lookups inside the Neo4j graph."""

    def __init__(
        self,
        manager: Neo4jManager,
        namespace: Optional[str] = None,
        max_candidates: int = 5,
    ) -> None:
        self.manager = manager
        self.namespace = namespace
        self.max_candidates = max_candidates
        self.manager.connect()

    def match_entity(self, name: str) -> EntityMatch:
        cleaned = name.strip()
        if not cleaned:
            return EntityMatch(name=name, matched=False, matches=[])

        results = self._exact_match(cleaned)
        if not results:
            results = self._contains_match(cleaned)
        if not results:
            tokens = self._tokenize(cleaned)
            for token in tokens:
                results.extend(self._contains_match(token))
                if results:
                    break

        unique: Dict[str, Dict[str, Optional[str]]] = {}
        for record in results:
            node_dict = _node_to_dict(record.get("entity"))
            # Use CUI as unique identifier
            unique_key = node_dict.get("cui")
            if unique_key:
                unique[unique_key] = node_dict

        matches = list(unique.values())[: self.max_candidates]
        return EntityMatch(name=name, matched=bool(matches), matches=matches)

    def batch_match(self, names: Sequence[str]) -> Dict[str, EntityMatch]:
        return {name: self.match_entity(name) for name in names}

    def _run_query(self, query: str, parameters: Dict[str, object]) -> List[Dict[str, object]]:
        if not self.manager.graph:
            self.manager.connect()
        cursor = self.manager.graph.run(query, parameters)
        return cursor.data()

    def _exact_match(self, name: str) -> List[Dict[str, object]]:
        query = """
        MATCH (entity:Entity)
        WHERE toLower(entity.name) = toLower($name)
          AND ($namespace IS NULL OR entity.namespace = $namespace)
        RETURN entity
        LIMIT $limit
        """
        return self._run_query(
            query,
            {"name": name, "namespace": self.namespace, "limit": self.max_candidates},
        )

    def _contains_match(self, name: str) -> List[Dict[str, object]]:
        if len(name) < 4:
            return []
        query = """
        MATCH (entity:Entity)
        WHERE toLower(entity.name) CONTAINS toLower($name)
          AND ($namespace IS NULL OR entity.namespace = $namespace)
        RETURN entity, size(entity.name) AS name_len
        ORDER BY name_len ASC
        LIMIT $limit
        """
        return self._run_query(
            query,
            {"name": name, "namespace": self.namespace, "limit": self.max_candidates * 3},
        )

    @staticmethod
    def _tokenize(name: str) -> List[str]:
        candidates = re.split(r"[^a-z0-9]+", name.lower())
        unique = []
        for token in candidates:
            if len(token) >= 4 and token not in unique:
                unique.append(token)
        return unique


class SubgraphRetriever:
    """Collect up to 3-hop neighborhoods for a set of seed nodes."""

    def __init__(
        self,
        manager: Neo4jManager,
        max_neighbors: int = 25,
        max_two_hop_paths: int = 50,
        max_three_hop_paths: int = 30,
    ) -> None:
        self.manager = manager
        self.max_neighbors = max_neighbors
        self.max_two_hop_paths = max_two_hop_paths
        self.max_three_hop_paths = max_three_hop_paths
        self.manager.connect()

    def fetch_subgraph(self, seed_ids: Sequence[str], max_hops: int = 2) -> Dict[str, object]:
        if not seed_ids:
            return {"nodes": [], "edges": [], "paths": []}

        one_hop_edges = self._fetch_one_hop(seed_ids)
        two_hop_paths = self._fetch_two_hop(seed_ids) if max_hops >= 2 else []
        three_hop_paths = self._fetch_three_hop(seed_ids) if max_hops >= 3 else []

        nodes: Dict[str, Dict[str, Optional[str]]] = {}
        edges: List[Dict[str, object]] = []
        paths: List[Dict[str, object]] = []

        # Process one-hop edges
        for record in one_hop_edges:
            # Extract nodes from query results
            seed_node = _node_to_dict(record.get("seed"))
            neighbor_node = _node_to_dict(record.get("neighbor"))
            
            # Use elementId as primary identifier, fallback to cui
            seed_id = (
                record.get("seed_element_id") or 
                seed_node.get("cui")
            )
            neighbor_id = (
                record.get("neighbor_element_id") or 
                neighbor_node.get("cui")
            )
            
            # Set the id field in node dicts
            if seed_id:
                seed_node["id"] = seed_id
                nodes[seed_id] = seed_node
            if neighbor_id:
                neighbor_node["id"] = neighbor_id
                nodes[neighbor_id] = neighbor_node
            
            # Build edge from relationship
            rel = record.get("rel")
            rel_type = record.get("rel_type")
            edge = {
                "id": None,  # Relationships may not have IDs
                "type": rel_type,
                "namespace": None,
                "confidence": None,
                "source": seed_node,
                "target": neighbor_node,
            }
            edges.append(edge)

        # Process two-hop paths
        for record in two_hop_paths:
            # Extract nodes from query results
            seed_node = _node_to_dict(record.get("seed"))
            mid_node = _node_to_dict(record.get("mid"))
            neighbor_node = _node_to_dict(record.get("neighbor"))
            
            # Use elementId as primary identifier, fallback to cui
            seed_id = (
                record.get("seed_element_id") or 
                seed_node.get("cui")
            )
            mid_id = (
                record.get("mid_element_id") or 
                mid_node.get("cui")
            )
            neighbor_id = (
                record.get("neighbor_element_id") or 
                neighbor_node.get("cui")
            )
            
            # Set the id field in node dicts
            if seed_id:
                seed_node["id"] = seed_id
                nodes[seed_id] = seed_node
            if mid_id:
                mid_node["id"] = mid_id
                nodes[mid_id] = mid_node
            if neighbor_id:
                neighbor_node["id"] = neighbor_id
                nodes[neighbor_id] = neighbor_node
            
            # Build edges for the path
            first_edge = {
                "id": None,
                "type": record.get("rel1_type"),
                "namespace": None,
                "confidence": None,
                "source": seed_node,
                "target": mid_node,
            }
            second_edge = {
                "id": None,
                "type": record.get("rel2_type"),
                "namespace": None,
                "confidence": None,
                "source": mid_node,
                "target": neighbor_node,
            }
            paths.append({"first": first_edge, "second": second_edge})

        # Process three-hop paths
        for record in three_hop_paths:
            seed_node = _node_to_dict(record.get("seed"))
            mid1_node = _node_to_dict(record.get("mid1"))
            mid2_node = _node_to_dict(record.get("mid2"))
            neighbor_node = _node_to_dict(record.get("neighbor"))

            seed_id = record.get("seed_element_id") or seed_node.get("cui")
            mid1_id = record.get("mid1_element_id") or mid1_node.get("cui")
            mid2_id = record.get("mid2_element_id") or mid2_node.get("cui")
            neighbor_id = record.get("neighbor_element_id") or neighbor_node.get("cui")

            if seed_id:
                seed_node["id"] = seed_id
                nodes[seed_id] = seed_node
            if mid1_id:
                mid1_node["id"] = mid1_id
                nodes[mid1_id] = mid1_node
            if mid2_id:
                mid2_node["id"] = mid2_id
                nodes[mid2_id] = mid2_node
            if neighbor_id:
                neighbor_node["id"] = neighbor_id
                nodes[neighbor_id] = neighbor_node

            edge1 = {
                "id": None,
                "type": record.get("rel1_type"),
                "namespace": None,
                "confidence": None,
                "source": seed_node,
                "target": mid1_node,
            }
            edge2 = {
                "id": None,
                "type": record.get("rel2_type"),
                "namespace": None,
                "confidence": None,
                "source": mid1_node,
                "target": mid2_node,
            }
            edge3 = {
                "id": None,
                "type": record.get("rel3_type"),
                "namespace": None,
                "confidence": None,
                "source": mid2_node,
                "target": neighbor_node,
            }
            paths.append({"sequence": [edge1, edge2, edge3]})

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "paths": paths,
        }

    def _fetch_one_hop(self, seed_ids: Sequence[str]) -> List[Dict[str, object]]:
        query = """
        MATCH (seed:Entity)-[rel]-(neighbor:Entity)
        WHERE seed.cui IN $seed_ids OR seed.id IN $seed_ids
        RETURN rel, type(rel) AS rel_type,
               seed, neighbor,
               elementId(seed) AS seed_element_id, 
               elementId(neighbor) AS neighbor_element_id
        LIMIT $limit
        """
        limit = max(1, self.max_neighbors * max(1, len(seed_ids)))
        return self.manager.graph.run(query, {"seed_ids": list(seed_ids), "limit": limit}).data()

    def _fetch_two_hop(self, seed_ids: Sequence[str]) -> List[Dict[str, object]]:
        query = """
        MATCH (seed:Entity)-[rel1]-(mid:Entity)-[rel2]-(neighbor:Entity)
        WHERE (seed.cui IN $seed_ids OR seed.id IN $seed_ids) AND seed <> neighbor
        RETURN rel1, type(rel1) AS rel1_type, rel2, type(rel2) AS rel2_type,
               seed, mid, neighbor,
               elementId(seed) AS seed_element_id,
               elementId(mid) AS mid_element_id,
               elementId(neighbor) AS neighbor_element_id
        LIMIT $limit
        """
        limit = max(1, self.max_two_hop_paths * max(1, len(seed_ids)))
        return self.manager.graph.run(query, {"seed_ids": list(seed_ids), "limit": limit}).data()

    def _fetch_three_hop(self, seed_ids: Sequence[str]) -> List[Dict[str, object]]:
        query = """
        MATCH (seed:Entity)-[rel1]-(mid1:Entity)-[rel2]-(mid2:Entity)-[rel3]-(neighbor:Entity)
        WHERE (seed.cui IN $seed_ids OR seed.id IN $seed_ids) AND seed <> neighbor
        RETURN rel1, type(rel1) AS rel1_type,
               rel2, type(rel2) AS rel2_type,
               rel3, type(rel3) AS rel3_type,
               seed, mid1, mid2, neighbor,
               elementId(seed) AS seed_element_id,
               elementId(mid1) AS mid1_element_id,
               elementId(mid2) AS mid2_element_id,
               elementId(neighbor) AS neighbor_element_id
        LIMIT $limit
        """
        limit = max(1, self.max_three_hop_paths * max(1, len(seed_ids)))
        return self.manager.graph.run(
            query, {"seed_ids": list(seed_ids), "limit": limit}
        ).data()


def format_subgraph_as_text(subgraph: Dict[str, object]) -> str:
    """Render the collected subgraph into a compact textual summary."""

    node_lines = []
    for node in subgraph.get("nodes", []):
        node_lines.append(
            f"[Node:{node.get('id')}] name={node.get('name')} | type={node.get('entity_type')} | cui={node.get('cui')}"
        )

    edge_lines = []
    for edge in subgraph.get("edges", []):
        source = edge.get("source", {})
        target = edge.get("target", {})
        edge_lines.append(
            " -> ".join(
                [
                    f"[Edge:{edge.get('type')}]",
                    f"{source.get('name')} ({source.get('id')})",
                    f"{target.get('name')} ({target.get('id')})",
                ]
            )
        )

    path_lines = []
    for idx, path in enumerate(subgraph.get("paths", []), start=1):
        first = path["first"]
        second = path["second"]
        mid = first.get("target", {})
        path_lines.append(
            f"[Path:{idx}] {first['source'].get('name')} -[{first.get('type')}]> {mid.get('name')} "
            f"-[{second.get('type')}]> {second['target'].get('name')}"
        )

    return "\n".join([
        "# Nodes:",
        *node_lines,
        "\n# Direct Edges:",
        *edge_lines,
        "\n# Two-hop Paths:",
        *path_lines,
    ])
