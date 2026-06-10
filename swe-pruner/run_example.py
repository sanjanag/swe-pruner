#!/usr/bin/env python3
"""Run SwePruner on a single row of the training dataset.

Usage: python3 run_example.py [ROW_INDEX] [THRESHOLD]   (defaults: 0, 0.5)
Loads the model the same way online_serving.py does (bf16 on GPU) and calls
model.prune(PruneRequest(...)) directly -- no HTTP service needed.
"""
import os
import sys
import json
import warnings

# Silence the transformers "`torch_dtype` is deprecated! Use `dtype` instead!"
# notice (triggered by torch_dtype in the model config.json) and other info logs.
warnings.filterwarnings("ignore", message=r".*torch_dtype.*is deprecated.*")
from transformers.utils import logging as hf_logging

hf_logging.set_verbosity_error()

import torch

from swe_pruner.prune_wrapper import SwePrunerForCodePruning, PruneRequest

DATASET = os.path.join(
    os.path.dirname(__file__), "..", "data", "swe-pruner-training-dataset-py.jsonl"
)
BAR = "=" * 80


def load_row(idx: int) -> dict:
    with open(DATASET) as f:
        for i, line in enumerate(f):
            if i == idx:
                return json.loads(line)
    raise IndexError(f"row {idx} not found")


def main() -> None:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    row = load_row(idx)

    # ---- RAW ROW ----
    print(BAR)
    print(f"RAW ROW [{idx}]")
    print(BAR)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    print()

    # ---- CODE (numbered) ----
    print(BAR)
    print("CODE (numbered)")
    print(BAR)
    for n, line in enumerate(row["code"].splitlines(), start=1):
        print(f"{n:4d} | {line}")
    print()

    # ---- INFERENCE ----
    print(BAR)
    print("INFERENCE")
    print(BAR)
    print(f"QUERY: {row['query']}")
    print(f"is_negative: {row.get('is_negative')}  gold kept_frags: {row.get('kept_frags')}")

    model_path = os.getenv("SWEPRUNER_MODEL_PATH", "./model")
    load_kwargs = {"dtype": torch.bfloat16} if torch.cuda.is_available() else {}
    model = SwePrunerForCodePruning.from_pretrained(model_path, **load_kwargs)

    resp = model.prune(
        PruneRequest(query=row["query"], code=row["code"], threshold=threshold)
    )

    print()
    print(f"score: {resp.score:.4f}")
    print(f"tokens: {resp.origin_token_cnt} -> {resp.left_token_cnt}")
    print(f"predicted kept_frags: {resp.kept_frags}")
    if resp.error_msg:
        print(f"error_msg: {resp.error_msg}")
    print()
    print("--- pruned code ---")
    print(resp.pruned_code)


if __name__ == "__main__":
    main()
