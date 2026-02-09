"""
Data Loader - Regional Dataset Management
Handles loading and validation of multi-region logistics data
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any

try:
    from coordinate_utils import convert_vn2000_to_wgs84
    _HAS_COORD_UTILS = True
except ImportError:
    _HAS_COORD_UTILS = False

class DataLoader:
    def __init__(self, data_dir: str = "data"):
        """
        Initialize data loader
        
        Args:
            data_dir: Base directory for regional data
        """
        self.data_dir = Path(data_dir)
        
    def get_available_regions(self) -> List[str]:
        """
        Get list of available regions
        
        Returns:
            List of region names
        """
        if not self.data_dir.exists():
            return ["Mekong Delta", "Toy Region"]
        
        regions = [d.name.replace('_', ' ').title() 
                  for d in self.data_dir.iterdir() 
                  if d.is_dir()]
        
        return regions if regions else ["Mekong Delta", "Toy Region"]
    
    def load_region_data(self, region: str) -> Dict[str, pd.DataFrame]:
        """
        Load complete dataset for a region
        
        Args:
            region: Region name
            
        Returns:
            Dictionary with nodes, edges, demand dataframes
        """
        region_path = self.data_dir / region.lower().replace(' ', '_')
        
        # Special handling for Mekong region (uses different file names)
        if region.lower() in ['mekong', 'mekong delta']:
            return self._load_mekong_data()
        
        # If data directory doesn't exist, generate sample data
        if not region_path.exists():
            return self._generate_sample_data(region)
        
        try:
            nodes = pd.read_csv(region_path / 'nodes.csv')
            edges = pd.read_csv(region_path / 'edges.csv')
            demand = pd.read_csv(region_path / 'demand.csv')
            
            return {
                'nodes': nodes,
                'edges': edges,
                'demand': demand
            }
        except FileNotFoundError:
            return self._generate_sample_data(region)
    
    def _load_mekong_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load Mekong Delta data with specific file format
        Files: nodes_remapped_with_coords.csv, arcs_remapped.csv
        """
        mekong_path = self.data_dir / 'Mekong'
        
        if not mekong_path.exists():
            return self._generate_sample_data('Mekong')
        
        try:
            # Load nodes file
            nodes_file = mekong_path / 'nodes_remapped_with_coords.csv'
            try:
                nodes_raw = pd.read_csv(nodes_file, encoding='utf-8')
            except UnicodeDecodeError:
                nodes_raw = pd.read_csv(nodes_file, encoding='latin-1')
            
            # Transform to standard format
            lon_raw = pd.to_numeric(nodes_raw['Longitude'], errors='coerce')
            lat_raw = pd.to_numeric(nodes_raw['Latitude'], errors='coerce')
            
            # Convert VN-2000 (UTM) to WGS84 for real map display if coordinates are in UTM range
            # VN-2000 Mekong: x ~416k-730k, y ~1.03M-1.22M
            coords_vn2000 = (lon_raw.dropna().between(400000, 800000).any() and 
                             lat_raw.dropna().between(1000000, 1300000).any())
            if _HAS_COORD_UTILS and coords_vn2000:
                lats, lons = [], []
                for _, row in nodes_raw.iterrows():
                    x = pd.to_numeric(row['Longitude'], errors='coerce')
                    y = pd.to_numeric(row['Latitude'], errors='coerce')
                    if pd.notna(x) and pd.notna(y) and 400000 <= x <= 800000 and 1000000 <= y <= 1300000:
                        lat, lon = convert_vn2000_to_wgs84(x, y)
                        lats.append(lat); lons.append(lon)
                    else:
                        lats.append(y); lons.append(x)  # Assume already WGS84
                nodes = pd.DataFrame({
                    'node_id': nodes_raw['New_ID'],
                    'name': nodes_raw['Name'],
                    'lon': lons,
                    'lat': lats,
                    'type': nodes_raw['Project'].apply(lambda x: 'hub' if str(x).upper() in ['E', 'NEW', 'UPGRADE'] else 'normal'),
                    'project': nodes_raw['Project'],
                    'capacity_goods': pd.to_numeric(
                        nodes_raw['Capacity (Goods: (Ton/Year))'].astype(str).str.replace(',', ''), 
                        errors='coerce'
                    ).fillna(0)
                })
            else:
                nodes = pd.DataFrame({
                    'node_id': nodes_raw['New_ID'],
                    'name': nodes_raw['Name'],
                    'lon': lon_raw,
                    'lat': lat_raw,
                    'type': nodes_raw['Project'].apply(lambda x: 'hub' if str(x).upper() in ['E', 'NEW', 'UPGRADE'] else 'normal'),
                    'project': nodes_raw['Project'],
                    'capacity_goods': pd.to_numeric(
                        nodes_raw['Capacity (Goods: (Ton/Year))'].astype(str).str.replace(',', ''), 
                        errors='coerce'
                    ).fillna(0)
                })
            
            # Load arcs file
            arcs_file = mekong_path / 'arcs_remapped.csv'
            try:
                edges_raw = pd.read_csv(arcs_file, encoding='utf-8')
            except UnicodeDecodeError:
                edges_raw = pd.read_csv(arcs_file, encoding='latin-1')
            
            # Transform to standard format
            edges = pd.DataFrame({
                'from_node': edges_raw['FromNode'],
                'to_node': edges_raw['ToNode'],
                'mode': edges_raw['Type'].apply(lambda x: 'road' if str(x).upper() == 'R' else 'water'),
                'length_m': pd.to_numeric(edges_raw['Length(m)'], errors='coerce'),
                'project': edges_raw['Project(P/E)'],
                'base_cost': pd.to_numeric(edges_raw['base_costs'], errors='coerce'),
                'investment_cost': pd.to_numeric(
                    edges_raw['Investment_Cost (Billion VND)'].astype(str).str.replace(',', ''), 
                    errors='coerce'
                ).fillna(0),
                'capacity': pd.to_numeric(
                    edges_raw['Capacity'].astype(str).str.replace(',', ''), 
                    errors='coerce'
                ).fillna(0),
                'capacity_after': pd.to_numeric(
                    edges_raw['Capacity_After_Investment'].astype(str).str.replace(',', ''), 
                    errors='coerce'
                ).fillna(0),
                'cost': pd.to_numeric(edges_raw['base_costs'], errors='coerce')  # Use base_cost as cost
            })
            
            # Generate sample demand data (since Mekong doesn't have demand.csv)
            # In production, this should come from actual demand data
            import numpy as np
            demand = pd.DataFrame({
                'origin': np.random.choice(nodes['node_id'].values, size=20),
                'destination': np.random.choice(nodes['node_id'].values, size=20),
                'commodity': np.random.choice(['Rice', 'Coal', 'Container', 'General'], size=20),
                'volume': np.random.uniform(100, 5000, size=20),
                'period': np.random.choice([1, 2], size=20)
            })
            
            return {
                'nodes': nodes,
                'edges': edges,
                'demand': demand
            }
            
        except Exception as e:
            print(f"Error loading Mekong data: {e}")
            return self._generate_sample_data('Mekong')
    
    def load_optimization_results(
        self, 
        region: str, 
        period: int
    ) -> Dict[str, Any]:
        """
        Load precomputed optimization results
        
        Args:
            region: Region name
            period: Planning period
            
        Returns:
            Optimization results dictionary
        """
        region_path = self.data_dir / region.lower().replace(' ', '_')
        result_file = region_path / f'optimization_results_period{period}.json'
        
        # Mekong Delta shares optimization results with Mekong folder
        if not result_file.exists() and region.lower() == 'mekong delta':
            result_file = self.data_dir / 'Mekong' / f'optimization_results_period{period}.json'
        
        if not result_file.exists():
            return self._generate_sample_results(region, period)
        
        try:
            with open(result_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._generate_sample_results(region, period)
    
    def validate_data(
        self, 
        nodes: pd.DataFrame, 
        edges: pd.DataFrame
    ) -> Dict[str, List[str]]:
        """
        Validate data quality
        
        Args:
            nodes: Node dataframe
            edges: Edge dataframe
            
        Returns:
            Dictionary of warnings and errors
        """
        warnings = []
        errors = []
        
        # Required columns
        required_node_cols = ['node_id']
        required_edge_cols = ['from_node', 'to_node']
        
        for col in required_node_cols:
            if col not in nodes.columns:
                errors.append(f"Missing required column in nodes: {col}")
        
        for col in required_edge_cols:
            if col not in edges.columns:
                errors.append(f"Missing required column in edges: {col}")
        
        # Check for missing values
        if nodes['node_id'].isnull().any():
            errors.append("Null values found in node_id")
        
        if 'lat' in nodes.columns and nodes['lat'].isnull().sum() > 0:
            warnings.append(f"{nodes['lat'].isnull().sum()} nodes missing latitude")
        
        if 'capacity' in edges.columns and edges['capacity'].isnull().sum() > 0:
            warnings.append(f"{edges['capacity'].isnull().sum()} edges missing capacity")
        
        return {
            'errors': errors,
            'warnings': warnings
        }
    
    # ========================================================================
    # SAMPLE DATA GENERATION (for demo when files don't exist)
    # ========================================================================
    
    def _generate_sample_data(self, region: str) -> Dict[str, pd.DataFrame]:
        """Generate sample dataset for demo"""
        import numpy as np
        
        # Generate 15 nodes
        num_nodes = 15
        nodes = pd.DataFrame({
            'node_id': range(1, num_nodes + 1),
            'name': [f'Node_{i}' for i in range(1, num_nodes + 1)],
            'lat': np.random.uniform(10.0, 12.0, num_nodes),
            'lon': np.random.uniform(105.0, 107.0, num_nodes),
            'type': ['hub' if i in [3, 7, 12] else 'normal' 
                    for i in range(1, num_nodes + 1)]
        })
        
        # Generate edges (sparse network)
        edges_data = []
        edge_id = 1
        
        for i in range(1, num_nodes):
            # Connect to next node
            edges_data.append({
                'edge_id': edge_id,
                'from_node': i,
                'to_node': i + 1,
                'mode': 'road' if np.random.random() > 0.4 else 'water',
                'cost': np.random.uniform(100, 500),
                'capacity': np.random.uniform(1000, 5000),
                'distance': np.random.uniform(20, 100)
            })
            edge_id += 1
            
            # Some random connections to create network
            if np.random.random() > 0.6 and i < num_nodes - 2:
                edges_data.append({
                    'edge_id': edge_id,
                    'from_node': i,
                    'to_node': i + 2,
                    'mode': 'water',
                    'cost': np.random.uniform(150, 600),
                    'capacity': np.random.uniform(2000, 8000),
                    'distance': np.random.uniform(40, 150)
                })
                edge_id += 1
        
        edges = pd.DataFrame(edges_data)
        
        # Generate demand
        demand_data = []
        for i in range(1, 6):
            demand_data.append({
                'demand_id': i,
                'origin': np.random.randint(1, num_nodes + 1),
                'destination': np.random.randint(1, num_nodes + 1),
                'commodity': np.random.choice(['Rice', 'Coal', 'Container']),
                'volume': np.random.uniform(100, 1000),
                'period': np.random.randint(1, 5)
            })
        
        demand = pd.DataFrame(demand_data)
        
        return {
            'nodes': nodes,
            'edges': edges,
            'demand': demand
        }
    
    def _generate_sample_results(
        self, 
        region: str, 
        period: int
    ) -> Dict[str, Any]:
        """Generate sample optimization results"""
        import numpy as np
        
        return {
            'region': region,
            'period': period,
            'total_cost': np.random.uniform(50000, 150000),
            'total_time': np.random.uniform(10, 30),
            'num_hubs': 3,
            'efficiency': np.random.uniform(0.75, 0.95),
            'top_routes': [
                {
                    'route_id': 1,
                    'path': [1, 3, 7, 12, 15],
                    'mode': 'multi-modal',
                    'cost': np.random.uniform(5000, 15000),
                    'time': np.random.uniform(3, 8),
                    'commodity': 'Rice'
                },
                {
                    'route_id': 2,
                    'path': [2, 5, 7, 10],
                    'mode': 'water',
                    'cost': np.random.uniform(3000, 10000),
                    'time': np.random.uniform(5, 12),
                    'commodity': 'Coal'
                },
                {
                    'route_id': 3,
                    'path': [4, 7, 12, 14],
                    'mode': 'road',
                    'cost': np.random.uniform(4000, 12000),
                    'time': np.random.uniform(2, 6),
                    'commodity': 'Container'
                }
            ],
            'hub_utilization': {
                3: 0.75,
                7: 0.92,
                12: 0.68
            },
            'modal_split': {
                'road': 0.35,
                'water': 0.65
            }
        }
