"""
Graph Engine - Network Visualization and Analysis
Handles graph building, visualization, and path highlighting
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Any, Tuple
import pandas as pd
import numpy as np

class GraphEngine:
    def __init__(self):
        """Initialize graph engine"""
        self.graph = None
        self.pos = None
        
    def build_graph(
        self, 
        nodes: pd.DataFrame, 
        edges: pd.DataFrame
    ) -> nx.DiGraph:
        """
        Build NetworkX directed graph from nodes and edges
        
        Args:
            nodes: DataFrame with columns: node_id, lat, lon, type
            edges: DataFrame with columns: from_node, to_node, mode, cost, capacity
            
        Returns:
            NetworkX directed graph
        """
        G = nx.DiGraph()
        
        # Add nodes
        for _, node in nodes.iterrows():
            G.add_node(
                node['node_id'],
                pos=(node.get('lon', 0), node.get('lat', 0)),
                type=node.get('type', 'normal'),
                label=node.get('name', f"N{node['node_id']}")
            )
        
        # Add edges
        for _, edge in edges.iterrows():
            G.add_edge(
                edge['from_node'],
                edge['to_node'],
                mode=edge.get('mode', 'road'),
                cost=edge.get('cost', 0),
                capacity=edge.get('capacity', 0),
                distance=edge.get('distance', 0)
            )
        
        self.graph = G
        self.pos = nx.get_node_attributes(G, 'pos')
        
        return G
    
    def visualize_network_interactive(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        optimization_results: Dict[str, Any] = None,
        highlight_paths: bool = False
    ) -> go.Figure:
        """
        Create interactive network visualization with Plotly
        
        Args:
            nodes: Node dataframe
            edges: Edge dataframe
            optimization_results: Results to highlight
            highlight_paths: Whether to highlight optimal paths
            
        Returns:
            Plotly figure
        """
        # Build graph
        G = self.build_graph(nodes, edges)
        
        # Get positions - use actual coordinates if available, otherwise use spring layout
        node_positions = nx.get_node_attributes(G, 'pos')
        
        # Check if we have valid coordinates (not all zeros or None)
        has_valid_coords = False
        if node_positions:
            # Check if coordinates are valid (not None, not (0,0), and reasonable range)
            valid_positions = {}
            for node_id, pos in node_positions.items():
                if pos and pos[0] is not None and pos[1] is not None:
                    # Check if coordinates are in reasonable range (not UTM which is 6-7 digits)
                    # For Mekong, coordinates are UTM (x: 500k-700k, y: 1M-1.2M)
                    # We'll use them as-is for visualization
                    if abs(pos[0]) > 1 and abs(pos[1]) > 1:  # Not (0,0) or very small
                        valid_positions[node_id] = pos
                        has_valid_coords = True
            
            if has_valid_coords:
                self.pos = valid_positions
            else:
                self.pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        else:
            self.pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        # Create edge traces
        edge_traces = []
        
        # Group edges by mode
        mode_colors = {
            'road': '#95a5a6',
            'water': '#3498db',
            'rail': '#e74c3c',
            'air': '#f39c12'
        }
        
        for mode, color in mode_colors.items():
            mode_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('mode') == mode]
            
            if mode_edges:
                edge_x = []
                edge_y = []
                
                for u, v in mode_edges:
                    x0, y0 = self.pos[u]
                    x1, y1 = self.pos[v]
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])
                
                edge_trace = go.Scatter(
                    x=edge_x, y=edge_y,
                    line=dict(width=2, color=color),
                    hoverinfo='none',
                    mode='lines',
                    name=f'{mode.capitalize()} Routes',
                    showlegend=True
                )
                edge_traces.append(edge_trace)
        
        # Highlight optimal paths if requested
        if highlight_paths and optimization_results:
            top_routes = optimization_results.get('top_routes', [])
            for route in top_routes[:3]:
                path = route.get('path', [])
                if len(path) >= 2:
                    path_x = []
                    path_y = []
                    for i in range(len(path) - 1):
                        if path[i] in self.pos and path[i+1] in self.pos:
                            x0, y0 = self.pos[path[i]]
                            x1, y1 = self.pos[path[i+1]]
                            path_x.extend([x0, x1, None])
                            path_y.extend([y0, y1, None])
                    
                    optimal_trace = go.Scatter(
                        x=path_x, y=path_y,
                        line=dict(width=4, color='#27ae60'),
                        hoverinfo='none',
                        mode='lines',
                        name='Optimal Route',
                        showlegend=(route == top_routes[0])  # Only show once in legend
                    )
                    edge_traces.append(optimal_trace)
        
        # Create node traces
        hub_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub']
        normal_nodes = [n for n, d in G.nodes(data=True) if d.get('type') != 'hub']
        
        # Normal nodes
        normal_x = [self.pos[n][0] for n in normal_nodes if n in self.pos]
        normal_y = [self.pos[n][1] for n in normal_nodes if n in self.pos]
        normal_text = [G.nodes[n].get('label', str(n)) for n in normal_nodes]
        
        normal_trace = go.Scatter(
            x=normal_x, y=normal_y,
            mode='markers+text',
            hoverinfo='text',
            text=normal_text,
            textposition="top center",
            marker=dict(
                size=15,
                color='#ecf0f1',
                line=dict(width=2, color='#34495e')
            ),
            name='Normal Nodes',
            showlegend=True
        )
        
        # Hub nodes
        hub_x = [self.pos[n][0] for n in hub_nodes if n in self.pos]
        hub_y = [self.pos[n][1] for n in hub_nodes if n in self.pos]
        hub_text = [G.nodes[n].get('label', str(n)) for n in hub_nodes]
        
        hub_trace = go.Scatter(
            x=hub_x, y=hub_y,
            mode='markers+text',
            hoverinfo='text',
            text=hub_text,
            textposition="top center",
            marker=dict(
                size=25,
                color='#f39c12',
                line=dict(width=3, color='#d68910'),
                symbol='star'
            ),
            name='Hub Nodes',
            showlegend=True
        )
        
        # Create figure
        fig = go.Figure(data=edge_traces + [normal_trace, hub_trace])
        
        # Update layout
        fig.update_layout(
            title=dict(
                text='Logistics Network Graph',
                font=dict(size=20, color='#2c3e50', family='Inter')
            ),
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='white',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    
    def visualize_network(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        optimization_results: Dict[str, Any] = None,
        highlight_paths: bool = False,
        figsize: Tuple[int, int] = (12, 8)
    ) -> plt.Figure:
        """
        Visualize logistics network with optional optimization overlay
        
        Args:
            nodes: Node dataframe
            edges: Edge dataframe
            optimization_results: Results to highlight
            highlight_paths: Whether to highlight optimal paths
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        # Build graph
        G = self.build_graph(nodes, edges)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize, facecolor='white')
        
        # Get positions
        if not self.pos or len(self.pos) != G.number_of_nodes():
            # Fallback to spring layout if positions missing
            self.pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Separate nodes by type
        hub_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub']
        normal_nodes = [n for n, d in G.nodes(data=True) if d.get('type') != 'hub']
        
        # Separate edges by mode
        road_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('mode') == 'road']
        water_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('mode') == 'water']
        other_edges = [(u, v) for u, v, d in G.edges(data=True) 
                       if d.get('mode') not in ['road', 'water']]
        
        # Draw edges by mode
        nx.draw_networkx_edges(
            G, self.pos, 
            edgelist=road_edges,
            edge_color='#95a5a6',
            width=1.5,
            alpha=0.6,
            arrows=True,
            arrowsize=15,
            ax=ax
        )
        
        nx.draw_networkx_edges(
            G, self.pos,
            edgelist=water_edges,
            edge_color='#3498db',
            width=2.0,
            alpha=0.6,
            arrows=True,
            arrowsize=15,
            style='--',
            ax=ax
        )
        
        if other_edges:
            nx.draw_networkx_edges(
                G, self.pos,
                edgelist=other_edges,
                edge_color='#e74c3c',
                width=1.5,
                alpha=0.6,
                arrows=True,
                arrowsize=15,
                ax=ax
            )
        
        # Highlight optimal paths if requested
        if highlight_paths and optimization_results:
            self._highlight_optimal_paths(G, optimization_results, ax)
        
        # Draw nodes
        nx.draw_networkx_nodes(
            G, self.pos,
            nodelist=normal_nodes,
            node_color='#ecf0f1',
            node_size=300,
            edgecolors='#34495e',
            linewidths=2,
            ax=ax
        )
        
        nx.draw_networkx_nodes(
            G, self.pos,
            nodelist=hub_nodes,
            node_color='#f39c12',
            node_size=600,
            edgecolors='#d68910',
            linewidths=3,
            ax=ax
        )
        
        # Draw labels
        labels = nx.get_node_attributes(G, 'label')
        if not labels:
            labels = {n: str(n) for n in G.nodes()}
            
        nx.draw_networkx_labels(
            G, self.pos,
            labels=labels,
            font_size=9,
            font_weight='bold',
            font_color='#2c3e50',
            ax=ax
        )
        
        # Add legend
        legend_elements = [
            mpatches.Patch(color='#f39c12', label='Hub Node'),
            mpatches.Patch(color='#ecf0f1', label='Normal Node'),
            mpatches.Patch(color='#95a5a6', label='Road Transport'),
            mpatches.Patch(color='#3498db', label='Water Transport')
        ]
        
        if highlight_paths:
            legend_elements.append(
                mpatches.Patch(color='#27ae60', label='Optimal Path')
            )
        
        ax.legend(
            handles=legend_elements,
            loc='upper right',
            fontsize=10,
            framealpha=0.9
        )
        
        ax.set_title(
            'Logistics Network Graph',
            fontsize=16,
            fontweight='bold',
            pad=20
        )
        ax.axis('off')
        
        plt.tight_layout()
        return fig
    
    def _highlight_optimal_paths(
        self,
        G: nx.DiGraph,
        optimization_results: Dict[str, Any],
        ax: plt.Axes
    ):
        """
        Highlight optimal paths from optimization results
        
        Args:
            G: NetworkX graph
            optimization_results: Optimization output
            ax: Matplotlib axes
        """
        top_routes = optimization_results.get('top_routes', [])
        
        for route in top_routes[:3]:  # Top 3 routes
            path = route.get('path', [])
            
            if len(path) < 2:
                continue
            
            # Convert path to edges
            path_edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
            
            # Draw highlighted path
            nx.draw_networkx_edges(
                G, self.pos,
                edgelist=path_edges,
                edge_color='#27ae60',
                width=3.5,
                alpha=0.8,
                arrows=True,
                arrowsize=20,
                ax=ax
            )
    
    def calculate_graph_metrics(self, G: nx.DiGraph = None) -> Dict[str, Any]:
        """
        Calculate key graph metrics
        
        Args:
            G: NetworkX graph (uses self.graph if None)
            
        Returns:
            Dictionary of metrics
        """
        if G is None:
            G = self.graph
            
        if G is None or G.number_of_nodes() == 0:
            return {}
        
        metrics = {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'density': nx.density(G),
            'is_connected': nx.is_weakly_connected(G)
        }
        
        # Centrality metrics (for hub identification)
        try:
            degree_centrality = nx.degree_centrality(G)
            metrics['top_centrality_nodes'] = sorted(
                degree_centrality.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
        except:
            pass
        
        # Average path length (if connected)
        if metrics['is_connected']:
            try:
                metrics['avg_shortest_path'] = nx.average_shortest_path_length(G)
            except:
                pass
        
        return metrics
    
    def find_paths(
        self,
        source: int,
        target: int,
        k: int = 3,
        weight: str = 'cost'
    ) -> List[List[int]]:
        """
        Find k shortest paths between source and target
        
        Args:
            source: Source node
            target: Target node
            k: Number of paths
            weight: Edge attribute to minimize
            
        Returns:
            List of paths
        """
        if self.graph is None:
            return []
        
        try:
            paths = list(nx.shortest_simple_paths(
                self.graph, 
                source, 
                target, 
                weight=weight
            ))
            return paths[:k]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
    
    def analyze_bottlenecks(
        self,
        flow_data: Dict[Tuple[int, int], float]
    ) -> List[Dict[str, Any]]:
        """
        Identify bottleneck edges based on flow vs capacity
        
        Args:
            flow_data: Dictionary mapping (from, to) to flow volume
            
        Returns:
            List of bottleneck edges with utilization
        """
        if self.graph is None:
            return []
        
        bottlenecks = []
        
        for (u, v), flow in flow_data.items():
            if self.graph.has_edge(u, v):
                capacity = self.graph[u][v].get('capacity', float('inf'))
                
                if capacity > 0:
                    utilization = flow / capacity
                    
                    if utilization > 0.8:  # 80% threshold
                        bottlenecks.append({
                            'edge': (u, v),
                            'flow': flow,
                            'capacity': capacity,
                            'utilization': utilization,
                            'mode': self.graph[u][v].get('mode', 'unknown')
                        })
        
        # Sort by utilization
        bottlenecks.sort(key=lambda x: x['utilization'], reverse=True)
        
        return bottlenecks
