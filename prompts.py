"""
Prompts for Gemini - Cost savings explanation and other flows.

Cost numbers are computed deterministically in cost_engine.py.
Gemini uses ONLY the provided comparison object to explain where savings come from.
"""

PROMPT_COST_SAVINGS_EXPLAIN = """You are a logistics analyst. Your task is to explain WHERE the cost savings come from, using ONLY the numbers provided below. Do NOT invent or recalculate any figures.

## Cost comparison (pre-computed)

{cost_comparison_json}

## Context (optional)

Graph / network summary:
{graph_summary}

Scenario / period context:
{scenario_context}

## Instructions

1. Use ONLY the numbers in the cost comparison above (baseline total, optimized total, savings_abs, savings_pct, and breakdowns by_mode and by_commodity).
2. Explain in 2–4 short paragraphs:
   - Which transport modes contributed most to the reduction (compare baseline vs optimized by_mode).
   - Which commodities saw the largest cost changes (compare by_commodity).
   - One sentence on what this means for decision-makers.
3. Do NOT add any percentages or dollar amounts that are not in the comparison object.
4. Write in a clear, professional tone. Prefer English; if the scenario context is in Vietnamese, you may mix or use Vietnamese for terms of reference.
5. Output plain text only (no JSON, no markdown headers)."""
