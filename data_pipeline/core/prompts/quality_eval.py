"""Quality-evaluation (LLM-as-a-Judge) prompt and output parser.

Judges a labeled (query, code, kept_frags) sample on three dimensions and
assigns an overall quality rating. Used by data_pipeline.inference.quality_filter
to filter the labeled dataset down to high-quality samples.
"""
import re
import json
from typing import Optional, Dict

quality_eval_prompt_template = """You are a code quality evaluator for a code pruning dataset. Your task is to assess the quality of a query-guided code deletion sample.

You will be given:
1. **Query**: A code snippet for means making completion below or a natural language question/task
2. **Original Code**: Full code snippet with line numbers
3. **Diff**: Shows which lines were removed (- prefix) and kept (no change or + prefix)

Evaluate THREE dimensions:

## 1. Query Quality
- **Good**: Realistic, specific, actionable developer question related to a partial feature/function
- **Acceptable**: Valid but generic, or slightly unclear but answerable
- **Poor**: Too vague, treats code as the subject ("explain this code")

HINT: just focus on query itself, don't take query-code relevance into consideration in this part.

## 2. Deletion Relevance
- **Appropriate**: Removes truly unrelated code while keeping necessary context
- **Minimal**: Mostly removes whitespace/comments/trivial lines, little semantic pruning
- **Excessive**: Removes too much, including code relevant to the query

HINT: Both query-code high relevance and low relevance are ok, key point is the context preserved correctly. For high relevance, might more code; For low relevance, might less code.

## 3. Semantic Preservation
- **Preserved**: Remaining code is syntactically valid and semantically coherent (can understand the query-relevant logic)
- **Partially Preserved**: Minor issues (e.g., unmatched braces, missing imports that don't affect core logic understanding)
- **Broken**: Code is syntactically invalid or key logic is incomprehensible

## Overall Quality Rating
Based on the above three dimensions, assign:
- **high**: All three dimensions are good/appropriate/preserved, or at most one acceptable/partially_preserved
- **medium**: Two dimensions are good/acceptable/appropriate, one has issues; or all three are acceptable
- **low**: Two or more dimensions are poor/minimal/broken, or query is fundamentally flawed

---

### Input Data:

**Query:**
{query}

**Original Code (with line numbers):**
{code_with_numbers}

**Diff (deletions marked with -):**
```diff
{diff}
```

---

### Your Task:
1. Provide concise reasoning for each dimension (1 sentences per dimension)
2. Assign ratings: query_quality (good/acceptable/poor), deletion_relevance (appropriate/minimal/excessive), semantic_preservation (preserved/partially_preserved/broken)
3. Determine overall_quality (low/medium/high)

Output JSON format (no code fences, just JSON):
{{
  "reasoning": "<Brief analysis covering all three dimensions>",
  "query_quality": "<good|acceptable|poor>",
  "deletion_relevance": "<appropriate|minimal|excessive>",
  "semantic_preservation": "<preserved|partially_preserved|broken>",
  "overall_quality": "<low|medium|high>"
}}
"""

# Allowed values per dimension (lowercased, used for validation/normalization).
_ALLOWED = {
    "query_quality": {"good", "acceptable", "poor"},
    "deletion_relevance": {"appropriate", "minimal", "excessive"},
    "semantic_preservation": {"preserved", "partially_preserved", "broken"},
    "overall_quality": {"low", "medium", "high"},
}
_RATING_KEYS = list(_ALLOWED.keys())


def _strip_thinking(text: str) -> str:
    """Drop a leading <think>...</think> block emitted by reasoning models."""
    if "</think>" in text:
        return text.rsplit("</think>", 1)[1]
    return text


def fetch_quality_from_output(out: str) -> Optional[Dict[str, str]]:
    """Parse the judge's JSON verdict into a dict, or None if unparseable.

    Returns keys: reasoning, query_quality, deletion_relevance,
    semantic_preservation, overall_quality. Ratings are lowercased and validated
    against the allowed value sets; overall_quality is required (None otherwise).
    """
    text = _strip_thinking(out)
    text = re.sub(r"```[a-zA-Z]*\s*|\s*```", "", text).strip()

    result: Optional[Dict[str, str]] = None
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            result = None

    if not isinstance(result, dict):
        # Regex fallback: pull each field individually.
        result = {}
        for key in ["reasoning"] + _RATING_KEYS:
            m = re.search(rf'"{key}"\s*:\s*"(.*?)"', text, re.DOTALL)
            if m:
                result[key] = m.group(1).strip()

    if not result:
        return None

    normalized: Dict[str, str] = {"reasoning": str(result.get("reasoning", "")).strip()}
    for key in _RATING_KEYS:
        val = str(result.get(key, "")).strip().lower().replace(" ", "_").replace("-", "_")
        normalized[key] = val if val in _ALLOWED[key] else ""

    # overall_quality is the field everything downstream keys on; require it.
    if normalized["overall_quality"] not in _ALLOWED["overall_quality"]:
        return None
    return normalized
