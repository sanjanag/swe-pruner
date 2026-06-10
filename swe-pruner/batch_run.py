#!/usr/bin/env python3
"""Run SwePruner over a contiguous block of dataset rows and dump JSON results.

Usage: python3 batch_run.py [START] [COUNT] [THRESHOLD] [OUT]
Defaults: START=6670 COUNT=50 THRESHOLD=0.5 OUT=results.json
"""
import os
import sys
import json
import warnings

warnings.filterwarnings("ignore", message=r".*torch_dtype.*is deprecated.*")
from transformers.utils import logging as hf_logging

hf_logging.set_verbosity_error()

import torch

from swe_pruner.prune_wrapper import SwePrunerForCodePruning, PruneRequest

DATASET = os.path.join(
    os.path.dirname(__file__), "..", "data", "swe-pruner-training-dataset-py.jsonl"
)


def main() -> None:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 6670
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    out = sys.argv[4] if len(sys.argv) > 4 else "results.json"

    end = start + count
    rows = {}
    with open(DATASET) as f:
        for i, line in enumerate(f):
            if i >= end:
                break
            if i >= start:
                rows[i] = json.loads(line)

    model_path = os.getenv("SWEPRUNER_MODEL_PATH", "./model")
    load_kwargs = {"dtype": torch.bfloat16} if torch.cuda.is_available() else {}
    model = SwePrunerForCodePruning.from_pretrained(model_path, **load_kwargs)
    device = next(model.parameters()).device
    print(f"model loaded on {device} dtype={next(model.parameters()).dtype}")

    results = []
    for i in range(start, end):
        row = rows.get(i)
        if row is None:
            print(f"row {i} missing, stopping")
            break
        resp = model.prune(
            PruneRequest(query=row["query"], code=row["code"], threshold=threshold)
        )
        gold = row.get("kept_frags")
        if isinstance(gold, str):
            try:
                gold = json.loads(gold)
            except Exception:
                gold = []
        results.append(
            {
                "idx": i,
                "query": row["query"],
                "code": row["code"],
                "is_negative": row.get("is_negative"),
                "gold_kept_frags": gold or [],
                "gold_score": row.get("score"),
                "evaluation": row.get("evaluation"),
                "score": resp.score,
                "origin_token_cnt": resp.origin_token_cnt,
                "left_token_cnt": resp.left_token_cnt,
                "model_input_token_cnt": resp.model_input_token_cnt,
                "predicted_kept_frags": resp.kept_frags,
                "pruned_code": resp.pruned_code,
                "error_msg": resp.error_msg,
            }
        )
        print(
            f"[{i}] score={resp.score:.4f} "
            f"tokens={resp.origin_token_cnt}->{resp.left_token_cnt} "
            f"kept={len(resp.kept_frags)}"
        )

    payload = {
        "meta": {
            "start": start,
            "count": len(results),
            "threshold": threshold,
            "device": str(device),
            "dtype": str(next(model.parameters()).dtype),
        },
        "results": results,
    }
    with open(out, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(results)} results to {out}")


if __name__ == "__main__":
    main()
