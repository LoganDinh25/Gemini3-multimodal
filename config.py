"""
Configuration file for Graph-Aware Logistics Planner
Centralized settings and paths
"""

from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# Region-specific paths
REGION_PATHS = {
    "Mekong": {
        "nodes": DATA_DIR / "Mekong" / "nodes_remapped_with_coords.csv",
        "arcs": DATA_DIR / "Mekong" / "arcs_remapped.csv",
        "demand": None  # Generated from nodes
    },
    "Toy Region": {
        "nodes": DATA_DIR / "toy_region" / "nodes.csv",
        "arcs": DATA_DIR / "toy_region" / "edges.csv",
        "demand": DATA_DIR / "toy_region" / "demand.csv"
    }
}

# Optimization results paths
def get_optimization_results_path(region: str, period: int) -> Path:
    """Get path to optimization results JSON file"""
    region_dir = DATA_DIR / region.lower().replace(' ', '_')
    return region_dir / f"optimization_results_period{period}.json"

# Gemini API settings
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
# Gemini API Key – Project: projects/223068287414 (Project number: 223068287414)
GEMINI_API_KEY = "AIzaSyAgAZu1kmuu8WhlIaWK7PlPHUVwDiMhaKc"
# gemini-pro deprecated 2025; use gemini-2.5-flash (stable) or gemini-2.5-pro
GEMINI_MODEL = "gemini-2.5-flash"

# Optimization settings
DEFAULT_PRIORITY = 0.5  # 0 = cost, 1 = speed
DEFAULT_PERIOD = 1
DEFAULT_COMMODITY = "Rice"

# UI Settings
APP_TITLE = "Graph-Aware Logistics Planner"
APP_SUBTITLE = "Powered by Gemini 3"
APP_TAGLINE = "Turn complex transport networks into explainable decisions"
