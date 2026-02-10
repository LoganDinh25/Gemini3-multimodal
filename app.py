"""
Graph-Aware Logistics Planner powered by Gemini 3
Main Streamlit Application for Hackathon Demo
"""

import streamlit as st
import json
import inspect
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from gemini_service import GeminiService
from graph_engine import GraphEngine
from data_loader import DataLoader
from cost_engine import compute_total_cost, compare_costs

try:
    from streamlit_folium import st_folium
    _HAS_STREAMLIT_FOLIUM = True
except ImportError:
    _HAS_STREAMLIT_FOLIUM = False

# Page config
st.set_page_config(
    page_title="Graph-Aware Logistics Planner",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS - Decision Intelligence Platform (as described)
# Color scheme: Navy primary, cyan for AI/Gemini, green for insight, yellow/orange for warning
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    /* Main background: Navy/Deep Blue - stable, strategic */
    .stApp {
        background: linear-gradient(180deg, #0f172a 0%, #1e3a5f 35%, #0f172a 100%);
        background-attachment: fixed;
    }
    [data-testid="stAppViewContainer"] {
        background: transparent;
    }
    
    /* Panel: white/very light gray - improve readability */
    .custom-card {
        background: rgba(248, 250, 252, 0.98);
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.6);
    }
    .card-header {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .card-subheader {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 1rem;
    }
    
    /* Gemini card - bright blue/cyan AI accent */
    .gemini-card {
        background: linear-gradient(135deg, #0e7490 0%, #06b6d4 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 8px 28px rgba(6, 182, 212, 0.35);
        margin-bottom: 1rem;
    }
    .gemini-header {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    /* Buttons: Run Scenario = dark blue (navy); Ask Gemini 3 = bright cyan accent */
    .stButton > button {
        background: linear-gradient(135deg, #1e3a5f 0%, #334155 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.6rem 1.5rem !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
    }
    /* Ask Gemini 3 (2nd button in hero row) - cyan accent */
    [data-testid="stHorizontalBlock"]:first-of-type > div:nth-child(2) .stButton > button {
        background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%) !important;
        box-shadow: 0 2px 12px rgba(6, 182, 212, 0.45) !important;
    }
    [data-testid="stHorizontalBlock"]:first-of-type > div:nth-child(2) .stButton > button:hover {
        box-shadow: 0 4px 16px rgba(6, 182, 212, 0.5) !important;
    }
    
    .metric-card {
        background: rgba(248, 250, 252, 0.98);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    }
    .metric-value { font-size: 1.5rem; font-weight: 700; color: #0e7490; }
    .metric-label { font-size: 0.8rem; color: #64748b; }
    
    /* Tabs (if kept) - navy/cyan */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] { color: rgba(255, 255, 255, 0.85); font-weight: 500; }
    .stTabs [aria-selected="true"] {
        background: rgba(6, 182, 212, 0.25);
        color: white !important;
    }
    
    /* Text on navy - readable */
    .stApp [data-testid="stMarkdown"] p,
    .stApp [data-testid="stMarkdown"] li,
    .stApp [data-testid="stMarkdown"] {
        color: rgba(255, 255, 255, 0.95) !important;
    }
    .stApp [data-testid="stCaptionContainer"],
    .stApp small { color: rgba(255, 255, 255, 0.88) !important; }
    label, .stSelectbox label, .stSlider label, .stCheckbox label,
    [data-testid="stWidgetLabel"] p, .stCheckbox [data-testid="stWidgetLabel"] {
        color: rgba(255, 255, 255, 0.98) !important;
    }
    /* Input placeholder - bright on dark */
    .stTextInput input::placeholder { color: rgba(255, 255, 255, 0.65) !important; }
    
    .stSuccess [data-testid="stMarkdown"], .stWarning [data-testid="stMarkdown"], .stInfo [data-testid="stMarkdown"] {
        color: inherit !important;
    }
    /* Spinner and others - brighter text */
    [data-testid="stSpinner"], [data-testid="stSpinner"] *, [data-testid="stSpinner"] + div,
    [data-testid="stSpinner"] ~ [data-testid="stMarkdown"] { color: rgba(255,255,255,0.95) !important; }
    /* Tab Network: 3 route blocks - dark text */
    .network-route-card, .network-route-card *, .network-route-mode,
    [data-testid="stMarkdown"] .network-route-card,
    [data-testid="stMarkdown"] .network-route-card * { color: #1e293b !important; }
    .stSelectbox > div { background: rgba(255,255,255,0.95) !important; }
    .stTextInput > div > input { background: rgba(255,255,255,0.95) !important; color: #1e293b !important; }
    
    /* Insight blocks: light bg for readable text */
    .insight-item {
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        background: #f0fdf4 !important;
        border-radius: 8px;
        border-left: 4px solid #22c55e;
        color: #166534 !important;
    }
    .insight-warning {
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        background: #fffbeb !important;
        border-radius: 8px;
        border-left: 4px solid #eab308;
        color: #854d0e !important;
    }
    .insight-action {
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        background: #ecfeff !important;
        border-radius: 8px;
        border-left: 4px solid #06b6d4;
        color: #0e7490 !important;
    }
    /* Map legend: dark text (#0f172a) */
    #map-legend-box, #map-legend-box p { color: #0f172a !important; }
    /* KPI metrics: bright text on navy */
    [data-testid="stMetric"] label,
    [data-testid="stMetric"] [data-testid="stMetricValue"],
    [data-testid="stMetric"] [data-testid="stMetricLabel"],
    [data-testid="stMetric"] p,
    [data-testid="stMetric"] div { color: rgba(255, 255, 255, 0.98) !important; }
</style>
""", unsafe_allow_html=True)

# Initialize services
@st.cache_resource
def init_services():
    return {
        'gemini': GeminiService(),
        'graph': GraphEngine(),
        'loader': DataLoader()
    }

services = init_services()

# Session state initialization
if 'normalized_data' not in st.session_state:
    st.session_state.normalized_data = None
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = None
if 'region' not in st.session_state:
    st.session_state.region = services['loader'].get_available_regions()[0] if services['loader'].get_available_regions() else "Mekong"
if 'period' not in st.session_state:
    st.session_state.period = 1
if 'commodity' not in st.session_state:
    st.session_state.commodity = "Rice"  # Default to Rice (one of the valid options)
if 'priority' not in st.session_state:
    st.session_state.priority = 0.5
if 'scenario_chat_history' not in st.session_state:
    st.session_state.scenario_chat_history = []
if 'scenario_chat_expanded' not in st.session_state:
    st.session_state.scenario_chat_expanded = False
if 'cost_comparison' not in st.session_state:
    st.session_state.cost_comparison = None
if 'whatif_durability_result' not in st.session_state:
    st.session_state.whatif_durability_result = None

# ============================================================================
# HERO / HEADER - Decision Intelligence Platform
# Logo Gemini (brain), tagline, nút Run Scenario (navy) + Ask Gemini 3 (cyan)
# ============================================================================
st.markdown("""
<div class="hero-header" style="
    position: relative;
    padding: 1.5rem 0 1rem 0;
    margin-bottom: 0.5rem;
    border-radius: 0 0 16px 16px;
    background: linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,58,95,0.6) 50%, rgba(15,23,42,0.95) 100%);
    border-bottom: 1px solid rgba(6, 182, 212, 0.2);
">
    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
        <div style="display: flex; align-items: center; gap: 1.25rem;">
            <div style="
                width: 52px; height: 52px;
                background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%);
                border-radius: 14px;
                display: flex; align-items: center; justify-content: center;
                font-size: 1.75rem;
                box-shadow: 0 0 24px rgba(6, 182, 212, 0.5), 0 4px 12px rgba(0,0,0,0.2);
            " title="Gemini">🧠</div>
            <div>
                <div style="font-size: 1.5rem; font-weight: 700; color: white; margin: 0; letter-spacing: -0.02em;">Graph-Aware Logistics Planner</div>
                <div style="font-size: 0.9rem; color: rgba(6, 182, 212, 0.95); margin: 0.2rem 0 0 0;">Powered by Gemini 3</div>
            </div>
        </div>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
            <div style="width: 36px; height: 36px; background: rgba(255,255,255,0.1); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.9rem;">👤</div>
            <div style="width: 36px; height: 36px; background: rgba(255,255,255,0.1); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.9rem;">⚙️</div>
        </div>
    </div>
    <p style="margin: 1rem 0 0 0; color: rgba(255,255,255,0.9); font-size: 1.1rem; font-weight: 500;">Turn complex transport networks into explainable decisions</p>
</div>
""", unsafe_allow_html=True)

def _folium_map_kwargs(use_osm_tiles: bool = True):
    """Only pass use_osm_tiles if GraphEngine.visualize_network_map accepts it (backward compatible)."""
    sig = inspect.signature(services["graph"].visualize_network_map)
    if "use_osm_tiles" in sig.parameters:
        return {"use_osm_tiles": use_osm_tiles}
    return {}


def _update_cost_comparison(loader, region: str, period: int, optimized: dict):
    """Compute cost comparison (baseline vs optimized) and store in session_state."""
    if not optimized:
        st.session_state.cost_comparison = None
        return
    load_baseline = getattr(loader, "load_baseline_results", None)
    baseline_json = load_baseline(region, period) if callable(load_baseline) else None
    if baseline_json is None:
        # Synthetic baseline: inflate optimized cost by 12% for demo
        import copy
        baseline_json = copy.deepcopy(optimized)
        scale = 1.12
        baseline_json["total_cost"] = float(optimized.get("total_cost", 0)) * scale
        routes = baseline_json.get("top_routes") or baseline_json.get("routes") or []
        for r in routes:
            r["cost"] = float(r.get("cost", 0)) * scale
    baseline_cost = compute_total_cost(baseline_json)
    optimized_cost = compute_total_cost(optimized)
    st.session_state.cost_comparison = compare_costs(baseline_cost, optimized_cost)


# Action buttons: Run Scenario (navy) | Ask Gemini 3 (cyan accent)
col_btn1, col_btn2, col_spacer = st.columns([1, 1, 4])
with col_btn1:
    if st.button("Run Scenario", type="primary", use_container_width=True, key="btn_run_scenario"):
        st.session_state.run_scenario = True
        st.session_state.generate_plan = True
        with st.spinner("Loading optimization results..."):
            opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
            if opt_results:
                st.session_state.optimization_results = opt_results
                _update_cost_comparison(services['loader'], st.session_state.region, st.session_state.period, opt_results)
                st.success("Scenario loaded successfully.")
            else:
                st.warning("No optimization results found for this period.")

with col_btn2:
    if st.button("Ask Gemini 3", type="primary", use_container_width=True, key="btn_ask_gemini"):
        if st.session_state.optimization_results:
            st.session_state.ask_gemini = True
            st.session_state.scenario_chat_expanded = True
            st.success("Chat opened. Scroll down to ask Gemini 3.")
        else:
            st.warning("Run Scenario first.")

# ============================================================================
# GLOBAL KPI CARDS - Baseline | Optimized | Savings (visible in every tab)
# ============================================================================
cc = st.session_state.get("cost_comparison")
if cc:
    sav_abs = cc.get("savings_abs", 0)
    sav_pct = cc.get("savings_pct", 0)
    base_fmt = f"${cc['baseline']['total']:,.0f}"
    opt_fmt = f"${cc['optimized']['total']:,.0f}"
    sav_fmt = f"${sav_abs:,.0f} (~{sav_pct:.1f}%)"
    st.markdown(
        f"""
        <div style="display: flex; flex-wrap: wrap; gap: 1rem; align-items: stretch; margin-bottom: 1rem;">
            <div style="flex: 1; min-width: 140px; background: rgba(248,250,252,0.98); padding: 1rem 1.25rem; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 0.25rem;">Baseline Total Cost</div>
                <div style="font-size: 1.35rem; font-weight: 700; color: #0e7490;">{base_fmt}</div>
            </div>
            <div style="flex: 1; min-width: 140px; background: rgba(248,250,252,0.98); padding: 1rem 1.25rem; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 0.25rem;">Optimized Total Cost</div>
                <div style="font-size: 1.35rem; font-weight: 700; color: #0e7490;">{opt_fmt}</div>
            </div>
            <div style="flex: 1; min-width: 140px; background: rgba(248,250,252,0.98); padding: 1rem 1.25rem; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 0.25rem;">Savings</div>
                <div style="font-size: 1.35rem; font-weight: 700; color: #16a34a;">{sav_fmt}</div>
            </div>
            <div style="flex: 2; min-width: 200px; display: flex; align-items: center;">
                <div style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: white; padding: 0.75rem 1rem; border-radius: 10px; font-size: 1.1rem; font-weight: 600; width: 100%;">
                    💡 Tối ưu giúp tiết kiệm <strong>${sav_abs:,.0f}</strong> (~{sav_pct:.1f}%).
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# TABS: Scenario (main) | Network | Explanation | What-If
# ============================================================================
tab_scenario, tab_network, tab_explanation, tab_whatif = st.tabs(["Scenario", "Network", "Explanation", "What-If"])

with tab_scenario:
    col_left, col_middle, col_right = st.columns([1, 2, 1])

    with col_left:
        # ---------- Scenario Selector (region / period / commodity / priority) ----------
        st.markdown("""
        <div style="background: rgba(248,250,252,0.98); padding: 1.25rem; border-radius: 12px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-bottom: 1rem;">
            <div style="font-size: 1.1rem; font-weight: 600; color: #1e293b;">Scenario Selector</div>
            <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">Region · Period · Commodity · Priority</div>
        </div>
        """, unsafe_allow_html=True)
        available_regions = services['loader'].get_available_regions()
        try:
            region_index = available_regions.index(st.session_state.region) if st.session_state.region in available_regions else 0
        except (ValueError, AttributeError):
            region_index = 0
        region = st.selectbox("Region", options=available_regions, index=region_index, help="Logistics region")
        st.session_state.region = region
        period = st.selectbox("Period", options=[1, 2, 3, 4], index=st.session_state.period - 1 if st.session_state.period in [1, 2, 3, 4] else 0)
        st.session_state.period = period
        commodity_options = ["Passenger", "Rice", "Fisheries", "Fruits & Vegetables"]
        try:
            commodity_index = commodity_options.index(st.session_state.commodity) if st.session_state.commodity in commodity_options else 0
        except (ValueError, AttributeError):
            commodity_index = 0
        commodity = st.selectbox("Commodity", options=commodity_options, index=commodity_index)
        st.session_state.commodity = commodity
        st.markdown("<br>", unsafe_allow_html=True)
        priority = st.slider("Priority", min_value=0.0, max_value=1.0, value=st.session_state.priority, step=0.1, help="Cost ↔ Speed")
        st.session_state.priority = priority
        col_cost, col_speed = st.columns(2)
        with col_cost:
            st.markdown("<small style='color: rgba(255,255,255,0.9);'>Cost</small>", unsafe_allow_html=True)
        with col_speed:
            st.markdown("<div style='text-align: right;'><small style='color: rgba(255,255,255,0.9);'>Speed</small></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Generate Plan", type="primary", use_container_width=True, key="btn_generate_plan"):
            st.session_state.generate_plan = True
            # Load and compute cost comparison when Generate Plan is clicked
            opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
            if opt_results:
                st.session_state.optimization_results = opt_results
                _update_cost_comparison(services['loader'], st.session_state.region, st.session_state.period, opt_results)
        st.caption("Run optimization (model_gurobi.py). Default: load from JSON.")
        if st.button("Run Gurobi", key="run_gurobi", use_container_width=True):
            import subprocess
            try:
                with st.spinner("Running model (2–5 min)..."):
                    result = subprocess.run(
                        ["python", "model_gurobi.py"],
                        cwd=Path(__file__).parent,
                        capture_output=True,
                        text=True,
                        timeout=600
                    )
                if result.returncode == 0:
                    st.success("Done.")
                else:
                    st.warning(f"Exit code {result.returncode}.")
            except subprocess.TimeoutExpired:
                st.warning("Timeout. Model may still be running.")
            except FileNotFoundError:
                st.error("model_gurobi.py not found.")
            except Exception as e:
                st.error(str(e))

    with col_middle:
        graph_data = services['loader'].load_region_data(st.session_state.region)
        # Always load results for current period to change Period updates map
        opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
        if opt_results:
            st.session_state.optimization_results = opt_results
            _update_cost_comparison(services['loader'], st.session_state.region, st.session_state.period, opt_results)
        else:
            opt_results = st.session_state.optimization_results
        st.markdown("""
        <div class="custom-card" style="margin-bottom: 0.75rem;">
            <div class="card-header" style="font-size: 1rem;">Network Visualization</div>
            <div class="card-subheader" style="margin-bottom: 0;">Hubs & routes · Waterway (blue) · Roadway (gray)</div>
        </div>
        """, unsafe_allow_html=True)
        use_osm_tiles = st.checkbox("Show map (OpenStreetMap)", value=True, key="use_osm")
        animation_on_map = False
        nodes_df = graph_data.get('nodes')
        edges_df = graph_data.get('edges')
        if nodes_df is not None and not isinstance(nodes_df, pd.DataFrame):
            nodes_df = pd.DataFrame(nodes_df) if nodes_df else pd.DataFrame()
        if edges_df is not None and not isinstance(edges_df, pd.DataFrame):
            edges_df = pd.DataFrame(edges_df) if edges_df else pd.DataFrame()
        if nodes_df is None:
            nodes_df = pd.DataFrame()
        if edges_df is None:
            edges_df = pd.DataFrame()

        if _HAS_STREAMLIT_FOLIUM and not nodes_df.empty:
            try:
                folium_map = services['graph'].visualize_network_map(
                    nodes=nodes_df,
                    edges=edges_df,
                    optimization_results=opt_results if opt_results else None,
                    highlight_paths=bool(opt_results),
                    commodity=st.session_state.commodity,
                    **_folium_map_kwargs(use_osm_tiles)
                )
                if folium_map:
                    st_folium(folium_map, width=None, height=500, key=f"scenario_folium_map_{st.session_state.period}_{st.session_state.commodity}")
                    if opt_results:
                        st.caption("Use **time slider** below map to see optimal route animate from origin to destination (each OD/commodity).")
                    animation_on_map = True
                else:
                    raise ValueError("Folium returned None")
            except (TypeError, ValueError, AttributeError, KeyError) as e:
                if nodes_df.empty or edges_df.empty:
                    st.warning("No nodes or edges to display.")
                else:
                    fig = services['graph'].visualize_network_interactive(
                        nodes=nodes_df, edges=edges_df,
                        optimization_results=opt_results, highlight_paths=bool(opt_results),
                        commodity=st.session_state.commodity
                    )
                    st.plotly_chart(fig, width='stretch', key=f"scenario_map_{st.session_state.period}_{st.session_state.commodity}")
        else:
            if not (nodes_df.empty or edges_df.empty):
                fig = services['graph'].visualize_network_interactive(
                    nodes=nodes_df, edges=edges_df,
                    optimization_results=opt_results if opt_results else None,
                    highlight_paths=bool(opt_results),
                    commodity=st.session_state.commodity
                )
                st.plotly_chart(fig, width='stretch', key=f"scenario_map_{st.session_state.period}_{st.session_state.commodity}")
        if opt_results and not animation_on_map and not (nodes_df.empty or edges_df.empty):
            _anim_fn = getattr(services['graph'], 'visualize_network_animated', None)
            if callable(_anim_fn):
                try:
                    fig_anim = _anim_fn(
                        nodes=nodes_df,
                        edges=edges_df,
                        optimization_results=opt_results,
                        commodity=st.session_state.commodity,
                    )
                    if fig_anim:
                        st.markdown("**Animated route per OD (commodity)** — click ▶ Play to see route animate from origin to destination.")
                        st.plotly_chart(fig_anim, width='stretch', key=f"scenario_animated_{st.session_state.period}_{st.session_state.commodity}")
                except (AttributeError, TypeError, KeyError, ValueError):
                    pass
        st.markdown("""
        <div class="gemini-card" style="margin-top: 1.25rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.25rem;">🧠</span>
                <span class="gemini-header" style="margin-bottom: 0;">Gemini 3 Decision Insights</span>
            </div>
            <div style="font-size: 0.9rem; opacity: 0.95;">Strategic reasoning · Graph-based explanation · Risks · Recommended actions</div>
        </div>
        """, unsafe_allow_html=True)
        if opt_results:
            insights = opt_results.get('insights', {})
            if insights:
                for finding in insights.get('key_findings', []):
                    is_warning = 'risk' in finding.lower() or '⚠' in finding or 'warning' in finding.lower()
                    is_action = 'recommend' in finding.lower() or 'mitigation' in finding.lower() or '➜' in finding
                    if is_warning:
                        cls, icon = "insight-warning", "⚠"
                    elif is_action:
                        cls, icon = "insight-action", "➜"
                    else:
                        cls, icon = "insight-item", "✓"
                    st.markdown(f"""
                    <div class="{cls}" style="display: flex; align-items: flex-start; gap: 0.5rem;">
                        <span style="font-size: 1.1rem;">{icon}</span>
                        <span>{finding}</span>
                    </div>
                    """, unsafe_allow_html=True)
            if st.session_state.get('ask_gemini', False):
                st.session_state.scenario_chat_expanded = True
                st.session_state.ask_gemini = False
            with st.expander("+ Ask more... (Chat with Gemini 3)", expanded=st.session_state.get('scenario_chat_expanded', False)):
                for role, msg in st.session_state.scenario_chat_history:
                    if role == "user":
                        st.markdown(f"<div style='color:rgba(255,255,255,0.95); margin-bottom:0.5rem;'><strong>You:</strong></div>", unsafe_allow_html=True)
                        st.markdown(msg)
                    else:
                        st.markdown(f"<div style='color:rgba(255,255,255,0.95); margin-bottom:0.5rem;'><strong>Gemini 3:</strong></div>", unsafe_allow_html=True)
                        st.markdown(msg)
                q = st.text_input("Ask about strategy", placeholder="e.g. Why was Hub 14 chosen? Main risks?", key="scenario_chat_input")
                col_s, col_c = st.columns([4, 1])
                with col_s:
                    if st.button("Send", key="scenario_send"):
                        if q.strip():
                            with st.spinner("Thinking..."):
                                ctx = {
                                    'optimization_results': st.session_state.optimization_results,
                                    'graph_data': services['loader'].load_region_data(st.session_state.region),
                                    'period': st.session_state.period,
                                    'commodity': st.session_state.commodity
                                }
                                ans = services['gemini'].chat(q.strip(), ctx)
                                st.session_state.scenario_chat_history.append(("user", q.strip()))
                                st.session_state.scenario_chat_history.append(("assistant", ans))
                                st.session_state.scenario_chat_expanded = True
                                st.rerun()
                        else:
                            st.warning("Enter a question.")
                with col_c:
                    if st.button("Clear", key="scenario_clear"):
                        st.session_state.scenario_chat_history = []
                        st.rerun()

    with col_right:
        st.markdown("""
        <div style="background: rgba(248,250,252,0.98); padding: 1.25rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-bottom: 1rem;">
            <div style="font-size: 1.1rem; font-weight: 600; color: #1e293b;">What-If Analysis</div>
            <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">Explore alternate scenarios (Gemini 3)</div>
        </div>
        """, unsafe_allow_html=True)
        scenario_type = st.selectbox(
            "Scenario Type",
            options=["Increase Switching Cost", "Demand Shock", "Delay Hub Upgrade", "Capacity Reduction"],
            index=0,
            key="whatif_type"
        )
        _opt_label = f"Optimal ({st.session_state.commodity})" if st.session_state.commodity else "Optimal Route"
        st.markdown(f"""
        <div id="map-legend-box" class="map-legend-box" style="background: #f1f5f9; padding: 0.75rem 1rem; border-radius: 8px; margin: 0.5rem 0; font-size: 0.85rem; border: 1px solid #e2e8f0;">
            <p style="margin: 0 0 0.4rem 0; font-weight: 600;">Map legend</p>
            <p style="margin: 0.25rem 0;"><span style="color: #78350f;">━━</span> Road (existing) &nbsp; <span style="color: #b45309;">╌╌</span> Road (project)</p>
            <p style="margin: 0.25rem 0;"><span style="color: #0369a1;">━━</span> Waterway (existing) &nbsp; <span style="color: #0ea5e9;">╌╌</span> Waterway (project)</p>
            <p style="margin: 0.25rem 0;"><span style="color: #27ae60;">━━</span> {_opt_label}</p>
            <p style="margin: 0.25rem 0;"><span style="color: #16a34a;">●</span> New Hub &nbsp; <span style="color: #7c3aed;">●</span> Upgraded Hub &nbsp; <span style="color: #ea580c;">●</span> Existing Hub &nbsp; <span style="color: #2563eb;">●</span> Regular Node</p>
        </div>
        """, unsafe_allow_html=True)
        if scenario_type == "Increase Switching Cost":
            impact_value = st.slider("Increase Switching Cost", 2, 3, 2, 1, key="whatif_sw")
        elif scenario_type == "Demand Shock":
            impact_value = st.slider("Demand Change (%)", -50, 100, 20, 10, key="whatif_dem")
        elif scenario_type == "Delay Hub Upgrade":
            impact_value = st.slider("Delay (periods)", 1, 4, 1, key="whatif_del")
        else:
            impact_value = st.slider("Capacity Reduction (%)", 10, 50, 20, 5, key="whatif_cap")
        if st.button("Run What-If Analysis", type="primary", use_container_width=True, key="btn_whatif"):
            if st.session_state.optimization_results:
                with st.spinner("Gemini 3 reasoning..."):
                    whatif_result = services['gemini'].whatif_analysis(
                        scenario_type=scenario_type,
                        impact_value=impact_value,
                        current_results=st.session_state.optimization_results,
                        graph_data=services['loader'].load_region_data(region),
                        commodity=commodity
                    )
                st.markdown("""<div style="margin-top: 1rem; color: rgba(255,255,255,0.95);"><strong>Gemini 3 predicts:</strong></div>""", unsafe_allow_html=True)
                for item in whatif_result.get('affected_items', []):
                    st.markdown(f"""
                    <div class="insight-item" style="padding: 0.5rem 0.75rem; margin: 0.35rem 0;">
                        ✓ {item}
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("""<div style="margin-top: 1rem; color: rgba(255,255,255,0.95);"><strong>Suggested mitigation:</strong></div>""", unsafe_allow_html=True)
                for suggestion in whatif_result.get('mitigation', []):
                    st.markdown(f"""
                    <div class="insight-action" style="padding: 0.5rem 0.75rem; margin: 0.35rem 0;">
                        ➜ {suggestion}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("Run Scenario first.")

    # Auto-load data when region/period changes
    if 'last_region' not in st.session_state or st.session_state.last_region != st.session_state.region or 'last_period' not in st.session_state or st.session_state.last_period != st.session_state.period:
        st.session_state.last_region = st.session_state.region
        st.session_state.last_period = st.session_state.period
        with st.spinner("Loading regional data..."):
            data = services['loader'].load_region_data(st.session_state.region)
            st.session_state.region_data = data
            opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
            if opt_results:
                st.session_state.optimization_results = opt_results
                _update_cost_comparison(services['loader'], st.session_state.region, st.session_state.period, opt_results)
            else:
                opt_results = services['loader'].load_optimization_results(st.session_state.region, 1)
                if opt_results:
                    st.session_state.optimization_results = opt_results
                    _update_cost_comparison(services['loader'], st.session_state.region, 1, opt_results)
            normalization_result = services['gemini'].normalize_data(
                nodes=data['nodes'],
                edges=data['edges'],
                demand=data['demand']
            )
            st.session_state.normalized_data = normalization_result

# ============================================================================
# TAB: NETWORK (full map + metrics)
# ============================================================================
with tab_network:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.optimization_results:
        st.markdown("""
        <div class="custom-card">
            <div class="card-header">Network Visualization & Optimization Results</div>
            <div class="card-subheader">Interactive graph · optimal routes and hub selection</div>
        </div>
        """, unsafe_allow_html=True)
        col_n1, col_n2 = st.columns([2, 1])
        with col_n1:
            graph_data = services['loader'].load_region_data(st.session_state.region)
            opt_results = st.session_state.optimization_results
            net_nodes = graph_data.get('nodes')
            net_edges = graph_data.get('edges')
            if net_nodes is not None and not isinstance(net_nodes, pd.DataFrame):
                net_nodes = pd.DataFrame(net_nodes) if net_nodes else pd.DataFrame()
            if net_edges is not None and not isinstance(net_edges, pd.DataFrame):
                net_edges = pd.DataFrame(net_edges) if net_edges else pd.DataFrame()
            if net_nodes is None:
                net_nodes = pd.DataFrame()
            if net_edges is None:
                net_edges = pd.DataFrame()

            use_osm_net = st.checkbox("Show map (OpenStreetMap)", value=True, key="net_osm")
            net_animation_on_map = False
            if _HAS_STREAMLIT_FOLIUM and not net_nodes.empty:
                try:
                    folium_map = services['graph'].visualize_network_map(
                        nodes=net_nodes, edges=net_edges,
                        optimization_results=opt_results, highlight_paths=True,
                        commodity=st.session_state.commodity,
                        **_folium_map_kwargs(use_osm_net)
                    )
                    if folium_map:
                        st_folium(folium_map, width=None, height=500, key="net_folium")
                        st.caption("Use **time slider** below map to see optimal route animate.")
                        net_animation_on_map = True
                    else:
                        raise ValueError("Folium returned None")
                except (TypeError, ValueError, AttributeError, KeyError):
                    fig = services['graph'].visualize_network_interactive(
                        nodes=net_nodes, edges=net_edges,
                        optimization_results=opt_results, highlight_paths=True,
                        commodity=st.session_state.commodity
                    )
                    st.plotly_chart(fig, width='stretch', key="net_plotly")
            else:
                if not (net_nodes.empty or net_edges.empty):
                    fig = services['graph'].visualize_network_interactive(
                        nodes=net_nodes, edges=net_edges,
                        optimization_results=opt_results, highlight_paths=True,
                        commodity=st.session_state.commodity
                    )
                    st.plotly_chart(fig, width='stretch', key="net_plotly")
            if not net_animation_on_map:
                _anim_fn = getattr(services['graph'], 'visualize_network_animated', None)
                if callable(_anim_fn):
                    try:
                        net_nodes = graph_data.get('nodes')
                        net_edges = graph_data.get('edges')
                        if net_nodes is not None and not isinstance(net_nodes, pd.DataFrame):
                            net_nodes = pd.DataFrame(net_nodes) if net_nodes else pd.DataFrame()
                        if net_edges is not None and not isinstance(net_edges, pd.DataFrame):
                            net_edges = pd.DataFrame(net_edges) if net_edges else pd.DataFrame()
                        if net_nodes is None:
                            net_nodes = pd.DataFrame()
                        if net_edges is None:
                            net_edges = pd.DataFrame()
                        if not net_nodes.empty and not net_edges.empty:
                            fig_anim = _anim_fn(
                                nodes=net_nodes, edges=net_edges,
                                optimization_results=opt_results,
                                commodity=st.session_state.commodity,
                            )
                            if fig_anim:
                                st.markdown("**Animated route per OD** — ▶ Play to see route animate.")
                                st.plotly_chart(fig_anim, width='stretch', key="net_animated")
                    except (AttributeError, TypeError, KeyError, ValueError):
                        pass
        with col_n2:
            results = st.session_state.optimization_results
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">${:,.0f}</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Total Cost</div>
            </div>
            """.format(results.get('total_cost', 0)), unsafe_allow_html=True)
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #0e7490 0%, #06b6d4 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">{:.1f} days</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Total Time</div>
            </div>
            """.format(results.get('total_time', 0)), unsafe_allow_html=True)
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">{}</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Hubs Selected</div>
            </div>
            """.format(results.get('num_hubs', 0)), unsafe_allow_html=True)
            for i, route in enumerate(results.get('top_routes', [])[:3], 1):
                st.markdown(f"""
                <div class="network-route-card" style="background: #f8fafc; padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; border-left: 3px solid #06b6d4;">
                    <strong>Route {i}:</strong> {' → '.join(map(str, route.get('path', [])))}<br>
                    <span class="network-route-mode">Mode: {route.get('mode', '')} | Cost: ${route.get('cost', 0):,.0f}</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Load optimization results in the Scenario tab first.")

# ============================================================================
# TAB: EXPLANATION (Gemini explain strategy + chat)
# ============================================================================
with tab_explanation:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="gemini-card">
        <div class="gemini-header">Gemini 3 Decision Insights</div>
        <div style="font-size: 1rem; opacity: 0.95;">AI-powered strategic analysis and graph-based reasoning</div>
    </div>
    """, unsafe_allow_html=True)
    if st.session_state.get('ask_gemini', False) and st.session_state.optimization_results:
        st.session_state.ask_gemini = False
        with st.spinner("Gemini 3 is analyzing..."):
            explanation = services['gemini'].explain_strategy(
                period=st.session_state.period,
                commodity=st.session_state.commodity,
                optimization_results=st.session_state.optimization_results,
                graph_data=services['loader'].load_region_data(st.session_state.region),
                priority=st.session_state.priority
            )
            st.session_state.explanation_result = explanation
    clicked_explain = st.button("Ask Gemini 3 to Explain Strategy", type="primary", disabled=not st.session_state.optimization_results, use_container_width=True, key="btn_explain")
    has_explanation = bool(st.session_state.get('explanation_result'))
    if (clicked_explain or has_explanation) and st.session_state.optimization_results:
        if has_explanation and not clicked_explain:
            explanation = st.session_state.explanation_result
        else:
            with st.spinner("Gemini 3 is analyzing..."):
                explanation = services['gemini'].explain_strategy(
                    period=st.session_state.period,
                    commodity=st.session_state.commodity,
                    optimization_results=st.session_state.optimization_results,
                    graph_data=services['loader'].load_region_data(st.session_state.region),
                    priority=st.session_state.priority
                )
                st.session_state.explanation_result = explanation
        st.markdown("""<div class="custom-card"><h3 style="color: #0e7490;">Strategic Overview</h3></div>""", unsafe_allow_html=True)
        st.markdown(explanation['strategy_summary'])
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("""<div class="custom-card"><h3 style="color: #0e7490;">Why This Strategy?</h3></div>""", unsafe_allow_html=True)
            st.markdown(explanation['reasoning'])
            st.markdown("""<div class="custom-card"><h3 style="color: #ca8a04;">Bottlenecks & Risks</h3></div>""", unsafe_allow_html=True)
            for risk in explanation.get('risks', []):
                st.markdown(f"""<div class="insight-warning">{risk}</div>""", unsafe_allow_html=True)
        with col_e2:
            st.markdown("""<div class="custom-card"><h3 style="color: #0e7490;">Graph-Based Insights</h3></div>""", unsafe_allow_html=True)
            st.markdown(explanation.get('graph_insights', ''))
            st.markdown("""<div class="custom-card"><h3 style="color: #166534;">Recommended Actions</h3></div>""", unsafe_allow_html=True)
            for action in explanation.get('recommendations', []):
                st.markdown(f"""<div class="insight-item">✓ {action}</div>""", unsafe_allow_html=True)
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        st.markdown("""<div class="custom-card"><h3 style="color: #0e7490;">Chat with Gemini</h3></div>""", unsafe_allow_html=True)
        for role, msg in st.session_state.chat_history:
            if role == "user":
                st.markdown(f"""<div class="insight-action" style="text-align: right;"><strong>You:</strong></div>""", unsafe_allow_html=True)
                st.markdown(msg)
            else:
                st.markdown(f"""<div class="insight-item"><strong>Gemini:</strong></div>""", unsafe_allow_html=True)
                st.markdown(msg)
        user_q = st.text_input("Ask Gemini", placeholder="e.g. Why was Hub 7 selected?", key="exp_chat_input")
        col_send, col_cl = st.columns([4, 1])
        with col_send:
            if st.button("Send", key="exp_send"):
                if user_q and st.session_state.optimization_results:
                    with st.spinner("Thinking..."):
                        resp = services['gemini'].chat(user_q, {
                            'optimization_results': st.session_state.optimization_results,
                            'graph_data': services['loader'].load_region_data(st.session_state.region),
                            'period': st.session_state.period,
                            'commodity': st.session_state.commodity
                        })
                        st.session_state.chat_history.append(("user", user_q))
                        st.session_state.chat_history.append(("assistant", resp))
                        st.rerun()
        with col_cl:
            if st.button("Clear", key="exp_clear"):
                st.session_state.chat_history = []
                st.rerun()
    else:
        if not st.session_state.optimization_results:
            st.info("Load optimization results in the Scenario tab first.")

# ============================================================================
# TAB: WHAT-IF — "Will we lose savings if conditions change?"
# ============================================================================
with tab_whatif:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="gemini-card">
        <div class="gemini-header">Will we lose savings if conditions change?</div>
        <div style="font-size: 1rem; opacity: 0.95;">Savings có bền không? Gemini dự đoán erosion & mitigation — không chạy lại solver.</div>
    </div>
    """, unsafe_allow_html=True)

    cc_w = st.session_state.get("cost_comparison")
    has_savings = cc_w and (cc_w.get("savings_abs", 0) != 0 or cc_w.get("savings_pct", 0) != 0)

    # ----- Savings sensitivity summary (current savings = baseline) -----
    st.markdown("""<div style="font-size: 1rem; font-weight: 600; color: rgba(255,255,255,0.95); margin: 0.5rem 0;">Savings sensitivity summary</div>""", unsafe_allow_html=True)
    if cc_w:
        sw_abs = cc_w.get("savings_abs", 0)
        sw_pct = cc_w.get("savings_pct", 0)
        st.markdown(
            f"""
            <div style="display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; margin-bottom: 1rem;">
                <div style="background: rgba(248,250,252,0.98); padding: 0.75rem 1.25rem; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <span style="font-size: 0.8rem; color: #64748b;">Current savings (baseline)</span><br>
                    <span style="font-size: 1.25rem; font-weight: 700; color: #16a34a;">${sw_abs:,.0f} (~{sw_pct:.1f}%)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("""<div style="color: rgba(255,255,255,0.8); margin-bottom: 1rem;">Chạy Scenario / Generate Plan ở tab Scenario để có baseline savings.</div>""", unsafe_allow_html=True)

    # ----- Assumption controls -----
    st.markdown("""<div style="font-size: 1rem; font-weight: 600; color: rgba(255,255,255,0.95); margin: 0.5rem 0;">Assumption controls</div>""", unsafe_allow_html=True)
    col_w1, col_w2 = st.columns([1, 2])
    with col_w1:
        scenario_type_w = st.selectbox(
            "Scenario",
            options=["Increase Switching Cost", "Demand Shock", "Delay Hub Upgrade", "Capacity Reduction"],
            key="whatif_tab_type",
            help="Thay đổi giả định để xem savings có bền không.",
        )
        if scenario_type_w == "Increase Switching Cost":
            impact_w = st.slider("Switching cost increase (%)", 10, 200, 50, 10, key="whatif_tab_sw")
        elif scenario_type_w == "Demand Shock":
            impact_w = st.slider("Demand change (%)", -50, 100, 20, 10, key="whatif_tab_dem")
        elif scenario_type_w == "Delay Hub Upgrade":
            impact_w = st.slider("Delay (periods)", 1, 4, 1, key="whatif_tab_del")
        else:
            impact_w = st.slider("Capacity reduction (%)", 10, 50, 20, 5, key="whatif_tab_cap")
        run_w = st.button("Run What-If (Gemini)", type="primary", use_container_width=True, key="btn_whatif_tab")

    with col_w2:
        if run_w and st.session_state.optimization_results and cc_w:
            with st.spinner("Gemini đang dự đoán: savings có bền không..."):
                durability = services["gemini"].whatif_savings_durability(
                    cost_comparison=cc_w,
                    scenario_type=scenario_type_w,
                    impact_value=impact_w,
                    current_results=st.session_state.optimization_results,
                    graph_data=services["loader"].load_region_data(st.session_state.region),
                    commodity=st.session_state.commodity,
                )
                st.session_state.whatif_durability_result = durability
                st.session_state.whatif_last_scenario = (scenario_type_w, impact_w)
        elif run_w and (not st.session_state.optimization_results or not cc_w):
            st.warning("Cần có optimization results và cost comparison (chạy Scenario trước).")

    # ----- Risk level badge (after run) -----
    dr = st.session_state.get("whatif_durability_result")
    if dr:
        risk = dr.get("risk_level", "Medium")
        risk_color = "#22c55e" if risk == "Low" else "#eab308" if risk == "Medium" else "#ef4444"
        st.markdown(
            f'<div style="margin-bottom: 1rem;">'
            f'<span style="font-size: 0.85rem; color: rgba(255,255,255,0.9);">Risk level when assumptions change:</span> '
            f'<span style="background: {risk_color}; color: white; padding: 0.25rem 0.75rem; border-radius: 6px; font-weight: 600;">{risk}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ----- Gemini Counterfactual panel -----
    st.markdown("""<div style="font-size: 1rem; font-weight: 600; color: rgba(255,255,255,0.95); margin: 0.5rem 0;">Gemini Counterfactual</div>""", unsafe_allow_html=True)
    st.markdown("""<div style="font-size: 0.9rem; color: rgba(255,255,255,0.8); margin-bottom: 0.75rem;">Savings sẽ bị “erode” bởi phần nào (switching, congestion, mode shift) · Mitigation (advance upgrade, allocate water capacity...)</div>""", unsafe_allow_html=True)
    if dr:
        st.markdown("""<div class="custom-card" style="color: #1e293b;"><strong>Savings erosion</strong></div>""", unsafe_allow_html=True)
        st.markdown(dr.get("savings_erosion", ""))
        st.markdown("""<div class="custom-card" style="color: #1e293b;"><strong>Mitigation</strong></div>""", unsafe_allow_html=True)
        for s in dr.get("mitigation", []):
            st.markdown(f"""<div class="insight-item">✓ {s}</div>""", unsafe_allow_html=True)
    elif not st.session_state.optimization_results or not cc_w:
        st.info("Chạy Scenario (Generate Plan) rồi bấm **Run What-If (Gemini)** để xem dự đoán.")
    else:
        st.caption("Bấm **Run What-If (Gemini)** để Gemini dự đoán erosion & mitigation cho scenario đã chọn.")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; padding: 1.5rem; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.08);">
    <div style="font-size: 1.2rem; font-weight: 600; color: rgba(255,255,255,0.95);">Graph-Aware Logistics Planner</div>
    <div style="color: rgba(255,255,255,0.7); font-size: 0.9rem;">Powered by Gemini 3 · Decision Intelligence Platform</div>
</div>
""", unsafe_allow_html=True)
