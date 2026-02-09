# Hướng Dẫn Tích Hợp Gurobi Optimization Model

## 🎯 Vị Trí của Gurobi Model trong Kiến Trúc

```
OFFLINE (Chạy trước khi demo)          ONLINE (Trong demo)
┌──────────────────────────┐           ┌──────────────────────────┐
│                          │           │                          │
│  YOUR GUROBI MODEL       │           │  Streamlit App           │
│  (optimization_module.py)│           │  (app.py)                │
│                          │           │                          │
│  Input:                  │           │  Input:                  │
│  - nodes.csv             │           │  - Precomputed JSON      │
│  - edges.csv             │           │                          │
│  - demand.csv            │           │  Process:                │
│                          │           │  1. Load JSON results    │
│  Process:                │           │  2. Visualize graph      │
│  - Build Gurobi model    │    ═══>   │  3. Gemini explains WHY  │
│  - Solve optimization    │   JSON    │  4. What-if analysis     │
│  - Extract solution      │           │                          │
│                          │           │  Output:                 │
│  Output:                 │           │  - Strategic insights    │
│  - optimization_results  │           │  - Decision support      │
│    _period1.json         │           │                          │
└──────────────────────────┘           └──────────────────────────┘
```

---

## 📋 Cách Tích Hợp Model Gurobi Của Bạn

### Bước 1: Paste Code Gurobi Vào `optimization_module.py`

Mở file `optimization_module.py` và tìm đến hàm `build_model()`:

```python
def build_model(self, period: int, commodity: str = None, priority: float = 0.5):
    """
    Build Gurobi optimization model
    
    ĐÂY LÀ NơI BạN PASTE CODE GUROBI MODEL CỦA BẠN
    """
    
    # ==================================================================
    # PASTE CODE GUROBI CỦA BẠN VÀO ĐÂY
    # ==================================================================
    
    # Ví dụ: Nếu model của bạn có dạng:
    
    # Sets
    N = ...  # Nodes
    A = ...  # Arcs
    K = ...  # Commodities
    T = ...  # Time periods
    
    # Parameters
    c = ...  # Cost
    t = ...  # Time
    cap = ...  # Capacity
    d = ...  # Demand
    
    # Decision Variables
    x = self.model.addVars(...)  # Flow variables
    y = self.model.addVars(...)  # Hub selection
    z = self.model.addVars(...)  # Mode switching
    
    # Objective
    self.model.setObjective(...)
    
    # Constraints
    # ... tất cả constraints của bạn ...
    
    # ==================================================================
```

### Bước 2: Cập Nhật Hàm `_extract_solution()`

Sửa hàm này để extract đúng decision variables của model bạn:

```python
def _extract_solution(self) -> Dict[str, Any]:
    """Extract solution từ model Gurobi của bạn"""
    
    # Example: Nếu bạn có variables x[i,j,k,t], y[i,t], z[i,j]
    
    # 1. Extract hub selection
    selected_hubs = []
    for i in self.nodes['node_id']:
        for t in range(1, self.periods + 1):
            if self.y[i, t].X > 0.5:  # Binary variable
                selected_hubs.append(i)
    
    # 2. Extract flows
    routes = []
    for i, j, k, t in self.x.keys():
        if self.x[i, j, k, t].X > 1e-6:  # Flow threshold
            routes.append({
                'from': i,
                'to': j,
                'commodity': k,
                'period': t,
                'flow': self.x[i, j, k, t].X
            })
    
    # 3. Build paths (nếu model của bạn tính paths)
    top_routes = self._build_paths_from_flows(routes)
    
    # 4. Calculate metrics
    return {
        'total_cost': self.model.objVal,
        'selected_hubs': selected_hubs,
        'top_routes': top_routes,
        # ... thêm metrics khác từ model của bạn
    }
```

### Bước 3: Map Dữ Liệu Input

Đảm bảo dữ liệu CSV của bạn có format đúng:

**nodes.csv:**
```csv
node_id,name,lat,lon,type,capacity,cost_per_day
1,Warehouse_A,10.762,106.660,hub,5000,1000
2,Depot_B,10.823,106.629,normal,2000,500
```

**edges.csv:**
```csv
edge_id,from_node,to_node,mode,cost,capacity,distance,time
1,1,2,road,250,3000,45,2.5
2,2,3,water,180,5000,60,8.0
```

**demand.csv:**
```csv
demand_id,origin,destination,commodity,volume,period,priority
1,1,5,Rice,500,1,cost
2,3,7,Coal,800,1,speed
```

---

## 🚀 Workflow: Từ Gurobi → Gemini Demo

### Workflow Hoàn Chỉnh:

```bash
# 1. CHUẨN BỊ DỮ LIỆU (Một lần)
# Tạo thư mục và CSV files
mkdir -p data/mekong_delta
# Copy nodes.csv, edges.csv, demand.csv vào đây

# 2. CHẠY GUROBI OPTIMIZATION (Offline, trước demo)
python optimization_module.py --region mekong_delta --period 1

# Output: data/mekong_delta/optimization_results_period1.json

# 3. CHẠY STREAMLIT DEMO (Online, trong demo)
streamlit run app.py

# App sẽ:
# - Load optimization_results_period1.json
# - Visualize network graph
# - Gemini giải thích strategy
# - Gemini phân tích what-if
```

### Output JSON Format:

File `optimization_results_period1.json` có dạng:

```json
{
  "region": "mekong_delta",
  "period": 1,
  "total_cost": 124500.50,
  "total_time": 18.5,
  "num_hubs": 3,
  "selected_hubs": [3, 7, 12],
  "top_routes": [
    {
      "route_id": 1,
      "path": [1, 3, 7, 12, 15],
      "commodity": "Rice",
      "mode": "multi-modal",
      "cost": 12000,
      "time": 5.5,
      "flow": 450
    }
  ],
  "hub_utilization": {
    "3": 0.75,
    "7": 0.92,
    "12": 0.68
  },
  "modal_split": {
    "road": 0.35,
    "water": 0.65
  },
  "efficiency": 0.88,
  "solver_status": "optimal",
  "solve_time": 125.3
}
```

---

## 🔧 Ví Dụ Cụ Thể

### Giả Sử Model Gurobi Của Bạn Có Dạng:

```python
# YOUR ORIGINAL GUROBI CODE
import gurobipy as gp
from gurobipy import GRB

# Data
nodes = [1, 2, 3, 4, 5]
arcs = [(1,2), (2,3), (3,4), (4,5), (1,3), (2,4), (3,5)]
commodities = ['Rice', 'Coal']

# Model
m = gp.Model()

# Variables
x = m.addVars(arcs, commodities, name="flow")
y = m.addVars(nodes, vtype=GRB.BINARY, name="hub")

# Objective
m.setObjective(
    gp.quicksum(cost[i,j] * x[i,j,k] for (i,j) in arcs for k in commodities),
    GRB.MINIMIZE
)

# Constraints
# ... your constraints ...

m.optimize()
```

### Tích Hợp Vào `optimization_module.py`:

```python
class LogisticsOptimizer:
    def build_model(self, period, commodity=None, priority=0.5):
        # Import data từ self.nodes, self.edges, self.demand
        nodes = self.nodes['node_id'].tolist()
        arcs = list(zip(self.edges['from_node'], self.edges['to_node']))
        commodities = self.demand['commodity'].unique().tolist()
        
        # CREATE YOUR MODEL (copy code trên)
        self.model = gp.Model()
        
        # Variables (copy từ code của bạn)
        self.x = self.model.addVars(arcs, commodities, name="flow")
        self.y = self.model.addVars(nodes, vtype=GRB.BINARY, name="hub")
        
        # Objective (copy từ code của bạn)
        cost = {(row['from_node'], row['to_node']): row['cost'] 
                for _, row in self.edges.iterrows()}
        
        self.model.setObjective(
            gp.quicksum(cost[i,j] * self.x[i,j,k] 
                       for (i,j) in arcs for k in commodities),
            GRB.MINIMIZE
        )
        
        # Constraints (copy từ code của bạn)
        # ... paste all your constraints here ...
```

---

## 📊 Mapping: Gurobi Results → Gemini Input

### Gurobi Output → JSON → Gemini Analysis

```python
# GUROBI OUTPUT (từ optimization_module.py)
{
  "selected_hubs": [3, 7, 12],
  "total_cost": 124500,
  "top_routes": [...]
}

↓ Load vào app.py

# GEMINI INPUT (trong gemini_service.py)
gemini.explain_strategy(
    optimization_results={
        "selected_hubs": [3, 7, 12],  # ← Từ Gurobi
        "total_cost": 124500,         # ← Từ Gurobi
        "top_routes": [...]           # ← Từ Gurobi
    },
    graph_data={...}
)

↓ Gemini reasoning

# GEMINI OUTPUT (hiển thị trong app)
"""
WHY Hub 7?
- Hub 7 có betweenness centrality cao nhất (0.42)
- Nằm ở vị trí trung tâm của network
- Kết nối 3 tuyến water và 4 tuyến road

Gurobi đã chọn đúng vì:
- Minimizes total path length
- Enables efficient modal switching
- Balances hub load distribution
"""
```

---

## 🎯 Tại Sao Thiết Kế Như Vậy?

### Lợi Ích của Việc Tách Optimization vs Demo:

| Aspect | Gurobi Offline | Gemini Demo |
|--------|----------------|-------------|
| **Execution Time** | Hours (acceptable) | Seconds (required) |
| **Purpose** | Find optimal solution | Explain solution |
| **Expertise Required** | OR specialist | Business user |
| **Scalability** | Heavy compute | Lightweight |
| **Flexibility** | Fixed model | Instant what-if |

### Flow Thực Tế Trong Doanh Nghiệp:

```
Week 1: OR Team
├─ Build Gurobi model
├─ Run optimization (overnight)
└─ Generate results JSON

Week 2: Management
├─ Open Streamlit app
├─ Gemini explains strategy
├─ Test what-if scenarios
└─ Make decisions
```

---

## 🔄 Nếu Bạn Muốn Tích Hợp Real-Time Optimization

Có thể làm, nhưng **không khuyến nghị cho hackathon** vì:

### Option A: Real-Time (Phức tạp, chậm)
```python
# Trong app.py
if st.button("Re-optimize with Gurobi"):
    with st.spinner("Solving (may take hours)..."):
        optimizer = LogisticsOptimizer(data)
        optimizer.build_model(period)
        results = optimizer.solve()  # ← CHẬM!
```

**Vấn đề:**
- User phải đợi hàng giờ
- Cần Gurobi license trên server
- Demo bị gián đoạn

### Option B: Precomputed (Khuyến nghị cho hackathon)
```python
# Trước demo
python optimization_module.py --region mekong --period 1

# Trong demo
results = loader.load_optimization_results("mekong", 1)  # ← NHANH!
gemini.explain_strategy(results)
```

**Lợi ích:**
- Demo smooth, không lag
- Focus vào Gemini, không phải Gurobi
- Có thể demo offline
- Không cần Gurobi license trong demo

---

## 📝 Checklist Tích Hợp

### Trước Hackathon:
- [ ] Paste Gurobi model code vào `optimization_module.py`
- [ ] Test chạy optimization: `python optimization_module.py`
- [ ] Verify JSON output format đúng
- [ ] Generate optimization results cho 2-3 scenarios
- [ ] Test load results trong Streamlit app

### Trong Demo:
- [ ] KHÔNG chạy Gurobi (too slow)
- [ ] Load precomputed JSON
- [ ] Gemini giải thích results
- [ ] Focus vào strategic insights

### Câu Hỏi Từ Judges:
**Q: "Where is the optimization?"**
A: "We ran Gurobi optimization offline to generate optimal solutions. The innovation here is using Gemini to EXPLAIN and REASON about those solutions, not to replace the optimizer."

**Q: "Can it re-optimize?"**
A: "Yes, by running `optimization_module.py` with new parameters. But the power of Gemini is instant what-if analysis WITHOUT re-optimization."

---

## 🎓 Key Takeaway

```
┌─────────────────────────────────────────────────┐
│  GUROBI = Tính toán tối ưu (Math truth)        │
│  GEMINI = Giải thích & suy luận (Understanding)│
│                                                 │
│  Together = Decision Intelligence Platform     │
└─────────────────────────────────────────────────┘
```

**Gemini KHÔNG thay thế Gurobi.**  
**Gemini biến Gurobi từ "black box" thành "glass box".**

---

## 📞 Bước Tiếp Theo

Nếu bạn gửi cho tôi file Gurobi model của bạn, tôi sẽ:

1. ✅ Tích hợp chính xác vào `optimization_module.py`
2. ✅ Viết hàm `_extract_solution()` phù hợp với decision variables của bạn
3. ✅ Tạo sample JSON output đúng format
4. ✅ Test end-to-end flow: Gurobi → JSON → Gemini

**Bạn có file Gurobi model không? Tôi sẽ giúp tích hợp ngay!**
