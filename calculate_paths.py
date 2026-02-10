"""
CELL 4 & CELL 5: TÍNH L_min VÀ NEAR-OPTIMAL PATHS CHO TỪNG O-D
This module computes paths and saves to pkl after completing CELL 5
"""

from collections import defaultdict
import heapq
import math
import itertools
import re
import pickle
from pathlib import Path


# ============================================================
# CELL 4: TÍNH L_min CHO TỪNG O-D
# ============================================================
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


def origin_states(o):
    # origin can be physical node "o" or state (o,1)/(o,2)
    return [o, (o, 1), (o, 2)]


def dest_targets(d):
    # destination can reach node d hoặc các trạng thái (d,1)/(d,2)
    # (d,0) in sample code is actually "d" (node thật). Keep both d.
    return [d, (d, 1), (d, 2)]


def calculate_L_min(G_exp, OD_pairs):
    """
    CELL 4: Compute L_min for each O-D pair
    """
    print("\n" + "="*80)
    print("CELL 4: TÍNH L_min CHO TỪNG O-D")
    print("="*80)
    
    # Build reverse graph once
    G_rev = build_reverse_graph(G_exp)
    print(f"[CELL 4] Reverse graph built: {len(G_rev)} keys")

    # Compute L_min for each OD
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

    print(f" Computed L_min for {len(Lmin_dict)} O-D pairs | unreachable = {inf_count}/{total_count}")

    # (optional) print sample
    sample = list(Lmin_dict.items())[:10]
    print("\nExample first 10 L_min:")
    for (comm, o, d), val in sample:
        print(f"  {comm}: {o} -> {d} | L_min = {val if not math.isinf(val) else 'INF'}")
    
    return Lmin_dict


# ============================================================
# CELL 5: TÍNH NEAR-OPTIMAL PATHS CHO TỪNG O-D
# ============================================================
def near_optimal_dfs(G, start_node, target_nodes, L_min, epsilon=0.2, max_paths=100):
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
            if neigh in path:  # avoid cycle
                continue
            new_cost = cost + float(w)
            if new_cost > cutoff:
                continue
            stack.append((neigh, new_cost, path + [neigh]))

    return results[:max_paths]


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

            paths[(comm, od)] = expanded  # each OD has own list
    return paths


def parse_virtual_for_paths(node):
    """'3^2' -> (3,2), else None"""
    if not isinstance(node, str):
        return None
    m = re.fullmatch(r"(\d+)\^(\d+)", node)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def generate_all_unique_paths_with_through_hubs(paths_list, H):
    """
    Input:
        paths_list : list of paths
            each path is list of arcs [(u,v), ...]
        H : list hubs (e.g. [3,4,6])

    Output:
        unique_paths : list of unique paths (list of arcs)
    """
    all_generated = []

    for base_path in paths_list:
        n = len(base_path)

        # --- find through-hub blocks ---
        blocks = []  # each block: {start, through_arc}
        for i in range(n - 2):
            (u1, v1) = base_path[i]
            (u2, v2) = base_path[i + 1]
            (u3, v3) = base_path[i + 2]

            # pattern: (prev -> h^m), (h^m -> h), (h -> next^m)
            hv = parse_virtual_for_paths(v1)
            if hv is None:
                continue
            h, mode = hv
            if h not in H:
                continue
            if (u2, v2) != (v1, h):
                continue
            if u3 != h:
                continue

            nv = parse_virtual_for_paths(v3)
            if nv is None:
                continue
            _, mode2 = nv
            if mode2 != mode:
                continue

            blocks.append({
                "start": i,
                "through_arc": (v1, v3)  # (h^m -> next^m)
            })

        # if no hubs, keep as-is
        if not blocks:
            all_generated.append(base_path)
            continue

        # --- generate non-overlapping block combos ---
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


def calculate_near_optimal_paths(G_exp, OD_pairs, Lmin_dict, H, EPSILON=0.2, MAX_PATHS_PER_OD=5000):
    """
    CELL 5: Compute near-optimal paths for each O-D pair
    """
    print("\n" + "="*80)
    print("CELL 5: TÍNH NEAR-OPTIMAL PATHS CHO TỪNG O-D")
    print("="*80)

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

            # start/end are physical nodes
            start_node = o
            target_nodes = {d}

            # if origin has no outgoing trong expanded graph thì bỏ
            if start_node not in G_exp:
                near_optimal_paths[comm][(o, d)] = []
                continue

            paths = near_optimal_dfs(
                G_exp, start_node, target_nodes, L_min,
                epsilon=EPSILON, max_paths=MAX_PATHS_PER_OD
            )

            # deduplicate
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

    print(f"Complete! Found {total_paths} near-optimal paths (ε={EPSILON})")
    print(f"   - Unreachable OD (L_min=INF): {unreachable}")

    # Build paths from near_optimal_paths
    paths = build_paths_from_near_optimal(near_optimal_paths)

    print("Number of paths for g1,(0,14):", len(paths.get(('g1',(0,14)), [])))
    if ('g1',(0,14)) in paths and paths[('g1',(0,14))]:
        print("Example endpoints:", paths[('g1',(0,14))][0][0][0], "->", paths[('g1',(0,14))][0][-1][1])

    # Generate all unique paths with through hubs
    all_pairs = {}
    for g, od_list in OD_pairs.items():
        for od in od_list:
            key = (g, od)
            base_paths = paths.get(key, [])
            all_pairs[key] = generate_all_unique_paths_with_through_hubs(base_paths, H)

    paths = all_pairs

    return paths


# ============================================================
# SAVE AND LOAD PKL AFTER CELL 5
# ============================================================
def save_paths_to_pkl(paths, Lmin_dict, node_names, node_projects, edges_raw, 
                      pkl_file="data/paths_data.pkl"):
    """Save paths and related data vào file pkl sau CELL 5"""
    pkl_path = Path(pkl_file)
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    
    data_dict = {
        'paths': paths,
        'Lmin_dict': Lmin_dict,
        'node_names': node_names,
        'node_projects': node_projects,
        'edges_raw': edges_raw,
    }
    
    with open(pkl_path, 'wb') as f:
        pickle.dump(data_dict, f)
    
    print(f"\n✓ Saved paths to: {pkl_path}")
    return pkl_path


def load_paths_from_pkl(pkl_file="data/paths_data.pkl"):
    """Read paths from pkl file"""
    pkl_path = Path(pkl_file)
    
    if not pkl_path.exists():
        raise FileNotFoundError(f"Pkl file not found: {pkl_path}")
    
    with open(pkl_path, 'rb') as f:
        data_dict = pickle.load(f)
    
    print(f"\n✓ Read paths from: {pkl_path}")
    return data_dict


# ============================================================
# Main function: Calculate paths (CELL 4 + CELL 5)
# ============================================================
def calculate_all_paths(G_exp, OD_pairs, H, node_names, node_projects, edges_raw,
                        EPSILON=0.5, MAX_PATHS_PER_OD=5000, save_pkl=True):
    """
    Compute all paths (CELL 4 + CELL 5) and save to pkl
    
    Returns:
        paths: Dictionary of paths
        Lmin_dict: Dictionary of L_min values
    """
    # CELL 4: Compute L_min
    Lmin_dict = calculate_L_min(G_exp, OD_pairs)
    
    # CELL 5: Tính near-optimal paths
    paths = calculate_near_optimal_paths(G_exp, OD_pairs, Lmin_dict, H, EPSILON, MAX_PATHS_PER_OD)
    
    # Save to pkl sau CELL 5
    if save_pkl:
        save_paths_to_pkl(paths, Lmin_dict, node_names, node_projects, edges_raw)
    
    print("\n✓ Hoàn tất CELL 4 & CELL 5!")
    
    return paths, Lmin_dict
