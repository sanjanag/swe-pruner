#!/bin/bash
# Usage: ./quality.sh <DATASET_NAME> <RESULT_DIR> [--model-name MODEL] ...
# Example: ./quality.sh mydata ./out --model-name Qwen/Qwen3-Next-80B-A3B-Thinking --filtered-jsonl ./out/hq.jsonl
# Run from repo root so that python -m data_pipeline.inference.quality_filter works.

set -e
DATASET_NAME="${1:?Usage: quality.sh DATASET_NAME RESULT_DIR [options]}"
RESULT_DIR="${2:?Usage: quality.sh DATASET_NAME RESULT_DIR [options]}"
shift 2 || true

python -m data_pipeline.inference.quality_filter \
  --input-file "${RESULT_DIR}/labeled_${DATASET_NAME}.jsonl" \
  --output-jsonl "${RESULT_DIR}/judged_${DATASET_NAME}.jsonl" \
  "$@"
