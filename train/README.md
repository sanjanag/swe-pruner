# Training SWE-Pruner

Run all commands from the **repository root** so that the `train` package is importable.

---

## Quick start: train with the released dataset

If you just want to reproduce or finetune the swe-pruner, download the pre-built dataset and start training directly.

### 1. Install dependencies

```bash
pip install torch transformers flash-attn torchmetrics typer rich pydantic tqdm
```

### 2. Download data and model

| Resource | Link |
|----------|------|
| Training data (61k, Python) | [Google Drive](https://drive.google.com/file/d/18g_kWeyvd8EICEDZcKylEEf8mnOFhwdi) — `swe-pruner-training-dataset-py.jsonl` |
| Base model | [Qwen/Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) |

### 3. Launch training

```bash
bash train/train_llm.sh 8 /path/to/swe-pruner-training-dataset-py.jsonl \
  --model-name /path/to/Qwen3-Reranker-0.6B \
  --epochs 3 \
  --lr 1e-4 \
  --log-dir llm_experiments/swe-pruner-py \
  --num-finetune-layers 2 \
  --num-fusion-layers 1 \
  --batch-size 16 \
  --compression-head-type crf \
  --compression-loss-type focal \
  --dropout 0.4 \
  --auto-focal-alpha \
  --use-multi-layer-fusion \
  --use-sample-level-aggregation
```

Replace `8` with your GPU count. With 8 × A100 80GB, each epoch takes ~75 min (~10 s/step, 431 steps/epoch); full run finishes in ~4 hours.

### Expected results

Numbers may vary slightly across hardware due to CUDA non-determinism — differences within ±0.02 on F1 are normal.

**8 × NVIDIA A100-SXM4-80GB:**

| Epoch | Loss | C_Loss | S_Loss | Accuracy | Precision | Recall | F1 |
|-------|------|--------|--------|----------|-----------|--------|----|
| 1 | 0.4489 | 0.4725 | 0.0007 | 0.7835 | 0.8125 | 0.6057 | 0.6940 |
| 2 | 0.3676 | 0.3869 | 0.0007 | 0.8184 | 0.7681 | 0.7907 | 0.7792 |
| 3 | 0.3593 | 0.3782 | 0.0007 | 0.8237 | 0.7868 | 0.7748 | **0.7808** |

**8 × NVIDIA H100:**

| Epoch | Loss | C_Loss | S_Loss | Accuracy | Precision | Recall | F1 |
|-------|------|--------|--------|----------|-----------|--------|----|
| 1 | 0.4992 | 0.5254 | 0.0007 | 0.7716 | 0.8388 | 0.5405 | 0.6574 |
| 2 | 0.3689 | 0.3882 | 0.0007 | 0.8182 | 0.7738 | 0.7795 | 0.7766 |
| 3 | 0.3615 | 0.3804 | 0.0007 | 0.8239 | 0.7931 | 0.7651 | **0.7788** |

### Monitoring

```bash
tensorboard --logdir llm_experiments/swe-pruner-py
```

### Output layout

All outputs land under `--log-dir`:

```
llm_experiments/swe-pruner-py/
├── best_model.pt                # Best checkpoint (by val F1)
├── model_config.json            # Full config snapshot for reproducibility
├── eval_with_token_scores.jsonl # Val set with per-token scores
└── events.out.tfevents.*        # TensorBoard logs
```

---

## Build your own training data

To generate your own line-level pruning dataset from scratch (pull → dedup → query gen → score → label), see the [`data_pipeline`](../data_pipeline/README.md) folder. Once you have a labeled JSONL with `query`, `code`, `kept_frags`, and `score`, feed it to the [Quick start](#3-launch-training) above.

---

## Parameter reference

### Data and I/O
- **`-i` / `--input-file`** – Input JSONL with `query`, `code`, `kept_frags`, `score`.
- **`--log-dir`** – Output directory for checkpoints, config, TensorBoard (default: `llm_experiments/swe-pruner`).
- **`--train-split`** – Train/val split ratio (default: 0.9).

### Model
- **`--model-name`** – Base model name or path. **Required.**
- **`--num-finetune-layers`** – Top transformer layers to unfreeze; 0 = freeze all (default: 0).
- **`--instruction`** – System instruction for the query–document task.

### Compression head
- **`--compression-head-type`** – `ffn` | `simple` | `residual` | `crf` (default: `ffn`).
- **`--hidden-size`** – Bottleneck dimension (default: 256).
- **`--dropout`** – Dropout rate (default: 0.1).
- **`--num-fusion-layers`** – Self-attention fusion layers (default: 1).
- **`--num-heads`** – Attention heads per fusion layer (default: 8).

### Loss
- **`--lambda-score`** – Score loss weight; compression weight = 1 − lambda (default: 0.05).
- **`--compression-loss-type`** – `bce` | `focal` (default: `focal`).
- **`--focal-alpha`** – Focal loss alpha (default: 0.25). Use **`--auto-focal-alpha`** to compute from data.
- **`--focal-gamma`** – Focal loss gamma (default: 2.0).
- **`--use-sample-level-aggregation`** – Per-sample loss averaging before batch mean (default: true).

### Optimization
- **`--lr`** – Learning rate (default: 1e-4).
- **`--weight-decay`** – AdamW weight decay (default: 0.01).
- **`--warmup-ratio`** – Linear warmup fraction (default: 0.1).
- **`--batch-size`** – Batch size per GPU (default: 4).
- **`--epochs`** – Training epochs (default: 2).

### Multi-layer fusion
- **`--use-multi-layer-fusion`** – Concatenate early/middle/final hidden states.
- **`--early-layer-ratio`**, **`--middle-layer-ratio`** – Layer index ratios (defaults: 0.25, 0.5).

### Eval-only mode
- **`--eval-only`** – Skip training, only evaluate (requires `--eval-dataset` and `--model-paths`).
- **`--eval-dataset`** – JSONL for evaluation.
- **`--model-paths`** – Checkpoint path(s) to evaluate or compare.

---

## Shell scripts

- **train_llm.sh** – `./train/train_llm.sh <NUM_GPUS> <INPUT_JSONL> [--model-name MODEL] ...`

Runs from repo root and forwards extra arguments to the underlying Python module. The data-pipeline scripts (`qgen.sh`, `label.sh`) now live in [`../data_pipeline`](../data_pipeline/README.md).
