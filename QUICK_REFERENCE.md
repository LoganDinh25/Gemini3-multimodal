# Quick Reference Guide - Logistics Planner

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run app
streamlit run app.py

# Access at: http://localhost:8501
```

---

## 📁 File Structure Reference

```
├── app.py                    # Main Streamlit UI (400+ lines)
├── gemini_service.py         # Gemini 3 API wrapper (350+ lines)
│   ├── normalize_data()      # CORE #1
│   ├── explain_strategy()    # CORE #2
│   └── whatif_analysis()     # CORE #3
├── graph_engine.py           # NetworkX operations (300+ lines)
├── data_loader.py            # Data management (250+ lines)
├── requirements.txt          # Dependencies
├── README.md                 # Full documentation
├── TECHNICAL_DOCS.md         # For judges
└── PRESENTATION_GUIDE.md     # Demo script
```

---

## 🔑 Key Functions Reference

### Data Loading
```python
from data_loader import DataLoader

loader = DataLoader()
regions = loader.get_available_regions()
data = loader.load_region_data("mekong_delta")
results = loader.load_optimization_results("mekong_delta", period=1)
```

### Gemini Service
```python
from gemini_service import GeminiService

gemini = GeminiService(api_key="your-key")

# Normalization
norm = gemini.normalize_data(nodes, edges, demand)

# Explanation
explanation = gemini.explain_strategy(
    period=1,
    commodity="Rice",
    optimization_results=results,
    graph_data=data,
    priority=0.5
)

# What-If
whatif = gemini.whatif_analysis(
    scenario_type="Increase Switching Cost",
    impact_value=50,
    current_results=results,
    graph_data=data,
    commodity="Rice"
)
```

### Graph Visualization
```python
from graph_engine import GraphEngine

graph = GraphEngine()
G = graph.build_graph(nodes, edges)
fig = graph.visualize_network(nodes, edges, optimization_results)
```

---

## 🎨 Streamlit UI Components

### Layout Pattern
```python
# Section header
st.header("Section Title")
st.markdown("Description...")

# Button trigger
if st.button("Action", type="primary"):
    with st.spinner("Processing..."):
        result = do_something()
    st.success("Done!")

# Display results
with st.expander("Details", expanded=True):
    st.json(result)
```

### Common Widgets
```python
# Selectors
region = st.selectbox("Region", options=regions)
period = st.selectbox("Period", options=[1,2,3,4])

# Slider
priority = st.slider("Priority", 0.0, 1.0, 0.5, 0.1)

# Columns
col1, col2 = st.columns(2)
with col1:
    st.metric("Cost", f"${value:,.0f}")
```

---

## 🔧 Customization Guide

### Adding New Region

1. Create directory:
```bash
mkdir -p data/new_region
```

2. Add files:
```
data/new_region/
├── nodes.csv          # node_id, name, lat, lon, type
├── edges.csv          # edge_id, from_node, to_node, mode, cost, capacity
├── demand.csv         # demand_id, origin, destination, commodity, volume
└── optimization_results_period1.json
```

3. Region auto-detected on next load

### Adding New Scenario Type

In `gemini_service.py`:
```python
def whatif_analysis(...):
    # Add new scenario type
    if scenario_type == "New Scenario":
        # Custom reasoning logic
        pass
```

### Customizing Visualization

In `graph_engine.py`:
```python
def visualize_network(...):
    # Modify colors
    hub_color = '#f39c12'  # Orange
    normal_color = '#ecf0f1'  # Light gray
    
    # Modify layout
    pos = nx.spring_layout(G, k=2, iterations=50)
```

---

## 🐛 Troubleshooting

### Issue: "No module named 'streamlit'"
**Fix:** 
```bash
pip install -r requirements.txt
```

### Issue: Gemini API key error
**Fix:**
```bash
export GEMINI_API_KEY="your-key-here"
# Or set in .env file
```

### Issue: Graph visualization not showing
**Fix:** Check matplotlib backend
```python
import matplotlib
matplotlib.use('Agg')
```

### Issue: Data files not found
**Fix:** App generates sample data automatically. Check `data/` directory created.

---

## 📊 Sample Data Format

### nodes.csv
```csv
node_id,name,lat,lon,type
1,Node_1,10.5,105.2,normal
2,Node_2,10.6,105.3,hub
```

### edges.csv
```csv
edge_id,from_node,to_node,mode,cost,capacity,distance
1,1,2,road,250.5,3000,45.2
2,2,3,water,180.0,5000,60.0
```

### optimization_results_period1.json
```json
{
  "region": "region_name",
  "period": 1,
  "total_cost": 124500,
  "total_time": 18.5,
  "num_hubs": 3,
  "top_routes": [
    {
      "route_id": 1,
      "path": [1, 3, 7, 12],
      "mode": "multi-modal",
      "cost": 12000,
      "time": 5.5,
      "commodity": "Rice"
    }
  ]
}
```

---

## 🌐 Deployment Options

### Local Demo
```bash
streamlit run app.py
```

### Streamlit Cloud (Free)
1. Push code to GitHub
2. Go to share.streamlit.io
3. Connect repository
4. Set environment variables (API key)
5. Deploy

### Docker (Production)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
```

Build & run:
```bash
docker build -t logistics-planner .
docker run -p 8501:8501 logistics-planner
```

---

## 🔐 Environment Variables

```bash
# .env file
GEMINI_API_KEY=your_api_key_here
DATA_DIR=./data
DEBUG_MODE=false
```

Load in code:
```python
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
```

---

## 📈 Performance Optimization

### Caching
```python
@st.cache_resource
def init_services():
    return {
        'gemini': GeminiService(),
        'graph': GraphEngine(),
        'loader': DataLoader()
    }

@st.cache_data
def load_data(region):
    return DataLoader().load_region_data(region)
```

### Lazy Loading
```python
# Only load when needed
if st.button("Load Data"):
    data = load_region_data(region)
```

---

## 🧪 Testing Checklist

**Before Demo:**
- [ ] All imports work
- [ ] Sample data generates correctly
- [ ] Graph visualization renders
- [ ] All buttons functional
- [ ] Gemini mock responses work
- [ ] No console errors

**Production Readiness:**
- [ ] Real Gemini API connected
- [ ] Error handling for API failures
- [ ] Input validation
- [ ] Rate limiting
- [ ] Logging enabled

---

## 💡 Pro Tips

### Streamlit Performance
```python
# Use session state for expensive operations
if 'data' not in st.session_state:
    st.session_state.data = load_data()

# Clear cache if needed
st.cache_data.clear()
```

### Gemini Optimization
```python
# Batch similar requests
# Use shorter prompts when possible
# Cache frequent scenarios
```

### Graph Visualization
```python
# For large graphs, use simplified layout
if num_nodes > 50:
    pos = nx.spring_layout(G, k=1, iterations=20)
```

---

## 📞 Support & Resources

**Documentation:**
- Full: README.md
- Technical: TECHNICAL_DOCS.md
- Presentation: PRESENTATION_GUIDE.md

**External:**
- Streamlit Docs: docs.streamlit.io
- NetworkX Docs: networkx.org
- Gemini API: ai.google.dev

**Common Commands:**
```bash
# Upgrade dependencies
pip install --upgrade -r requirements.txt

# Check Streamlit version
streamlit --version

# Clear Streamlit cache
streamlit cache clear

# Run on specific port
streamlit run app.py --server.port 8080
```

---

## ✅ Pre-Launch Checklist

**Code:**
- [ ] All files present
- [ ] No syntax errors
- [ ] Dependencies installed
- [ ] Environment variables set

**Demo:**
- [ ] Sample data works
- [ ] Gemini responses reasonable
- [ ] Graphs render correctly
- [ ] No browser console errors

**Documentation:**
- [ ] README complete
- [ ] Code comments clear
- [ ] API documented

**Presentation:**
- [ ] Demo flow tested
- [ ] Screenshots ready (backup)
- [ ] Talking points prepared

---

**Ready to go! 🚀**

**Quick commands to remember:**
```bash
streamlit run app.py           # Run app
pip install -r requirements.txt  # Install deps
python -m pytest               # Run tests (if added)
```
