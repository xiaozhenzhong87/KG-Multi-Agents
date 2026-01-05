# ZXZ Utilities

This folder collects standalone scripts that support MedQA experimentation on top of the healthcare knowledge graph.

## Fast Oracle Coverage Test

```
python zxz/run_fast_test_entity_match.py \
  --dataset eval_data/fast_test_medqa_20.jsonl \
  --output-dir zxz/match_results
```

- Reads each MedQA question.
- Calls the Deepseek-V3 model to extract structured entities.
- Matches extracted entities against the UMLS-backed Neo4j graph and records coverage metrics.

## Agentic Reasoning-Chain Evaluation

```
python zxz/run_reasoning_chain_eval.py \
  --dataset eval_data/fast_test_medqa_20.jsonl \
  --output-dir zxz/match_results \
  --max-iterations 3
```

- Reuses LLM entity extraction + KG matching from the oracle script.
- Builds 1-hop/2-hop subgraphs around matched nodes and lets the LLM iteratively filter/answer.
- Saves full agent traces (per iteration reasoning, filtered entities, final answer status) for later inspection.

Both scripts require the following environment variables (export them before running):

```
export DEEPSEEK_API_KEY="<api-key>"
export DEEPSEEK_BASE_URL="https://api.modelarts-maas.com/v1"
export DEEPSEEK_MODEL="Deepseek-V3"
```

Make sure Neo4j is reachable with the credentials configured in `src/config/settings.py` (defaults: `bolt://localhost:7688`, user `neo4j`, password `12345678`).
