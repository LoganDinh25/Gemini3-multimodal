"""
Graph-Aware Logistics Planner powered by Gemini 3
Main Streamlit Application for Hackathon Demo
"""

import streamlit as st
import json
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px

from gemini_service import GeminiService
from graph_engine import GraphEngine
from data_loader import DataLoader

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

# Custom CSS - Decision Intelligence Platform (theo mô tả)
# Bảng màu: Navy chủ đạo, cyan nhấn AI/Gemini, xanh lá insight tốt, vàng/cam cảnh báo
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    /* Nền chính: Navy / Deep Blue - ổn định, chiến lược */
    .stApp {
        background: linear-gradient(180deg, #0f172a 0%, #1e3a5f 35%, #0f172a 100%);
        background-attachment: fixed;
    }
    [data-testid="stAppViewContainer"] {
        background: transparent;
    }
    
    /* Panel: nền trắng / xám rất nhạt - tăng độ đọc */
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
    
    /* Gemini card - xanh dương sáng / cyan nhấn AI */
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
    
    /* Nút: Run Scenario = xanh đậm (navy); Ask Gemini 3 = xanh sáng/cyan nổi bật */
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
    /* Ask Gemini 3 (nút thứ 2 trong hàng hero) - cyan nổi bật */
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
    
    /* Tabs (nếu giữ) - navy/cyan */
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
    
    /* Chữ trên nền navy - dễ đọc */
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
    /* Placeholder trong input - sáng trên nền tối */
    .stTextInput input::placeholder { color: rgba(255, 255, 255, 0.65) !important; }
    
    .stSuccess [data-testid="stMarkdown"], .stWarning [data-testid="stMarkdown"], .stInfo [data-testid="stMarkdown"] {
        color: inherit !important;
    }
    /* Spinner "Running model (2–5 min)..." và các spinner khác - chữ sáng hơn */
    [data-testid="stSpinner"], [data-testid="stSpinner"] *, [data-testid="stSpinner"] + div,
    [data-testid="stSpinner"] ~ [data-testid="stMarkdown"] { color: rgba(255,255,255,0.95) !important; }
    /* Tab Network: 3 route blocks - chữ màu tối (dùng span thay small để tránh .stApp small trắng) */
    .network-route-card, .network-route-card *, .network-route-mode,
    [data-testid="stMarkdown"] .network-route-card,
    [data-testid="stMarkdown"] .network-route-card * { color: #1e293b !important; }
    .stSelectbox > div { background: rgba(255,255,255,0.95) !important; }
    .stTextInput > div > input { background: rgba(255,255,255,0.95) !important; color: #1e293b !important; }
    
    /* Insight blocks: nền sáng hẳn để chữ đọc rõ (✓ ⚠ ➜) */
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
    /* Chú thích bản đồ: chữ tối (#0f172a), id ghi đè .stApp [data-testid="stMarkdown"] trắng */
    #map-legend-box, #map-legend-box p { color: #0f172a !important; }
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

# ============================================================================
# HERO / HEADER - Decision Intelligence Platform
# Logo Gemini (não/brain), tagline, nút Run Scenario (navy) + Ask Gemini 3 (cyan)
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

# Action buttons: Run Scenario (navy) | Ask Gemini 3 (cyan - nổi bật)
col_btn1, col_btn2, col_spacer = st.columns([1, 1, 4])
with col_btn1:
    if st.button("Run Scenario", type="primary", use_container_width=True, key="btn_run_scenario"):
        st.session_state.run_scenario = True
        st.session_state.generate_plan = True
        with st.spinner("Loading optimization results..."):
            opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
            if opt_results:
                st.session_state.optimization_results = opt_results
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
# TABS: Scenario (main) | Network | Explanation | What-If
# ============================================================================
tab_scenario, tab_network, tab_explanation, tab_whatif = st.tabs(["Scenario", "Network", "Explanation", "What-If"])

with tab_scenario:
    col_left, col_middle, col_right = st.columns([1, 2, 1])

    with col_left:
        # ---------- Set Transport Scenario (gọn, ít chữ) ----------
        st.markdown("""
        <div style="background: rgba(248,250,252,0.98); padding: 1.25rem; border-radius: 12px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-bottom: 1rem;">
            <div style="font-size: 1.1rem; font-weight: 600; color: #1e293b;">Set Transport Scenario</div>
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
        # Luôn load kết quả theo period hiện tại để đổi Period cập nhật map
        opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
        if opt_results:
            st.session_state.optimization_results = opt_results
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
        if _HAS_STREAMLIT_FOLIUM:
            folium_map = services['graph'].visualize_network_map(
                nodes=graph_data['nodes'],
                edges=graph_data['edges'],
                optimization_results=opt_results if opt_results else None,
                highlight_paths=bool(opt_results),
                commodity=st.session_state.commodity,
                use_osm_tiles=use_osm_tiles
            )
            if folium_map:
                st_folium(folium_map, width=None, height=500, key=f"scenario_folium_map_{st.session_state.period}_{st.session_state.commodity}")
                if opt_results:
                    st.caption("Dùng **thanh thời gian** phía dưới bản đồ để xem đường optimal vẽ dần từ điểm đầu đến điểm cuối (từng cặp OD/commodity).")
                    animation_on_map = True
            else:
                st.warning("Coordinates need WGS84. Install pyproj.")
                fig = services['graph'].visualize_network_interactive(
                    nodes=graph_data['nodes'], edges=graph_data['edges'],
                    optimization_results=opt_results, highlight_paths=bool(opt_results),
                    commodity=st.session_state.commodity
                )
                st.plotly_chart(fig, use_container_width=True, key=f"scenario_map_{st.session_state.period}_{st.session_state.commodity}")
        else:
            fig = services['graph'].visualize_network_interactive(
                nodes=graph_data['nodes'],
                edges=graph_data['edges'],
                optimization_results=opt_results if opt_results else None,
                highlight_paths=bool(opt_results),
                commodity=st.session_state.commodity
            )
            st.plotly_chart(fig, use_container_width=True, key=f"scenario_map_{st.session_state.period}_{st.session_state.commodity}")
        if opt_results and not animation_on_map:
            fig_anim = services['graph'].visualize_network_animated(
                nodes=graph_data['nodes'],
                edges=graph_data['edges'],
                optimization_results=opt_results,
                commodity=st.session_state.commodity,
            )
            if fig_anim:
                st.markdown("**Đường chuyển động theo cặp OD (commodity)** — bấm ▶ Phát để xem tuyến vẽ dần từ điểm đầu đến điểm cuối.")
                st.plotly_chart(fig_anim, use_container_width=True, key=f"scenario_animated_{st.session_state.period}_{st.session_state.commodity}")
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
            <p style="margin: 0 0 0.4rem 0; font-weight: 600;">Chú thích bản đồ</p>
            <p style="margin: 0.25rem 0;"><span style="color: #78350f;">━━</span> Đường bộ (hiện có) &nbsp; <span style="color: #b45309;">╌╌</span> Đường bộ (dự án)</p>
            <p style="margin: 0.25rem 0;"><span style="color: #0369a1;">━━</span> Đường thủy (hiện có) &nbsp; <span style="color: #0ea5e9;">╌╌</span> Đường thủy (dự án)</p>
            <p style="margin: 0.25rem 0;"><span style="color: #27ae60;">━━</span> {_opt_label}</p>
            <p style="margin: 0.25rem 0;"><span style="color: #16a34a;">●</span> Hub Mới &nbsp; <span style="color: #7c3aed;">●</span> Hub Nâng cấp &nbsp; <span style="color: #ea580c;">●</span> Hub Hiện có &nbsp; <span style="color: #2563eb;">●</span> Node thường</p>
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
            else:
                opt_results = services['loader'].load_optimization_results(st.session_state.region, 1)
                if opt_results:
                    st.session_state.optimization_results = opt_results
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
            use_osm_net = st.checkbox("Show map (OpenStreetMap)", value=True, key="net_osm")
            net_animation_on_map = False
            if _HAS_STREAMLIT_FOLIUM:
                folium_map = services['graph'].visualize_network_map(
                    nodes=graph_data['nodes'], edges=graph_data['edges'],
                    optimization_results=opt_results, highlight_paths=True,
                    commodity=st.session_state.commodity, use_osm_tiles=use_osm_net
                )
                if folium_map:
                    st_folium(folium_map, width=None, height=500, key="net_folium")
                    st.caption("Dùng **thanh thời gian** dưới bản đồ để xem đường optimal vẽ dần từ đầu đến cuối.")
                    net_animation_on_map = True
                else:
                    fig = services['graph'].visualize_network_interactive(
                        nodes=graph_data['nodes'], edges=graph_data['edges'],
                        optimization_results=opt_results, highlight_paths=True,
                        commodity=st.session_state.commodity
                    )
                    st.plotly_chart(fig, use_container_width=True, key="net_plotly")
            else:
                fig = services['graph'].visualize_network_interactive(
                    nodes=graph_data['nodes'], edges=graph_data['edges'],
                    optimization_results=opt_results, highlight_paths=True,
                    commodity=st.session_state.commodity
                )
                st.plotly_chart(fig, use_container_width=True, key="net_plotly")
            if not net_animation_on_map:
                fig_anim = services['graph'].visualize_network_animated(
                    nodes=graph_data['nodes'], edges=graph_data['edges'],
                    optimization_results=opt_results,
                    commodity=st.session_state.commodity,
                )
                if fig_anim:
                    st.markdown("**Đường chuyển động theo cặp OD** — ▶ Phát để xem tuyến vẽ dần.")
                    st.plotly_chart(fig_anim, use_container_width=True, key="net_animated")
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
# TAB: WHAT-IF (full what-if page)
# ============================================================================
with tab_whatif:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="gemini-card">
        <div class="gemini-header">What-If Analysis</div>
        <div style="font-size: 1rem; opacity: 0.95;">Explore alternate scenarios with AI predictions</div>
    </div>
    """, unsafe_allow_html=True)
    col_w1, col_w2 = st.columns([1, 2])
    with col_w1:
        scenario_type_w = st.selectbox("Scenario Type", options=["Increase Switching Cost", "Demand Shock", "Delay Hub Upgrade", "Capacity Reduction"], key="whatif_tab_type")
        if scenario_type_w == "Increase Switching Cost":
            impact_w = st.slider("Cost Increase (%)", 10, 200, 50, 10, key="whatif_tab_sw")
        elif scenario_type_w == "Demand Shock":
            impact_w = st.slider("Demand Change (%)", -50, 100, 20, 10, key="whatif_tab_dem")
        elif scenario_type_w == "Delay Hub Upgrade":
            impact_w = st.slider("Delay (periods)", 1, 4, 1, key="whatif_tab_del")
        else:
            impact_w = st.slider("Capacity Reduction (%)", 10, 50, 20, 5, key="whatif_tab_cap")
        run_w = st.button("Run What-If Analysis", type="primary", use_container_width=True, key="btn_whatif_tab")
    with col_w2:
        if run_w and st.session_state.optimization_results:
            with st.spinner("Gemini 3 reasoning..."):
                whatif_r = services['gemini'].whatif_analysis(
                    scenario_type=scenario_type_w,
                    impact_value=impact_w,
                    current_results=st.session_state.optimization_results,
                    graph_data=services['loader'].load_region_data(st.session_state.region),
                    commodity=st.session_state.commodity
                )
            _desc = (whatif_r.get('scenario_description', '') or '').replace('<', '&lt;').replace('>', '&gt;')
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.18); color: rgba(255,255,255,0.98); padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <strong>Scenario:</strong> {_desc}
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""<div class="custom-card" style="color: #1e293b;"><strong>Expected Impact</strong></div>""", unsafe_allow_html=True)
            st.markdown(whatif_r.get('expected_impact', ''))
            st.markdown("""<div class="custom-card" style="color: #1e293b;"><strong>Affected Routes</strong></div>""", unsafe_allow_html=True)
            for item in whatif_r.get('affected_items', []):
                st.markdown(f"""<div class="insight-warning">⚡ {item}</div>""", unsafe_allow_html=True)
            st.markdown("""<div class="custom-card" style="color: #1e293b;"><strong>Mitigation</strong></div>""", unsafe_allow_html=True)
            for s in whatif_r.get('mitigation', []):
                st.markdown(f"""<div class="insight-item">✓ {s}</div>""", unsafe_allow_html=True)
        elif not st.session_state.optimization_results:
            st.info("Load optimization results in the Scenario tab first.")

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
