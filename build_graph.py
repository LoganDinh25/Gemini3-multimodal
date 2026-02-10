"""
CELL 3: BUILD EXTENDED GRAPH
This module builds expanded graph from loaded data
"""

from collections import defaultdict


# ============================================================
# Helper functions
# ============================================================
def to_edge_tuple_list(edges_raw):
    """
    Normalize edges_raw to list of tuples: (u, v, mode, length, project)
    Support:
      - dict: {"u","v","mode","length_m","project",...}
      - tuple: (u,v,mode,length,project,...) or (u,v,mode,length,project)
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
            # item can be: (v, dist, arc_type)  hoặc (v, 0, 'virtual_arc')
            v, _, arc_type = item

            if arc_type in ("road", "water"):
                # real arc: u must be physical node (int), v usually virtual node (tuple)
                if isinstance(u, int):
                    real_arcs.append((u, to_virtual_label(v)))

            elif arc_type == "virtual_arc":
                # virtual arc: u thường là node ảo (tuple), v usually physical node (int)
                if isinstance(u, tuple) and isinstance(v, int):
                    virtual_arcs.append((to_virtual_label(u), v))

    return real_arcs, virtual_arcs


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

    # keep "clean" order: real->virtual trước, then virtual->virtual
    def arc_key(a):
        u, v = a
        typ = 0 if isinstance(u, int) else 1
        return (typ, str(u), str(v))

    return sorted(A_set, key=arc_key)


# ============================================================
# Create arc structure from edges_raw
# ============================================================
def create_arc_structure(edges_raw, all_hubs_from_data):
    real_arcs = []
    virtual_arcs = []
    through_hub_arc = []
    
    # Set of hubs for quick lookup
    hubs_set = set(all_hubs_from_data)
    
    for edge in edges_raw:
        u = edge["u"]
        v = edge["v"]
        mode = edge["mode"]
        
        # Create corresponding virtual node
        v_virtual = f'{v}^{mode}'
        u_virtual = f'{u}^{mode}'
        
        # Real arc: from physical to virtual node
        real_arcs.append((u, v_virtual))
        real_arcs.append((v, u_virtual))
        
        # Virtual arc: from virtual back to physical node
        virtual_arcs.append((v_virtual, v))
        if (u_virtual, u) not in virtual_arcs:
            virtual_arcs.append((u_virtual, u))
        
        # Create through-hub arcs if both u and v are hubs
        if u in hubs_set:
            # Create through-hub arc for this mode
            v_virtual = f'{v}^{mode}'
            through_hub_arc.append((u_virtual, v_virtual))
    
    return real_arcs, virtual_arcs, through_hub_arc


# ============================================================
# Classify arcs (potential vs existing)
# ============================================================
def classify_arcs(edges_raw, A, real_arcs, virtual_arcs, through_hub_arc):
    """Classify arcs as potential and existing"""
    # Map real arcs để xác định loại project
    arc_project_type = {}
    for edge in edges_raw:
        u = edge["u"]
        v = edge["v"]
        mode = edge["mode"]
        project = edge["project"]
        v_virtual = f'{v}^{mode}'
        arc_project_type[(u, v_virtual)] = project

    # Classify potential and existing arcs
    potential_arcs_list = []
    existing_arcs_list = []

    for arc in A:
        if arc in arc_project_type:
            if arc_project_type[arc] == "P":
                potential_arcs_list.append(arc)
            else:
                existing_arcs_list.append(arc)
        else:
            # Virtual and through-hub arcs
            # Check if virtual arc
            if arc in virtual_arcs:
                existing_arcs_list.append(arc)
            # Check if through-hub arc
            elif arc in through_hub_arc:
                # Find corresponding real arc
                u_physical = int(arc[0].split('^')[0])
                v_physical = int(arc[1].split('^')[0])
                mode = int(arc[0].split('^')[1])
                
                # Find corresponding edge
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
    
    return potential_arcs_list, existing_arcs_list


# ============================================================
# Main function: Build expanded graph
# ============================================================
def build_graph_structure(edges_raw, H, N, OD_pairs):
    """
    Build expanded graph and arc structures
    
    Returns:
        G_exp: Expanded graph
        A: All arcs
        A_tilde: Potential arcs
        A0: Existing arcs
        N_virtual: Virtual nodes list
        all_nodes: All nodes (real + virtual)
    """
    print("\n" + "="*80)
    print("CELL 3: BUILD EXTENDED GRAPH")
    print("="*80)
    
    # Create arcs from CSV data
    print("\n[3] Create arcs from CSV data:")
    real_arcs, virtual_arcs, through_hub_arc = create_arc_structure(edges_raw, H)
    
    # Create A (all arcs)
    A = real_arcs + virtual_arcs + through_hub_arc
    
    print(f"  • Real arcs: {len(real_arcs)} arcs")
    print(f"  • Virtual arcs: {len(virtual_arcs)} arcs")
    print(f"  • Through-hub arcs: {len(through_hub_arc)} arcs")
    print(f"  • Total A: {len(A)} arcs")
    
    # Classify arcs (potential vs existing)
    print("\n Classify arcs (potential vs existing):")
    potential_arcs_list, existing_arcs_list = classify_arcs(edges_raw, A, real_arcs, virtual_arcs, through_hub_arc)
    
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
    
    # Build expanded graph
    print("\n[3.2] Xây dựng expanded graph:")
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
    
    # Build arcs từ expanded graph
    real_arcs_from_graph, virtual_arcs_from_graph = build_arcs(G_exp)
    
    print("real_arcs:", real_arcs_from_graph[:5] if len(real_arcs_from_graph) > 5 else real_arcs_from_graph)
    print("virtual_arcs:", virtual_arcs_from_graph[:5] if len(virtual_arcs_from_graph) > 5 else virtual_arcs_from_graph)
    
    # Add reverse arcs
    A_tilde = add_reverse_arcs(A_tilde)
    through_hub_arc = add_reverse_arcs(through_hub_arc)
    A = add_reverse_arcs(real_arcs_from_graph) + virtual_arcs_from_graph + through_hub_arc
    
    A0 = [arc for arc in A if arc not in A_tilde]
    
    # Virtual nodes
    N_virtual = []
    for i in virtual_nodes_list:
        virtual_node = str(i[0]) + '^' + str(i[1])
        if virtual_node not in N_virtual:
            N_virtual.append(virtual_node)
    
    all_nodes = N + N_virtual
    
    print(f"\n✓ Hoàn tất CELL 3!")
    print(f"  • Total arcs: {len(A)}")
    print(f"  • Potential arcs: {len(A_tilde)}")
    print(f"  • Existing arcs: {len(A0)}")
    print(f"  • Virtual nodes: {len(N_virtual)}")
    
    return {
        'G_exp': G_exp,
        'A': A,
        'A_tilde': A_tilde,
        'A0': A0,
        'N_virtual': N_virtual,
        'all_nodes': all_nodes,
        'OD_pairs': OD_pairs,
        'real_nodes_list': real_nodes_list,
        'virtual_nodes_list': virtual_nodes_list,
    }
