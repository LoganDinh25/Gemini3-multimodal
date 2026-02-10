"""
Cost Engine - Deterministic cost computation (no Gemini for numbers).

Computes baseline vs optimized total cost and breakdown (by_mode, by_commodity).
Used so Gemini only explains savings from pre-computed figures.
"""

from typing import Dict, Any, Optional


# ---------------------------------------------------------------------------
# Solution JSON schema (normalized for baseline_solution.json / optimized_solution.json)
# ---------------------------------------------------------------------------
# Expected keys (at least one of):
#   - total_cost: float
#   - top_routes: list of {
#       "commodity": str,
#       "mode": str,           # "road" | "waterway" | "multi-modal"
#       "cost": float,         # total cost for this route (or per-unit; see cost_params)
#       "flow": float,
#       "demand_od": float,
#       "od_pair": [o, d],
#       ...
#     }
# cost_params (optional): { "cost_is_per_unit": bool } -> if True, route cost is per unit, total += cost * flow
# ---------------------------------------------------------------------------


def compute_total_cost(
    solution_json: Dict[str, Any],
    cost_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute total cost and breakdown from a solution JSON (deterministic).

    Args:
        solution_json: Solution dict with total_cost and/or top_routes.
        cost_params: Optional. e.g. {"cost_is_per_unit": True} -> route cost * flow.
                     Default: cost is total per route (sum of route["cost"]).

    Returns:
        {
            "total": float,
            "by_mode": { "road": float, "waterway": float, "multi-modal": float, ... },
            "by_commodity": { "Passenger": float, "Rice": float, ... },
        }
    """
    cost_params = cost_params or {}
    cost_is_per_unit = cost_params.get("cost_is_per_unit", False)

    total = float(solution_json.get("total_cost", 0.0))
    by_mode: Dict[str, float] = {}
    by_commodity: Dict[str, float] = {}

    routes = solution_json.get("top_routes") or solution_json.get("routes") or []
    if routes:
        total = 0.0
        for r in routes:
            c = float(r.get("cost", 0.0))
            f = float(r.get("flow", 1.0))
            if cost_is_per_unit:
                c = c * f
            total += c
            mode = (r.get("mode") or "multi-modal").strip().lower()
            if not mode:
                mode = "multi-modal"
            by_mode[mode] = by_mode.get(mode, 0.0) + c
            comm = (r.get("commodity") or "Unknown").strip()
            by_commodity[comm] = by_commodity.get(comm, 0.0) + c

    return {
        "total": round(total, 2),
        "by_mode": {k: round(v, 2) for k, v in sorted(by_mode.items())},
        "by_commodity": {k: round(v, 2) for k, v in sorted(by_commodity.items())},
    }


def compare_costs(
    baseline_dict: Dict[str, Any],
    optimized_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare baseline vs optimized cost breakdown.

    Args:
        baseline_dict: Output of compute_total_cost(baseline_solution, ...).
        optimized_dict: Output of compute_total_cost(optimized_solution, ...).

    Returns:
        {
            "baseline": { "total": ..., "by_mode": {...}, "by_commodity": {...} },
            "optimized": { "total": ..., "by_mode": {...}, "by_commodity": {...} },
            "savings_abs": float,
            "savings_pct": float,
        }
    """
    b_total = float(baseline_dict.get("total", 0.0))
    o_total = float(optimized_dict.get("total", 0.0))
    savings_abs = round(b_total - o_total, 2)
    savings_pct = round((savings_abs / b_total * 100.0) if b_total else 0.0, 2)

    return {
        "baseline": {
            "total": b_total,
            "by_mode": baseline_dict.get("by_mode") or {},
            "by_commodity": baseline_dict.get("by_commodity") or {},
        },
        "optimized": {
            "total": o_total,
            "by_mode": optimized_dict.get("by_mode") or {},
            "by_commodity": optimized_dict.get("by_commodity") or {},
        },
        "savings_abs": savings_abs,
        "savings_pct": savings_pct,
    }


def compute_total_cost_from_solution_file(
    solution_path: str,
    cost_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Load solution JSON from file and return cost breakdown (convenience).
    """
    import json
    from pathlib import Path

    path = Path(solution_path)
    if not path.exists():
        return {"total": 0.0, "by_mode": {}, "by_commodity": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return compute_total_cost(data, cost_params)
