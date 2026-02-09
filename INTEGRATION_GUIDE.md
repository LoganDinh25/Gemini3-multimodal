# Hướng Dẫn Tích Hợp Optimization Module với model_gurobi.py

## 📋 Tổng Quan

File `model_gurobi.py` chứa code Gurobi optimization model đầy đủ nhưng được viết dưới dạng script chạy trực tiếp. Để tích hợp vào `optimization_module.py`, bạn có 2 cách:

## 🔧 Cách 1: Refactor model_gurobi.py thành Class (Khuyến nghị)

### Bước 1: Tạo class wrapper trong optimization_module.py

```python
from model_gurobi import load_all_data, load_arcs, load_nodes

class LogisticsOptimizer:
    def __init__(self, region_data: Dict[str, pd.DataFrame]):
        self.nodes = region_data['nodes']
        self.edges = region_data['edges']
        self.demand = region_data['demand']
        self.model = None
        self.solution = None
        
    def build_model(self, period: int, commodity: str = None, priority: float = 0.5):
        """
        Build model bằng cách gọi các hàm từ model_gurobi.py
        """
        # Load data từ format chuẩn
        # Convert region_data về format mà model_gurobi.py expect
        node_file = 'data/Mekong/nodes_remapped_with_coords.csv'
        arc_file = 'data/Mekong/arcs_remapped.csv'
        
        # Load data
        edges_raw, OD_pairs, node_names, ... = load_all_data(node_file, arc_file)
        
        # Build Gurobi model (copy code từ model_gurobi.py)
        self.model = gp.Model("Multimodal_Hub_Network_Optimization")
        
        # ... paste tất cả code build model từ model_gurobi.py ...
        
    def solve(self):
        """Solve và extract results"""
        self.model.optimize()
        # Extract solution...
```

### Bước 2: Extract các hàm từ model_gurobi.py

Tách các phần sau từ `model_gurobi.py`:
- `load_arcs()` - đã có sẵn
- `load_nodes()` - đã có sẵn  
- `load_all_data()` - đã có sẵn
- Code build model (dòng 1719-2020)
- Code solve và extract results (dòng 2029-2447)

## 🔧 Cách 2: Chạy model_gurobi.py như subprocess (Đơn giản hơn)

### Tạo wrapper function:

```python
import subprocess
import json
from pathlib import Path

def run_gurobi_optimization(region: str, period: int, output_dir: str = "data"):
    """
    Chạy model_gurobi.py như một script và capture output
    """
    # Modify model_gurobi.py để export results ra JSON
    # Sau đó chạy:
    
    result = subprocess.run(
        ['python', 'model_gurobi.py', '--region', region, '--period', str(period)],
        capture_output=True,
        text=True
    )
    
    # Load results từ JSON file
    result_file = Path(output_dir) / region / f"optimization_results_period{period}.json"
    if result_file.exists():
        with open(result_file, 'r') as f:
            return json.load(f)
    return None
```

## 📝 Cách 3: Sử dụng Precomputed Results (Hiện tại - Demo)

Hiện tại app đã được setup để sử dụng precomputed results từ JSON files:

1. **Chạy optimization offline** bằng `model_gurobi.py`:
   ```bash
   python model_gurobi.py
   ```

2. **Export results** ra JSON format (cần thêm code export vào model_gurobi.py)

3. **App tự động load** từ `data/Mekong/optimization_results_period1.json`

## 🎯 Khuyến Nghị

Cho hackathon demo, **Cách 3 (Precomputed)** là đơn giản nhất:
- Chạy optimization offline trước khi demo
- App load kết quả từ JSON
- Gemini 3 giải thích và phân tích kết quả

Sau hackathon, có thể refactor để tích hợp trực tiếp (Cách 1).

## 📂 File Structure

```
logistics-planner/
├── app.py                    # Streamlit UI (đã hoàn chỉnh)
├── optimization_module.py     # Wrapper class (cần tích hợp model_gurobi.py)
├── model_gurobi.py          # Gurobi model script (cần refactor)
├── data_loader.py           # ✅ Đã cập nhật để load Mekong data
├── gemini_service.py        # ✅ Gemini 3 service
├── graph_engine.py          # ✅ Network visualization
├── config.py                # ✅ Configuration
└── data/
    └── Mekong/
        ├── nodes_remapped_with_coords.csv
        ├── arcs_remapped.csv
        └── optimization_results_period1.json  # ✅ Sample results
```

## ✅ Checklist Tích Hợp

- [x] Data loader hỗ trợ Mekong format
- [x] Sample optimization results JSON
- [x] UI layout matching design
- [ ] Tích hợp model_gurobi.py vào optimization_module.py
- [ ] Export function từ model_gurobi.py ra JSON
- [ ] Test end-to-end flow
