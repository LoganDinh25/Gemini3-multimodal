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

# Custom CSS for beautiful UI
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main background gradient */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Hero section */
    .hero-container {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }
    
    .hero-title {
        font-size: 3rem;
        font-weight: 700;
        color: white;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    .hero-subtitle {
        font-size: 1.5rem;
        color: rgba(255,255,255,0.9);
        font-weight: 300;
        margin-bottom: 1rem;
    }
    
    .hero-tagline {
        font-size: 1.2rem;
        color: rgba(255,255,255,0.85);
        font-style: italic;
        margin-top: 1rem;
    }
    
    /* Card styles */
    .custom-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        margin-bottom: 1.5rem;
    }
    
    .card-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .card-subheader {
        font-size: 1rem;
        color: #7f8c8d;
        margin-bottom: 1.5rem;
    }
    
    /* Gemini insight card */
    .gemini-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        margin-bottom: 1.5rem;
    }
    
    .gemini-header {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Button styles */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 10px;
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #f6f8fb 0%, #ffffff 100%);
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #7f8c8d;
        font-weight: 500;
    }
    
    /* Success/Warning/Info boxes */
    .stSuccess, .stWarning, .stInfo {
        border-radius: 10px;
        padding: 1rem;
    }
    
    /* Selectbox and slider styling */
    .stSelectbox > div > div {
        border-radius: 10px;
    }
    
    .stSlider > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Navigation tabs */
    .nav-container {
        background: rgba(255,255,255,0.95);
        padding: 1rem 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
    }
    
    /* Insight list items */
    .insight-item {
        padding: 1rem;
        margin: 0.5rem 0;
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        border-left: 4px solid #f39c12;
    }
    
    .risk-item {
        border-left-color: #e74c3c;
    }
    
    .action-item {
        border-left-color: #27ae60;
    }
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
# HEADER WITH NAVIGATION
# ============================================================================
col_header_left, col_header_right = st.columns([3, 1])

with col_header_left:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <div style="width: 50px; height: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: white; font-weight: bold;">G</div>
        <div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #2c3e50; margin: 0;">Graph-Aware Logistics Planner</div>
            <div style="font-size: 1rem; color: #7f8c8d; margin: 0;">Powered by Gemini 3</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_header_right:
    st.markdown("""
    <div style="display: flex; gap: 1rem; justify-content: flex-end; align-items: center; margin-top: 1rem;">
        <div style="width: 35px; height: 35px; background: #ecf0f1; border-radius: 50%; display: flex; align-items: center; justify-content: center;">👤</div>
        <div style="width: 35px; height: 35px; background: #ecf0f1; border-radius: 50%; display: flex; align-items: center; justify-content: center;">⚙️</div>
    </div>
    """, unsafe_allow_html=True)

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Scenario", "Network", "Explanation", "What-If"])

# Main banner
col_banner_left, col_banner_right = st.columns([3, 1])
with col_banner_left:
    st.markdown("""
    <div style="padding: 1rem 0;">
        <h2 style="margin: 0; color: #2c3e50; font-size: 2rem; font-weight: 700;">Turn complex transport networks into explainable decisions</h2>
    </div>
    """, unsafe_allow_html=True)

with col_banner_right:
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🚀 Run Scenario", type="primary", use_container_width=True):
            st.session_state.run_scenario = True
            st.session_state.generate_plan = True
            # Auto-load optimization results
            with st.spinner("🔍 Loading optimization results..."):
                opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
                if opt_results:
                    st.session_state.optimization_results = opt_results
                    st.success("✅ Scenario loaded successfully!")
                else:
                    st.warning("⚠️ No optimization results found for this period. Please check data files.")
    
    with col_btn2:
        if st.button("🧠 Ask Gemini 3", type="primary", use_container_width=True):
            if st.session_state.optimization_results:
                st.session_state.ask_gemini = True
                st.session_state.scenario_chat_expanded = True
                st.success("💬 Chat đã mở! Cuộn xuống để hỏi Gemini 3.")
            else:
                st.warning("⚠️ Vui lòng chạy 'Run Scenario' trước!")

# Use tab1 for main scenario view
with tab1:
    # Region selector - must be defined first
    available_regions = services['loader'].get_available_regions()
    try:
        region_index = available_regions.index(st.session_state.region) if st.session_state.region in available_regions else 0
    except (ValueError, AttributeError):
        region_index = 0
    
    region = st.selectbox(
        "🌍 Region",
        options=available_regions,
        index=region_index,
        help="Select the logistics region to analyze"
    )
    st.session_state.region = region

    # ============================================================================
    # SCENARIO SELECTOR - LEFT PANEL STYLE
    # ============================================================================
    col_left, col_middle, col_right = st.columns([1, 2, 1])
    
    with col_left:
        st.markdown("""
        <div class="custom-card" style="min-height: 400px;">
            <div class="card-header">
                🎯 Set Transport Scenario
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        period = st.selectbox(
            "Period:",
            options=[1, 2, 3, 4],
            index=st.session_state.period - 1 if st.session_state.period in [1, 2, 3, 4] else 0,
            help="Planning period for analysis"
        )
        st.session_state.period = period
        
        # Commodity options matching model_gurobi.py
        commodity_options = ["Passenger", "Rice", "Fisheries", "Fruits & Vegetables"]
        try:
            commodity_index = commodity_options.index(st.session_state.commodity) if st.session_state.commodity in commodity_options else 0
        except (ValueError, AttributeError):
            commodity_index = 0
        
        commodity = st.selectbox(
            "Commodity:",
            options=commodity_options,
            index=commodity_index,
            help="Type of cargo to optimize"
        )
        st.session_state.commodity = commodity
        
        st.markdown("<br>", unsafe_allow_html=True)
        priority = st.slider(
            "Priority:",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.priority,
            step=0.1,
            help="0 = minimize cost, 1 = minimize time"
        )
        st.session_state.priority = priority
        
        # Display priority labels
        col_cost, col_speed = st.columns(2)
        with col_cost:
            st.markdown("<small>Cost</small>", unsafe_allow_html=True)
        with col_speed:
            st.markdown("<div style='text-align: right;'><small>Speed</small></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Generate Plan", type="primary", use_container_width=True):
            st.session_state.generate_plan = True
        
        # Chạy model_gurobi.py (dùng đúng format demand, cost từ arcs_remapped, nodes)
        st.markdown("---")
        st.caption("Mặc định đọc từ file JSON. Chạy model_gurobi.py:")
        if st.button("🔄 Chạy Gurobi", key="run_gurobi", use_container_width=True, help="Chạy model_gurobi.py (data từ arcs_remapped.csv, nodes_remapped_with_coords.csv)"):
            import subprocess
            try:
                with st.spinner("⏳ Đang chạy model_gurobi.py... (có thể mất 2-5 phút)"):
                    result = subprocess.run(
                        ["python", "model_gurobi.py"],
                        cwd=Path(__file__).parent,
                        capture_output=True,
                        text=True,
                        timeout=600
                    )
                if result.returncode == 0:
                    st.success("✅ model_gurobi.py hoàn thành! Xem kết quả trong terminal.")
                else:
                    st.warning(f"⚠️ Thoát với code {result.returncode}. Xem terminal để debug.")
            except subprocess.TimeoutExpired:
                st.warning("⚠️ Timeout (10 phút). Model vẫn có thể đang chạy trong terminal.")
            except FileNotFoundError:
                st.error("❌ Không tìm thấy model_gurobi.py")
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")
    
    with col_middle:
        # Always load and display map (from Mekong data)
        # Load data from Mekong
        graph_data = services['loader'].load_region_data(st.session_state.region)
        
        # Try to load optimization results
        opt_results = st.session_state.optimization_results
        if not opt_results:
            opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
            if opt_results:
                st.session_state.optimization_results = opt_results
        
        # Always show map visualization (even without optimization results)
        st.markdown("""
        <div class="custom-card">
            <div class="card-header">🧠 Gemini 3 Decision Insights</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Toggle: Real map (Folium) vs Graph (Plotly)
        use_real_map = st.checkbox(
            "🗺️ Hiển thị bản đồ thực tế (OpenStreetMap)",
            value=True,
            help="Bật để xem network trên bản đồ thực tế. Tắt để xem dạng đồ thị."
        )
        
        if use_real_map and _HAS_STREAMLIT_FOLIUM:
            # Real map with Folium
            folium_map = services['graph'].visualize_network_map(
                nodes=graph_data['nodes'],
                edges=graph_data['edges'],
                optimization_results=opt_results if opt_results else None,
                highlight_paths=bool(opt_results),
                commodity=st.session_state.commodity
            )
            if folium_map:
                st_folium(folium_map, width=None, height=500, key="scenario_folium_map")
            else:
                st.warning("Tọa độ chưa chuẩn WGS84. Dùng đồ thị hoặc cài pyproj để chuyển đổi tự động.")
                fig = services['graph'].visualize_network_interactive(
                    nodes=graph_data['nodes'], edges=graph_data['edges'],
                    optimization_results=opt_results, highlight_paths=bool(opt_results),
                    commodity=st.session_state.commodity
                )
                st.plotly_chart(fig, use_container_width=True, key="scenario_map")
        else:
            # Plotly graph
            fig = services['graph'].visualize_network_interactive(
                nodes=graph_data['nodes'],
                edges=graph_data['edges'],
                optimization_results=opt_results if opt_results else None,
                highlight_paths=bool(opt_results),
                commodity=st.session_state.commodity
            )
            st.plotly_chart(fig, use_container_width=True, key="scenario_map")
        
        # Show insights only if we have optimization results
        if opt_results:
                
                # Textual insights
                st.markdown("""
                <div class="custom-card" style="margin-top: 1rem;">
                    <h4 style="color: #667eea; margin-bottom: 1rem;">📋 Insights</h4>
                </div>
                """, unsafe_allow_html=True)
                
                insights = opt_results.get('insights', {})
                if insights:
                    for finding in insights.get('key_findings', []):
                        st.markdown(f"""
                        <div style="padding: 0.75rem; margin: 0.5rem 0; background: #e8f5e9; border-radius: 8px; border-left: 4px solid #27ae60;">
                            ✓ {finding}
                        </div>
                        """, unsafe_allow_html=True)
                
                # Auto-expand chat when Ask Gemini 3 was clicked
                if st.session_state.get('ask_gemini', False):
                    st.session_state.scenario_chat_expanded = True
                    st.session_state.ask_gemini = False
                
                # + Ask more... - Chat with Gemini (functional)
                with st.expander("💬 + Ask more... (Chat với Gemini 3)", expanded=st.session_state.get('scenario_chat_expanded', False)):
                    # Display chat history
                    for role, msg in st.session_state.scenario_chat_history:
                        if role == "user":
                            st.markdown(f"**Bạn:** {msg}")
                        else:
                            st.markdown(f"**Gemini 3:**\n{msg}")
                    
                    # Chat input
                    q = st.text_input("Đặt câu hỏi về chiến lược:", placeholder="VD: Tại sao Hub 14 được chọn? Rủi ro chính là gì?", key="scenario_chat_input")
                    col_s, col_c = st.columns([4, 1])
                    with col_s:
                        if st.button("📤 Gửi", key="scenario_send"):
                            if q.strip():
                                with st.spinner("🧠 Gemini 3 đang suy nghĩ..."):
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
                                st.warning("Vui lòng nhập câu hỏi.")
                    with col_c:
                        if st.button("🗑️ Xóa", key="scenario_clear"):
                            st.session_state.scenario_chat_history = []
                            st.rerun()
    
    with col_right:
        st.markdown("""
        <div class="custom-card">
            <div class="card-header">🔮 What-If Analysis</div>
            <div class="card-subheader">Explore Alternate Scenarios (Gemini 3)</div>
        </div>
        """, unsafe_allow_html=True)
        
        scenario_type = st.selectbox(
            "Scenario Type",
            options=["Increase Switching Cost", "Demand Shock", "Delay Hub Upgrade", "Capacity Reduction"],
            index=0
        )
        
        if scenario_type == "Increase Switching Cost":
            impact_value = st.slider("Increase Switching Cost", 2, 3, 2, 1)
        elif scenario_type == "Demand Shock":
            impact_value = st.slider("Demand Change (%)", -50, 100, 20, 10)
        elif scenario_type == "Delay Hub Upgrade":
            impact_value = st.slider("Delay (periods)", 1, 4, 1)
        else:
            impact_value = st.slider("Capacity Reduction (%)", 10, 50, 20, 5)
        
        if st.button("Run What-If Analysis", type="primary", use_container_width=True):
            if st.session_state.optimization_results:
                with st.spinner("🧠 Gemini 3 is reasoning..."):
                    whatif_result = services['gemini'].whatif_analysis(
                        scenario_type=scenario_type,
                        impact_value=impact_value,
                        current_results=st.session_state.optimization_results,
                        graph_data=services['loader'].load_region_data(region),
                        commodity=commodity
                    )
                
                st.markdown("""
                <div style="margin-top: 1rem;">
                    <h4 style="color: #3498db;">Gemini 3 predicts:</h4>
                </div>
                """, unsafe_allow_html=True)
                
                for item in whatif_result.get('affected_items', []):
                    st.markdown(f"""
                    <div style="padding: 0.5rem; margin: 0.25rem 0; background: #e8f5e9; border-radius: 6px;">
                        ✓ {item}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("""
                <div style="margin-top: 1rem;">
                    <h4 style="color: #27ae60;">Suggested mitigation:</h4>
                </div>
                """, unsafe_allow_html=True)
                
                for suggestion in whatif_result.get('mitigation', []):
                    st.markdown(f"""
                    <div style="padding: 0.5rem; margin: 0.25rem 0; background: #fff3e0; border-radius: 6px;">
                        • {suggestion}
                    </div>
                    """, unsafe_allow_html=True)
    
    # Auto-load data when region/period changes
    if 'last_region' not in st.session_state or st.session_state.last_region != st.session_state.region or 'last_period' not in st.session_state or st.session_state.last_period != st.session_state.period:
        st.session_state.last_region = st.session_state.region
        st.session_state.last_period = st.session_state.period
        with st.spinner("🔍 Loading regional data..."):
            data = services['loader'].load_region_data(st.session_state.region)
            st.session_state.region_data = data
            
            # Load optimization results
            opt_results = services['loader'].load_optimization_results(st.session_state.region, st.session_state.period)
            if opt_results:
                st.session_state.optimization_results = opt_results
            else:
                # If no results found, try to load from period 1 as fallback
                opt_results = services['loader'].load_optimization_results(st.session_state.region, 1)
                if opt_results:
                    st.session_state.optimization_results = opt_results
            
            # Normalize with Gemini
            normalization_result = services['gemini'].normalize_data(
                nodes=data['nodes'],
                edges=data['edges'],
                demand=data['demand']
            )
            st.session_state.normalized_data = normalization_result

# ============================================================================
# TAB 2: NETWORK VISUALIZATION
# ============================================================================
with tab2:
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.session_state.optimization_results:
        st.markdown("""
        <div class="custom-card">
            <div class="card-header">
                🗺️ Network Visualization & Optimization Results
            </div>
            <div class="card-subheader">
                Interactive graph showing optimal routes and hub selection
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Build interactive graph with Plotly or real map
            graph_data = services['loader'].load_region_data(st.session_state.region)
            opt_results = st.session_state.optimization_results
            
            use_real_map_net = st.checkbox(
                "🗺️ Bản đồ thực tế",
                value=True,
                key="network_map_toggle"
            )
            
            if use_real_map_net and _HAS_STREAMLIT_FOLIUM:
                folium_map = services['graph'].visualize_network_map(
                    nodes=graph_data['nodes'],
                    edges=graph_data['edges'],
                    optimization_results=opt_results,
                    highlight_paths=True,
                    commodity=st.session_state.commodity
                )
                if folium_map:
                    st_folium(folium_map, width=None, height=500, key="network_folium_map")
                else:
                    fig = services['graph'].visualize_network_interactive(
                        nodes=graph_data['nodes'], edges=graph_data['edges'],
                        optimization_results=opt_results, highlight_paths=True,
                        commodity=st.session_state.commodity
                    )
                    st.plotly_chart(fig, use_container_width=True, key="network_map")
            else:
                fig = services['graph'].visualize_network_interactive(
                    nodes=graph_data['nodes'],
                    edges=graph_data['edges'],
                    optimization_results=opt_results,
                    highlight_paths=True,
                    commodity=st.session_state.commodity
                )
                st.plotly_chart(fig, use_container_width=True, key="network_map")
        
        with col2:
            st.markdown("<div style='padding: 1rem;'>", unsafe_allow_html=True)
            
            # Key Metrics with beautiful cards
            results = st.session_state.optimization_results
            
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">${:,.0f}</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Total Cost</div>
            </div>
            """.format(results.get('total_cost', 0)), unsafe_allow_html=True)
            
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">{:.1f} days</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Total Time</div>
            </div>
            """.format(results.get('total_time', 0)), unsafe_allow_html=True)
            
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">{}</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Hubs Selected</div>
            </div>
            """.format(results.get('num_hubs', 0)), unsafe_allow_html=True)
            
            st.markdown("""
            <div class="metric-card" style="background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); color: white; margin-bottom: 1rem;">
                <div class="metric-value" style="color: white;">{:.1%}</div>
                <div class="metric-label" style="color: rgba(255,255,255,0.9);">Flow Efficiency</div>
            </div>
            """.format(results.get('efficiency', 0)), unsafe_allow_html=True)
            
            st.markdown("**🛣️ Top Routes:**", unsafe_allow_html=True)
            for i, route in enumerate(results.get('top_routes', [])[:3], 1):
                st.markdown(f"""
                <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; border-left: 3px solid #667eea;">
                    <strong>Route {i}:</strong> {' → '.join(map(str, route['path']))}<br>
                    <small>Mode: {route['mode']} | Cost: ${route['cost']:,.0f}</small>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("⚠️ Please load optimization results first in the Scenario tab.", icon="ℹ️")

# ============================================================================
# TAB 3: EXPLANATION
# ============================================================================
with tab3:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="gemini-card">
        <div class="gemini-header">
            🧠 Gemini 3 Decision Insights
        </div>
        <div style="font-size: 1rem; opacity: 0.9;">
            AI-powered strategic analysis and graph-based reasoning
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Auto-trigger if button was clicked in banner
    if st.session_state.get('ask_gemini', False) and st.session_state.optimization_results:
        st.session_state.ask_gemini = False
        # Auto-run explanation
        with st.spinner("🧠 Gemini 3 is analyzing the optimization strategy..."):
            explanation = services['gemini'].explain_strategy(
                period=st.session_state.period,
                commodity=st.session_state.commodity,
                optimization_results=st.session_state.optimization_results,
                graph_data=services['loader'].load_region_data(st.session_state.region),
                priority=st.session_state.priority
            )
            st.session_state.explanation_result = explanation
    
    # Check if we should auto-run explanation (from banner button)
    should_show_explanation = False
    if st.session_state.get('ask_gemini', False) and st.session_state.optimization_results:
        should_show_explanation = True
        st.session_state.ask_gemini = False
    
    clicked_explain = st.button("✨ Ask Gemini 3 to Explain Strategy", type="primary", disabled=not st.session_state.optimization_results, use_container_width=True)
    has_explanation = bool(st.session_state.get('explanation_result'))
    
    # Show explanation + chat when: clicked explain, or have cached explanation (e.g. after Send rerun)
    if (clicked_explain or should_show_explanation or has_explanation) and st.session_state.optimization_results:
        # Use cached explanation if available (e.g. after Send rerun); generate when user clicked Explain
        if has_explanation and not clicked_explain and not should_show_explanation:
            explanation = st.session_state.explanation_result
        else:
            with st.spinner("🧠 Gemini 3 is analyzing the optimization strategy..."):
                explanation = services['gemini'].explain_strategy(
                    period=st.session_state.period,
                    commodity=st.session_state.commodity,
                    optimization_results=st.session_state.optimization_results,
                    graph_data=services['loader'].load_region_data(st.session_state.region),
                    priority=st.session_state.priority
                )
                st.session_state.explanation_result = explanation
        
        # Display explanation in beautiful format
        st.markdown("""
        <div class="custom-card" style="background: linear-gradient(135deg, #f6f8fb 0%, #ffffff 100%);">
            <h3 style="color: #667eea; margin-bottom: 1rem;">📋 Strategic Overview</h3>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(explanation['strategy_summary'])
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="custom-card">
                <h3 style="color: #3498db; margin-bottom: 1rem;">🎯 Why This Strategy?</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(explanation['reasoning'])
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("""
            <div class="custom-card" style="background: linear-gradient(135deg, #ffe8e8 0%, #fff5f5 100%);">
                <h3 style="color: #e74c3c; margin-bottom: 1rem;">⚠️ Bottlenecks & Risks</h3>
            </div>
            """, unsafe_allow_html=True)
            for risk in explanation['risks']:
                st.markdown(f"""
                <div class="risk-item" style="background: white; padding: 1rem; margin: 0.5rem 0; border-radius: 8px; border-left: 4px solid #e74c3c;">
                    {risk}
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="custom-card">
                <h3 style="color: #9b59b6; margin-bottom: 1rem;">📊 Graph-Based Insights</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(explanation['graph_insights'])
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("""
            <div class="custom-card" style="background: linear-gradient(135deg, #e8f8f5 0%, #f0fdf7 100%);">
                <h3 style="color: #27ae60; margin-bottom: 1rem;">💡 Recommended Actions</h3>
            </div>
            """, unsafe_allow_html=True)
            for action in explanation['recommendations']:
                st.markdown(f"""
                <div class="action-item" style="background: white; padding: 1rem; margin: 0.5rem 0; border-radius: 8px; border-left: 4px solid #27ae60;">
                    ✓ {action}
                </div>
                """, unsafe_allow_html=True)
        
        # Chat with Gemini section
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="custom-card" style="background: linear-gradient(135deg, #e8eaf6 0%, #f3f4f6 100%);">
            <h3 style="color: #667eea; margin-bottom: 1rem;">💬 Chat with Gemini</h3>
            <p style="color: #7f8c8d;">Ask follow-up questions to understand the strategy better</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Initialize chat history
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for i, (role, message) in enumerate(st.session_state.chat_history):
                if role == "user":
                    st.markdown(f"""
                    <div style="background: #667eea; color: white; padding: 0.75rem; border-radius: 10px; margin-bottom: 0.5rem; text-align: right;">
                        <strong>You:</strong> {message}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background: #f0f0f0; padding: 0.75rem; border-radius: 10px; margin-bottom: 0.5rem;">
                        <strong>Gemini:</strong> {message}
                    </div>
                    """, unsafe_allow_html=True)
        
        # Chat input
        user_question = st.text_input(
            "Ask Gemini a question:",
            placeholder="e.g., Why was Hub 7 selected? What are the risks?",
            key="chat_input"
        )
        
        col_send, col_clear = st.columns([4, 1])
        with col_send:
            if st.button("💬 Send", type="primary", use_container_width=True):
                if user_question and st.session_state.optimization_results:
                    with st.spinner("🧠 Gemini is thinking..."):
                        # Prepare context
                        context = {
                            'optimization_results': st.session_state.optimization_results,
                            'graph_data': services['loader'].load_region_data(st.session_state.region),
                            'period': st.session_state.period,
                            'commodity': st.session_state.commodity
                        }
                        
                        # Get response from Gemini
                        response = services['gemini'].chat(user_question, context)
                        
                        # Add to chat history
                        st.session_state.chat_history.append(("user", user_question))
                        st.session_state.chat_history.append(("assistant", response))
                        
                        st.rerun()
                elif not st.session_state.optimization_results:
                    st.warning("⚠️ Please load optimization results first!")
        
        with col_clear:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
    else:
        if not st.session_state.optimization_results:
            st.info("⚠️ Please load optimization results first in the Scenario tab.", icon="ℹ️")

# ============================================================================
# TAB 4: WHAT-IF ANALYSIS
# ============================================================================
with tab4:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="gemini-card">
        <div class="gemini-header">
            🔮 Gemini 3 What-If Analysis
        </div>
        <div style="font-size: 1rem; opacity: 0.9;">
            Explore alternate scenarios with instant AI predictions (no re-optimization needed)
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("""
        <div class="custom-card">
            <h4 style="color: #667eea; margin-bottom: 1rem;">Scenario Parameters</h4>
        </div>
        """, unsafe_allow_html=True)
        
        scenario_type = st.selectbox(
            "📋 Scenario Type",
            options=[
                "Increase Switching Cost",
                "Demand Shock",
                "Delay Hub Upgrade",
                "Capacity Reduction"
            ]
        )
        
        if scenario_type == "Increase Switching Cost":
            impact_value = st.slider("Cost Increase (%)", 10, 200, 50, 10)
        elif scenario_type == "Demand Shock":
            impact_value = st.slider("Demand Change (%)", -50, 100, 20, 10)
        elif scenario_type == "Delay Hub Upgrade":
            impact_value = st.slider("Delay (periods)", 1, 4, 1)
        else:
            impact_value = st.slider("Capacity Reduction (%)", 10, 50, 20, 5)
        
        run_whatif = st.button("🔮 Run What-If Analysis", type="primary", use_container_width=True)

    with col2:
        if run_whatif and st.session_state.optimization_results:
            with st.spinner("🧠 Gemini 3 is reasoning about scenario impact..."):
                whatif_result = services['gemini'].whatif_analysis(
                    scenario_type=scenario_type,
                    impact_value=impact_value,
                    current_results=st.session_state.optimization_results,
                    graph_data=services['loader'].load_region_data(st.session_state.region),
                    commodity=st.session_state.commodity
                )
            
            st.markdown("""
            <div class="custom-card" style="background: linear-gradient(135deg, #e8eaf6 0%, #f3f4f6 100%);">
                <h3 style="color: #667eea; margin-bottom: 1rem;">🔮 Scenario Impact Analysis</h3>
            </div>
            """, unsafe_allow_html=True)
            
            st.info(f"**Scenario:** {whatif_result['scenario_description']}", icon="📋")
            
            st.markdown("""
            <div class="custom-card">
                <h4 style="color: #3498db; margin-bottom: 1rem;">Expected Impact</h4>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(whatif_result['expected_impact'])
            
            st.markdown("""
            <div class="custom-card" style="background: linear-gradient(135deg, #fff3e0 0%, #fffbf0 100%);">
                <h4 style="color: #f39c12; margin-bottom: 1rem;">Affected Routes & Commodities</h4>
            </div>
            """, unsafe_allow_html=True)
            for item in whatif_result['affected_items']:
                st.markdown(f"""
                <div style="background: white; padding: 0.75rem; margin: 0.5rem 0; border-radius: 8px; border-left: 3px solid #f39c12;">
                    ⚡ {item}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="custom-card" style="background: linear-gradient(135deg, #e8f5e9 0%, #f1f8f4 100%);">
                <h4 style="color: #27ae60; margin-bottom: 1rem;">Mitigation Strategies</h4>
            </div>
            """, unsafe_allow_html=True)
            for suggestion in whatif_result['mitigation']:
                st.markdown(f"""
                <div style="background: white; padding: 0.75rem; margin: 0.5rem 0; border-radius: 8px; border-left: 3px solid #27ae60;">
                    ✓ {suggestion}
                </div>
                """, unsafe_allow_html=True)
        elif not st.session_state.optimization_results:
            st.info("⚠️ Please load optimization results first in the Scenario tab.", icon="ℹ️")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; padding: 2rem; background: rgba(255,255,255,0.1); border-radius: 15px;">
    <div style="font-size: 1.5rem; font-weight: 600; color: white; margin-bottom: 0.5rem;">
        Graph-Aware Logistics Planner
    </div>
    <div style="color: rgba(255,255,255,0.8); margin-bottom: 1rem;">
        Powered by Gemini 3 | Built for Hackathon Demo
    </div>
    <div style="font-style: italic; color: rgba(255,255,255,0.7); font-size: 1.1rem;">
        "If Gemini 3 is removed, the app loses its decision-making capability.<br>
        If optimization is removed, the app loses its credibility."
    </div>
</div>
""", unsafe_allow_html=True)
