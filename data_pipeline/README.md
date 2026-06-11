# SWE-Pruner Data Pipeline

Build your own line-level pruning training data from scratch.

The full pipeline: **pull code → dedup → query gen → score → label → quality filter → train**. Stages 1–6 live here; training (stage 7) lives in [`../train`](../train/README.md).

Run all commands from the **repository root** so that the `data_pipeline` package is importable.

---

## Install dependencies

```bash
pip install torch transformers vllm modelscope torchmetrics typer rich pydantic tqdm
```

`modelscope` is only needed for stage 1 (pull); `vllm` is needed for stages 3–6.

---

## JSONL format at each stage

Each line is one JSON object. Fields accumulate as the pipeline progresses.

| Stage | Fields | Note |
|-------|--------|------|
| **1. Pull** | `code`, `repo` | `repo`: `repo_id/file_path`. Long files chunked by `--max-lines`/`--min-lines`. |
| **2. Dedup** | same | Rows whose `code` appears in the eval set are removed. |
| **3. Query gen** | + `query` | One generated query per code snippet. |
| **4. Score** | + `score` | `score` ∈ [0,1]: query–code relevance from reranker. |
| **5. Label** | + `kept_frags` | 1-based line indices to keep (line-level pruning label). |
| **6. Quality filter** | + `evaluation` | LLM-as-a-Judge verdict (nested dict); optionally drops low-quality rows. |
| **7. Train** | must have: `query`, `code`, `kept_frags`, `score` | Extra fields (incl. `evaluation`) ignored. |

Example labeled line:
```json
{"query": "Where is auth configured?", "code": "def foo():\n  x = 1\n  return x", "score": 0.92, "kept_frags": [1, 3]}
```

The `evaluation` dict added in stage 6 has keys `reasoning`, `query_quality`
(good/acceptable/poor), `deletion_relevance` (appropriate/minimal/excessive),
`semantic_preservation` (preserved/partially_preserved/broken), and
`overall_quality` (low/medium/high).

---

## Step-by-step commands

**1. Pull GitHub code (ModelScope)**
```bash
python -m data_pipeline.scripts.gh_code_dataset --output-prefix ghcode --want-rows 200000 --lang python
```
We used the first 200k samples. Scaling to 2M did not improve results much — better labeling models or a larger base model (e.g. Qwen3-Reranker-8B) may help more.

**2. Dedup against eval set**
```bash
python -m data_pipeline.scripts.dedup --final-dataset final_dataset.jsonl --eval-dataset eval_ds.jsonl --output final_dedup.jsonl
```

**3. Generate queries**
```bash
python -m data_pipeline.inference.qgen -i data.jsonl -o generated_queries.jsonl --model <vLLM_MODEL_PATH>
```

**4. Score (query, code) pairs**
```bash
python -m data_pipeline.inference.score -i generated_queries.jsonl -o scored.jsonl --model <RERANKER_MODEL_PATH>
```

**5. Line-level labeling**
```bash
python -m data_pipeline.inference.build_label \
  --input-file scored.jsonl \
  --output-jsonl labeled.jsonl \
  --model-name <vLLM_MODEL_PATH> \
  --tensor-parallel-size 8
```

**6. Quality filter (LLM-as-a-Judge)**
```bash
python -m data_pipeline.inference.quality_filter \
  --input-file labeled.jsonl \
  --output-jsonl judged.jsonl \
  --filtered-jsonl high_quality.jsonl \
  --keep-levels high \
  --model-name <JUDGE_MODEL_PATH> \
  --tensor-parallel-size 8
```
A judge model (paper uses `Qwen3-Next-80B-A3B-Thinking`) scores each sample on three
dimensions and assigns `overall_quality`. `--output-jsonl` gets every row plus its
`evaluation` dict; `--filtered-jsonl` (optional) gets only rows whose `overall_quality`
is in `--keep-levels` (default `high`) — this is the high-quality training subset
(the paper retains ~1/6). Runs a per-level retention summary at the end.

**7. Train** — feed the labeled (and quality-filtered) JSONL to [`../train/README.md`](../train/README.md).

---

## Shell scripts

- **qgen.sh** – `./data_pipeline/qgen.sh <DATASET_NAME> <RESULT_DIR> [--model MODEL]`
- **label.sh** – `./data_pipeline/label.sh <DATASET_NAME> <RESULT_DIR> [--model-name MODEL] ...`
- **quality.sh** – `./data_pipeline/quality.sh <DATASET_NAME> <RESULT_DIR> [--model-name MODEL] ...`

All run from repo root and forward extra arguments to the underlying Python module.
