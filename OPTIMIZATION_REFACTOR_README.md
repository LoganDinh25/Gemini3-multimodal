# Hướng Dẫn Sử Dụng Optimization Module Đã Tối Ưu

## 📋 Tổng Quan

Code đã được tối ưu và tách thành các module riêng để dễ hiểu và tái sử dụng. Sau khi chạy xong CELL 5, dữ liệu sẽ được lưu vào file `.pkl` để lần sau chỉ cần đọc mà không phải load lại.

## 📁 Cấu Trúc Files

```
.
├── load_data.py              # CELL 2: Load CSV và lưu pkl
├── build_graph.py            # CELL 3: Build expanded graph
├── calculate_paths.py        # CELL 4 + CELL 5: Tính paths và lưu pkl
├── run_optimization.py       # File chính để chạy tất cả
├── model_gurobi.py          # File gốc (đã được cập nhật hỗ trợ pkl)
└── data/
    ├── preprocessed_data.pkl    # Dữ liệu sau CELL 2
    └── paths_data.pkl           # Dữ liệu sau CELL 5
```

## 🚀 Cách Sử Dụng

### Cách 1: Sử dụng `run_optimization.py` (Khuyến nghị)

```bash
python run_optimization.py
```

File này sẽ:
1. **STEP 1**: Load data từ CSV hoặc pkl (nếu đã có)
2. **STEP 2**: Build expanded graph
3. **STEP 3**: Calculate paths từ CSV hoặc pkl (nếu đã có)
4. **STEP 4**: Hướng dẫn tiếp tục với model_gurobi.py

### Cách 2: Sử dụng `model_gurobi.py` trực tiếp

```bash
python model_gurobi.py
```

File này đã được cập nhật để:
- Tự động kiểm tra và đọc từ `data/preprocessed_data.pkl` nếu đã có (sau CELL 2)
- Tự động kiểm tra và đọc từ `data/paths_data.pkl` nếu đã có (sau CELL 5)
- Hỏi bạn có muốn sử dụng pkl hay không

### Cách 3: Chạy từng module riêng

#### Load data (CELL 2):
```bash
python load_data.py
```
Sẽ tạo file `data/preprocessed_data.pkl`

#### Build graph (CELL 3):
```python
from load_data import load_data_from_pkl
from build_graph import build_graph_structure

data = load_data_from_pkl()
graph_data = build_graph_structure(...)
```

#### Calculate paths (CELL 4 + CELL 5):
```python
from calculate_paths import calculate_all_paths

paths, Lmin_dict = calculate_all_paths(...)
```
Sẽ tạo file `data/paths_data.pkl`

## 💾 Files PKL

### `data/preprocessed_data.pkl`
Chứa dữ liệu sau CELL 2:
- `edges_raw`: Danh sách các arcs từ CSV
- `OD_pairs`: Origin-Destination pairs
- `node_names`, `node_projects`, `node_type`, `node_coords`
- `node_capacity_*`: Thông tin capacity của nodes
- `real_nodes`, `existing_hubs`, `potential_hubs`
- `existing_arcs`, `potential_arcs`
- Và các biến khác...

### `data/paths_data.pkl`
Chứa dữ liệu sau CELL 5:
- `paths`: Dictionary chứa tất cả paths cho mỗi (commodity, OD)
- `Lmin_dict`: Dictionary chứa L_min cho mỗi (commodity, origin, destination)
- `node_names`, `node_projects`, `edges_raw`: Dữ liệu tham chiếu

## 🔄 Workflow

### Lần đầu chạy:
1. Chạy `python run_optimization.py` hoặc `python model_gurobi.py`
2. Hệ thống sẽ load từ CSV và tính toán tất cả
3. Tự động lưu vào pkl sau CELL 2 và CELL 5

### Lần sau chạy:
1. Chạy lại `python run_optimization.py` hoặc `python model_gurobi.py`
2. Hệ thống sẽ hỏi có muốn dùng pkl không
3. Nếu chọn `y` (mặc định), sẽ đọc từ pkl → **TIẾT KIỆM THỜI GIAN**
4. Nếu chọn `n`, sẽ tính toán lại từ đầu

## ⚡ Lợi Ích

1. **Tiết kiệm thời gian**: Không phải load lại CSV và tính toán paths mỗi lần
2. **Dễ hiểu**: Code được tách thành các module riêng biệt
3. **Dễ bảo trì**: Mỗi module có trách nhiệm rõ ràng
4. **Linh hoạt**: Có thể chạy từng phần riêng hoặc chạy toàn bộ

## 📝 Lưu Ý

- File pkl sẽ được tạo tự động sau khi chạy xong CELL 2 và CELL 5
- Nếu thay đổi dữ liệu CSV, nên xóa file pkl để tính toán lại
- File pkl có thể khá lớn (tùy thuộc vào số lượng paths)

## 🔧 Troubleshooting

### Lỗi: File pkl không tồn tại
→ Chạy lại từ đầu để tạo file pkl

### Lỗi: Dữ liệu không khớp
→ Xóa file pkl và chạy lại từ CSV

### Muốn tính toán lại từ đầu
→ Xóa các file pkl trong thư mục `data/` hoặc chọn `n` khi được hỏi

## 📚 Module Details

### `load_data.py`
- `load_arcs()`: Load arcs từ CSV
- `load_nodes()`: Load nodes từ CSV
- `load_all_data()`: Load tất cả và trả về tuple
- `save_data_to_pkl()`: Lưu vào pkl
- `load_data_from_pkl()`: Đọc từ pkl

### `build_graph.py`
- `build_graph_structure()`: Build expanded graph và arc structures
- Các helper functions: `to_edge_tuple_list()`, `make_bidirectional_edges()`, etc.

### `calculate_paths.py`
- `calculate_L_min()`: CELL 4 - Tính L_min
- `calculate_near_optimal_paths()`: CELL 5 - Tính paths
- `calculate_all_paths()`: Tổng hợp CELL 4 + CELL 5
- `save_paths_to_pkl()`: Lưu paths vào pkl
- `load_paths_from_pkl()`: Đọc paths từ pkl

### `run_optimization.py`
- `main()`: Hàm chính tích hợp tất cả các bước
