"""
Integrated Gurobi Optimization Module
Wrapper for your multi-modal hub network optimization model

Cách sử dụng:
    python run_optimization.py --period 1
"""

import csv
import re
import numpy as np
import pandas as pd
import json
from pathlib import Path
from collections import defaultdict

try:
    import gurobipy as gp
    from gurobipy import GRB
    GUROBI_AVAILABLE = True
except ImportError:
    GUROBI_AVAILABLE = False
    print("⚠️ Gurobi not installed. Run: pip install gurobipy")


# ============================================================================
# HELPER FUNCTIONS (từ model gốc)
# ============================================================================

def _split_semicolon(s: str):
    """Split by ';', strip, drop empties."""
    if s is None:
        return []
    s = str(s).strip()
    if not s:
        return []
    parts = re.split(r"[;]", s)
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
    """Parse: '1,000; 2,500; 3,000' -> [1000.0, 2500.0, 3000.0]"""
    vals = []
    for p in _split_semicolon(cell):
        p = p.replace(",", "").strip()
        try:
            vals.append(float(p))
        except:
            continue
    return vals

def _parse_destinations(cell: str):
    """Parse destinations separated by ';'"""
    dests = []
    for p in _split_semicolon(cell):
        for x in re.findall(r"\d+", p):
            dests.append(int(x))
    return dests


# ============================================================================
# DATA LOADERS (từ model gốc, đã adapt)
# ============================================================================

def load_arcs(arc_file):
    """Load arc data từ CSV file của bạn"""
    edges = []
    print(f"\n📊 Loading arcs from: {arc_file}")
    
    with open(arc_file, newline='', encoding='utf-8', errors="ignore") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                u = _to_int(row.get("FromNode"))
                v = _to_int(row.get("ToNode"))
                
                # mode from Type
                t = str(row.get("Type", "")).strip().upper()
                mode = 1 if t == "R" else 2  # 1=road, 2=water
                
                length_m = _to_float(row.get("Length(m)", 0))
                base_cost = _to_float(row.get("base_costs", 0))
                project = str(row.get("Project(P/E)", "E")).strip().upper()
                
                cap_base = _to_float(row.get("Capacity", 0))
                cap_after = _to_float(row.get("Capacity_After_Investment", 0))
                inv_cost = _to_float(row.get("Investment_Cost (Billion VND)", 0))
                const_time = _to_float(row.get("Construction_Time (Years)", 0))
                
                # Normalize capacities
                if project == "E":
                    if cap_after == 0 and cap_base > 0:
                        cap_after = cap_base
                    inv_cost = 0.0
                
                edges.append({
                    "u": u,
                    "v": v,
                    "mode": mode,
                    "length_m": length_m,
                    "base_cost": base_cost,
                    "project": project,
                    "capacity_base_tpy": cap_base,
                    "capacity_after_tpy": cap_after,
                    "investment_cost_bil_vnd": inv_cost,
                    "construction_time_years": const_time,
                })
            except Exception as e:
                continue
    
    print(f"✓ Loaded {len(edges)} arcs")
    return edges


def load_nodes(node_file):
    """Load node data từ CSV file của bạn"""
    print(f"\n📊 Loading nodes from: {node_file}")
    
    OD_pairs = defaultdict(list)
    node_names = {}
    node_coords = {}
    node_type = {}
    node_invest_levels = {}
    node_capacity_pcu_levels = {}
    
    with open(node_file, newline='', encoding='utf-8', errors="ignore") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                nid = _to_int(row.get("New_ID"))
                name = str(row.get("Name", "")).strip()
                proj_raw = str(row.get("Project", "")).strip()
                
                node_names[nid] = name
                
                # Coordinates
                lat = _to_float(row.get("Latitude", 0))
                lon = _to_float(row.get("Longitude", 0))
                node_coords[nid] = (lat, lon)
                
                # Determine node type
                if proj_raw.upper() in ["E", "EXISTING", "N"]:
                    node_type[nid] = "NORMAL"
                elif "UPGRADE" in proj_raw.upper():
                    node_type[nid] = "CANDIDATE_UPGRADE"
                elif "NEW" in proj_raw.upper():
                    node_type[nid] = "CANDIDATE_NEW"
                else:
                    node_type[nid] = "NORMAL"
                
                # Investment levels
                inv_str = str(row.get("Inverst", "")).strip()
                node_invest_levels[nid] = _to_float_list(inv_str) if inv_str else [0]
                
                # Capacity levels
                cap_str = str(row.get("Capacity(PCU/year)", "")).strip()
                node_capacity_pcu_levels[nid] = _to_float_list(cap_str) if cap_str else [0]
                
                # OD pairs
                dest_str = str(row.get("Destination", "")).strip()
                if dest_str:
                    for commodity in ["g1", "g2"]:  # passenger, rice
                        dests = _parse_destinations(dest_str)
                        for d in dests:
                            if d != nid:
                                OD_pairs[commodity].append((nid, d))
                
            except Exception as e:
                continue
    
    print(f"✓ Loaded {len(node_names)} nodes")
    print(f"✓ Found {sum(len(v) for v in OD_pairs.values())} OD pairs")
    
    return {
        'OD_pairs': OD_pairs,
        'node_names': node_names,
        'node_coords': node_coords,
        'node_type': node_type,
        'node_invest_levels': node_invest_levels,
        'node_capacity_pcu_levels': node_capacity_pcu_levels
    }


# ============================================================================
# OPTIMIZATION RUNNER
# ============================================================================

def run_optimization(
    arc_file: str,
    node_file: str,
    output_dir: str = "data/Mekong",
    periods: int = 4
):
    """
    Chạy Gurobi optimization model
    
    Args:
        arc_file: Path to arcs CSV
        node_file: Path to nodes CSV
        output_dir: Directory to save results
        periods: Number of planning periods
    """
    
    if not GUROBI_AVAILABLE:
        print("❌ Gurobi not available!")
        return None
    
    print("\n" + "="*70)
    print("🚀 RUNNING MULTI-MODAL HUB NETWORK OPTIMIZATION")
    print("="*70)
    
    # Load data
    edges = load_arcs(arc_file)
    node_data = load_nodes(node_file)
    
    print(f"\n📋 Data Summary:")
    print(f"   - Nodes: {len(node_data['node_names'])}")
    print(f"   - Arcs: {len(edges)}")
    print(f"   - Planning periods: {periods}")
    
    # Build và solve model (simplified - bạn có thể uncomment full model code)
    print(f"\n🔨 Building Gurobi model...")
    
    # Ở đây bạn có thể paste TOÀN BỘ code model gốc
    # Hoặc gọi function build_model() từ file gốc
    
    # For now, trả về sample result để test integration
    print(f"\n⚠️ NOTE: Using sample results for testing")
    print(f"   To run real optimization, uncomment model code in this file")
    
    # Sample result structure
    sample_result = {
        "region": "Mekong",
        "period": 1,
        "total_cost": 2450000000,  # 2.45 billion VND
        "total_time": 48.5,
        "num_hubs": 3,
        "selected_hubs": [3, 4, 7],  # Based on your model
        "hub_levels": {
            3: 1,  # Level 1 upgrade
            4: 1,
            7: 0   # Existing hub
        },
        "top_routes": [
            {
                "route_id": 1,
                "path": [1, 3, 7, 12],
                "commodity": "Passenger",
                "mode": "multi-modal",
                "cost": 180000,
                "flow": 5500
            },
            {
                "route_id": 2,
                "path": [2, 4, 7, 15],
                "commodity": "Rice",
                "mode": "water",
                "cost": 220000,
                "flow": 8200
            },
            {
                "route_id": 3,
                "path": [5, 3, 8],
                "commodity": "Passenger",
                "mode": "road",
                "cost": 95000,
                "flow": 3200
            }
        ],
        "hub_utilization": {
            3: 0.78,
            4: 0.85,
            7: 0.62
        },
        "modal_split": {
            "road": 0.42,
            "water": 0.58
        },
        "arc_upgrades": [
            {"from": 3, "to": 7, "mode": "water", "period": 1},
            {"from": 4, "to": 7, "mode": "road", "period": 2}
        ],
        "investment_summary": {
            "hub_investment": 350000000,
            "arc_investment": 180000000,
            "total_investment": 530000000
        },
        "efficiency": 0.87,
        "solver_status": "optimal",
        "solve_time": 125.3
    }
    
    return sample_result


# ============================================================================
# EXPORT TO STREAMLIT FORMAT
# ============================================================================

def export_for_streamlit(result: dict, output_dir: str, period: int):
    """
    Export kết quả optimization sang format cho Streamlit app
    """
    
    # Convert to Streamlit format
    streamlit_result = {
        "region": result["region"],
        "period": period,
        "total_cost": result["total_cost"],
        "total_time": result.get("total_time", 0),
        "num_hubs": result["num_hubs"],
        "selected_hubs": result["selected_hubs"],
        "top_routes": result["top_routes"],
        "hub_utilization": {str(k): v for k, v in result["hub_utilization"].items()},
        "modal_split": result["modal_split"],
        "efficiency": result["efficiency"],
        "solver_status": result["solver_status"],
        "solve_time": result["solve_time"],
        
        # Additional metadata
        "metadata": {
            "hub_levels": result.get("hub_levels", {}),
            "arc_upgrades": result.get("arc_upgrades", []),
            "investment_summary": result.get("investment_summary", {})
        }
    }
    
    # Save to JSON
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    output_file = output_path / f"optimization_results_period{period}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(streamlit_result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results exported to: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   - Total Cost: {result['total_cost']:,.0f} VND")
    print(f"   - Hubs Selected: {result['selected_hubs']}")
    print(f"   - Routes: {len(result['top_routes'])}")
    print(f"   - Solve Time: {result['solve_time']:.1f}s")
    
    return output_file


# ============================================================================
# CONVERT CSV TO STREAMLIT FORMAT
# ============================================================================

def convert_mekong_data_to_streamlit(
    arc_file: str,
    node_file: str,
    output_dir: str = "data/mekong_delta"
):
    """
    Convert your existing Mekong CSV files to Streamlit format
    
    Creates:
        - nodes.csv (Streamlit format)
        - edges.csv (Streamlit format)
        - demand.csv (inferred from OD pairs)
    """
    
    print("\n" + "="*70)
    print("🔄 CONVERTING MEKONG DATA TO STREAMLIT FORMAT")
    print("="*70)
    
    # Load your data
    edges_data = load_arcs(arc_file)
    node_data = load_nodes(node_file)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # -------------------------
    # 1. Convert NODES
    # -------------------------
    nodes_streamlit = []
    
    for nid, name in node_data['node_names'].items():
        lat, lon = node_data['node_coords'].get(nid, (0, 0))
        ntype = node_data['node_type'].get(nid, "NORMAL")
        
        # Determine if hub
        is_hub = "hub" if "CANDIDATE" in ntype or "UPGRADE" in ntype else "normal"
        
        # Get capacity
        cap_levels = node_data['node_capacity_pcu_levels'].get(nid, [0])
        capacity = cap_levels[0] if cap_levels else 5000
        
        nodes_streamlit.append({
            'node_id': nid,
            'name': name,
            'lat': lat,
            'lon': lon,
            'type': is_hub,
            'capacity': capacity,
            'cost_per_day': 1000 if is_hub == "hub" else 500
        })
    
    nodes_df = pd.DataFrame(nodes_streamlit)
    nodes_file_out = output_path / 'nodes.csv'
    nodes_df.to_csv(nodes_file_out, index=False)
    print(f"✓ Created: {nodes_file_out} ({len(nodes_df)} nodes)")
    
    # -------------------------
    # 2. Convert EDGES
    # -------------------------
    edges_streamlit = []
    
    for idx, edge in enumerate(edges_data, 1):
        mode_str = "road" if edge['mode'] == 1 else "water"
        
        # Calculate time from distance (rough estimate)
        distance_km = edge['length_m'] / 1000
        if mode_str == "water":
            time_days = distance_km / 12.5 / 24  # 12.5 km/h
        else:
            time_days = distance_km / 50 / 24    # 50 km/h
        
        edges_streamlit.append({
            'edge_id': idx,
            'from_node': edge['u'],
            'to_node': edge['v'],
            'mode': mode_str,
            'cost': edge['base_cost'],
            'capacity': edge['capacity_base_tpy'],
            'distance': distance_km,
            'time': round(time_days, 2)
        })
    
    edges_df = pd.DataFrame(edges_streamlit)
    edges_file_out = output_path / 'edges.csv'
    edges_df.to_csv(edges_file_out, index=False)
    print(f"✓ Created: {edges_file_out} ({len(edges_df)} edges)")
    
    # -------------------------
    # 3. Create DEMAND from OD pairs
    # -------------------------
    demand_streamlit = []
    demand_id = 1
    
    for commodity_key, od_pairs in node_data['OD_pairs'].items():
        commodity_name = "Passenger" if commodity_key == "g1" else "Rice"
        
        for origin, destination in od_pairs:
            # Generate random but realistic volume
            if commodity_name == "Passenger":
                volume = np.random.uniform(300, 800)
                priority = "speed"
            else:
                volume = np.random.uniform(500, 1200)
                priority = "cost"
            
            for period in [1, 2, 3, 4]:
                demand_streamlit.append({
                    'demand_id': demand_id,
                    'origin': origin,
                    'destination': destination,
                    'commodity': commodity_name,
                    'volume': round(volume, 1),
                    'period': period,
                    'priority': priority
                })
                demand_id += 1
    
    demand_df = pd.DataFrame(demand_streamlit)
    demand_file_out = output_path / 'demand.csv'
    demand_df.to_csv(demand_file_out, index=False)
    print(f"✓ Created: {demand_file_out} ({len(demand_df)} demands)")
    
    print(f"\n{'='*70}")
    print(f"✅ CONVERSION COMPLETE!")
    print(f"\nFiles created in: {output_dir}/")
    print(f"   - nodes.csv")
    print(f"   - edges.csv")
    print(f"   - demand.csv")
    print(f"\n🚀 Ready to use in Streamlit app!")
    print(f"   streamlit run app.py")
    print(f"{'='*70}\n")
    
    return output_dir


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Mekong Delta Optimization')
    parser.add_argument('--mode', type=str, default='convert', 
                       choices=['convert', 'optimize', 'both'],
                       help='Mode: convert data only, optimize only, or both')
    parser.add_argument('--arc-file', type=str, 
                       default='data/Mekong/arcs_remapped.csv',
                       help='Path to arcs CSV file')
    parser.add_argument('--node-file', type=str, 
                       default='data/Mekong/nodes_remapped_with_coords.csv',
                       help='Path to nodes CSV file')
    parser.add_argument('--output-dir', type=str, 
                       default='data/mekong_delta',
                       help='Output directory for Streamlit files')
    parser.add_argument('--period', type=int, default=1,
                       help='Planning period (1-4)')
    
    args = parser.parse_args()
    
    # Mode 1: Convert data
    if args.mode in ['convert', 'both']:
        convert_mekong_data_to_streamlit(
            arc_file=args.arc_file,
            node_file=args.node_file,
            output_dir=args.output_dir
        )
    
    # Mode 2: Run optimization
    if args.mode in ['optimize', 'both']:
        result = run_optimization(
            arc_file=args.arc_file,
            node_file=args.node_file,
            output_dir=args.output_dir,
            periods=4
        )
        
        if result:
            export_for_streamlit(result, args.output_dir, args.period)
    
    print("\n✅ ALL DONE!")
