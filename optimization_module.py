"""
Optimization Module - Gurobi Integration
Chạy offline để tạo optimization results cho Gemini phân tích

Flow:
1. Load dữ liệu vùng (nodes, edges, demand)
2. Chạy Gurobi optimization model
3. Export kết quả ra JSON
4. JSON này được load vào app.py để Gemini giải thích
"""

import json
from typing import Dict, List, Any
import pandas as pd
from pathlib import Path

try:
    import gurobipy as gp
    from gurobipy import GRB
    GUROBI_AVAILABLE = True
except ImportError:
    GUROBI_AVAILABLE = False
    print("Warning: Gurobi not installed. Install with: pip install gurobipy")


class LogisticsOptimizer:
    """
    Wrapper cho Gurobi optimization model
    
    Chức năng:
    - Build optimization model từ dữ liệu vùng
    - Solve với Gurobi
    - Export kết quả ra format chuẩn cho Gemini
    """
    
    def __init__(self, region_data: Dict[str, pd.DataFrame]):
        """
        Initialize optimizer với dữ liệu vùng
        
        Args:
            region_data: Dict chứa 'nodes', 'edges', 'demand' DataFrames
        """
        self.nodes = region_data['nodes']
        self.edges = region_data['edges']
        self.demand = region_data['demand']
        
        self.model = None
        self.solution = None
        
    def build_model(
        self,
        period: int,
        commodity: str = None,
        priority: float = 0.5  # 0 = cost, 1 = speed
    ):
        """
        Build Gurobi optimization model
        
        ĐÂY LÀ NơI BạN PASTE CODE GUROBI MODEL CỦA BẠN
        
        Args:
            period: Giai đoạn tối ưu
            commodity: Loại hàng hóa (None = tất cả)
            priority: Ưu tiên cost (0) vs speed (1)
        """
        if not GUROBI_AVAILABLE:
            raise ImportError("Gurobi is not installed")
        
        # Create model
        self.model = gp.Model("logistics_optimization")
        
        # ==================================================================
        # EXAMPLE MODEL STRUCTURE (REPLACE WITH YOUR ACTUAL GUROBI CODE)
        # ==================================================================
        
        # Sets - ensure UNIQUE to avoid "Duplicate keys in Model.addVars()"
        N = list(self.nodes['node_id'].drop_duplicates().tolist())
        arcs_raw = list(zip(self.edges['from_node'], self.edges['to_node']))
        A = list(dict.fromkeys(arcs_raw))  # preserve order, remove duplicates
        K = [str(c) for c in self.demand['commodity'].dropna().unique().tolist()]
        if not K:
            K = ['default']  # fallback if no demand
        
        # Parameters - use same unique arc keys as A
        cost = {}
        time = {}
        capacity = {}
        for _, row in self.edges.iterrows():
            key = (row['from_node'], row['to_node'])
            if key not in cost:  # first occurrence only (or take min cost)
                cost[key] = float(row.get('cost', 0) or 0)
                time[key] = float(row.get('time', row.get('cost', 0)/100) or 0)
                capacity[key] = float(row.get('capacity', 10000) or 10000)
        
        demand_data = {}
        for _, row in self.demand.iterrows():
            if int(row.get('period', 0)) == period:
                key = (row['origin'], row['destination'], str(row.get('commodity', 'default')))
                demand_data[key] = float(row.get('volume', 0) or 0)
        
        # Decision Variables
        # x[i,j,k] = flow of commodity k on arc (i,j)
        x = self.model.addVars(A, K, name="flow", lb=0)
        
        # y[i] = 1 if node i is selected as hub
        y = self.model.addVars(N, name="hub", vtype=GRB.BINARY)
        
        # Objective: weighted combination of cost and time
        obj_cost = gp.quicksum(cost.get((i,j), 0) * x[i,j,k] 
                              for (i,j) in A for k in K)
        
        obj_time = gp.quicksum(time.get((i,j), 0) * x[i,j,k] 
                              for (i,j) in A for k in K)
        
        # Priority: 0=cost, 1=speed
        self.model.setObjective(
            (1 - priority) * obj_cost + priority * obj_time,
            GRB.MINIMIZE
        )
        
        # Constraints
        
        # 1. Flow conservation
        for k in K:
            for i in N:
                inflow = gp.quicksum(x[j,i,k] for (j,i_) in A if i_ == i)
                outflow = gp.quicksum(x[i,j,k] for (i_,j) in A if i_ == i)
                
                # Supply/demand
                supply_demand = sum(
                    demand_data.get((i, d, k), 0) - demand_data.get((o, i, k), 0)
                    for o in N for d in N
                )
                
                self.model.addConstr(
                    outflow - inflow == supply_demand,
                    name=f"flow_conservation_{i}_{k}"
                )
        
        # 2. Capacity constraints
        for (i, j) in A:
            cap = capacity.get((i, j), 10000)
            self.model.addConstr(
                gp.quicksum(x[i,j,k] for k in K) <= cap,
                name=f"capacity_{i}_{j}"
            )
        
        # 3. Hub selection (max 5 hubs)
        self.model.addConstr(
            gp.quicksum(y[i] for i in N) <= 5,
            name="max_hubs"
        )
        
        # ==================================================================
        # PASTE YOUR ACTUAL GUROBI MODEL CODE HERE
        # Thay thế example code trên bằng model logistics của bạn
        # ==================================================================
        
        self.model.setParam('OutputFlag', 1)  # Show solver output
        self.model.setParam('TimeLimit', 3600)  # 1 hour limit
        
    def solve(self) -> Dict[str, Any]:
        """
        Solve optimization model và extract kết quả
        
        Returns:
            Dictionary chứa optimization results
        """
        if self.model is None:
            raise ValueError("Model chưa được build. Call build_model() first.")
        
        print("Solving optimization model with Gurobi...")
        self.model.optimize()
        
        if self.model.status == GRB.OPTIMAL:
            print(f"✓ Optimal solution found!")
            print(f"  Objective value: {self.model.objVal:.2f}")
        else:
            print(f"✗ Solver status: {self.model.status}")
            return None
        
        # Extract solution
        solution = self._extract_solution()
        self.solution = solution
        
        return solution
    
    def _extract_solution(self) -> Dict[str, Any]:
        """
        Extract optimization solution vào format cho Gemini
        
        Returns:
            Structured solution dictionary
        """
        # Get decision variables
        flow_vars = [v for v in self.model.getVars() if v.varName.startswith('flow')]
        hub_vars = [v for v in self.model.getVars() if v.varName.startswith('hub')]
        
        # Extract selected hubs
        selected_hubs = [
            int(v.varName.split('[')[1].split(']')[0])
            for v in hub_vars if v.X > 0.5
        ]
        
        # Extract top routes (flows > threshold)
        routes = []
        flow_threshold = 10  # Minimum flow to include
        
        for v in flow_vars:
            if v.X > flow_threshold:
                # Parse variable name: flow[i,j,k]
                parts = v.varName.replace('flow[', '').replace(']', '').split(',')
                
                routes.append({
                    'from': int(parts[0]),
                    'to': int(parts[1]),
                    'commodity': parts[2],
                    'flow': v.X
                })
        
        # Aggregate routes into paths (simplified)
        top_routes = self._aggregate_routes(routes)
        
        # Calculate metrics
        total_cost = self.model.objVal
        
        # Hub utilization (simplified - you may have actual constraints)
        hub_utilization = {
            hub: sum(r['flow'] for r in routes 
                    if r['from'] == hub or r['to'] == hub) / 10000
            for hub in selected_hubs
        }
        
        # Modal split (if your edges have mode info)
        modal_split = self._calculate_modal_split(routes)
        
        return {
            'total_cost': total_cost,
            'total_time': total_cost / 100,  # Estimate based on cost
            'num_hubs': len(selected_hubs),
            'selected_hubs': selected_hubs,
            'top_routes': top_routes[:10],  # Top 10 routes
            'hub_utilization': hub_utilization,
            'modal_split': modal_split,
            'efficiency': 0.85,  # Calculate actual efficiency if you have ideal solution
            'solver_status': 'optimal',
            'solve_time': self.model.Runtime
        }
    
    def _aggregate_routes(self, routes: List[Dict]) -> List[Dict]:
        """
        Aggregate individual arcs into full paths
        (Simplified version - may need graph traversal for actual paths)
        """
        # Group by commodity
        by_commodity = {}
        for r in routes:
            k = r['commodity']
            if k not in by_commodity:
                by_commodity[k] = []
            by_commodity[k].append(r)
        
        # Create path summaries
        aggregated = []
        for commodity, flows in by_commodity.items():
            # Sort by flow volume
            flows.sort(key=lambda x: x['flow'], reverse=True)
            
            # Take top 3 flows per commodity
            for i, flow in enumerate(flows[:3]):
                # Get edge info
                edge_info = self.edges[
                    (self.edges['from_node'] == flow['from']) &
                    (self.edges['to_node'] == flow['to'])
                ]
                
                if len(edge_info) > 0:
                    edge = edge_info.iloc[0]
                    
                    aggregated.append({
                        'route_id': len(aggregated) + 1,
                        'path': [flow['from'], flow['to']],  # Simplified - build full path
                        'commodity': commodity,
                        'mode': edge.get('mode', 'road'),
                        'cost': edge.get('cost', 0) * flow['flow'],
                        'time': edge.get('time', edge.get('cost', 0)/100),
                        'flow': flow['flow']
                    })
        
        return aggregated
    
    def _calculate_modal_split(self, routes: List[Dict]) -> Dict[str, float]:
        """Calculate percentage of flow by transport mode"""
        mode_flow = {}
        total_flow = 0
        
        for route in routes:
            # Get mode from edges
            edge = self.edges[
                (self.edges['from_node'] == route['from']) &
                (self.edges['to_node'] == route['to'])
            ]
            
            if len(edge) > 0:
                mode = edge.iloc[0].get('mode', 'road')
                mode_flow[mode] = mode_flow.get(mode, 0) + route['flow']
                total_flow += route['flow']
        
        if total_flow > 0:
            return {mode: flow/total_flow for mode, flow in mode_flow.items()}
        else:
            return {}
    
    def export_results(
        self,
        output_path: str,
        region: str,
        period: int
    ):
        """
        Export optimization results to JSON file
        
        Args:
            output_path: Directory to save results
            region: Region name
            period: Period number
        """
        if self.solution is None:
            raise ValueError("No solution to export. Run solve() first.")
        
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = output_dir / f"optimization_results_period{period}.json"
        
        # Add metadata
        export_data = {
            'region': region,
            'period': period,
            **self.solution
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✓ Results exported to: {filename}")
        return filename


# ==================================================================
# HELPER FUNCTIONS - Chạy optimization offline
# ==================================================================

def run_optimization_for_region(
    region: str,
    period: int,
    data_dir: str = "data",
    output_dir: str = "data"
):
    """
    Chạy optimization cho một vùng và period
    
    Usage:
        python optimization_module.py --region mekong_delta --period 1
    
    Args:
        region: Tên vùng
        period: Giai đoạn
        data_dir: Thư mục chứa dữ liệu input
        output_dir: Thư mục lưu kết quả
    """
    from data_loader import DataLoader
    
    print(f"\n{'='*60}")
    print(f"Running Optimization: {region} - Period {period}")
    print(f"{'='*60}\n")
    
    # Load data
    loader = DataLoader(data_dir)
    data = loader.load_region_data(region)
    
    print(f"Loaded data:")
    print(f"  - Nodes: {len(data['nodes'])}")
    print(f"  - Edges: {len(data['edges'])}")
    print(f"  - Demand: {len(data['demand'])}")
    print()
    
    # Build and solve model
    optimizer = LogisticsOptimizer(data)
    optimizer.build_model(period=period, priority=0.5)
    
    solution = optimizer.solve()
    
    if solution:
        print(f"\nOptimization Summary:")
        print(f"  Total Cost: ${solution['total_cost']:,.2f}")
        print(f"  Hubs Selected: {solution['selected_hubs']}")
        print(f"  Routes Found: {len(solution['top_routes'])}")
        print(f"  Solve Time: {solution['solve_time']:.2f}s")
        
        # Export
        output_path = Path(output_dir) / region
        optimizer.export_results(output_path, region, period)
        
        print(f"\n✓ Optimization complete!")
        print(f"  Results can now be loaded in the Streamlit app")
        print(f"  Gemini 3 will analyze and explain this strategy")
    else:
        print("\n✗ Optimization failed")


if __name__ == "__main__":
    """
    Command line interface để chạy optimization
    
    Usage:
        # Chạy cho một vùng
        python optimization_module.py
        
        # Hoặc import và chạy programmatically
        from optimization_module import run_optimization_for_region
        run_optimization_for_region("mekong_delta", period=1)
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Gurobi optimization for logistics')
    parser.add_argument('--region', type=str, default='mekong_delta',
                       help='Region name')
    parser.add_argument('--period', type=int, default=1,
                       help='Planning period')
    parser.add_argument('--data-dir', type=str, default='data',
                       help='Input data directory')
    parser.add_argument('--output-dir', type=str, default='data',
                       help='Output results directory')
    
    args = parser.parse_args()
    
    if not GUROBI_AVAILABLE:
        print("ERROR: Gurobi is not installed")
        print("Install with: pip install gurobipy")
        print("Or activate your Gurobi license")
        exit(1)
    
    run_optimization_for_region(
        region=args.region,
        period=args.period,
        data_dir=args.data_dir,
        output_dir=args.output_dir
    )
