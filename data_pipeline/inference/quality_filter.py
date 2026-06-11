"""LLM-as-a-Judge quality filter.

Judges each labeled (query, code, kept_frags) sample on three dimensions
(query quality, deletion relevance, semantic preservation), attaches a nested
`evaluation` dict, and optionally filters the dataset down to the high-quality
samples. Mirrors the released dataset's row format: all original fields are
preserved and an `evaluation` dict is appended.
"""
import json
from typing import List, Optional
from pathlib import Path

import typer
from rich.console import Console
from tqdm import tqdm
from vllm import LLM, SamplingParams

from data_pipeline.core.prompts.quality_eval import (
    quality_eval_prompt_template,
    fetch_quality_from_output,
)
from data_pipeline.utils.line_chunker import split_code_into_lines

app = typer.Typer(help="LLM-as-a-Judge quality filter; annotates rows with `evaluation` and optionally filters")
console = Console()


def code_with_numbers(lines: List[str]) -> str:
    """Format code as 1-based numbered lines: `1: <line>`."""
    return "\n".join(f"{i}: {line}" for i, line in enumerate(lines, start=1))


def build_diff(lines: List[str], kept: set) -> str:
    """Render a diff: kept lines get a space prefix, removed lines a `- ` prefix."""
    out = []
    for i, line in enumerate(lines, start=1):
        prefix = "  " if i in kept else "- "
        out.append(f"{prefix}{i}: {line}")
    return "\n".join(out)


def _coerce_frags(kept_frags) -> List[int]:
    if isinstance(kept_frags, str):
        try:
            kept_frags = json.loads(kept_frags)
        except json.JSONDecodeError:
            return []
    if isinstance(kept_frags, list):
        return [int(x) for x in kept_frags]
    return []


def load_processed_codes(output_jsonl: Path) -> set:
    """Load already-judged code snippets so reruns are resumable."""
    processed = set()
    if not output_jsonl.exists():
        return processed
    try:
        with open(output_jsonl, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        processed.add(json.loads(line).get("code", ""))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        console.print(f"[yellow]Warning: could not read existing output: {e}[/yellow]")
    return processed


@app.command()
def main(
    input_file: Path = typer.Option(
        "labeled.jsonl", "--input-file", help="Labeled JSONL with query, code, kept_frags"
    ),
    output_jsonl: Path = typer.Option(
        "judged.jsonl", "--output-jsonl", help="Output JSONL: every row + an `evaluation` dict"
    ),
    filtered_jsonl: Optional[Path] = typer.Option(
        None, "--filtered-jsonl", help="If set, also write only rows whose overall_quality is in --keep-levels"
    ),
    keep_levels: str = typer.Option(
        "high", "--keep-levels", help="Comma-separated overall_quality levels to retain in --filtered-jsonl"
    ),
    model_name: str = typer.Option(
        ..., "--model-name", help="vLLM judge model path (e.g. Qwen/Qwen3-Next-80B-A3B-Thinking)"
    ),
    tensor_parallel_size: int = typer.Option(8, "--tensor-parallel-size", help="Tensor parallel size for vLLM"),
    max_model_len: int = typer.Option(16384, "--max-model-len", help="Max model length for vLLM"),
    temperature: float = typer.Option(0.6, "--temperature", help="Sampling temperature"),
    max_tokens: int = typer.Option(8192, "--max-tokens", help="Max output tokens (judge may emit a long reasoning trace)"),
    max_code_length: int = typer.Option(12000, "--max-code-length", help="Skip code longer than this (chars)"),
):
    keep = {lvl.strip().lower() for lvl in keep_levels.split(",") if lvl.strip()}

    # 1. Load labeled input
    console.print(f"Loading data from {input_file}...")
    input_data = []
    with open(input_file, "r") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                console.print(f"[yellow]Skipping invalid line: {e}[/yellow]")
                continue
            if not (isinstance(item, dict) and "query" in item and "code" in item and "kept_frags" in item):
                continue
            if isinstance(item["code"], str) and len(item["code"]) > max_code_length:
                continue
            input_data.append(item)

    if not input_data:
        console.print("[red]No valid input data found (need query, code, kept_frags)![/red]")
        raise SystemExit(1)
    console.print(f"Loaded {len(input_data)} items")

    processed = load_processed_codes(output_jsonl)
    console.print(f"Found {len(processed)} already judged in output file")
    filtered_input = [d for d in input_data if d["code"] not in processed]
    console.print(f"Total: {len(input_data)}, Remaining: {len(filtered_input)}")

    # 2. Build prompts
    console.print("Building prompts...")
    prompts = []
    for item in filtered_input:
        lines = [c.text for c in split_code_into_lines(item["code"])]
        kept = set(_coerce_frags(item["kept_frags"]))
        prompt = quality_eval_prompt_template.format(
            query=item["query"],
            code_with_numbers=code_with_numbers(lines),
            diff=build_diff(lines, kept),
        )
        prompts.append(prompt)

    # 3. Init vLLM
    console.print(f"Initializing vLLM with judge model {model_name}...")
    sampling_params = SamplingParams(max_tokens=max_tokens, temperature=temperature)
    llm = LLM(
        model=model_name,
        max_model_len=max_model_len,
        enable_prefix_caching=True,
        tensor_parallel_size=tensor_parallel_size,
    )

    # 4. Batch inference with streaming writes
    console.print(f"Judging {len(prompts)} samples...")
    system_prompt = "You are a meticulous code quality evaluator for a code pruning dataset."
    messages = [
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": p}]
        for p in prompts
    ]
    batch_size = 128
    err_cnt = 0
    counts = {"high": 0, "medium": 0, "low": 0}
    kept_cnt = 0

    out_f = open(output_jsonl, "a")
    filt_f = open(filtered_jsonl, "a") if filtered_jsonl else None
    try:
        for i in tqdm(range(0, len(messages), batch_size), desc="Judging"):
            batch_outputs = llm.chat(messages=messages[i : i + batch_size], sampling_params=sampling_params)
            batch_items = filtered_input[i : i + batch_size]
            for item, output in zip(batch_items, batch_outputs):
                text = output.outputs[0].text
                evaluation = fetch_quality_from_output(text)
                if evaluation is None:
                    err_cnt += 1
                    continue
                counts[evaluation["overall_quality"]] += 1
                row = {**item, "evaluation": evaluation}
                out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                if filt_f is not None and evaluation["overall_quality"] in keep:
                    filt_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    kept_cnt += 1
    finally:
        out_f.close()
        if filt_f is not None:
            filt_f.close()

    # 5. Summary
    console.print()
    console.rule("Quality evaluation complete")
    judged = sum(counts.values())
    console.print(f"Judged: {judged}  |  Parse errors: {err_cnt}")
    for lvl in ("high", "medium", "low"):
        pct = (counts[lvl] / judged * 100) if judged else 0
        console.print(f"  {lvl}: {counts[lvl]} ({pct:.1f}%)")
    console.print(f"Annotated output: [bold]{output_jsonl}[/bold]")
    if filtered_jsonl is not None:
        console.print(f"Filtered (keep={sorted(keep)}): {kept_cnt} rows -> [bold]{filtered_jsonl}[/bold]")


if __name__ == "__main__":
    app()
