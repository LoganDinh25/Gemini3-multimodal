"""
CELL 2: LOAD DATA FROM CSV FILES - UPDATE
Module này load data from CSV and save to pkl để tái sử dụng
"""

import csv
import re
import pickle
from pathlib import Path
from collections import defaultdict


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
    parts = re.split(r"[;]", s)   # delimiter: ';'
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
# 2.1 LOAD ARCS - UPDATE
# ============================================================
def load_arcs(arc_file):
    """
    Arc file columns columns:
    FromNode, ToNode, Type, Length(m), Project(P/E),
    Investment_Cost (Billion VND), Construction_Time (Years),
    Capacity(tons/year), Capacity_After_Investment (tons/year),
    base_costs  # ADD
    
    Rules:
    - Type: R => road (mode=1), W => waterway (mode=2)
    - Project(P/E):
        P: upgrade project
        E: existing arc
    - base_costs: base transport cost
    """
    edges = []
    print(f"\n[1] Loading arcs from: {arc_file}")

    try:
        with open(arc_file, newline='', encoding='utf-8', errors="ignore") as f:
            reader = csv.DictReader(f)
            print(f"   - Fields in file: {reader.fieldnames}")

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
                    print(f"   ⚠️ Row error {row_num}: {e}")
                    continue

        print(f"   ✓ Loaded {len(edges)} arcs successfully")

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
        print(f"   ✗ File not found: {arc_file}")
    except Exception as e:
        print(f"   ✗ Error loading file: {e}")

    return edges


# ============================================================
# 2.2 LOAD NODES - UPDATE
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

    print(f"\n[2] Loading nodes from: {node_file}")

    try:
        with open(node_file, newline='', encoding='utf-8', errors="ignore") as f:
            reader = csv.DictReader(f)
            print(f"   - Fields in file: {reader.fieldnames}")

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
                    print(f"   ⚠️ Row error {row_num}: {e}")
                    continue

        print(f"   ✓ Loaded {len(node_names)} nodes successfully")
        print(f"     - Normal: {len(normal_nodes)} | Existing hubs(E): {len(existing_hubs)} | "
              f"New candidates: {len(candidate_hubs_new)} | Upgrade candidates: {len(candidate_hubs_upgrade)}")

    except FileNotFoundError:
        print(f"   ✗ File not found: {node_file}")
    except Exception as e:
        print(f"   ✗ Error loading file: {e}")

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
# LƯU VÀ ĐỌC PKL
# ============================================================
def save_data_to_pkl(data_dict, pkl_file="data/preprocessed_data.pkl"):
    """Lưu dữ liệu đã load vào file pkl"""
    pkl_path = Path(pkl_file)
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(pkl_path, 'wb') as f:
        pickle.dump(data_dict, f)
    
    print(f"\n✓ Đã lưu dữ liệu vào: {pkl_path}")
    return pkl_path


def load_data_from_pkl(pkl_file="data/preprocessed_data.pkl"):
    """Đọc dữ liệu từ file pkl"""
    pkl_path = Path(pkl_file)
    
    if not pkl_path.exists():
        raise FileNotFoundError(f"File pkl không tồn tại: {pkl_path}")
    
    with open(pkl_path, 'rb') as f:
        data_dict = pickle.load(f)
    
    print(f"\n✓ Đã đọc dữ liệu từ: {pkl_path}")
    return data_dict


if __name__ == "__main__":
    # Test load và save
    print("\n" + "="*80)
    print("CELL 2: LOAD DATA FROM CSV FILES - UPDATE")
    print("="*80)
    
    arc_file = 'data/Mekong/arcs_remapped.csv'
    node_file = 'data/Mekong/nodes_remapped_with_coords.csv'
    
    # Load data
    result = load_all_data(node_file, arc_file)
    
    # Unpack
    (edges_raw, OD_pairs, node_names, node_projects, node_type, node_coords,
     node_capacity_passenger, node_capacity_goods,
     node_capacity_pcu_levels, node_invest_levels,
     real_nodes, existing_hubs, potential_hubs,
     existing_arcs, potential_arcs,
     normal_nodes, candidate_hubs_new, candidate_hubs_upgrade,
     potential_arcs_cap_0, potential_arcs_cap_up, existing_arcs_cap,
     real_arc_upgrade_costs) = result
    
    # Save to pkl
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
    
    save_data_to_pkl(data_dict, "data/preprocessed_data.pkl")
    print("\n✓ Hoàn tất CELL 2!")
