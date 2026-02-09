# 📋 Hướng dẫn Thêm Dữ liệu và Bản đồ Thực tế

## 1. Tổng quan Cấu trúc Dữ liệu

```
data/
├── Mekong/                              # Vùng Đồng bằng sông Cửu Long
│   ├── nodes_remapped_with_coords.csv   # Nodes với tọa độ
│   ├── arcs_remapped.csv                # Cạnh/arcs (road + waterway)
│   ├── optimization_results_period1.json
│   └── optimization_results_period2.json
├── mekong_delta/                         # Format chuẩn (nodes, edges, demand)
│   ├── nodes.csv
│   ├── edges.csv
│   └── demand.csv
└── toy_region/                          # Vùng mẫu
    ├── nodes.csv
    ├── edges.csv
    ├── demand.csv
    └── optimization_results_period1.json
```

---

## 2. Định dạng File Chi tiết

### 2.1 Nodes (nodes.csv hoặc nodes_remapped_with_coords.csv)

**Format chuẩn (cho toy_region / mekong_delta):**

| Cột | Bắt buộc | Mô tả |
|-----|----------|-------|
| `node_id` | ✓ | ID duy nhất (int) |
| `name` | ✓ | Tên node (string) |
| `lat` | ✓ | Vĩ độ WGS84 (10-11 cho Mekong) |
| `lon` | ✓ | Kinh độ WGS84 (104-107 cho Mekong) |
| `type` | | `hub` hoặc `normal` |
| `capacity` | | Công suất (ton/năm) |

**Format Mekong (nodes_remapped_with_coords.csv):**

| Cột | Mô tả |
|-----|-------|
| `New_ID` | ID node |
| `Name` | Tên địa điểm |
| `Longitude` | X (VN-2000 UTM) hoặc lon |
| `Latitude` | Y (VN-2000 UTM) hoặc lat |
| `Project` | E=Existing, New, Upgrade |

> **Lưu ý tọa độ:** Dữ liệu Mekong hiện dùng **VN-2000 UTM zone 48N** (EPSG:3405). Ứng dụng tự động chuyển sang WGS84 cho bản đồ thực tế.

### 2.2 Edges/Arcs (edges.csv hoặc arcs_remapped.csv)

**Format chuẩn:**

| Cột | Bắt buộc | Mô tả |
|-----|----------|-------|
| `from_node` | ✓ | ID node nguồn |
| `to_node` | ✓ | ID node đích |
| `mode` | ✓ | `road`, `water`, `rail` |
| `cost` | | Chi phí vận chuyển |
| `capacity` | | Công suất (ton/năm) |
| `distance` | | Khoảng cách (km) |

**Format Mekong (arcs_remapped.csv):**

| Cột | Mô tả |
|-----|-------|
| `FromNode`, `ToNode` | ID nguồn/đích |
| `Type` | `R` = Road, `W` = Waterway |
| `Length(m)` | Độ dài (mét) |
| `base_costs` | Chi phí cơ sở |

### 2.3 Demand (demand.csv)

**Format chuẩn:**

| Cột | Bắt buộc | Mô tả |
|-----|----------|-------|
| `origin` | ✓ | ID node nguồn |
| `destination` | ✓ | ID node đích |
| `commodity` | ✓ | Rice, Coal, Container, Passenger, Fisheries, Fruits & Vegetables |
| `volume` | ✓ | Khối lượng (ton) |
| `period` | ✓ | Kỳ kế hoạch (1, 2, 3, 4) |

**Ví dụ demand.csv:**

```csv
origin,destination,commodity,volume,period
0,14,Rice,2500,1
1,7,Rice,1800,1
3,15,Rice,1500,2
6,14,Rice,2100,1
8,7,Container,1200,1
```

### 2.4 Optimization Results (optimization_results_periodN.json)

```json
{
  "region": "Mekong",
  "period": 1,
  "total_cost": 125000000,
  "total_time": 18.5,
  "num_hubs": 3,
  "selected_hubs": [7, 10, 14],
  "efficiency": 0.87,
  "top_routes": [
    {
      "route_id": 1,
      "path": [0, 7, 10, 14],
      "commodity": "Rice",
      "mode": "multi-modal",
      "cost": 15000000,
      "time": 4.2,
      "flow": 2500
    }
  ],
  "hub_utilization": {"7": 0.85, "10": 0.72, "14": 0.91},
  "modal_split": {"road": 0.35, "water": 0.60, "multi-modal": 0.05},
  "insights": {
    "key_findings": ["Can Tho hub is critical...", "Waterways handle 60%..."]
  }
}
```

---

## 3. Thêm Vùng Mới

### Bước 1: Tạo thư mục

```bash
mkdir -p data/ten_vung_moi
```

### Bước 2: Chuẩn bị files

1. **nodes.csv** – nodes với `lat`, `lon` WGS84 (hoặc tọa độ VN-2000 nếu dùng `coordinate_utils`)
2. **edges.csv** – cạnh với `mode` (road/water)
3. **demand.csv** – nhu cầu vận chuyển
4. **optimization_results_period1.json** (tùy chọn) – kết quả tối ưu

### Bước 3: Cập nhật DataLoader

Trong `data_loader.py`, nếu dùng format đặc biệt, thêm logic trong `load_region_data()`:

```python
if region.lower() == 'ten_vung_moi':
    return self._load_ten_vung_moi_data()
```

---

## 4. Bản đồ Thực tế

### 4.1 Tọa độ

- **WGS84** (lat/lon): dùng trực tiếp cho Folium/OpenStreetMap
- **VN-2000 UTM**: dùng module `coordinate_utils` để chuyển sang WGS84

### 4.2 Chuyển đổi VN-2000 → WGS84

```python
from coordinate_utils import convert_vn2000_to_wgs84

# Tọa độ VN-2000 (x, y) - Mekong Delta
# Longitude column = Easting (x), Latitude column = Northing (y)
x, y = 696169.65, 1205836.64
lat, lon = convert_vn2000_to_wgs84(x, y)
# lat ~ 10.9, lon ~ 106.8 (TP.HCM area)
# Cài pyproj để chuyển đổi chính xác: pip install pyproj
```

### 4.3 Hiển thị bản đồ

Trong app, dùng tab **Scenario** hoặc **Network** với **"Bản đồ thực tế"** được bật. `graph_engine` sẽ vẽ network lên Folium/OpenStreetMap.

### 4.4 Kiểm tra tọa độ

- Mekong Delta: lat ~ 9–11, lon ~ 104–107
- Nếu thấy giá trị ~500k–700k (x) và ~1M–1.2M (y) → đang là VN-2000, cần chuyển sang WGS84

---

## 5. Checklist Thêm Dữ liệu

- [ ] `nodes` có `lat`, `lon` (WGS84 hoặc VN-2000)
- [ ] `edges` có `from_node`, `to_node`, `mode`
- [ ] `demand` có `origin`, `destination`, `commodity`, `volume`, `period`
- [ ] ID node trong `edges`/`demand` khớp với `nodes`
- [ ] Commodity nằm trong: Passenger, Rice, Fisheries, Fruits & Vegetables
- [ ] `optimization_results` (nếu có) đúng format JSON

---

## 6. Nguồn Dữ liệu Gợi ý

- **OpenStreetMap**: xuất nodes/edges từ transport network
- **GDELT/DIVA-GIS**: shapefile có thể chuyển sang CSV
- **Vietnam government**: dữ liệu logistics, ports, waterways
- **UN Comtrade**: trade flows theo commodity
