"""
Main file to run optimization
Integrates all split modules
"""

import os
import sys
from pathlib import Path

# Import split modules
from load_data import load_all_data, save_data_to_pkl, load_data_from_pkl
from build_graph import build_graph_structure
from calculate_paths import calculate_all_paths, load_paths_from_pkl


def main():
    """
    Main function to run optimization
    """
    print("\n" + "="*80)
    print("GRAPH-AWARE LOGISTICS PLANNER - OPTIMIZATION RUNNER")
    print("="*80)
    
    # ============================================================
    # STEP 1: Load data (CELL 2)
    # ============================================================
    print("\n" + "="*80)
    print("STEP 1: LOAD DATA (CELL 2)")
    print("="*80)
    
    arc_file = 'data/Mekong/arcs_remapped.csv'
    node_file = 'data/Mekong/nodes_remapped_with_coords.csv'
    data_pkl = 'data/preprocessed_data.pkl'
    
    # Check if pkl file exists
    if Path(data_pkl).exists():
        print(f"\n✓ Found pkl file: {data_pkl}")
        use_pkl = input("  Use pkl file? (y/n, default=y): ").strip().lower()
        if use_pkl != 'n':
            print("  Reading from pkl...")
            data_dict = load_data_from_pkl(data_pkl)
            
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
        else:
            print("  Loading from CSV...")
            result = load_all_data(node_file, arc_file)
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
            save_data_to_pkl(data_dict, data_pkl)
    else:
        print("  Không tìm thấy file pkl, đang load từ CSV...")
        result = load_all_data(node_file, arc_file)
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
        save_data_to_pkl(data_dict, data_pkl)
    
    # Setup các biến cần thiết
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
    
    # ============================================================
    # STEP 2: Build graph (CELL 3)
    # ============================================================
    print("\n" + "="*80)
    print("STEP 2: BUILD GRAPH (CELL 3)")
    print("="*80)
    
    graph_data = build_graph_structure(edges_raw, H, N, OD_pairs)
    
    G_exp = graph_data['G_exp']
    A = graph_data['A']
    A_tilde = graph_data['A_tilde']
    A0 = graph_data['A0']
    N_virtual = graph_data['N_virtual']
    all_nodes = graph_data['all_nodes']
    OD_pairs = graph_data['OD_pairs']  # Updated với format mới
    
    # ============================================================
    # STEP 3: Calculate paths (CELL 4 + CELL 5)
    # ============================================================
    print("\n" + "="*80)
    print("STEP 3: CALCULATE PATHS (CELL 4 + CELL 5)")
    print("="*80)
    
    paths_pkl = 'data/paths_data.pkl'
    
    # Check if pkl file exists
    if Path(paths_pkl).exists():
        print(f"\n✓ Found pkl file: {paths_pkl}")
        use_pkl = input("  Use pkl file? (y/n, default=y): ").strip().lower()
        if use_pkl != 'n':
            print("  Reading paths từ pkl...")
            paths_data = load_paths_from_pkl(paths_pkl)
            paths = paths_data['paths']
            Lmin_dict = paths_data['Lmin_dict']
        else:
            print("  Đang tính toán paths...")
            paths, Lmin_dict = calculate_all_paths(
                G_exp, OD_pairs, H, node_names, node_projects, edges_raw,
                EPSILON=0.5, MAX_PATHS_PER_OD=5000, save_pkl=True
            )
    else:
        print("  Không tìm thấy file pkl, đang tính toán paths...")
        paths, Lmin_dict = calculate_all_paths(
            G_exp, OD_pairs, H, node_names, node_projects, edges_raw,
            EPSILON=0.5, MAX_PATHS_PER_OD=5000, save_pkl=True
        )
    
    # ============================================================
    # STEP 4: Setup costs và build model
    # ============================================================
    print("\n" + "="*80)
    print("STEP 4: SETUP COSTS & BUILD MODEL")
    print("="*80)
    print("\n⚠️  Phần này cần import từ model_gurobi.py gốc")
    print("   Hoặc tách thành các module riêng: setup_costs.py, build_model.py")
    print("   Hiện tại bạn có thể chạy model_gurobi.py trực tiếp sau khi đã có pkl")
    
    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✓ Loaded data: {len(edges_raw)} arcs, {len(node_names)} nodes")
    print(f"✓ Đã build graph: {len(A)} arcs, {len(N_virtual)} virtual nodes")
    print(f"✓ Đã tính paths: {sum(len(p) for p in paths.values())} paths")
    print(f"\n📁 Files pkl đã tạo:")
    print(f"  - {data_pkl}")
    print(f"  - {paths_pkl}")
    print(f"\n💡 Để chạy optimization, bạn có thể:")
    print(f"  1. Sử dụng model_gurobi.py với dữ liệu đã load")
    print(f"  2. Hoặc tách thêm các module: setup_costs.py, build_model.py, solve_and_export.py")


if __name__ == "__main__":
    main()
