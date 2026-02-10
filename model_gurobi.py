import csv
import re
import numpy as np
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

print("\n" + "="*80)
print("CELL 2: LOAD DỮ LIỆU TỪ FILE CSV - CẬP NHẬT MỚI")
print("="*80)

# ============================================================
# Helpers
# ============================================================
def _split_semicolon(s: str):
    """Split by ';' (also tolerate ','), strip, drop empties."""
    if s is None:
        return []
    s = str(s).strip()
    if not s:
        return []
    parts = re.split(r"[;]", s)   # phân cách bằng ';'
    return [p.strip() for p in parts if p.strip()]

def _to_float(cell, default=0.0):
    cell = "" if cell is None else str(cell)
    cell = cell.replace(",", "").strip()
    if not cell:
        return default
    try:
        return float(cell)
    except:
        return default

def _to_int(cell, default=0):
    cell = "" if cell is None else str(cell).strip()
    if not cell:
        return default
    try:
        return int(float(cell))
    except:
        return default

def _to_float_list(cell: str):
    """
    Parse like: "1,000; 2,500; 3,000" -> [1000.0, 2500.0, 3000.0]
    """
    vals = []
    for p in _split_semicolon(cell):
        p = p.replace(",", "").strip()
        try:
            vals.append(float(p))
        except:
            continue
    return vals

def _parse_destinations(cell: str):
    """
    Parse destinations separated by ';'
    Example: "5; 12; 18" => [5, 12, 18]
    """
    dests = []
    for p in _split_semicolon(cell):
        # pick all ints in token
        for x in re.findall(r"\d+", p):
            dests.append(int(x))
    return dests

# ============================================================
# 2.1 LOAD ARCS - CẬP NHẬT THEO YÊU CẦU MỚI
# ============================================================
def load_arcs(arc_file):
    """
    Arc file columns cập nhật:
    FromNode, ToNode, Type, Length(m), Project(P/E),
    Investment_Cost (Billion VND), Construction_Time (Years),
    Capacity(tons/year), Capacity_After_Investment (tons/year),
    base_costs  # THÊM CỘT NÀY
    
    Rules:
    - Type: R => road (mode=1), W => waterway (mode=2)
    - Project(P/E):
        P: upgrade project
        E: existing arc
    - base_costs: chi phí vận tải gốc
    """
    edges = []
    print(f"\n[1] Đang load arcs từ: {arc_file}")

    try:
        with open(arc_file, newline='', encoding='utf-8', errors="ignore") as f:
            reader = csv.DictReader(f)
            print(f"   - Các trường trong file: {reader.fieldnames}")

            for row_num, row in enumerate(reader, 1):
                try:
                    u = _to_int(row.get("FromNode"))
                    v = _to_int(row.get("ToNode"))

                    # mode from Type
                    t = str(row.get("Type", "")).strip().upper()
                    if t == "R":
                        mode = 1
                    elif t == "W":
                        mode = 2
                    else:
                        raise ValueError(f"Invalid Type='{t}' (expect R/W)")

                    length_m = _to_float(row.get("Length(m)", 0))
                    
                    # THÊM: base_costs từ file
                    base_cost = _to_float(row.get("base_costs", 0))

                    project = str(row.get("Project(P/E)", "")).strip().upper()
                    if project not in ["P", "E"]:
                        project = "E"  # fallback

                    cap_base = _to_float(row.get("Capacity", 0))
                    cap_after = _to_float(row.get("Capacity_After_Investment", 0))

                    inv_cost = _to_float(row.get("Investment_Cost (Billion VND)", 0))
                    const_time = _to_float(row.get("Construction_Time (Years)", 0))

                    # normalize by rules
                    if project == "E":
                        # existing: after == base, inv=0
                        if cap_after == 0 and cap_base > 0:
                            cap_after = cap_base
                        elif cap_base == 0 and cap_after > 0:
                            cap_base = cap_after
                        elif abs(cap_after - cap_base) > 1e-9:
                            cap_after = cap_base
                        inv_cost = 0.0
                    else:
                        # upgrade project: infer missing if needed
                        if cap_base == 0 and cap_after > 0:
                            cap_base = cap_after
                        if cap_after == 0 and cap_base > 0:
                            cap_after = cap_base

                    edges.append({
                        "u": u,
                        "v": v,
                        "mode": mode,  # 1 road, 2 waterway
                        "length_m": length_m,
                        "base_cost": base_cost,  # THÊM
                        "project": project,  # P or E
                        "capacity_base_tpy": cap_base,
                        "capacity_after_tpy": cap_after,
                        "investment_cost_bil_vnd": inv_cost,
                        "construction_time_years": const_time,
                    })

                except Exception as e:
                    print(f"   ⚠️ Lỗi dòng {row_num}: {e}")
                    continue

        print(f"   ✓ Đã load {len(edges)} arcs thành công")

        # quick summary
        road = sum(1 for a in edges if a["mode"] == 1)
        water = sum(1 for a in edges if a["mode"] == 2)
        Pcnt = sum(1 for a in edges if a["project"] == "P")
        Ecnt = sum(1 for a in edges if a["project"] == "E")
        total_inv = sum(a["investment_cost_bil_vnd"] for a in edges)
        print(f"     - Road arcs: {road} | Waterway arcs: {water}")
        print(f"     - Project P: {Pcnt} | Project E: {Ecnt}")
        print(f"     - Total investment (bil VND): {total_inv:,.2f}")

    except FileNotFoundError:
        print(f"   ✗ Không tìm thấy file: {arc_file}")
    except Exception as e:
        print(f"   ✗ Lỗi khi load file: {e}")

    return edges

# ============================================================
# 2.2 LOAD NODES - CẬP NHẬT THEO YÊU CẦU MỚI
# ============================================================
def load_nodes(node_file):
    """
    Node file columns với yêu cầu mới:
    - Capacity(PCU/year): "5000" hoặc "5000;8000;10000" hoặc "0;5000;8000;10000"
    - Inverst: "100;200" hoặc "100;200;210"
    - Project: "Upgrade" hoặc "New" hoặc "E" hoặc "N"
    """
    OD_pairs = defaultdict(list)

    node_names = {}
    node_projects = {}    # raw
    node_type = {}        # NORMAL / EXISTING_HUB / CANDIDATE_NEW / CANDIDATE_UPGRADE
    node_coords = {}

    node_invest_levels = {}         # nid -> [cost_lvl1, cost_lvl2, ...]
    node_capacity_pcu_levels = {}   # nid -> [base, lvl1, lvl2, ...] hoặc [single]
    node_capacity_passenger = {}    # single float
    node_capacity_goods = {}        # single float

    existing_hubs = []
    candidate_hubs_new = []
    candidate_hubs_upgrade = []
    normal_nodes = []

    print(f"\n[2] Đang load nodes từ: {node_file}")

    try:
        with open(node_file, newline='', encoding='utf-8', errors="ignore") as f:
            reader = csv.DictReader(f)
            print(f"   - Các trường trong file: {reader.fieldnames}")

            for row_num, row in enumerate(reader, 1):
                try:
                    nid = _to_int(row.get("New_ID"))
                    name = str(row.get("Name", "")).strip()
                    proj_raw = str(row.get("Project", "")).strip()

                    node_names[nid] = name
                    node_projects[nid] = proj_raw

                    # classify project
                    p = proj_raw.strip().lower()
                    if p == "n":
                        node_type[nid] = "NORMAL"
                        normal_nodes.append(nid)
                    elif p == "e":
                        node_type[nid] = "EXISTING_HUB"
                        existing_hubs.append(nid)
                    elif p == "new":
                        node_type[nid] = "CANDIDATE_NEW"
                        candidate_hubs_new.append(nid)
                    elif p == "upgrade":
                        node_type[nid] = "CANDIDATE_UPGRADE"
                        candidate_hubs_upgrade.append(nid)
                    else:
                        node_type[nid] = "NORMAL"
                        normal_nodes.append(nid)

                    # coords
                    lon = str(row.get("Longitude", "")).strip()
                    lat = str(row.get("Latitude", "")).strip()
                    node_coords[nid] = (float(lon), float(lat)) if lon and lat else (None, None)

                    # capacities (single)
                    node_capacity_passenger[nid] = _to_float(row.get("Capacity (Passenger)", 0))
                    node_capacity_goods[nid] = _to_float(row.get("Capacity (Goods: (Ton/Year))", 0))

                    # PCU capacity levels - CẬP NHẬT THEO YÊU CẦU
                    pcu_cell = row.get("Capacity(PCU/year)", "")
                    pcu_levels = _to_float_list(pcu_cell)
                    if not pcu_levels:
                        pcu_levels = [0.0]
                    
                    # Xử lý đặc biệt cho new hub (level 0 = 0)
                    if node_type[nid] == "CANDIDATE_NEW" and len(pcu_levels) > 0:
                        # Đảm bảo level 0 = 0
                        pcu_levels[0] = 0.0
                    
                    node_capacity_pcu_levels[nid] = pcu_levels

                    # investment levels - CẬP NHẬT THEO YÊU CẦU
                    inv_cell = row.get("Inverst", "")
                    inv_levels = _to_float_list(inv_cell)
                    
                    if node_type[nid] in ["CANDIDATE_NEW", "CANDIDATE_UPGRADE"]:
                        node_invest_levels[nid] = inv_levels
                    else:
                        node_invest_levels[nid] = []

                    # OD pairs
                    for comm in ["Passenger", "Rice", "Fisheries", "Fruits & Vegetables"]:
                        dests = _parse_destinations(row.get(comm, ""))
                        for d in dests:
                            OD_pairs[comm].append((nid, d))

                except Exception as e:
                    print(f"   ⚠️ Lỗi dòng {row_num}: {e}")
                    continue

        print(f"   ✓ Đã load {len(node_names)} nodes thành công")
        print(f"     - Normal: {len(normal_nodes)} | Existing hubs(E): {len(existing_hubs)} | "
              f"New candidates: {len(candidate_hubs_new)} | Upgrade candidates: {len(candidate_hubs_upgrade)}")

    except FileNotFoundError:
        print(f"   ✗ Không tìm thấy file: {node_file}")
    except Exception as e:
        print(f"   ✗ Lỗi khi load file: {e}")

    return {
        "OD_pairs": OD_pairs,
        "node_names": node_names,
        "node_projects": node_projects,
        "node_type": node_type,
        "node_coords": node_coords,
        "node_capacity_passenger": node_capacity_passenger,
        "node_capacity_goods": node_capacity_goods,
        "node_capacity_pcu_levels": node_capacity_pcu_levels,
        "node_invest_levels": node_invest_levels,
        "existing_hubs": existing_hubs,
        "candidate_hubs_new": candidate_hubs_new,
        "candidate_hubs_upgrade": candidate_hubs_upgrade,
        "normal_nodes": normal_nodes,
    }

# ============================================================
# 2.3 THỰC HIỆN LOAD DỮ LIỆU
# ============================================================
def load_all_data(node_file, arc_file):
    print("\n[3] BẮT ĐẦU LOAD DỮ LIỆU...")

    # Load arcs
    edges_raw = load_arcs(arc_file)

    # Load nodes
    nodes_data = load_nodes(node_file)

    # Unpack theo style bạn hay dùng
    OD_pairs = nodes_data["OD_pairs"]
    node_names = nodes_data["node_names"]
    node_projects = nodes_data["node_projects"]
    node_type = nodes_data["node_type"]
    node_coords = nodes_data["node_coords"]
    node_capacity_passenger = nodes_data["node_capacity_passenger"]
    node_capacity_goods = nodes_data["node_capacity_goods"]
    node_capacity_pcu_levels = nodes_data["node_capacity_pcu_levels"]
    node_invest_levels = nodes_data["node_invest_levels"]

    existing_hubs = nodes_data["existing_hubs"]
    candidate_hubs_new = nodes_data["candidate_hubs_new"]
    candidate_hubs_upgrade = nodes_data["candidate_hubs_upgrade"]
    normal_nodes = nodes_data["normal_nodes"]

    # Useful sets for later modeling
    real_nodes = list(node_names.keys())

    # Potential hubs are New + Upgrade (candidates)
    potential_hubs = candidate_hubs_new + candidate_hubs_upgrade

    # Existing hubs are only E
    existing_hubs = existing_hubs

    # Potential arcs are project == P
    potential_arcs = [(a["u"], a["v"], a["mode"]) for a in edges_raw if a["project"] == "P"]
    potential_arcs_cap_0 = [a["capacity_base_tpy"] for a in edges_raw if a["project"] == "P"]
    potential_arcs_cap_up = [a["capacity_after_tpy"] for a in edges_raw if a["project"] == "P"]
    real_arc_upgrade_costs =  [a["investment_cost_bil_vnd"] for a in edges_raw if a["project"] == "P"]
    existing_arcs = [(a["u"], a["v"], a["mode"]) for a in edges_raw if a["project"] == "E"]
    existing_arcs_cap = [a["capacity_base_tpy"] for a in edges_raw if a["project"] == "E"]

    print("\n[3.1] TẠO CÁC BIẾN TỔNG HỢP:")
    print(f"  • Real nodes: {len(real_nodes)}")
    print(f"  • Existing hubs (E): {len(existing_hubs)}")
    print(f"  • Candidate hubs (New+Upgrade): {len(potential_hubs)}")
    print(f"  • Existing arcs (E): {len(existing_arcs)}")
    print(f"  • Potential arcs (P): {len(potential_arcs)}")
    print(f"  • Commodities: {list(OD_pairs.keys())}")

    return (
        edges_raw,
        OD_pairs, node_names, node_projects, node_type, node_coords,
        node_capacity_passenger, node_capacity_goods,
        node_capacity_pcu_levels, node_invest_levels,
        real_nodes, existing_hubs, potential_hubs,
        existing_arcs, potential_arcs,
        normal_nodes, candidate_hubs_new, candidate_hubs_upgrade, potential_arcs_cap_0, potential_arcs_cap_up, existing_arcs_cap,
        real_arc_upgrade_costs
    )

# ============================================================
# 2.4 THỰC HIỆN LOAD - HỖ TRỢ ĐỌC TỪ PKL
# ============================================================

import pickle
from pathlib import Path

arc_file = 'data/Mekong/arcs_remapped.csv'
node_file = 'data/Mekong/nodes_remapped_with_coords.csv'
data_pkl = 'data/preprocessed_data.pkl'

# Kiểm tra xem đã có file pkl chưa
if Path(data_pkl).exists():
    print(f"\n✓ Tìm thấy file pkl: {data_pkl}")
    print("  Đang đọc từ pkl...")
    with open(data_pkl, 'rb') as f:
        data_dict = pickle.load(f)
    
    # Unpack data
    edges_raw = data_dict['edges_raw']
    OD_pairs = data_dict['OD_pairs']
    node_names = data_dict['node_names']
    node_projects = data_dict['node_projects']
    node_type = data_dict['node_type']
    node_coords = data_dict['node_coords']
    node_capacity_passenger = data_dict['node_capacity_passenger']
    node_capacity_goods = data_dict['node_capacity_goods']
    node_capacity_pcu_levels = data_dict['node_capacity_pcu_levels']
    node_invest_levels = data_dict['node_invest_levels']
    real_nodes = data_dict['real_nodes']
    existing_hubs = data_dict['existing_hubs']
    potential_hubs = data_dict['potential_hubs']
    existing_arcs = data_dict['existing_arcs']
    potential_arcs = data_dict['potential_arcs']
    normal_nodes = data_dict['normal_nodes']
    candidate_hubs_new = data_dict['candidate_hubs_new']
    candidate_hubs_upgrade = data_dict['candidate_hubs_upgrade']
    potential_arcs_cap_0 = data_dict['potential_arcs_cap_0']
    potential_arcs_cap_up = data_dict['potential_arcs_cap_up']
    existing_arcs_cap = data_dict['existing_arcs_cap']
    real_arc_upgrade_costs = data_dict['real_arc_upgrade_costs']
    print("  ✓ Đã đọc xong từ pkl!")
else:
    print(f"\n  Không tìm thấy file pkl: {data_pkl}")
    print("  Đang load từ CSV...")
    edges_raw, OD_pairs, node_names, node_projects, node_type, node_coords, \
    node_capacity_passenger, node_capacity_goods, node_capacity_pcu_levels, node_invest_levels, \
    real_nodes, existing_hubs, potential_hubs, existing_arcs, potential_arcs, \
    normal_nodes, candidate_hubs_new, candidate_hubs_upgrade, potential_arcs_cap_0, potential_arcs_cap_up, existing_arcs_cap, real_arc_upgrade_costs = load_all_data(node_file, arc_file)
    
    # Lưu vào pkl để lần sau dùng
    print(f"\n  Đang lưu vào pkl: {data_pkl}...")
    Path(data_pkl).parent.mkdir(parents=True, exist_ok=True)
    data_dict = {
        'edges_raw': edges_raw,
        'OD_pairs': OD_pairs,
        'node_names': node_names,
        'node_projects': node_projects,
        'node_type': node_type,
        'node_coords': node_coords,
        'node_capacity_passenger': node_capacity_passenger,
        'node_capacity_goods': node_capacity_goods,
        'node_capacity_pcu_levels': node_capacity_pcu_levels,
        'node_invest_levels': node_invest_levels,
        'real_nodes': real_nodes,
        'existing_hubs': existing_hubs,
        'potential_hubs': potential_hubs,
        'existing_arcs': existing_arcs,
        'potential_arcs': potential_arcs,
        'normal_nodes': normal_nodes,
        'candidate_hubs_new': candidate_hubs_new,
        'candidate_hubs_upgrade': candidate_hubs_upgrade,
        'potential_arcs_cap_0': potential_arcs_cap_0,
        'potential_arcs_cap_up': potential_arcs_cap_up,
        'existing_arcs_cap': existing_arcs_cap,
        'real_arc_upgrade_costs': real_arc_upgrade_costs,
    }
    with open(data_pkl, 'wb') as f:
        pickle.dump(data_dict, f)
    print(f"  ✓ Đã lưu xong!")

T = [1, 2]
T_len = len(T)

N = real_nodes

# Tìm tất cả các hub từ dữ liệu
H = existing_hubs + potential_hubs
H_tilde = potential_hubs
H0 = existing_hubs
new_hubs = candidate_hubs_new
print(f"  • Tất cả hubs từ dữ liệu: {H}")

print(f"  • Real nodes: {len(N)} nodes")
# ============================================
#TẠO ARCS TỪ DỮ LIỆU CSV
# ============================================

print("\n[3] Tạo arcs từ dữ liệu CSV:")

# Tạo mapping từ (u,v,mode) sang các loại arcs
def create_arc_structure(edges_raw, all_hubs_from_data):
    real_arcs = []
    virtual_arcs = []
    through_hub_arc = []
    
    # Tạo set của các hub để kiểm tra nhanh
    hubs_set = set(all_hubs_from_data)
    
    for edge in edges_raw:
        u = edge["u"]
        v = edge["v"]
        mode = edge["mode"]
        
        # Tạo virtual node tương ứng
        v_virtual = f'{v}^{mode}'
        u_virtual = f'{u}^{mode}'
        
        # Real arc: từ node thực đến virtual node
        real_arcs.append((u, v_virtual))
        real_arcs.append((v, u_virtual))
        
        # Virtual arc: từ virtual node trở lại node thực
        virtual_arcs.append((v_virtual, v))
        if (u_virtual, u) not in virtual_arcs:
            virtual_arcs.append((u_virtual, u))
        
        # Tạo through-hub arcs nếu cả u và v đều là hub
        if u in hubs_set:
            # Tạo through-hub arc cho mode này
            v_virtual = f'{v}^{mode}'
            through_hub_arc.append((u_virtual, v_virtual))
        
    
    return real_arcs, virtual_arcs, through_hub_arc

real_arcs, virtual_arcs, through_hub_arc = create_arc_structure(edges_raw, H)

# Tạo A (tất cả arcs)
A = real_arcs + virtual_arcs + through_hub_arc

print(f"  • Real arcs: {len(real_arcs)} arcs")
print(f"  • Virtual arcs: {len(virtual_arcs)} arcs")
print(f"  • Through-hub arcs: {len(through_hub_arc)} arcs")
print(f"  • Tổng A: {len(A)} arcs")

# ============================================
# 3.4 PHÂN LOẠI ARCS (POTENTIAL VS EXISTING)
# ============================================

print("\n Phân loại arcs (potential vs existing):")

# Tạo mapping từ real arcs để xác định loại project
arc_project_type = {}
for edge in edges_raw:
    u = edge["u"]
    v = edge["v"]
    mode = edge["mode"]
    project = edge["project"]
    v_virtual = f'{v}^{mode}'
    arc_project_type[(u, v_virtual)] = project

# Phân loại potential và existing arcs
potential_arcs_list = []
existing_arcs_list = []

for arc in A:
    if arc in arc_project_type:
        if arc_project_type[arc] == "P":
            potential_arcs_list.append(arc)
        else:
            existing_arcs_list.append(arc)
    else:
        # Các virtual arcs và through-hub arcs
        # Kiểm tra nếu là virtual arc
        if arc in virtual_arcs:
            existing_arcs_list.append(arc)
        # Kiểm tra nếu là through-hub arc
        elif arc in through_hub_arc:
            # Tìm real arc tương ứng
            u_physical = int(arc[0].split('^')[0])
            v_physical = int(arc[1].split('^')[0])
            mode = int(arc[0].split('^')[1])
            
            # Tìm edge tương ứng
            corresponding_edge = None
            for edge in edges_raw:
                if edge["u"] == u_physical and edge["v"] == v_physical and edge["mode"] == mode:
                    corresponding_edge = edge
                    break
            
            if corresponding_edge and corresponding_edge["project"] == "P":
                potential_arcs_list.append(arc)
            else:
                existing_arcs_list.append(arc)
        else:
            existing_arcs_list.append(arc)
A_tilde = potential_arcs_list
A = real_arcs + virtual_arcs + through_hub_arc
A0 = [arc for arc in A if arc not in A_tilde]

print(f"  • Potential arcs (P): {len(potential_arcs_list)} arcs")
print(f"  • Existing arcs (E): {len(existing_arcs_list)} arcs")

# Map commodity names
G = {
    'Passenger': 'g1',
    'Rice': 'g2',
    'Fisheries': 'g3',
    'Fruits & Vegetables': 'g4'
}

# Tạo OD_pairs theo định dạng mới
OD_pairs_formatted = {}
for comm_name, comm_id in G.items():
    if comm_name in OD_pairs:
        OD_pairs_formatted[comm_id] = OD_pairs[comm_name]

OD_pairs = OD_pairs_formatted

# ============================================
# PATHS FOR EACH OD PAIR - TẠO ĐẦY ĐỦ CÁC PATHS
# ============================================
# ============================================
# CELL 3: XÂY DỰNG ĐỒ THỊ MỞ RỘNG (từ 2026_ToyExample.ipynb)
# ============================================

def to_edge_tuple_list(edges_raw):
    """
    Chuẩn hoá edges_raw về list tuple: (u, v, mode, length, project)
    Hỗ trợ:
      - dict: {"u","v","mode","length_m","project",...}
      - tuple: (u,v,mode,length,project,...) hoặc (u,v,mode,length,project)
    """
    out = []
    for e in edges_raw:
        if isinstance(e, dict):
            u = int(e["u"])
            v = int(e["v"])
            mode = int(e["mode"])                     # 1 road, 2 water
            length = float(e.get("length_m", 0.0))
            project = str(e.get("project", "E"))
        else:
            # assume at least (u,v,mode,length,project)
            u = int(e[0]); v = int(e[1]); mode = int(e[2]); length = float(e[3])
            project = str(e[4]) if len(e) > 4 else "E"
        out.append((u, v, mode, length, project))
    return out

def make_bidirectional_edges(edges):
    """Add reverse direction for every edge (same mode/length/project)."""
    return edges + [(v, u, mode, length, project) for (u, v, mode, length, project) in edges]

def build_expanded_graph(edges_bidir):
    """
    Output G format:
      G[u] contains: [((v,mode), length, 'road'/'water'), ...]
      G[(v,mode)] contains: [(v,0,'virtual_arc')]  # only once
    """
    G = defaultdict(list)

    virtual_nodes = set()  # (v,mode)
    real_nodes = set()

    for u, v, mode, length, _project in edges_bidir:
        real_nodes.add(u)
        real_nodes.add(v)

        if mode == 1:  # ROAD
            G[u].append(((v, 1), float(length), "road"))
            virtual_nodes.add((v, 1))

            # add virtual link (v,1) -> v
            if (v, 0, "virtual_arc") not in G[(v, 1)]:
                G[(v, 1)].append((v, 0, "virtual_arc"))

        elif mode == 2:  # WATERWAY
            G[u].append(((v, 2), float(length), "water"))
            virtual_nodes.add((v, 2))

            # add virtual link (v,2) -> v
            if (v, 0, "virtual_arc") not in G[(v, 2)]:
                G[(v, 2)].append((v, 0, "virtual_arc"))

        else:
            # ignore unknown mode
            continue

    return G, sorted(real_nodes), sorted(list(virtual_nodes))

# =========================
# 2 CHIỀU + BUILD
# =========================
edges_std = to_edge_tuple_list(edges_raw)          # (u,v,mode,length,project)
edges_bidir = make_bidirectional_edges(edges_std)  # add reverse

G_exp, real_nodes_list, virtual_nodes_list = build_expanded_graph(edges_bidir)

print(f"Đồ thị mở rộng: {len(G_exp)} keys trong adjacency")
print(f" - Real nodes: {len(real_nodes_list)}")
print(f" - Virtual nodes: {len(virtual_nodes_list)} (dạng (v,mode))")

# Hiển thị một phần đồ thị để kiểm tra
print("\nSample of expanded graph (first 5 nodes):")
for k in list(G_exp.keys())[:5]:
    print(f"  {k}: {G_exp[k][:3] if len(G_exp[k]) > 3 else G_exp[k]}")

N_virtual = []

for i in virtual_nodes_list:
    virtual_node = str(i[0]) + '^' + str(i[1])
    if virtual_node not in N_virtual:
        N_virtual.append(virtual_node)
all_nodes = N + N_virtual

def to_virtual_label(node):
    """(i, m) -> 'i^m' ; i -> i"""
    if isinstance(node, tuple) and len(node) == 2:
        i, m = node
        return f"{i}^{m}"
    return node

def build_arcs(G_exp):
    real_arcs = []
    virtual_arcs = []

    for u, out_list in G_exp.items():
        for item in out_list:
            # item có thể là: (v, dist, arc_type)  hoặc (v, 0, 'virtual_arc')
            v, _, arc_type = item

            if arc_type in ("road", "water"):
                # cạnh thật: u phải là node thật (int), v thường là node ảo (tuple)
                if isinstance(u, int):
                    real_arcs.append((u, to_virtual_label(v)))

            elif arc_type == "virtual_arc":
                # cạnh ảo: u thường là node ảo (tuple), v thường là node thật (int)
                if isinstance(u, tuple) and isinstance(v, int):
                    virtual_arcs.append((to_virtual_label(u), v))

    return real_arcs, virtual_arcs


# dùng:
real_arcs, virtual_arcs = build_arcs(G_exp)

print("real_arcs:", real_arcs)
print("virtual_arcs:", virtual_arcs)



def parse_virtual(node):
    """
    '2^1' -> (2, 1)
    return (real_node:int, mode:int)
    """
    if isinstance(node, str) and "^" in node:
        a, b = node.split("^", 1)
        return int(a), int(b)
    raise ValueError(f"Not a virtual node label: {node}")

def make_virtual(real_node, mode):
    return f"{int(real_node)}^{int(mode)}"

def add_reverse_arcs(A_tilde):
    A_set = set(A_tilde)
    for u, v in list(A_set):
        # Case 1: real -> virtual
        if isinstance(u, int) and isinstance(v, str) and "^" in v:
            j, m = parse_virtual(v)          # v = 'j^m'
            rev = (j, make_virtual(u, m))    # (j, 'u^m')
            A_set.add(rev)

        # Case 2: virtual -> virtual (through hub)
        elif isinstance(u, str) and "^" in u and isinstance(v, str) and "^" in v:
            A_set.add((v, u))

        else:
            raise ValueError(f"Unknown arc type: {(u, v)}")

    # giữ thứ tự “đẹp”: real->virtual trước, rồi virtual->virtual
    def arc_key(a):
        u, v = a
        typ = 0 if isinstance(u, int) else 1
        return (typ, str(u), str(v))

    return sorted(A_set, key=arc_key)

# dùng:
A_tilde = add_reverse_arcs(A_tilde)

through_hub_arc = add_reverse_arcs(through_hub_arc)
A = add_reverse_arcs(real_arcs) + virtual_arcs + through_hub_arc

A0 = [arc for arc in A if arc not in A_tilde]

# ============================================
# CELL 4: TÍNH L_min CHO TỪNG O-D (từ 2026_ToyExample.ipynb)
# ============================================

print("\n" + "="*80)
print("CELL 4: TÍNH L_min CHO TỪNG O-D")
print("="*80)

from collections import defaultdict
import heapq
import math

def build_reverse_graph(G_exp):
    """
    Build reverse adjacency G_rev so that
      dist_to_targets = dijkstra_multi_target(G_rev, targets)
    gives shortest distance from ANY node -> targets in original graph.

    Input G_exp format:
      - G_exp[u] : [((v,mode), length, 'road'/'water'), ...]
      - G_exp[(v,mode)] : [(v,0,'virtual_arc')]  (implicit length=0)
    Output:
      G_rev[x] : list of (neighbor, weight, edge_type) meaning x -> neighbor in reversed graph
    """
    G_rev = defaultdict(list)

    # collect all real nodes and virtual nodes present
    real_nodes_set = set()
    virtual_nodes_set = set()

    for u, outs in G_exp.items():
        # u may be int or tuple
        if isinstance(u, int):
            real_nodes_set.add(u)
        elif isinstance(u, tuple) and len(u) == 2:
            virtual_nodes_set.add(u)

        for item in outs:
            # case 1: real -> virtual: ((v,mode), length, 'road'/'water')
            if isinstance(item, tuple) and len(item) == 3 and isinstance(item[0], tuple):
                to_node, w, etype = item
                w = float(w)

                # original edge: u -> to_node with weight w
                # reversed edge: to_node -> u with same weight w
                G_rev[to_node].append((u, w, etype))

                # update sets
                if isinstance(u, int):
                    real_nodes_set.add(u)
                if isinstance(to_node, tuple) and len(to_node) == 2:
                    virtual_nodes_set.add(to_node)

            # case 2: virtual -> real: (v,0,'virtual_arc') with weight 0
            elif isinstance(item, tuple) and len(item) == 3 and item[2] == "virtual_arc":
                v, _, _ = item

                # original edge: u(=(v,mode)) -> v with weight 0
                # reversed edge: v -> u with weight 0
                G_rev[v].append((u, 0.0, "virtual_arc"))

                # update sets
                if isinstance(v, int):
                    real_nodes_set.add(v)
                if isinstance(u, tuple) and len(u) == 2:
                    virtual_nodes_set.add(u)

    return G_rev

def dijkstra_multi_target(G_adj, targets):
    """
    Multi-target Dijkstra on adjacency list:
      G_adj[node] = [(neigh, w, etype), ...]
    Return:
      dist[node] = shortest distance from node -> ANY target (in original graph if you passed reverse graph)
    """
    dist = defaultdict(lambda: float('inf'))
    pq = []

    for t in targets:
        dist[t] = 0.0
        heapq.heappush(pq, (0.0, str(type(t)), id(t), t))  # stable tie-break

    while pq:
        d, _, _, node = heapq.heappop(pq)
        if d > dist[node]:
            continue

        for neigh, w, _etype in G_adj.get(node, []):
            nd = d + float(w)
            if nd < dist[neigh]:
                dist[neigh] = nd
                heapq.heappush(pq, (nd, str(type(neigh)), id(neigh), neigh))

    return dist

# Kiểm tra xem đã có file pkl chưa (để skip CELL 4 nếu cần)
paths_pkl_check = 'data/paths_data.pkl'
Lmin_dict_from_pkl = None

if Path(paths_pkl_check).exists():
    try:
        with open(paths_pkl_check, 'rb') as f:
            paths_data_check = pickle.load(f)
        if 'Lmin_dict' in paths_data_check:
            Lmin_dict_from_pkl = paths_data_check['Lmin_dict']
            print(f"\n✓ Tìm thấy Lmin_dict trong pkl, sẽ skip CELL 4 nếu dùng pkl")
    except Exception as e:
        print(f"  ⚠️ Không thể đọc pkl: {e}")

# ------------------------------------------------------------
# 4.1 Build reverse graph once
# ------------------------------------------------------------
if Lmin_dict_from_pkl is None:
    G_rev = build_reverse_graph(G_exp)
    print(f"[CELL 4] Reverse graph built: {len(G_rev)} keys")

    # ------------------------------------------------------------
    # 4.2 Compute L_min for each OD
    #   L_min(comm,o,d) = min_{origin_state in {(o,0),(o,1),(o,2),o}} dist(origin_state -> any target_state)
    #   targets_of_d = {(d,0),(d,1),(d,2),d}  (tùy bạn)
    # ------------------------------------------------------------
    def origin_states(o):
        # origin có thể là node thật "o" hoặc trạng thái (o,1)/(o,2)
        return [o, (o, 1), (o, 2)]

    def dest_targets(d):
        # destination có thể đến trực tiếp node d hoặc các trạng thái (d,1)/(d,2)
        # (d,0) trong code mẫu của bạn thực ra "d" (node thật). Ta giữ cả d cho chắc.
        return [d, (d, 1), (d, 2)]

    Lmin_dict = {}

    inf_count = 0
    total_count = 0

    for comm, pairs in OD_pairs.items():
        for o, d in pairs:
            total_count += 1

            # distances FROM any node TO destination targets in original graph
            dist_to_d = dijkstra_multi_target(G_rev, dest_targets(d))

            # L_min = min distance over origin states
            L_min = min(dist_to_d.get(s, float("inf")) for s in origin_states(o))

            Lmin_dict[(comm, o, d)] = L_min
            if math.isinf(L_min):
                inf_count += 1

    print(f" Đã tính L_min cho {len(Lmin_dict)} cặp O-D | unreachable = {inf_count}/{total_count}")

    # (optional) in thử vài kết quả
    sample = list(Lmin_dict.items())[:10]
    print("\nVí dụ 10 L_min đầu tiên:")
    for (comm, o, d), val in sample:
        print(f"  {comm}: {o} -> {d} | L_min = {val if not math.isinf(val) else 'INF'}")
else:
    Lmin_dict = Lmin_dict_from_pkl
    print(f"\n✓ Đã có Lmin_dict từ pkl, skip CELL 4")

# ============================================
# CELL 5: TÍNH Near optimal CHO TỪNG O-D (từ 2026_ToyExample.ipynb)
# HỖ TRỢ ĐỌC TỪ PKL NẾU ĐÃ CÓ
# ============================================

print("\n" + "="*80)
print("CELL 5: TÍNH NEAR-OPTIMAL PATHS CHO TỪNG O-D")
print("="*80)

paths_pkl = 'data/paths_data.pkl'
skip_path_calculation = False

# Kiểm tra xem đã có file pkl chưa
if Path(paths_pkl).exists():
    print(f"\n✓ Tìm thấy file pkl: {paths_pkl}")
    print("  Đang đọc paths từ pkl...")
    with open(paths_pkl, 'rb') as f:
        paths_data = pickle.load(f)
    
    paths = paths_data['paths']
    if 'Lmin_dict' in paths_data and Lmin_dict is None:
        Lmin_dict = paths_data['Lmin_dict']
    print("  ✓ Đã đọc xong paths từ pkl!")
    print(f"  ✓ Số lượng paths: {sum(len(p) for p in paths.values())}")
    
    # Skip tính toán paths, đi thẳng đến phần sau
    skip_path_calculation = True

EPSILON = 0.25   # Khớp với notebook mẫu (Data Model _ 2026-Feb_05_eps_05.ipynb)
MAX_PATHS_PER_OD = 5000

if not skip_path_calculation:
    def near_optimal_dfs(G, start_node, target_nodes, L_min, epsilon=EPSILON, max_paths=100):
        cutoff = L_min * (1.0 + float(epsilon))
        results = []
        stack = [(start_node, 0.0, [start_node])]  # (node, cost, path)

        while stack and len(results) < max_paths:
            node, cost, path = stack.pop()

            if cost > cutoff:
                continue

            if node in target_nodes:
                results.append((path[:], cost))
                continue

            for neigh, w, edge_type in G.get(node, []):
                if neigh in path:  # tránh vòng
                    continue
                new_cost = cost + float(w)
                if new_cost > cutoff:
                    continue
                stack.append((neigh, new_cost, path + [neigh]))

        return results[:max_paths]

    near_optimal_paths = {}
    total_paths = 0
    unreachable = 0

    for comm, pairs in OD_pairs.items():
        near_optimal_paths[comm] = {}

        for o, d in pairs:
            L_min = Lmin_dict.get((comm, o, d), float("inf"))
            if L_min == float("inf"):
                unreachable += 1
                continue

            # start/end đều là node thật
            start_node = o
            target_nodes = {d}

            # nếu origin không có outgoing trong expanded graph thì bỏ
            if start_node not in G_exp:
                near_optimal_paths[comm][(o, d)] = []
                continue

            paths = near_optimal_dfs(
                G_exp, start_node, target_nodes, L_min,
                epsilon=EPSILON, max_paths=MAX_PATHS_PER_OD
            )

            # loại trùng
            seen = set()
            unique_paths = []
            for path, cost in sorted(paths, key=lambda x: x[1]):
                key = tuple(path)
                if key in seen:
                    continue
                seen.add(key)
                unique_paths.append((path, cost))
                if len(unique_paths) >= MAX_PATHS_PER_OD:
                    break

            near_optimal_paths[comm][(o, d)] = unique_paths
            total_paths += len(unique_paths)

    print(f"Hoàn tất! Tìm được {total_paths} near-optimal paths (ε={EPSILON})")
    print(f"   - Unreachable OD (L_min=INF): {unreachable}")

    def token_to_node(tok):
        """(i,m) -> 'i^m', int stays int"""
        if isinstance(tok, tuple) and len(tok) == 2:
            i, m = tok
            return f"{i}^{m}"
        return tok

    def seq_to_arcs(seq):
        nodes = [token_to_node(tok) for tok in seq]
        return [(nodes[i], nodes[i+1]) for i in range(len(nodes)-1)]

    def build_paths_from_near_optimal(near_optimal_paths):
        """
        near_optimal_paths[comm][(o,d)] = list of (seq, cost)
        return paths[(comm,(o,d))] = list of paths; each path is list of arcs [(u,v),...]
        """
        paths = {}
        for comm, od_dict in near_optimal_paths.items():
            for od, seq_cost_list in od_dict.items():
                expanded = [seq_to_arcs(seq) for (seq, cost) in seq_cost_list]

                # sanity check: start/end must match od
                o, d = od
                for i, p in enumerate(expanded):
                    s, e = p[0][0], p[-1][1]
                    if s != o or e != d:
                        raise ValueError(
                            f"[BUG] {comm} od={od} path{i} has start={s}, end={e}"
                        )

                paths[(comm, od)] = expanded  # mỗi OD có list riêng
        return paths

    # ====== USE ======
    paths = build_paths_from_near_optimal(near_optimal_paths)

    print("Number of paths for g1,(1,5):", len(paths[('g1',(0,14))]))
    print("Example endpoints:", paths[('g1',(0,14))][0][0][0], "->", paths[('g1',(0,14))][0][-1][1])

    import itertools
    import re

    def generate_all_unique_paths_with_through_hubs(paths_list, H):
        """
        Input:
            paths_list : list of paths
                mỗi path là list các arc [(u,v), ...]
            H : list hubs (ví dụ [3,4,6])

        Output:
            unique_paths : list of unique paths (list of arcs)
        """
        def parse_virtual(node):
            """'3^2' -> (3,2), else None"""
            if not isinstance(node, str):
                return None
            m = re.fullmatch(r"(\d+)\^(\d+)", node)
            if not m:
                return None
            return int(m.group(1)), int(m.group(2))

        all_generated = []

        for base_path in paths_list:
            n = len(base_path)

            # --- tìm các block hub có thể through ---
            blocks = []  # mỗi block: {start, through_arc}
            for i in range(n - 2):
                (u1, v1) = base_path[i]
                (u2, v2) = base_path[i + 1]
                (u3, v3) = base_path[i + 2]

                # pattern: (prev -> h^m), (h^m -> h), (h -> next^m)
                hv = parse_virtual(v1)
                if hv is None:
                    continue
                h, mode = hv
                if h not in H:
                    continue
                if (u2, v2) != (v1, h):
                    continue
                if u3 != h:
                    continue

                nv = parse_virtual(v3)
                if nv is None:
                    continue
                _, mode2 = nv
                if mode2 != mode:
                    continue

                blocks.append({
                    "start": i,
                    "through_arc": (v1, v3)  # (h^m -> next^m)
                })

            # nếu không có hub nào thì giữ nguyên
            if not blocks:
                all_generated.append(base_path)
                continue

            # --- sinh tất cả combination không chồng block ---
            for mask in itertools.product([0, 1], repeat=len(blocks)):
                chosen = [blocks[j] for j, b in enumerate(mask) if b == 1]

                # check overlap
                used = set()
                valid = True
                for b in chosen:
                    cover = {b["start"], b["start"] + 1, b["start"] + 2}
                    if used & cover:
                        valid = False
                        break
                    used |= cover
                if not valid:
                    continue

                chosen_by_start = {b["start"]: b for b in chosen}

                # build new path
                new_path = []
                i = 0
                while i < n:
                    if i in chosen_by_start:
                        new_path.append(base_path[i])                 # keep (prev -> h^m)
                        new_path.append(chosen_by_start[i]["through_arc"])
                        i += 3
                    else:
                        new_path.append(base_path[i])
                        i += 1

                all_generated.append(new_path)

        # --- deduplicate ---
        unique_paths = []
        seen = set()
        for p in all_generated:
            key = tuple(p)
            if key not in seen:
                seen.add(key)
                unique_paths.append(p)

        return unique_paths

    all_pairs = {}
    for g, od_list in OD_pairs.items():
        for od in od_list:
            key = (g, od)
            base_paths = paths[key]
            all_pairs[key] = generate_all_unique_paths_with_through_hubs(base_paths, H)

    paths = all_pairs
    
    # Lưu paths vào pkl sau CELL 5
    print("\n  Đang lưu paths vào pkl...")
    Path(paths_pkl).parent.mkdir(parents=True, exist_ok=True)
    paths_data = {
        'paths': paths,
        'Lmin_dict': Lmin_dict,
        'node_names': node_names,
        'node_projects': node_projects,
        'edges_raw': edges_raw,
    }
    with open(paths_pkl, 'wb') as f:
        pickle.dump(paths_data, f)
    print(f"  ✓ Đã lưu paths vào: {paths_pkl}")


# Hub capacity levels 
def build_L_h(node_capacity_pcu_levels, new_hubs, H_tilde, H0):
    """
    node_capacity_pcu_levels: {node: [cap0, cap1, ...]}
    new_hubs: list hubs mới (level0 = 0)
    H_tilde: list potential hubs (level0..)
    H0: list existing hubs (fix at level0 only)

    return: L_h = {h: {level: capacity}}
    """
    L_h = {}

    # 1) New hubs: force level 0 = 0, shift remaining levels to 1..K
    for h in new_hubs:
        caps = node_capacity_pcu_levels.get(h, [])
        if not caps:
            continue
        L_h[h] = {0: 0.0}
        # nếu caps[0] cũng là 0 thì bỏ đi, còn lại gán từ level 1
        tail = caps[1:] if len(caps) > 1 and caps[0] == 0 else caps[1:]
        # nếu dữ liệu của bạn luôn [0, 5000, 8000, 10000] thì tail = [5000,8000,10000]
        for l, cap in enumerate(tail, start=1):
            L_h[h][l] = float(cap)

    # 2) Potential hubs: keep levels as given (0..K)
    for h in H_tilde:
        caps = node_capacity_pcu_levels.get(h, [])
        if not caps:
            continue
        L_h[h] = {l: float(cap) for l, cap in enumerate(caps)}

    # 3) Existing hubs: only level 0
    for h in H0:
        caps = node_capacity_pcu_levels.get(h, [])
        if not caps:
            continue
        L_h[h] = {0: float(caps[0])}

    return L_h
L_h = build_L_h(
    node_capacity_pcu_levels=node_capacity_pcu_levels,
    new_hubs=new_hubs,
    H_tilde=H_tilde,
    H0=H0
)

# Capacity cho các cạnh có thể nâng cấp (potential arcs)
print(f"\n  c) CÁC CẠNH CÓ THỂ NÂNG CẤP (potential arcs):")

L_a = {}
for a in A_tilde:
    # Base capacity (level 0) - đủ cho nhu cầu cơ bản
    base_capacity = 10000000
    
    # Upgraded capacity (level 1) - đủ cho nhu cầu cao nhất
    if '^1' in str(a[0]) or '^1' in str(a[1]):  # Road
        upgraded_capacity =  15398438 # Tăng lên
        mode = 'road'
    else:  # Waterway
        upgraded_capacity = 18472500   # Tăng lên
        mode = 'waterway'
    
    L_a[a] = {0: base_capacity, 1: upgraded_capacity}
    print(f"     {a} ({mode}): level 0 = {base_capacity:,}, level 1 = {upgraded_capacity:,}")

def build_through_hub_mapping_all(H, A_tilde):
    """
    Tổng quát: tạo through_hub_mapping cho mọi cặp (hub -> node) và mọi mode.
    
    Mapping: (f"{h}{m}", f"{j}{m}") -> (h, f"{j}{m}")
    
    Inputs:
      - H: list hubs (ví dụ [3,4,6])
      - nodes: list các node thật mà hub có thể "đi tới"
               nếu None -> dùng union(H) (không khuyến nghị) 
               => nên truyền danh sách node thật của bạn (VD: N_real)
      - modes: tuple/list các mode suffix (vd ('^1','^2'))
    
    Output:
      - through_hub_mapping: dict
    """
    through_hub_mapping = {}
    for u, v in A_tilde:
        if isinstance(u, int) and u in H and isinstance(v, str) and '^' in v:
            m = v[-1]
            through_hub_mapping[(f"{u}^{m}", f"{v}")] = (u, f"{v}")
    return through_hub_mapping

# ============================================
# COSTS AND CAPACITIES 
# ============================================

print("\n=== THIẾT LẬP CHI PHÍ VÀ NĂNG LỰC NÂNG CẤP (THEO YÊU CẦU) ===")
# Hub upgrade cost (per unit capacity) - CHỈ ÁP DỤNG CHO HUB 3,4
f_lh = {1: 100, 2: 200, 3: 210}

print("\n[4] Thiết lập chi phí nâng cấp (trên mỗi đơn vị công suất):")

f_la = {}

# Chi phí nâng cấp cho real arcs
real_arc_upgrade_costs_dict = {}
for i in range(len(potential_arcs)):
    u = potential_arcs[i][0]
    v = potential_arcs[i][1]
    m = potential_arcs[i][2]
    real_arc_upgrade_costs_dict[(u, f"{v}^{m}")] = int(real_arc_upgrade_costs[i])

 
print("\n  a) Chi phí nâng cấp cho real arcs:")
for arc, cost in real_arc_upgrade_costs_dict.items():
    f_la[arc] = cost
    mode = 'road' if '^1' in arc[1] else 'waterway'
    print(f"     Real arc {arc} ({mode}): {cost}")


# Through-hub arcs có chi phí nâng cấp bằng real arc tương ứng
print("\n  b) Chi phí nâng cấp for through-hub arcs (bằng real arc tương ứng):")
through_hub_mapping = build_through_hub_mapping_all(H, A_tilde)

for thru_arc, real_arc in through_hub_mapping.items():
    cost = f_la.get(real_arc, 100)
    f_la[thru_arc] = cost
    mode = 'road' if '^1' in thru_arc[0] else 'waterway'
    print(f"     Through-hub arc {thru_arc} ({mode}): {cost} (bằng {real_arc})")

# Các cạnh ảo KHÔNG có chi phí nâng cấp (vì không thể/không cần nâng cấp)
print("\n  c) Chi phí nâng cấp cho các cạnh ảo = 0:")
# Tất cả các cạnh ảo (mode node → physical node)
virtual_arcs_all = virtual_arcs
for hub in H:
    if (f'{hub}^1', hub) not in virtual_arcs_all:
        virtual_arcs_all.append((f'{hub}^1', hub))  # Road mode → Physical hub
    if (f'{hub}^2', hub) not in virtual_arcs_all:
        virtual_arcs_all.append((f'{hub}^2', hub))  # Waterway mode → Physical hub

for arc in virtual_arcs_all:
    f_la[arc] = 0
    mode = 'road' if '^1' in arc[0] else 'waterway'
    print(f"     Virtual arc {arc} ({mode}): 0")

# ============================================
# TRANSPORT COSTS: CONSTANT BASE = 400
# ============================================

BASE_CONST = 400.0
HUB_HUB_DISCOUNT = 0.75

c_a = {}
base_costs = {}

def physical_node(n):
    """Return physical node id from real/virtual label, e.g. '4^1' -> 4, 3 -> 3."""
    if isinstance(n, str) and '^' in n:
        return int(n.split('^')[0])
    return n

# 1) Base cost for ALL real arcs = 400
for arc in real_arcs:
    base_costs[arc] = BASE_CONST

# 2) Base cost for ALL through-hub arcs = 400
for arc in through_hub_arc:
    base_costs[arc] = BASE_CONST

# 3) THÊM: Base cost cho các arc ngược chiều của real arcs
print("\n[2.5] Thêm base cost cho arcs ngược chiều:")
for arc in real_arcs:
    # Tạo arc ngược chiều: (j^m, i) từ (i, j^m)
    j_physical = physical_node(arc[1])  # Lấy node thực từ j^m
    reverse_arc = (arc[1], j_physical)  # (j^m, j)
    
    # Gán cùng base cost cho arc ngược chiều
    base_costs[reverse_arc] = BASE_CONST
    print(f"  Đã thêm: {reverse_arc}: {BASE_CONST}")

# 4) Assign real arc costs (apply discount if hub-hub)
print("\n[3] Chi phí real arcs (đi vào hub):")
for arc in real_arcs:
    if arc in base_costs:
        base = base_costs[arc]
        i = physical_node(arc[0])  # tail (real node)
        j = physical_node(arc[1])  # head physical node
        
        # Điều kiện giảm: i và j đều là hub trong H
        if (i in H) and (j in H):
            cost = base * HUB_HUB_DISCOUNT
            note = "GIẢM 25% (hub-hub)"
        else:
            cost = base
            note = "GIỮ NGUYÊN (không phải hub-hub)"
        
        c_a[arc] = cost
        mode = 'road' if '^1' in arc[1] else 'waterway'
        print(f"  {arc} ({mode}): {cost:.2f} | base={base} | {note}")

# 5) THÊM: Chi phí cho arcs ngược chiều (phải tính giống như real arcs)
print("\n[4] Chi phí cho arcs ngược chiều:")
for arc in real_arcs:
    j_physical = physical_node(arc[1])
    reverse_arc = (arc[1], j_physical)
    
    if reverse_arc in base_costs:
        base = base_costs[reverse_arc]
        i_rev = physical_node(reverse_arc[0])  # từ j^m lấy j
        j_rev = physical_node(reverse_arc[1])  # j
        
        # Điều kiện giảm: cả 2 đầu đều là hub
        if (i_rev in H) and (j_rev in H):
            cost = base * HUB_HUB_DISCOUNT
            note = "GIẢM 25% (hub-hub)"
        else:
            cost = base
            note = "GIỮ NGUYÊN (không phải hub-hub)"
        
        c_a[reverse_arc] = cost
        mode = 'road' if '^1' in reverse_arc[0] else 'waterway'
        print(f"  {reverse_arc} ({mode}): {cost:.2f} | base={base} | {note}")

# 6) Assign through-hub arc costs (KHÔNG giảm giá)
print("\n[5] Chi phí through-hub arcs (không vào hub):")
for arc in through_hub_arc:
    if arc in base_costs:
        cost = base_costs[arc]
        c_a[arc] = cost
        mode = 'road' if '^1' in arc[0] else 'waterway'
        print(f"  {arc} ({mode}): {cost}")

# 7) Virtual arcs cost = 0
print("\n[6] Chi phí virtual arcs (luôn = 0):")
for arc in virtual_arcs_all:
    c_a.setdefault(arc, 0.0)
    print(f"  {arc}: 0.0")

# 8) KIỂM TRA TÍNH ĐỐI XỨNG
print("\n[7] Kiểm tra tính đối xứng của chi phí:")
for arc in real_arcs:
    j_physical = physical_node(arc[1])
    reverse_arc = (arc[1], j_physical)
    
    if arc in c_a and reverse_arc in c_a:
        if abs(c_a[arc] - c_a[reverse_arc]) < 0.01:
            print(f"  ✓ {arc}: {c_a[arc]:.2f} == {reverse_arc}: {c_a[reverse_arc]:.2f}")
        else:
            print(f"  ✗ {arc}: {c_a[arc]:.2f} ≠ {reverse_arc}: {c_a[reverse_arc]:.2f}")

print(f"\n✓ Done. Total arcs with cost: {len(c_a)}")

# ============================================
# SETUP COSTS + CAPACITIES (GENERALIZED FOR MANY HUBS)
# ============================================

import gurobipy as gp
from gurobipy import GRB

# ------------------------------------------------
# 0) COST PARAMETERS (general)
# ------------------------------------------------
# Mode switching cost at hub (theo Data Model _ 2026-Feb_05-Eps_02.ipynb)
c_s = 500

# Service cost at hubs
# Tạo dictionary c_h cho TẤT CẢ hubs trong H với giá trị mặc định
c_h = {h: 1000 for h in H}

# Định nghĩa budget cho từng period (theo Data Model _ 2026-Feb_05-Eps_02.ipynb)
B = {
    1: 200_000_000_000_000_000_000,
    2: 250_000_000_000_000_000_000,
    3: 350_000_000_000_000_000_000,
}

print("\n=== COST PARAMETERS ===")
print(f"  Mode switching cost c_s = {c_s}")
print(f"  Service cost c_h (cho tất cả {len(H)} hubs): đều = 1000")
print(f"  Budget B theo period: {B}")


# ------------------------------------------------
# 1) HUB CAPACITY DICTIONARY L_h
#    Tạo từ node_capacity_pcu_levels: {hub: [cap_level0, cap_level1, ...]}
# ------------------------------------------------
print("\n[1] THIẾT LẬP CAPACITY CHO HUBS (GENERALIZED):")

# Tạo L_h từ node_capacity_pcu_levels
L_h = {}
for h in H:
    levels = node_capacity_pcu_levels.get(h, [])
    if not levels:
        L_h[h] = {0: 0.0}
    else:
        L_h[h] = {l: float(cap) for l, cap in enumerate(levels)}

# a) NEW HUBS (phải mở mới có capacity)
print("\n  a) NEW HUBS (phải mở mới có capacity):")
if len(new_hubs) == 0:
    print("    (None)")
else:
    for h in sorted(new_hubs):
        if h in L_h:
            print(f"    Hub {h}:")
            for l in sorted(L_h[h].keys()):
                cap = L_h[h][l]
                if l == 0:
                    print(f"      Level {l}: {cap:,.0f} (KHÔNG MỞ - capacity = 0)")
                else:
                    up_cost = f_lh.get(l, 0)
                    print(f"      Level {l}: {cap:,.0f} (chi phí nâng cấp: {up_cost} per unit)")
            print("      Note: Nếu hub ở level 0 → không thể dùng hub-service, phải dùng through-hub paths")

# b) POTENTIAL HUBS (có thể nâng cấp, level 0 là base capacity)
print("\n  b) POTENTIAL HUBS (có thể nâng cấp):")
if len(H_tilde) == 0:
    print("    (None)")
else:
    for h in sorted(H_tilde):
        if h in L_h:
            print(f"    Hub {h}:")
            for l in sorted(L_h[h].keys()):
                cap = L_h[h][l]
                if l == 0:
                    print(f"      Level {l}: {cap:,.0f} (base capacity)")
                else:
                    up_cost = f_lh.get(l, 0)
                    print(f"      Level {l}: {cap:,.0f} (chi phí nâng cấp: {up_cost} per unit)")

# c) EXISTING HUBS (cố định, không thể nâng cấp)
print("\n  c) EXISTING HUBS (không thể nâng cấp):")
if len(H0) == 0:
    print("    (None)")
else:
    for h in sorted(H0):
        if h in L_h:
            cap0 = L_h[h].get(0, 0.0)
            print(f"    Hub {h}:")
            print(f"      Level 0: {cap0:,.0f} (cố định, không thể nâng cấp)")

print(f"\n✓ Phân loại hub:")
print(f"  - New hubs (phải mở): {sorted(new_hubs)}")
print(f"  - Potential hubs: {sorted(H_tilde)}")
print(f"  - Existing hubs: {sorted(H0)}")


# ============================================
# 2) XÁC ĐỊNH TẤT CẢ CÁC LOẠI CẠNH
# ============================================
print("\n[2] Xác định tất cả các loại cạnh:")

print(f"  • Virtual arcs: {len(virtual_arcs_all)} cạnh")
if len(virtual_arcs_all) <= 10:
    for arc in list(virtual_arcs_all)[:10]:
        print(f"      {arc}")
    if len(virtual_arcs_all) > 10:
        print(f"      ... và {len(virtual_arcs_all)-10} cạnh nữa")

print(f"  • Potential arcs: {len(A_tilde)} cạnh")
if len(A_tilde) <= 10:
    for arc in list(A_tilde)[:10]:
        print(f"      {arc}")
    if len(A_tilde) > 10:
        print(f"      ... và {len(A_tilde)-10} cạnh nữa")

print(f"  • Existing arcs: {len(A0)} cạnh")
if len(A0) <= 10:
    for arc in list(A0)[:10]:
        print(f"      {arc}")
    if len(A0) > 10:
        print(f"      ... và {len(A0)-10} cạnh nữa")

# Capacity cho các cạnh ảo = VÔ CÙNG LỚN
M = 10_000_000  # Số rất lớn đại diện cho vô cùng
# Capacity cho các cạnh hiện có (không thể nâng cấp) - GIỮ LẠI 10,000,000
existing_arc_capacity = 10_000_000

print(f"\n  Capacity mặc định:")
print(f"    - Virtual arcs: {M:,} (vô cùng lớn)")
print(f"    - Existing arcs: {existing_arc_capacity:,} (cố định)")


# ============================================
# 3) HÀM LẤY HUB CAPACITY
# ============================================
print("\n[3] Hàm lấy hub capacity:")

def get_hub_capacity(hub, upgrade_level=0):
    """
    Lấy capacity của hub dựa trên loại hub và mức nâng cấp
    """
    if hub not in L_h:
        return 0.0
    
    # Existing hub: chỉ có level 0, không thể nâng cấp
    if hub in H0:
        if upgrade_level == 0:
            return L_h[hub][0]
        else:
            # Cảnh báo nhưng vẫn trả về capacity level 0
            print(f"  [WARNING] Hub {hub} là existing hub, không thể nâng cấp. Trả về capacity level 0.")
            return L_h[hub][0]
    
    # Potential / New hub: có thể nâng cấp
    if upgrade_level in L_h[hub]:
        return L_h[hub][upgrade_level]
    else:
        # Nếu level không tồn tại, trả về level cao nhất có sẵn
        max_level = max(L_h[hub].keys())
        if upgrade_level > max_level:
            return L_h[hub][max_level]
        else:
            return L_h[hub].get(0, 0.0)


# ============================================
# 4) HÀM LẤY ARC CAPACITY
# ============================================
print("\n[4] Hàm lấy capacity thống nhất cho tất cả các loại cạnh:")

def get_arc_capacity(arc, level=0):
    """
    Lấy capacity của một cạnh
    """
    # 1. Virtual arcs: capacity vô cùng lớn
    if arc in virtual_arcs_all:
        return M
    
    # 2. Potential arcs: có thể nâng cấp
    elif arc in A_tilde:
        if level == 0:
            return L_a[arc][0]  # Base capacity
        else:
            return L_a[arc][1]  # Upgraded capacity
    
    # 3. Existing arcs: capacity cố định (10,000,000)
    elif arc in A0:
        return existing_arc_capacity
    
    # 4. Through-hub arcs: xử lý đặc biệt
    elif arc in through_hub_arc:
        # Tìm real arc tương ứng
        real_arc = None
        if arc in through_hub_mapping:
            real_arc = through_hub_mapping[arc]
        
        if real_arc and real_arc in L_a:
            if level == 0:
                return L_a[real_arc][0]
            else:
                return L_a[real_arc][1]
        elif real_arc and real_arc in A0:
            return existing_arc_capacity  # Nếu real arc là existing
        else:
            return existing_arc_capacity  # Default
    
    # 5. Default
    else:
        return existing_arc_capacity

print(f"✓ Virtual arcs: capacity = {M:,} (vô cùng lớn)")
print(f"✓ Potential arcs: có thể nâng cấp từ level 0 → level 1")
print(f"✓ Existing arcs: capacity cố định = {existing_arc_capacity:,}")


# ============================================
# 5) LINK UPGRADE DEPENDENCIES
# ============================================
print("\n=== PHỤ THUỘC NÂNG CẤP GIỮA CÁC ARCS ===")

# Khi real arc được nâng cấp, through-hub arc tương ứng cũng được nâng cấp
upgrade_dependencies = through_hub_mapping

print(f"Có {len(upgrade_dependencies)} phụ thuộc nâng cấp:")
shown = 0
for through_arc, real_arc in upgrade_dependencies.items():
    print(f"  {real_arc} → {through_arc}")
    shown += 1
    if shown >= 10 and len(upgrade_dependencies) > 10:
        print(f"  ... ({len(upgrade_dependencies)-10} mappings more)")
        break


# ============================================
# 6) TRANSPORTATION DEMAND
# ============================================
print("\n[5] THIẾT LẬP NHU CẦU VẬN TẢI")

# Tạo w_gk dựa trên OD_pairs
w_gk = {}
T_list = list(T)  # Đảm bảo T là iterable

# Base demand mỗi commodity (theo Data Model _ 2026-Feb_05-Eps_02.ipynb)
BASE_DEMAND = 10_000

# Nếu có growth_factor, tính demand tăng dần theo thời gian
growth_factor = {1: 1.0, 2: 1.5, 3: 2.0}  # Ví dụ: tăng 50% mỗi kỳ

for g, od_list in OD_pairs.items():
    # Phân bố base demand = 1,000,000 cho mỗi commodity
    # Nếu có nhiều OD pairs, chia đều
    num_od_pairs = len(od_list)
    if num_od_pairs > 0:
        demand_per_od = BASE_DEMAND / num_od_pairs
    else:
        demand_per_od = BASE_DEMAND
    
    for t in T_list:
        # Tính demand cho kỳ t (có thể dùng growth_factor)
        growth = growth_factor.get(t, 1.0)
        demand_t = demand_per_od * growth
        
        for od in od_list:
            w_gk[(g, od, t)] = demand_t

print(f"  ✓ Đã tạo w_gk cho {len(OD_pairs)} commodities:")
print(f"  ✓ Base demand mỗi commodity: {BASE_DEMAND:,}")
for g in OD_pairs:
    od_list = OD_pairs[g]
    commodity_name = "Passenger" if g == 'g1' else "Rice" if g == 'g2' else g
    print(f"\n    • {commodity_name} ({g}): {len(od_list)} OD pairs")
    
    # Tính tổng demand cho commodity này
    total_demand_g = 0
    for od in od_list:
        for t in T_list:
            if (g, od, t) in w_gk:
                total_demand_g += w_gk[(g, od, t)]
    
    print(f"      Tổng demand (tất cả kỳ): {total_demand_g:,.0f}")
    
    # Hiển thị 2 OD đầu tiên và 2 kỳ đầu
    for od in od_list[:2]:
        print(f"      OD {od[0]}→{od[1]}:")
        for t in T_list[:2]:
            if (g, od, t) in w_gk:
                print(f"        Kỳ {t}: {w_gk[(g, od, t)]:,.0f}")
    
    if len(od_list) > 2:
        print(f"      ... và {len(od_list)-2} OD pairs nữa")


# ============================================
# 7) KIỂM TRA TÍNH KHẢ THI VỚI DỮ LIỆU LỚN
# ============================================
print("\n[6] Kiểm tra tính khả thi của mô hình (với dữ liệu lớn):")

# Tính tổng demand cho mỗi kỳ
print(f"\n  Tổng demand theo từng kỳ:")
for t in T_list:
    total_demand = 0
    for (g, od, period), demand in w_gk.items():
        if period == t:
            total_demand += demand
    print(f"    Period {t}: {total_demand:,.0f}")

# Tính tổng demand tất cả kỳ
total_all_periods = sum(w_gk.values())
print(f"  Tổng demand tất cả kỳ: {total_all_periods:,.0f}")

print("\n  Kiểm tra capacity tại các hub quan trọng:")
important_hubs = []
if new_hubs: important_hubs.extend(new_hubs[:3])  # Lấy 3 new hubs đầu
if H_tilde: important_hubs.extend(H_tilde[:3])    # Lấy 3 potential hubs đầu
if H0: important_hubs.extend(H0[:3])              # Lấy 3 existing hubs đầu

# Lấy kỳ có demand cao nhất
max_t = max(T_list)
total_demand_max_t = sum(demand for (g, od, t), demand in w_gk.items() if t == max_t)

for hub in important_hubs:
    if hub in L_h:
        if hub in H0:
            hub_cap = get_hub_capacity(hub, 0)
            hub_type = "Existing hub (cố định)"
        else:
            # Lấy capacity level cao nhất
            max_level = max(L_h[hub].keys())
            hub_cap = get_hub_capacity(hub, max_level)
            hub_type = f"Non-existing hub (max level {max_level})"
        
        print(f"\n  Hub {hub} ({hub_type}):")
        print(f"    - Capacity tối đa: {hub_cap:,.0f}")
        
        # Ước tính demand qua hub này (phân bố theo tỷ lệ)
        # Giả sử các hub chính xử lý phần lớn demand
        if hub in [6, 10, 12] or hub in new_hubs[:3] or hub in H_tilde[:3]:
            # Hub quan trọng: xử lý nhiều demand
            hub_demand = total_demand_max_t * 0.7  # 70% demand
        else:
            # Hub phụ: xử lý ít demand hơn
            hub_demand = total_demand_max_t * 0.3  # 30% demand
        
        print(f"    - Ước tính demand (period {max_t}): {hub_demand:,.0f}")
        
        if hub_demand <= hub_cap:
            print(f"    ✓ ĐỦ capacity: {hub_demand:,.0f} ≤ {hub_cap:,.0f}")
            print(f"      Dư capacity: {hub_cap - hub_demand:,.0f} ({((hub_cap - hub_demand)/hub_cap*100):.1f}%)")
        else:
            print(f"    ✗ THIẾU capacity: {hub_demand:,.0f} > {hub_cap:,.0f}")
            print(f"      Thiếu: {hub_demand - hub_cap:,.0f} (cần nâng cấp {((hub_demand - hub_cap)/hub_cap*100):.1f}%)")


# ============================================
# 8) KIỂM TRA HÀM GET_HUB_CAPACITY
# ============================================
print("\n[7] Kiểm tra hàm get_hub_capacity():")

# Kiểm tra các hub tiêu biểu
test_cases = []
if new_hubs: test_cases.append(("New hub", new_hubs[0]))
if H_tilde: test_cases.append(("Potential hub", H_tilde[0]))
if H0: test_cases.append(("Existing hub", H0[0]))

for hub_type, hub in test_cases:
    if hub in L_h:
        print(f"\n  {hub_type} {hub}:")
        levels_to_check = sorted(L_h[hub].keys())
        if len(levels_to_check) > 3:
            levels_to_check = [levels_to_check[0], levels_to_check[len(levels_to_check)//2], levels_to_check[-1]]
        
        for level in levels_to_check:
            capacity = get_hub_capacity(hub, level)
            actual = L_h[hub][level]
            if abs(capacity - actual) < 0.01:
                print(f"    ✓ Level {level}: {capacity:,.0f}")
            else:
                print(f"    ✗ Level {level}: {capacity:,.0f} (thực tế: {actual:,.0f})")


print("\n=== KẾT LUẬN (VỚI DỮ LIỆU LỚN) ===")
print("✓ c_h: tất cả hubs có service cost = 1")
print(f"✓ L_h: capacity hubs (có thể lên đến hàng triệu)")
print(f"✓ Capacity mặc định: existing arcs = {existing_arc_capacity:,}, virtual arcs = {M:,}")
print(f"✓ Base demand: {BASE_DEMAND:,} per commodity")
print(f"✓ Tổng demand tất cả kỳ: {total_all_periods:,.0f}")
print("✓ Mô hình đã được scale phù hợp với dữ liệu thực tế lớn")

# ============================================
# INITIALIZE GUROBI MODEL VÀ BIẾN 
# ============================================

print("\n" + "="*60)
print("KHỞI TẠO MÔ HÌNH VÀ BIẾN QUYẾT ĐỊNH")
print("="*60)

model = gp.Model("Multimodal_Hub_Network_Optimization")
model.setParam('OutputFlag', 1)
model.setParam('TimeLimit', 3600)
model.setParam('MIPGap', 0.01)

# 3.1 Hub state variables
y_h = {}
print("\n[1] Biến trạng thái hub (y_h):")
print("  a) NEW HUB 3 (4 levels, level 0 = không mở):")
for h in new_hubs:  # [3]
    for l in [0, 1, 2, 3]:  # 4 levels, level 0 = không mở
        for t in T:
            var_name = f"y_h_{h}_l{l}_t{t}"
            y_h[(h, l, t)] = model.addVar(vtype=GRB.BINARY, name=var_name)
            print(f"    {var_name}")


print("\n  b) Potential hub 4 (3 levels):")
for h in H_tilde:  # [4]
    for l in [0, 1, 2]:  # 3 levels
        for t in T:
            var_name = f"y_hub_{h}_l{l}_t{t}"
            y_h[(h, l, t)] = model.addVar(vtype=GRB.BINARY, name=var_name)
            print(f"    {var_name}")


print("\n  c) Existing hub (6) - chỉ có level 0:")
for h in H0:
    for t in T:
        # Hub 6 luôn ở level 0
        var_name = f"y_hub_{h}_l0_t{t}"
        y_h[(h, 0, t)] = model.addVar(vtype=GRB.BINARY, name=var_name)
        print(f"    {var_name}")
    
        # Tạo biến level 1, 2 cho hub 6 (sẽ bị constraint = 0)
        for l in [1, 2]:
            var_name = f"y_hub_{h}_l{l}_t{t}"
            y_h[(h, l, t)] = model.addVar(vtype=GRB.BINARY, name=var_name)
            print(f"    {var_name} (sẽ bị constraint = 0)")


# 3.2 Arc state variables
y_a = {}
print("\n[2] Biến trạng thái arc (y_a):")
for a in A_tilde:
    for l in [0, 1]:
        for t in T:
            y_a[(a[0], a[1], l, t)] = model.addVar(vtype=GRB.BINARY, 
                                                    name=f"y_arc_{a[0]}_{a[1]}_{l}_{t}")

# 3.3 Flow allocation variables 
v_path = {}
print("\n[3] Biến phân bố luồng (v_path):")
for g, od_pairs_list in OD_pairs.items():
    for od in od_pairs_list:
        for idx, _ in enumerate(paths[(g, od)]):
            for t in T:
                v_path[(g, od, idx, t)] = model.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS,
                                                      name=f"v_{g}_{od[0]}_{od[1]}_p{idx+1}_t{t}")

# 3.4 Total flow through hub variables 
u_hub = {}
print("\n[4] Biến tổng luồng qua hub (u_hub):")
for h in H:  # [3, 4, 6]
    for t in T:
        u_hub[(h, t)] = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"u_hub_{h}_{t}")

# 3.5  Total flow through arc variables - GIỮ NGUYÊN
x_arc = {}
print("\n[7] Biến luồng trên arc (x_arc):")
for a in A:
    for t in T:
        x_arc[(a[0], a[1], t)] = model.addVar(lb=0, vtype=GRB.CONTINUOUS, 
                                             name=f"x_arc_{a[0]}_{a[1]}_{t}")

model.update()
print(f"\n✓ Đã tạo {model.numVars} biến")
print(f"  - Potential hubs (3,4): 3 levels × 2 periods × 2 hubs = 12 biến")
print(f"  - Existing hub (6): 3 levels × 2 periods = 6 biến (level 1,2 sẽ constraint = 0)")
print(f"  - Tổng biến y_h: 18 biến")


def get_hub_capacity_constraint(hub, t):
    """
    Trả về biểu thức capacity constraint cho hub
    """
    if hub in H0:
        # Hub hiện có: capacity cố định
        return L_h[hub][0]
    else:
        # Hub tiềm năng: capacity phụ thuộc vào level
        return gp.quicksum(
            L_h[hub][l] * y_h[(hub, l, t)] 
            for l in [0, 1, 2]
        )

print("\n" + "="*60)
print("8. THIẾT LẬP HÀM MỤC TIÊU (THEO FORMULATION TOÁN HỌC - NEW HUB 3)")
print("="*60)

# 8.1 Hub service cost
print("\n[1] Chi phí dịch vụ tại hub (hub service cost):")
service_cost = gp.quicksum(
    c_h[h] * u_hub[(h, t)]
    for h in H for t in T
    if h in c_h
)
print(f"  ✓ Đã tính hub service cost")

# 8.2 Transportation cost

def calculate_transport_cost(path):
    """Calculate transport cost for a path - FIXED VERSION"""
    path_transport_cost = 0
    for i in range(len(path) - 1):
        path_transport_cost += c_a.get((path[i][0], path[i][1]), 0)
    return path_transport_cost

transport_terms = []
for g, od_pairs_list in OD_pairs.items():
    for od in od_pairs_list:
        for idx, path in enumerate(paths[(g, od)]):
            path_transport_cost = calculate_transport_cost(path)
            for t in T:
                transport_terms.append(path_transport_cost * w_gk[(g, od, t)] * v_path[(g, od, idx, t)] )
                
print("\n[2] Chi phí vận tải (transportation cost):")
transport_cost = gp.quicksum(transport_terms)
print(f"  ✓ Đã tính transportation cost")


# 8.3 Mode switching cost
print("\n[3] Chi phí chuyển đổi mode (mode switching cost):")
# Cần tạo biến mode switching
mode_switch_terms = []
print("  Tạo biến mode switching và tính chi phí...")
for g, od_pairs_list in OD_pairs.items():
    for od in od_pairs_list:
        for idx, path in enumerate(paths[(g, od)]):
            for t in T:
                # Tạo biến cho mỗi hub trong path nếu có chuyển đổi mode
                for i in range(len(path) - 2):
                    current_arc = path[i]
                    next_arc = path[i+1]
                    
                    # Kiểm tra nếu là chuyển đổi mode tại hub
                    if isinstance(current_arc[0], str) and isinstance (next_arc[1], str) and next_arc[1].startswith(('3', '4', '6')):
                        hub = int(next_arc[1][0]) if next_arc[1][0].isdigit() else None
                        if hub and hub in H:
                            current_mode = 'road' if '^1' in str(current_arc[0]) else 'waterway'
                            next_mode = 'road' if '^1' in str(next_arc[1]) else 'waterway'
                            if current_mode != next_mode:
                                mode_switch_terms.append(c_s * w_gk[(g, od, t)] * v_path[(g, od, idx, t)])

mode_switch_cost = gp.quicksum(mode_switch_terms)

# 8.4 Total cost sẽ được thiết lập sau khi có hub_upgrade_cost và arc_upgrade_cost (bên dưới)



# 8.4 Hub upgrade cost - SỬA LẠI CHO NEW HUB 3
print("\n[4] Chi phí nâng cấp hub (NEW HUB 3):")
hub_upgrade_cost = 0
hub_upgrade_vars = {}  # Biến mới để lưu trữ các biến nâng cấp

# a) NEW HUB 3 (có 4 levels: 0,1,2,3)
print("\n  a) NEW HUB 3 (4 levels, level 0 = không mở):")
for h in new_hubs:  # [3]
    for t in T:
        if t == 1:
            # Period 1: Chi phí nếu không ở level 0
            for l in [1, 2, 3]:
                if l in L_h[h]:
                    capacity_increase = L_h[h][l] - L_h[h][0]
                    cost_per_unit = f_lh.get(l, 0)
                    hub_upgrade_cost += y_h[(h, l, t)] * capacity_increase * cost_per_unit
                else:
                    print(f"  [WARNING] Hub {h} không có level {l} trong L_h")
        else:
            # Period t: Chi phí nâng cấp từ period t-1
            for l in [1, 2, 3]:
                for prev_l in [0, 1, 2]:
                    if l > prev_l:  # Chỉ tính khi nâng cấp lên
                        capacity_increase = L_h[h][l] - L_h[h][prev_l]
                        cost_per_unit = f_lh.get(l, 0)
                        
                        # Tạo biến indicator cho nâng cấp
                        var_name = f"hub_upgrade_{h}_{prev_l}_to_{l}_t{t}"
                        upgrade_indicator = model.addVar(
                            vtype=GRB.BINARY, 
                            name=var_name
                        )
                        hub_upgrade_vars[(h, prev_l, l, t)] = upgrade_indicator
                        
                        # Ràng buộc: upgrade_indicator = 1 nếu y_{h,l}^t = 1 và y_{h,prev_l}^{t-1} = 1
                        model.addConstr(upgrade_indicator <= y_h[(h, l, t)], 
                                       name=f"upg_ind_new_{h}_{prev_l}_{l}_t{t}")
                        model.addConstr(upgrade_indicator <= y_h[(h, prev_l, t-1)], 
                                       name=f"upg_ind_new_{h}_{prev_l}_{l}_t{t}_prev")
                        model.addConstr(upgrade_indicator >= y_h[(h, l, t)] + y_h[(h, prev_l, t-1)] - 1,
                                       name=f"upg_ind_new_{h}_{prev_l}_{l}_t{t}_logic")
                        
                        hub_upgrade_cost += upgrade_indicator * capacity_increase * cost_per_unit

print(f"  - Hub 3: Chi phí nâng cấp được tính cho levels 1,2,3")

# b) POTENTIAL HUB 4 (chỉ có 3 levels: 0,1,2)
print("\n  b) POTENTIAL HUB 4 (3 levels):")
for h in H_tilde:  # [4]
    for t in T:
        if t == 1:
            # Period 1: Chi phí nếu không ở level 0
            for l in [1, 2]:
                capacity_increase = L_h[h][l] - L_h[h][0]
                cost_per_unit = f_lh.get(l, 0)
                hub_upgrade_cost += y_h[(h, l, t)] * capacity_increase * cost_per_unit
        else:
            # Period t: Chi phí nâng cấp từ period t-1
            for l in [1, 2]:
                for prev_l in [0, 1]:
                    if l > prev_l:  # Chỉ tính khi nâng cấp lên
                        capacity_increase = L_h[h][l] - L_h[h][prev_l]
                        cost_per_unit = f_lh.get(l, 0)
                        
                        # Tạo biến indicator cho nâng cấp
                        var_name = f"hub_upgrade_{h}_{prev_l}_to_{l}_t{t}"
                        upgrade_indicator = model.addVar(
                            vtype=GRB.BINARY, 
                            name=var_name
                        )
                        hub_upgrade_vars[(h, prev_l, l, t)] = upgrade_indicator
                        
                        # Ràng buộc: upgrade_indicator = 1 nếu y_{h,l}^t = 1 và y_{h,prev_l}^{t-1} = 1
                        model.addConstr(upgrade_indicator <= y_h[(h, l, t)], 
                                       name=f"upg_ind_pot_{h}_{prev_l}_{l}_t{t}")
                        model.addConstr(upgrade_indicator <= y_h[(h, prev_l, t-1)], 
                                       name=f"upg_ind_pot_{h}_{prev_l}_{l}_t{t}_prev")
                        model.addConstr(upgrade_indicator >= y_h[(h, l, t)] + y_h[(h, prev_l, t-1)] - 1,
                                       name=f"upg_ind_pot_{h}_{prev_l}_{l}_t{t}_logic")
                        
                        hub_upgrade_cost += upgrade_indicator * capacity_increase * cost_per_unit

print(f"  - Hub 4: Chi phí nâng cấp được tính cho levels 1,2")

# c) EXISTING HUB 7 - không có chi phí nâng cấp
print("\n  c) EXISTING HUB 7: Không có chi phí nâng cấp (cố định level 0)")
print(f"  ✓ Tổng cộng: {len([k for k in hub_upgrade_vars.keys() if k[0] in new_hubs])} biến upgrade cho hub 3")
print(f"                {len([k for k in hub_upgrade_vars.keys() if k[0] in H_tilde])} biến upgrade cho hub 4")

# 8.5 Arc upgrade cost
print("\n[5] Chi phí nâng cấp arc (arc upgrade cost):")
arc_upgrade_cost = 0
arc_upgrade_vars = {}  # Biến lưu trữ các biến nâng cấp arc

print("  Tính chi phí nâng cấp cho potential arcs...")
for a in A_tilde:
    for t in T:
        if t == 1:
            # Period 1: Tính chi phí nếu ở level 1
            capacity_increase = L_a[a][1] - L_a[a][0]
            cost_per_unit = f_la.get(a, 0)
            arc_upgrade_cost += y_a[(a[0], a[1], 1, t)] * capacity_increase * cost_per_unit
        else:
            # Period t: Tính chi phí nâng cấp từ level 0 lên level 1
            capacity_increase = L_a[a][1] - L_a[a][0]
            cost_per_unit = f_la.get(a, 0)
            
            # Tạo biến indicator cho nâng cấp arc
            arc_upgrade_indicator = model.addVar(
                vtype=GRB.BINARY,
                name=f"arc_upgrade_{a[0]}_{a[1]}_t{t}"
            )
            arc_upgrade_vars[(a[0], a[1], t)] = arc_upgrade_indicator
            
            # Ràng buộc: arc_upgrade_indicator = 1 nếu y_arc_level1^t = 1 và y_arc_level0^{t-1} = 1
            model.addConstr(arc_upgrade_indicator <= y_a[(a[0], a[1], 1, t)],
                           name=f"arc_upg_1_{a[0]}_{a[1]}_t{t}")
            model.addConstr(arc_upgrade_indicator <= y_a[(a[0], a[1], 0, t-1)],
                           name=f"arc_upg_2_{a[0]}_{a[1]}_t{t}")
            model.addConstr(arc_upgrade_indicator >= y_a[(a[0], a[1], 1, t)] + y_a[(a[0], a[1], 0, t-1)] - 1,
                           name=f"arc_upg_3_{a[0]}_{a[1]}_t{t}")
            
            arc_upgrade_cost += arc_upgrade_indicator * capacity_increase * cost_per_unit

print(f"  ✓ Đã tính chi phí nâng cấp cho {len(A_tilde)} potential arcs")

# 8.6 Hàm mục tiêu: CHỈ operating cost (theo notebook – investment bị ràng buộc bởi budget B[t])
print("\n[6] Tổng chi phí (total cost) – chỉ operating:")
total_cost = service_cost + transport_cost + mode_switch_cost
model.setObjective(total_cost, GRB.MINIMIZE)
print("✓ Đã thiết lập hàm mục tiêu: Minimize operating cost (service + transport + mode_switch)")
print(f"  - Hub/Arc upgrade KHÔNG trong objective – ràng buộc bởi budget B[t] từng period")

# ============================================
# 9. THIẾT LẬP RÀNG BUỘC (CRITICAL - THIẾU SẼ RA KẾT QUẢ 0)
# ============================================
# Nguồn: Data Model _ 2026-Feb_05_eps_05.ipynb - Section 9
print("\n" + "="*60)
print("9. THIẾT LẬP RÀNG BUỘC (THEO NOTEBOOK MẪU)")
print("="*60)

# 9.1 Path flow balance - BẮT BUỘC: Tổng v_path cho mỗi (g,od,t) = 1
# Không có ràng buộc này, solver sẽ đặt tất cả v_path=0 → cost=0
print("\n[1] Path flow balance (sum v_path = 1 cho mỗi (g,od,t)):")
path_flow_count = 0
for g, od_pairs_list in OD_pairs.items():
    for od in od_pairs_list:
        for t in T:
            model.addConstr(
                gp.quicksum(v_path[(g, od, idx, t)] for idx in range(len(paths[(g, od)]))) == 1,
                name=f"path_flow_balance_{g}_{od[0]}_{od[1]}_t{t}"
            )
            path_flow_count += 1
print(f"  ✓ Đã thêm {path_flow_count} ràng buộc path flow balance")

# 9.1b Luồng qua hub: u_hub[(h,t)] >= tổng demand đi qua hub h trong period t (để hub service cost phản ánh đúng)
def path_uses_hub(path, h):
    """True nếu path đi qua hub h (node h xuất hiện trong path dưới dạng h hoặc 'h^1', 'h^2', ...)."""
    for (u, v) in path:
        if physical_node(u) == h or physical_node(v) == h:
            return True
    return False

print("\n[1b] Định nghĩa u_hub = luồng qua hub (hub service cost):")
for h in H:
    for t in T:
        flow_through_h = gp.quicksum(
            w_gk[(g, od, t)] * v_path[(g, od, idx, t)]
            for g, od_list in OD_pairs.items()
            for od in od_list
            for idx in range(len(paths[(g, od)]))
            if path_uses_hub(paths[(g, od)][idx], h)
        )
        model.addConstr(u_hub[(h, t)] == flow_through_h, name=f"u_hub_{h}_t{t}_flow")
print(f"  ✓ Đã thêm ràng buộc u_hub = flow qua hub")

# 9.1c Ràng buộc capacity tại hub (bắt buộc nâng cấp khi luồng vượt capacity – theo notebook)
print("\n[1c] Capacity tại hub (u_hub ≤ capacity theo level):")
M_big_hub = 1e9
for h in new_hubs:
    for t in T:
        model.addConstr(
            u_hub[(h, t)] <= gp.quicksum(L_h[h][l] * y_h[(h, l, t)] for l in [0, 1, 2, 3] if (h, l, t) in y_h),
            name=f"new_hub_capacity_{h}_t{t}"
        )
        model.addConstr(
            u_hub[(h, t)] <= M_big_hub * (1 - y_h[(h, 0, t)]),
            name=f"new_hub_no_flow_if_closed_{h}_t{t}"
        )
for h in H_tilde:
    for t in T:
        model.addConstr(
            u_hub[(h, t)] <= gp.quicksum(L_h[h][l] * y_h[(h, l, t)] for l in [0, 1, 2] if (h, l, t) in y_h),
            name=f"potential_hub_capacity_{h}_t{t}"
        )
for h in H0:
    for t in T:
        model.addConstr(u_hub[(h, t)] <= L_h[h][0], name=f"existing_hub_capacity_{h}_t{t}")
print(f"  ✓ Đã thêm ràng buộc capacity hub (new / potential / existing)")

# 9.1d Định nghĩa x_arc = luồng trên cung và capacity cung (potential arcs) – theo notebook
def arc_in_path(path, arc):
    """True nếu arc (u,v) xuất hiện trong path."""
    u, v = arc[0], arc[1]
    for (pu, pv) in path:
        if (pu, pv) == (u, v):
            return True
    return False

print("\n[1d] Định nghĩa x_arc = luồng trên cung và capacity cung:")
for a in A:
    for t in T:
        flow_on_arc = gp.quicksum(
            w_gk[(g, od, t)] * v_path[(g, od, idx, t)]
            for g, od_list in OD_pairs.items()
            for od in od_list
            for idx in range(len(paths[(g, od)]))
            if arc_in_path(paths[(g, od)][idx], a)
        )
        model.addConstr(x_arc[(a[0], a[1], t)] == flow_on_arc, name=f"x_arc_def_{a[0]}_{a[1]}_t{t}")
for a in A_tilde:
    for t in T:
        cap_t = L_a[a][0] * y_a[(a[0], a[1], 0, t)] + L_a[a][1] * y_a[(a[0], a[1], 1, t)]
        model.addConstr(x_arc[(a[0], a[1], t)] <= cap_t, name=f"arc_capacity_{a[0]}_{a[1]}_t{t}")
print(f"  ✓ Đã thêm định nghĩa x_arc và capacity cho potential arcs")

# 9.2 Hub level: mỗi hub phải chọn đúng 1 level mỗi period
print("\n[2] Single level per hub per period:")
for h in new_hubs:
    for t in T:
        model.addConstr(
            gp.quicksum(y_h[(h, l, t)] for l in [0, 1, 2, 3] if (h, l, t) in y_h) == 1,
            name=f"hub_level_new_{h}_t{t}"
        )
for h in H_tilde:
    for t in T:
        model.addConstr(
            gp.quicksum(y_h[(h, l, t)] for l in [0, 1, 2] if (h, l, t) in y_h) == 1,
            name=f"hub_level_pot_{h}_t{t}"
        )
for h in H0:
    for t in T:
        model.addConstr(y_h[(h, 0, t)] == 1, name=f"hub{h}_always_level0_t{t}")
        for l in [1, 2]:
            if (h, l, t) in y_h:
                model.addConstr(y_h[(h, l, t)] == 0, name=f"hub{h}_no_upgrade_{l}_t{t}")
print(f"  ✓ Đã thêm ràng buộc single level cho hubs")

# 9.3 Arc level: mỗi arc phải chọn đúng 1 level mỗi period
print("\n[3] Single level per arc per period:")
for a in A_tilde:
    for t in T:
        model.addConstr(
            gp.quicksum(y_a[(a[0], a[1], l, t)] for l in [0, 1]) == 1,
            name=f"arc_level_{a[0]}_{a[1]}_t{t}"
        )
print(f"  ✓ Đã thêm ràng buộc single level cho arcs")

# 9.4 Budget: investment_cost_per_period[t] == (hub + arc investment trong t), và <= B[t] (theo notebook)
print("\n[4] Ràng buộc budget theo từng period (investment ≤ B[t]):")
investment_cost_per_period = {}
for t in T:
    investment_cost_per_period[t] = model.addVar(
        lb=0, vtype=GRB.CONTINUOUS,
        name=f"investment_cost_period_{t}"
    )

for t in T:
    period_terms = []
    # Hub investment trong period t
    for h in new_hubs:
        if t == 1:
            for l in [1, 2, 3]:
                if l in L_h.get(h, {}):
                    capacity_increase = L_h[h][l] - L_h[h][0]
                    cost_per_unit = f_lh.get(l, 0)
                    period_terms.append(y_h[(h, l, t)] * capacity_increase * cost_per_unit)
        else:
            for (hh, prev_l, l, tt) in hub_upgrade_vars:
                if hh == h and tt == t:
                    capacity_increase = L_h[h][l] - L_h[h][prev_l]
                    cost_per_unit = f_lh.get(l, 0)
                    period_terms.append(hub_upgrade_vars[(h, prev_l, l, t)] * capacity_increase * cost_per_unit)
    for h in H_tilde:
        if t == 1:
            for l in [1, 2]:
                if l in L_h.get(h, {}):
                    capacity_increase = L_h[h][l] - L_h[h][0]
                    cost_per_unit = f_lh.get(l, 0)
                    period_terms.append(y_h[(h, l, t)] * capacity_increase * cost_per_unit)
        else:
            for (hh, prev_l, l, tt) in hub_upgrade_vars:
                if hh == h and tt == t:
                    capacity_increase = L_h[h][l] - L_h[h][prev_l]
                    cost_per_unit = f_lh.get(l, 0)
                    period_terms.append(hub_upgrade_vars[(h, prev_l, l, t)] * capacity_increase * cost_per_unit)
    # Arc investment trong period t
    for a in A_tilde:
        if t == 1:
            capacity_increase = L_a[a][1] - L_a[a][0]
            cost_per_unit = f_la.get(a, 0)
            period_terms.append(y_a[(a[0], a[1], 1, t)] * capacity_increase * cost_per_unit)
        else:
            if (a[0], a[1], t) in arc_upgrade_vars:
                capacity_increase = L_a[a][1] - L_a[a][0]
                cost_per_unit = f_la.get(a, 0)
                period_terms.append(arc_upgrade_vars[(a[0], a[1], t)] * capacity_increase * cost_per_unit)

    period_investment = gp.quicksum(period_terms) if period_terms else 0
    model.addConstr(
        investment_cost_per_period[t] == period_investment,
        name=f"investment_cost_def_period_{t}"
    )
    model.addConstr(
        investment_cost_per_period[t] <= B[t],
        name=f"budget_constraint_period_{t}"
    )
    print(f"    Period {t}: investment_cost ≤ {B[t]:,}")
print(f"  ✓ Đã thêm ràng buộc budget cho từng period")

print(f"\n✓ ĐÃ THIẾT LẬP XONG CÁC RÀNG BUỘC CƠ BẢN")

# ============================================
# 11. SOLVE AND DISPLAY RESULTS (ĐÃ CẬP NHẬT)
# ============================================
import time

start_time = time.time()   # Start timer

print("\n" + "="*60)
print("SOLVING THE MODEL...")
print("="*60)

model.optimize()

solve_time = time.time() - start_time   # End timer

# ———————————————————————— RESULTS ————————————————————————
if model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
    print(f"\n{'='*60}")
    print("SOLVED! Status: {model.Status} "
          f"| Runtime: {solve_time:.2f} seconds ({solve_time/60:.2f} minutes)")
    print(f"{'='*60}")

    if model.status == GRB.OPTIMAL:
        print("   → Optimal solution found!")
    else:
        print("   → Time limit reached (near-optimal solution)")

    print(f"\nTotal optimal cost: {model.ObjVal:,.0f}")

    # Tính các thành phần chi phí từ biến
    print(f"\n{'='*55}")
    print("=== COST BREAKDOWN ===")
    print(f"{'='*55}")
    
    
    
    # Hub service cost
    serv_cost = 0
    for h in H:
        for t in T:
            if h in c_h:
                flow = u_hub[(h, t)].X
                serv_cost += flow * c_h[h]
    
    print(f" Hub service cost    : {serv_cost:>15,.0f}")
    
   # Transportation cost
        # Transportation cost (MATCH objective: path_cost * demand * v_path)
    trans_cost = 0.0
    for g, od_pairs_list in OD_pairs.items():
        for od in od_pairs_list:
            for idx, path in enumerate(paths[(g, od)]):
                path_transport_cost = calculate_transport_cost(path)
                for t in T:
                    trans_cost += path_transport_cost * w_gk[(g, od, t)] * v_path[(g, od, idx, t)].X

    print(f" Transportation cost : {trans_cost:>15,.0f}")

    # Mode switching cost (MATCH objective: indicator(path has mode-switch at hub) * c_s * demand * v_path)
    def path_has_mode_switch(path, hubs=H):
        """
        Return True if this path includes a mode switch at one of hubs.
        You can adjust this logic to match your exact path encoding.
        """
        # helper to infer mode from a node/arc endpoint string
        def infer_mode(x):
            s = str(x)
            return 'road' if '^1' in s else 'waterway'

        for i in range(len(path) - 2):
            current_arc = path[i]
            next_arc = path[i+1]

            # Your original condition (keep consistent)
            if isinstance(current_arc[0], str) and isinstance(next_arc[1], str) and next_arc[1].startswith(tuple(str(h) for h in hubs)):
                hub = int(next_arc[1][0]) if next_arc[1][0].isdigit() else None
                if hub in hubs:
                    current_mode = infer_mode(current_arc[0])
                    next_mode = infer_mode(next_arc[1])
                    if current_mode != next_mode:
                        return True
        return False

    mode_switch_cost_val = 0.0
    for g, od_pairs_list in OD_pairs.items():
        for od in od_pairs_list:
            for idx, path in enumerate(paths[(g, od)]):
                has_switch = path_has_mode_switch(path, hubs=(3,4,6))
                if not has_switch:
                    continue
                for t in T:
                    mode_switch_cost_val += c_s * w_gk[(g, od, t)] * v_path[(g, od, idx, t)].X

    print(f" Mode switching cost : {mode_switch_cost_val:>15,.0f}")

    
    # Hub upgrade cost - ĐÃ SỬA
    # Trong phần summary results, sửa phần hiển thị hub levels:
    print("\n[1] HUB LEVELS (NEW HUB 3):")
    
    # a) NEW HUB 3
    print("\n  a) NEW HUB 3 (phải mở mới có capacity):")
    for h in new_hubs:  # [3]
        for t in T:
            hub_level = None
            for l in [0, 1, 2, 3]:
                if y_h[(h, l, t)].X > 0.5:
                    hub_level = l
                    capacity = L_h[h][l]
                    break
            
            if hub_level is not None:
                if hub_level == 0:
                    status = "NOT OPENED (capacity = 0)"
                    action = "→ Using through-hub paths"
                elif hub_level == 1:
                    status = "OPENED Level 1"
                    action = f"→ Capacity: {capacity:,}"
                elif hub_level == 2:
                    status = "OPENED Level 2"
                    action = f"→ Capacity: {capacity:,}"
                elif hub_level == 3:
                    status = "OPENED Level 3"
                    action = f"→ Capacity: {capacity:,}"
                
                print(f"    Hub {h} period {t}: {status}")
                print(f"      {action}")
            
    print(f"\n[4] Hub upgrade cost (ĐÃ SỬA):")
    hub_upg_cost = 0
    
    # CHỈ tính cho potential hubs ( 4)
    for h in H_tilde:
        print(f"\n  Hub {h}:")
        for t in T:
            if t == 1:
                # Period 1: Tính chi phí nếu không ở level 0
                for l in [1, 2]:
                    if y_h[(h, l, t)].X > 0.5:
                        capacity_increase = L_h[h][l] - L_h[h][0]
                        cost_per_unit = f_lh.get(l, 0)
                        upgrade_cost = capacity_increase * cost_per_unit
                        hub_upg_cost += upgrade_cost
                        print(f"    Period {t}, level {l}: {upgrade_cost:,.0f} "
                              f"(Δcapacity={capacity_increase:,} × {cost_per_unit}/unit)")
            else:
                # Period t: Tính chi phí nâng cấp từ period t-1
                for l in [1, 2]:
                    for prev_l in [0, 1]:
                        if l > prev_l:  # Chỉ tính khi nâng cấp lên
                            # Tìm biến upgrade_indicator
                            var_name = f"hub_upgrade_{h}_{prev_l}_to_{l}_t{t}"
                            upgrade_var = model.getVarByName(var_name)
                            if upgrade_var and upgrade_var.X > 0.5:
                                capacity_increase = L_h[h][l] - L_h[h][prev_l]
                                cost_per_unit = f_lh.get(l, 0)
                                upgrade_cost = capacity_increase * cost_per_unit
                                hub_upg_cost += upgrade_cost
                                print(f"    Period {t}, upgrade {prev_l}→{l}: {upgrade_cost:,.0f} "
                                      f"(Δcapacity={capacity_increase:,} × {cost_per_unit}/unit)")
    
    # Hub 6 không có chi phí nâng cấp
    print(f"\n  Hub 6 (existing hub): No upgrade cost (fixed capacity)")
    print(f"  Total hub upgrade cost: {hub_upg_cost:>15,.0f}")
    
    # Arc upgrade cost - GIỮ NGUYÊN
    print(f"\n[5] Arc upgrade cost:")
    arc_upg_cost = 0
    for a in A_tilde:
        mode = 'road' if '^1' in str(a[0]) or '^1' in str(a[1]) else 'waterway'
        for t in T:
            if t == 1:
                # Period 1: Tính chi phí nếu ở level 1
                if y_a[(a[0], a[1], 1, t)].X > 0.5:
                    capacity_increase = L_a[a][1] - L_a[a][0]
                    cost_per_unit = f_la.get(a, 0)
                    upgrade_cost = capacity_increase * cost_per_unit
                    arc_upg_cost += upgrade_cost
                    print(f"  Arc ({a[0]}→{a[1]}) {mode}, period {t}, level 1: {upgrade_cost:,.0f}")
            else:
                # Period t: Tìm biến arc_upgrade_indicator
                var_name = f"arc_upgrade_{a[0]}_{a[1]}_t{t}"
                upgrade_var = model.getVarByName(var_name)
                if upgrade_var and upgrade_var.X > 0.5:
                    capacity_increase = L_a[a][1] - L_a[a][0]
                    cost_per_unit = f_la.get(a, 0)
                    upgrade_cost = capacity_increase * cost_per_unit
                    arc_upg_cost += upgrade_cost
                    print(f"  Arc ({a[0]}→{a[1]}) {mode}, period {t}, upgrade: {upgrade_cost:,.0f}")
    
    print(f"\n  Total arc upgrade cost: {arc_upg_cost:>15,.0f}")
    
    # Tổng chi phí từ các thành phần
    total_calculated = trans_cost + serv_cost + mode_switch_cost_val

    total_value = trans_cost + serv_cost + mode_switch_cost_val + hub_upg_cost + arc_upg_cost

    print(f"\n{'—'*45}")
    print(f" TOTAL CALCULATED      : {total_calculated:>15,.0f}")
    print(f" MODEL OBJECTIVE VALUE : {model.ObjVal:>15,.0f}")
    
    # Kiểm tra chênh lệch với objective value
    diff = abs(model.ObjVal - total_calculated)
    if diff > 1:
        print(f"\n  ⚠ Lưu ý: Có chênh lệch {diff:.2f} giữa objective và tổng chi phí tính toán")
    else:
        print(f"\n  ✓ Tổng chi phí tính toán khớp với objective value")

    # ==================== SUMMARY RESULTS ====================
    print(f"\n{'='*65}")
    print("=== SUMMARY RESULTS ===")
    print(f"{'='*65}")

    # 1. Hub levels - ĐÃ SỬA
    print("\n[1] HUB LEVELS (ĐÃ SỬA):")
    
    # Potential hubs (3, 4)
    print("\n  a) Potential hubs (có thể nâng cấp):")
    for h in H_tilde:
        for t in T:
            hub_level = None
            for l in [0, 1, 2]:
                if y_h[(h, l, t)].X > 0.5:
                    hub_level = l
                    capacity = L_h[h][l]
                    break
            
            if hub_level is not None:
                status = "UPGRADED" if hub_level > 0 else "BASE"
                print(f"    Hub {h} period {t} → level {hub_level} ({status})")
                print(f"      Capacity: {capacity:,}")
            else:
                print(f"    Hub {h} period {t} → ERROR: No level selected!")

    # Existing hub (6)
    print("\n  b) Existing hub (cố định):")
    for t in T:
        if y_h[(7, 0, t)].X > 0.5:
            capacity = L_h[7][0]
            print(f"    Hub 7 period {t} → level 0 (EXISTING, FIXED)")
            print(f"      Capacity: {capacity:,} (cố định)")
        else:
            print(f"    Hub 7 period {t} → ERROR: Not at level 0!")

    # 2. ARC UPGRADES
    print(f"\n[2] ARC UPGRADES:")
    arc_upgraded = False
    
    for a in A_tilde:
        mode = "road" if '^1' in str(a[0]) or '^1' in str(a[1]) else "waterway"
        for t in T:
            # Kiểm tra level của arc
            level_1 = y_a[(a[0], a[1], 1, t)].X > 0.5
            
            if level_1:
                arc_upgraded = True
                base_capacity = L_a[a][0]
                upgraded_capacity = L_a[a][1]
                print(f"  Arc ({a[0]} → {a[1]}) period {t}:")
                print(f"    Status: UPGRADED to level 1 ({mode})")
                print(f"    Capacity: {base_capacity:,} → {upgraded_capacity:,}")

    if not arc_upgraded:
        print("  No arcs upgraded in any period.")

    # 3. Hub flows and utilization - ĐÃ SỬA
    print(f"\n[3] HUB FLOWS AND UTILIZATION:")
    for t in T:
        print(f"\n  Period {t}:")
        for h in H:
            flow = u_hub[(h, t)].X
            
            # Xác định capacity dựa trên loại hub
            if h in H_tilde:
                # Tìm level của hub
                hub_level = 0
                for l in [0, 1, 2]:
                    if y_h[(h, l, t)].X > 0.5:
                        hub_level = l
                        break
                capacity = L_h[h][hub_level]
                hub_type = f"potential (level {hub_level})"
            else:  # Hub 6
                capacity = L_h[6][0]
                hub_type = "existing (fixed)"
            
            if capacity > 0:
                utilization = (flow / capacity) * 100
                print(f"    Hub {h} ({hub_type}):")
                print(f"      Flow: {flow:,.0f}, Capacity: {capacity:,}, Utilization: {utilization:.1f}%")
            else:
                print(f"    Hub {h}: ERROR - capacity is zero!")

    # 4. Capacity constraints check - THÊM MỚI
    print(f"\n[4] CAPACITY CONSTRAINTS CHECK:")
    capacity_violations = 0
    
    for t in T:
        print(f"\n  Period {t}:")
        # Kiểm tra hub capacity constraints
        for h in H:
            flow = u_hub[(h, t)].X
            
            # Tính capacity từ solution
            if h in H_tilde:
                capacity = 0
                for l in [0, 1, 2]:
                    if y_h[(h, l, t)].X > 0.5:
                        capacity += L_h[h][l] * y_h[(h, l, t)].X
            else:  # Hub 6
                capacity = L_h[7][0]
            
            if flow > capacity + 0.001:  # Cho phép sai số nhỏ
                capacity_violations += 1
                print(f"    ⚠ VIOLATION: Hub {h} flow ({flow:,.0f}) > capacity ({capacity:,.0f})")
            else:
                print(f"    ✓ OK: Hub {h} flow ({flow:,.0f}) ≤ capacity ({capacity:,.0f})")
    
    if capacity_violations == 0:
        print(f"\n  ✓ Tất cả capacity constraints được thỏa mãn!")
    else:
        print(f"\n  ⚠ Có {capacity_violations} capacity constraint violations!")

    # 5. Flow distribution
    print(f"\n[5] FLOW DISTRIBUTION:")
    for t in T:
        print(f"\n  Period {t}:")
        total_demand = sum(w_gk[(g, od, t)] for g in ['g1', 'g2'] for od in OD_pairs[g])
        
        # Tính flow qua từng path
        passenger_flows = []
        rice_flows = []
        
        for g, od_pairs_list in OD_pairs.items():
            for od in od_pairs_list:
                demand = w_gk[(g, od, t)]
                commodity = "Passenger" if g == 'g1' else "Rice"
                
                for idx in range(len(paths[(g, od)])):
                    path_flow = v_path[(g, od, idx, t)].X * demand
                    if path_flow > 0:
                        path_str = paths[(g, od)][idx]
                        simplified_path = []
                        for arc in path_str:
                            simplified_path.append(f"{arc[0]}→{arc[1]}")
                        
                        if g == 'g1':
                            passenger_flows.append((path_flow, simplified_path))
                        else:
                            rice_flows.append((path_flow, simplified_path))
        
        print(f"    Total demand: {total_demand:,.0f}")
        
        if passenger_flows:
            print(f"\n    Passenger flows:")
            for flow, path in passenger_flows:
                print(f"      {flow:,.0f} units: {' → '.join(path)}")
        
        if rice_flows:
            print(f"\n    Rice flows:")
            for flow, path in rice_flows:
                print(f"      {flow:,.0f} units: {' → '.join(path)}")

    # Final summary
    print(f"\n{'='*65}")
    print("=== SOLUTION SUMMARY ===")
    print(f"{'='*65}")
    
    # Hub investment summary
    print(f"\nHub Investment Summary:")
    total_hub_investment = 0
    for h in H_tilde:
        for t in T:
            for l in [1, 2]:
                if y_h[(h, l, t)].X > 0.5:
                    capacity_increase = L_h[h][l] - L_h[h][0]
                    cost_per_unit = f_lh.get(l, 0)
                    investment = capacity_increase * cost_per_unit
                    total_hub_investment += investment
                    print(f"  Hub {h} period {t}: Level {l}, Investment: {investment:,.0f}")
    
    # Arc investment summary
    print(f"\nArc Investment Summary:")
    total_arc_investment = 0
    for a in A_tilde:
        mode = 'road' if '^1' in str(a[0]) or '^1' in str(a[1]) else 'waterway'
        for t in T:
            if y_a[(a[0], a[1], 1, t)].X > 0.5:
                capacity_increase = L_a[a][1] - L_a[a][0]
                cost_per_unit = f_la.get(a, 0)
                investment = capacity_increase * cost_per_unit
                total_arc_investment += investment
                print(f"  Arc ({a[0]}→{a[1]}) {mode} period {t}: Level 1, Investment: {investment:,.0f}")
    
    print(f"\n{'—'*45}")
    print(f"Total Hub Investment  : {total_hub_investment:>15,.0f}")
    print(f"Total Arc Investment  : {total_arc_investment:>15,.0f}")
    print(f"Total Investment Cost : {total_hub_investment + total_arc_investment:>15,.0f}")
    print(f"Operating Cost        : {trans_cost + serv_cost + mode_switch_cost_val:>15,.0f}")
    print(f"{'='*45}")
    print(f"TOTAL COST            : {model.ObjVal:>15,.0f}")
    print(f"{'='*45}")

    # Final banner
    print(f"\n{'='*65}")
    print(f"ALL DONE! Total runtime: {solve_time:.2f} seconds ({solve_time/60:.2f} minutes)")
    print(f"{'='*65}")
    
    # ============================================
    # EXPORT RESULTS TO JSON FOR STREAMLIT APP
    # ============================================
    import json
    from pathlib import Path
    
    def extract_real_node(node):
        """Extract real node ID from virtual node representation"""
        if isinstance(node, int):
            return node
        if isinstance(node, str) and '^' in node:
            return int(node.split('^')[0])
        if isinstance(node, tuple):
            return node[0] if isinstance(node[0], int) else None
        return None
    
    def export_results_to_json(period: int = 1, output_dir: str = "data/Mekong"):
        """Export optimization results to JSON format for Streamlit app"""
        print(f"\n{'='*65}")
        print(f"EXPORTING RESULTS TO JSON FOR PERIOD {period}...")
        print(f"{'='*65}")
        print(f"Debug: T = {T}, period = {period}")
        print(f"Debug: H = {H}, H_tilde = {H_tilde}")
        print(f"Debug: y_h keys sample: {list(y_h.keys())[:5] if y_h else 'EMPTY'}")
        print(f"Debug: v_path keys sample: {list(v_path.keys())[:5] if v_path else 'EMPTY'}")
        
        # Map commodity IDs to names
        commodity_map = {'g1': 'Passenger', 'g2': 'Rice', 'g3': 'Fisheries', 'g4': 'Fruits & Vegetables'}
        
        # 1. Extract selected hubs (hubs with level > 0 in requested period)
        selected_hubs = []
        hub_levels = {}
        print(f"\nExtracting hubs for period {period}...")
        for h in H:
            hub_level = None
            capacity = 0
            for l in [0, 1, 2, 3]:
                key = (h, l, period)
                if key in y_h:
                    val = y_h[key].X
                    if val > 0.5:
                        hub_level = l
                        if h in L_h and l in L_h[h]:
                            capacity = L_h[h][l]
                        print(f"  Hub {h}: level {l} selected (X={val:.3f}, capacity={capacity:,.0f})")
                        break
            if hub_level is not None and hub_level > 0:
                if h not in selected_hubs:
                    selected_hubs.append(h)
                hub_levels[str(h)] = {
                    "hub": h,
                    "period": period,
                    "level": hub_level,
                    "capacity": capacity
                }
        
        print(f"Selected hubs: {selected_hubs}")
        
        # 2. Extract arc upgrades
        arc_upgrades = []
        for a in A_tilde:
            # Determine mode from arc
            mode = 'road'
            if isinstance(a[0], str) and '^2' in str(a[0]):
                mode = 'waterway'
            elif isinstance(a[1], str) and '^2' in str(a[1]):
                mode = 'waterway'
            elif isinstance(a[0], tuple) and len(a[0]) > 1 and a[0][1] == 2:
                mode = 'waterway'
            elif isinstance(a[1], tuple) and len(a[1]) > 1 and a[1][1] == 2:
                mode = 'waterway'
            
            if (a[0], a[1], 1, period) in y_a and y_a[(a[0], a[1], 1, period)].X > 0.5:
                from_node = extract_real_node(a[0])
                to_node = extract_real_node(a[1])
                if from_node is not None and to_node is not None:
                    arc_upgrades.append({
                        "from": from_node,
                        "to": to_node,
                        "mode": mode,
                        "period": period
                    })
        
        # 3. Extract top routes from v_path
        top_routes = []
        route_id = 1
        
        print(f"\nExtracting routes for period {period}...")
        routes_found = 0
        for g, od_pairs_list in OD_pairs.items():
            commodity_name = commodity_map.get(g, g)
            print(f"  Commodity {g} ({commodity_name}): {len(od_pairs_list)} OD pairs")
            for od in od_pairs_list:
                if (g, od, period) not in w_gk:
                    continue
                demand = w_gk[(g, od, period)]
                if demand == 0:
                    continue
                
                if (g, od) not in paths:
                    continue
                
                for idx in range(len(paths[(g, od)])):
                    key = (g, od, idx, period)
                    if key not in v_path:
                        continue
                    path_flow_ratio = v_path[key]
                    flow_val = path_flow_ratio.X
                    if flow_val > 0.001:  # Flow > 0.1% (lower threshold)
                        routes_found += 1
                        if routes_found <= 3:  # Debug first 3 routes
                            print(f"    Route {routes_found}: {od}, path_idx={idx}, flow_ratio={flow_val:.6f}, demand={demand:.0f}")
                        path_str = paths[(g, od)][idx]
                        
                        # Convert path to simple node list (extract real nodes)
                        simple_path = []
                        seen_nodes = set()
                        for arc in path_str:
                            u = arc[0]
                            v = arc[1]
                            u_real = extract_real_node(u)
                            v_real = extract_real_node(v)
                            if u_real is not None and u_real not in seen_nodes:
                                simple_path.append(u_real)
                                seen_nodes.add(u_real)
                            if v_real is not None and v_real not in seen_nodes:
                                simple_path.append(v_real)
                                seen_nodes.add(v_real)
                        
                        if len(simple_path) < 2:
                            continue
                        
                        # Determine mode
                        path_modes = set()
                        for arc in path_str:
                            u_str = str(arc[0])
                            if '^1' in u_str:
                                path_modes.add('road')
                            elif '^2' in u_str:
                                path_modes.add('water')
                        
                        if len(path_modes) > 1:
                            mode = 'multi-modal'
                        elif 'road' in path_modes:
                            mode = 'road'
                        elif 'water' in path_modes:
                            mode = 'water'
                        else:
                            mode = 'road'  # default
                        
                        # Calculate cost and time
                        path_transport_cost = calculate_transport_cost(path_str)
                        path_cost = path_transport_cost * demand * path_flow_ratio.X
                        path_time = path_transport_cost / 100  # Estimate time from cost
                        
                        flow_val = float(demand * path_flow_ratio.X)
                        top_routes.append({
                            "route_id": route_id,
                            "path": simple_path,
                            "commodity": commodity_name,
                            "mode": mode,
                            "cost": float(path_cost),
                            "time": float(path_time),
                            "flow": flow_val,
                            "flow_ratio": float(path_flow_ratio.X),
                            "od_pair": [od[0], od[1]],
                            "demand_od": float(demand)
                        })
                        route_id += 1
        
        print(f"  Total routes found: {routes_found}")
        
        # Sort routes by flow (descending) and take top 20
        top_routes.sort(key=lambda x: x['flow'], reverse=True)
        top_routes = top_routes[:20]
        print(f"  Top routes after sorting: {len(top_routes)}")
        
        # Thêm path_labels (tên node), origin/destination cho mỗi route
        for r in top_routes:
            path_ids = r['path']
            r['path_labels'] = [node_names.get(nid, str(nid)) for nid in path_ids]
            r['origin'] = path_ids[0] if path_ids else None
            r['destination'] = path_ids[-1] if path_ids else None
            r['origin_name'] = node_names.get(path_ids[0], str(path_ids[0])) if path_ids else ""
            r['destination_name'] = node_names.get(path_ids[-1], str(path_ids[-1])) if path_ids else ""
        
        # 4. Calculate hub utilization
        hub_utilization = {}
        for h in selected_hubs:
            if (h, period) in u_hub:
                flow_val = u_hub[(h, period)].X
                # Get capacity
                capacity = 0
                for l in [0, 1, 2, 3]:
                    if (h, l, period) in y_h and y_h[(h, l, period)].X > 0.5:
                        if h in L_h and l in L_h[h]:
                            capacity = L_h[h][l]
                        break
                if capacity > 0:
                    hub_utilization[str(h)] = float(flow_val / capacity)
        
        # 5. Calculate modal split
        modal_split = {'road': 0.0, 'water': 0.0, 'multi-modal': 0.0}
        total_flow = sum(r['flow'] for r in top_routes)
        if total_flow > 0:
            for route in top_routes:
                mode = route['mode']
                if mode in modal_split:
                    modal_split[mode] += route['flow'] / total_flow
        
        # 6. Build cost breakdown - recalculate for THIS period only
        print(f"\nCalculating cost breakdown for period {period}...")
        
        # Transportation cost for this period
        trans_cost_period = 0.0
        for g, od_pairs_list in OD_pairs.items():
            for od in od_pairs_list:
                if (g, od, period) not in w_gk:
                    continue
                demand = w_gk[(g, od, period)]
                if (g, od) not in paths:
                    continue
                for idx, path in enumerate(paths[(g, od)]):
                    key = (g, od, idx, period)
                    if key in v_path:
                        path_transport_cost = calculate_transport_cost(path)
                        trans_cost_period += path_transport_cost * demand * v_path[key].X
        
        # Hub service cost for this period
        serv_cost_period = 0.0
        for h in H:
            if h in c_h and (h, period) in u_hub:
                flow = u_hub[(h, period)].X
                serv_cost_period += flow * c_h[h]
        
        # Mode switching cost for this period
        mode_switch_cost_period = 0.0
        def path_has_mode_switch_local(path, hubs=H):
            """Check if path has mode switch at hub"""
            def infer_mode(x):
                s = str(x)
                return 'road' if '^1' in s else 'waterway'
            for i in range(len(path) - 2):
                current_arc = path[i]
                next_arc = path[i+1]
                if isinstance(current_arc[0], str) and isinstance(next_arc[1], str) and next_arc[1].startswith(tuple(str(h) for h in hubs)):
                    hub = int(next_arc[1][0]) if next_arc[1][0].isdigit() else None
                    if hub in hubs:
                        current_mode = infer_mode(current_arc[0])
                        next_mode = infer_mode(next_arc[1])
                        if current_mode != next_mode:
                            return True
            return False
        
        for g, od_pairs_list in OD_pairs.items():
            for od in od_pairs_list:
                if (g, od, period) not in w_gk:
                    continue
                demand = w_gk[(g, od, period)]
                if (g, od) not in paths:
                    continue
                for idx, path in enumerate(paths[(g, od)]):
                    key = (g, od, idx, period)
                    if key in v_path:
                        has_switch = path_has_mode_switch_local(path, hubs=H)
                        if has_switch:
                            mode_switch_cost_period += c_s * demand * v_path[key].X
        
        # Hub upgrade cost for this period
        hub_upg_cost_period = 0.0
        for h in H_tilde:
            if period == 1:
                # Period 1: Tính chi phí nếu không ở level 0
                for l in [1, 2]:
                    if (h, l, period) in y_h and y_h[(h, l, period)].X > 0.5:
                        capacity_increase = L_h[h][l] - L_h[h][0]
                        cost_per_unit = f_lh.get(l, 0)
                        hub_upg_cost_period += capacity_increase * cost_per_unit
            else:
                # Period > 1: Tính chi phí nâng cấp từ period trước
                for l in [1, 2]:
                    for prev_l in [0, 1]:
                        if l > prev_l:
                            var_name = f"hub_upgrade_{h}_{prev_l}_to_{l}_t{period}"
                            upgrade_var = model.getVarByName(var_name)
                            if upgrade_var and upgrade_var.X > 0.5:
                                capacity_increase = L_h[h][l] - L_h[h][prev_l]
                                cost_per_unit = f_lh.get(l, 0)
                                hub_upg_cost_period += capacity_increase * cost_per_unit
        
        # Arc upgrade cost for this period
        arc_upg_cost_period = 0.0
        for a in A_tilde:
            if period == 1:
                if (a[0], a[1], 1, period) in y_a and y_a[(a[0], a[1], 1, period)].X > 0.5:
                    capacity_increase = L_a[a][1] - L_a[a][0]
                    cost_per_unit = f_la.get(a, 0)
                    arc_upg_cost_period += capacity_increase * cost_per_unit
            else:
                var_name = f"arc_upgrade_{a[0]}_{a[1]}_t{period}"
                upgrade_var = model.getVarByName(var_name)
                if upgrade_var and upgrade_var.X > 0.5:
                    capacity_increase = L_a[a][1] - L_a[a][0]
                    cost_per_unit = f_la.get(a, 0)
                    arc_upg_cost_period += capacity_increase * cost_per_unit
        
        print(f"  Period {period} costs:")
        print(f"    Transportation: {trans_cost_period:,.0f}")
        print(f"    Hub service: {serv_cost_period:,.0f}")
        print(f"    Mode switching: {mode_switch_cost_period:,.0f}")
        print(f"    Hub upgrade: {hub_upg_cost_period:,.0f}")
        print(f"    Arc upgrade: {arc_upg_cost_period:,.0f}")
        
        cost_breakdown = {
            "transportation": float(trans_cost_period),
            "hub_service": float(serv_cost_period),
            "mode_switching": float(mode_switch_cost_period),
            "hub_upgrade": float(hub_upg_cost_period),
            "arc_upgrade": float(arc_upg_cost_period)
        }
        
        # 7. Calculate efficiency (simplified)
        total_demand = sum(w_gk.get((g, od, period), 0) for g in OD_pairs.keys() for od in OD_pairs[g])
        efficiency = 0.85  # Placeholder
        
        # 8. Build insights
        insights = {
            "strategy": f"Multi-modal hub-and-spoke with {len(selected_hubs)} hubs selected",
            "key_findings": []
        }
        
        if len(selected_hubs) > 0:
            insights["key_findings"].append(f"{len(selected_hubs)} hubs selected: {selected_hubs}")
        if modal_split.get('water', 0) > 0.5:
            insights["key_findings"].append(f"Waterways handle {modal_split['water']*100:.0f}% of flow")
        if len(arc_upgrades) > 0:
            insights["key_findings"].append(f"{len(arc_upgrades)} arcs upgraded in period {period}")
        
        # 9. Build final JSON - cập nhật chi tiết đầy đủ
        from datetime import datetime
        total_demand_period = sum(w_gk.get((g, od, period), 0) for g in OD_pairs.keys() for od in OD_pairs[g])
        
        result_json = {
            "region": "Mekong",
            "period": period,
            "total_cost": float(model.ObjVal),
            "total_time": float((trans_cost_period + serv_cost_period) / 1000),  # Estimate
            "num_hubs": len(selected_hubs),
            "selected_hubs": selected_hubs,
            "efficiency": efficiency,
            "solver_status": "optimal" if model.status == GRB.OPTIMAL else "time_limit",
            "solve_time": float(solve_time),
            "num_routes": len(top_routes),
            "total_routes_found": routes_found,
            "total_demand": float(total_demand_period),
            "top_routes": top_routes,
            "hub_utilization": hub_utilization,
            "modal_split": modal_split,
            "cost_breakdown": cost_breakdown,
            "hub_levels": hub_levels,
            "arc_upgrades": arc_upgrades,
            "insights": insights,
            # Metadata để app dễ hiển thị
            "node_names": node_names,
            "node_coords": node_coords,
            "export_timestamp": datetime.now().isoformat(),
        }
        
        # 10. Save to JSON
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / f"optimization_results_period{period}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Results exported to: {output_file}")
        print(f"  - Selected hubs: {selected_hubs} (count: {len(selected_hubs)})")
        print(f"  - Routes: {len(top_routes)}")
        print(f"  - Arc upgrades: {len(arc_upgrades)}")
        print(f"  - Total cost: {model.ObjVal:,.0f}")
        print(f"  - Hub utilization: {hub_utilization}")
        print(f"  - Modal split: {modal_split}")
        print(f"  - Cost breakdown: {cost_breakdown}")
        
        # Debug: Print first route if exists
        if top_routes:
            print(f"\n  Sample route: {top_routes[0]}")
        else:
            print(f"\n  ⚠ WARNING: No routes extracted! Check v_path values.")
        
        return output_file
    
    # Export for each period
    for t in T:
        export_results_to_json(period=t, output_dir="data/Mekong")

elif model.status == GRB.INFEASIBLE:
    print("\n" + "="*60)
    print("MODEL INFEASIBLE! Computing IIS...")
    print("="*60)
    
    model.computeIIS()
    model.write("model_iis.ilp")
    
    print("\nPossible causes of infeasibility:")
    print("1. Demand > total capacity even with all upgrades")
    print("2. Budget constraint too tight")
    print("3. Existing hub 6 capacity (5000) may be insufficient")
    print("4. Check capacity constraints on bottleneck arcs")
    print("\n→ IIS saved to model_iis.ilp for detailed analysis")

else:
    print(f"\nSolver terminated with status: {model.status}")

# Always save the LP file for inspection
model.write("multimodal_hub_network_model.lp")
print("\nModel saved to: multimodal_hub_network_model.lp")
