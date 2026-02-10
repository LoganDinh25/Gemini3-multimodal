"""
Graph Engine - Network Visualization and Analysis
Handles graph building, visualization, and path highlighting
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Any, Tuple, Optional
import json
import pandas as pd
import numpy as np

try:
    import folium
    _HAS_FOLIUM = True
except ImportError:
    _HAS_FOLIUM = False

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
                project=node.get('project', 'N'),
                label=node.get('name', f"N{node['node_id']}")
            )
        
        # Add edges
        for _, edge in edges.iterrows():
            G.add_edge(
                edge['from_node'],
                edge['to_node'],
                mode=edge.get('mode', 'road'),
                project=edge.get('project', 'E'),
                cost=edge.get('cost', 0),
                capacity=edge.get('capacity', 0),
                distance=edge.get('distance', 0)
            )
        
        self.graph = G
        self.pos = nx.get_node_attributes(G, 'pos')
        
        return G
    
    def _filter_routes_by_commodity(
        self, 
        optimization_results: Dict[str, Any], 
        commodity: Optional[str] = None
    ) -> List[Dict]:
        """Filter top_routes by commodity. Returns filtered list or all if no match."""
        routes = optimization_results.get('top_routes', [])
        if not commodity or not routes:
            return routes[:10]
        c = str(commodity).strip().lower()
        filtered = [r for r in routes if str(r.get('commodity', '')).strip().lower() == c]
        return filtered[:10] if filtered else routes[:10]  # Fallback to all

    def _resolve_node_pos(self, node_id, node_coords_opt: Dict = None) -> Optional[Tuple[float, float]]:
        """Get (lon, lat) for node - from self.pos or node_coords in JSON."""
        if node_id in self.pos:
            return self.pos[node_id]
        if node_coords_opt:
            c = node_coords_opt.get(node_id) or node_coords_opt.get(str(node_id))
            if c and len(c) >= 2:
                x, y = float(c[0]), float(c[1])
                if 8 <= y <= 12 and 103 <= x <= 108:
                    return (x, y)
                if 400000 <= x <= 800000 and 1000000 <= y <= 1300000:
                    try:
                        from coordinate_utils import convert_vn2000_to_wgs84
                        lat, lon = convert_vn2000_to_wgs84(x, y)
                        return (lon, lat)
                    except Exception:
                        return (x, y)
                return (x, y)
        return None

    def _to_wgs84_if_utm(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert VN-2000 to WGS84 if needed, so graph matches map."""
        if 400000 <= lon <= 800000 and 1000000 <= lat <= 1300000:
            try:
                from coordinate_utils import convert_vn2000_to_wgs84
                lat_w, lon_w = convert_vn2000_to_wgs84(lon, lat)
                return (lon_w, lat_w)
            except Exception:
                pass
        return (lon, lat)

    def visualize_network_interactive(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        optimization_results: Dict[str, Any] = None,
        highlight_paths: bool = False,
        commodity: Optional[str] = None
    ) -> go.Figure:
        """
        Create interactive network visualization with Plotly
        Use WGS84 when available to match map; draw optimal route in green.
        """
        G = self.build_graph(nodes, edges)
        node_positions = nx.get_node_attributes(G, 'pos')
        node_coords_opt = (optimization_results or {}).get('node_coords', {})

        valid_positions = {}
        if node_positions:
            for node_id, pos in node_positions.items():
                if pos and pos[0] is not None and pos[1] is not None:
                    lon, lat = float(pos[0]), float(pos[1])
                    lon, lat = self._to_wgs84_if_utm(lon, lat)
                    valid_positions[node_id] = (lon, lat)

        if valid_positions:
            self.pos = valid_positions
        else:
            self.pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        edge_traces = []
        # Edges: mode + project (E=existing bold, P=potential light)
        edge_styles = [
            ('road', 'E', '#78350f', 3),
            ('road', 'P', '#b45309', 1.5),
            ('water', 'E', '#0369a1', 3.5),
            ('water', 'P', '#0ea5e9', 1.5),
            ('waterway', 'E', '#0369a1', 3.5),
            ('waterway', 'P', '#0ea5e9', 1.5),
            ('rail', 'E', '#e11d48', 2.5),
            ('rail', 'P', '#f472b6', 1.5),
            ('air', 'E', '#f59e0b', 2.5),
            ('air', 'P', '#fcd34d', 1.5),
        ]
        for mode, proj, color, w in edge_styles:
            mode_edges = [(u, v) for u, v, d in G.edges(data=True)
                          if d.get('mode') == mode
                          and str(d.get('project', 'E')).upper().strip()[:1] == proj]
            if mode_edges:
                edge_x, edge_y = [], []
                for u, v in mode_edges:
                    if u in self.pos and v in self.pos:
                        x0, y0 = self.pos[u]
                        x1, y1 = self.pos[v]
                        edge_x.extend([x0, x1, None])
                        edge_y.extend([y0, y1, None])
                if edge_x:
                    label = f'{mode.capitalize()} ({proj})' if proj == 'P' else f'{mode.capitalize()}'
                    edge_traces.append(go.Scatter(
                        x=edge_x, y=edge_y,
                        line=dict(width=w, color=color, dash='dot' if proj == 'P' else 'solid'),
                        hoverinfo='none', mode='lines', name=label, showlegend=True
                    ))
        
        # Optimal route in green - dùng node_coords từ JSON nếu thiếu pos
        if highlight_paths and optimization_results:
            top_routes = self._filter_routes_by_commodity(optimization_results, commodity)
            for route in top_routes[:5]:
                path = route.get('path', [])
                if len(path) >= 2:
                    path_x, path_y = [], []
                    for i in range(len(path) - 1):
                        p0 = self._resolve_node_pos(path[i], node_coords_opt)
                        p1 = self._resolve_node_pos(path[i + 1], node_coords_opt)
                        if p0 and p1:
                            path_x.extend([p0[0], p1[0], None])
                            path_y.extend([p0[1], p1[1], None])
                    if path_x and path_y:
                        optimal_trace = go.Scatter(
                            x=path_x, y=path_y,
                            line=dict(width=6, color='#27ae60'),
                            hoverinfo='none',
                            mode='lines',
                            name=f"Optimal ({route.get('commodity', '')})" if commodity else 'Optimal Route',
                            showlegend=(route == top_routes[0])
                        )
                        edge_traces.append(optimal_trace)
        
        # Node traces: Normal | Hub New | Hub Upgrade | Hub Existing
        hub_new = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub' and str(d.get('project', '')).upper().strip() == 'NEW']
        hub_upgrade = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub' and str(d.get('project', '')).upper().strip() == 'UPGRADE']
        hub_existing = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub' and str(d.get('project', '')).upper().strip() == 'E']
        normal_nodes = [n for n, d in G.nodes(data=True) if d.get('type') != 'hub']
        
        node_traces = []
        norm_in_pos = [n for n in normal_nodes if n in self.pos]
        if norm_in_pos:
            node_traces.append(go.Scatter(
                x=[self.pos[n][0] for n in norm_in_pos], y=[self.pos[n][1] for n in norm_in_pos],
                mode='markers+text', text=[G.nodes[n].get('label', str(n)) for n in norm_in_pos],
                textposition="top center", hoverinfo='text',
                marker=dict(size=12, color='#60a5fa', line=dict(width=2, color='#3b82f6')),
                name='Regular Node', showlegend=True
            ))
        for nlist, color, size, label in [
            (hub_new, '#22c55e', 18, 'New Hub'),
            (hub_upgrade, '#a78bfa', 16, 'Upgraded Hub'),
            (hub_existing, '#f97316', 14, 'Existing Hub'),
        ]:
            if nlist:
                nlist = [n for n in nlist if n in self.pos]
                if nlist:
                    node_traces.append(go.Scatter(
                        x=[self.pos[n][0] for n in nlist], y=[self.pos[n][1] for n in nlist],
                        mode='markers+text', text=[G.nodes[n].get('label', str(n)) for n in nlist],
                        textposition="top center", hoverinfo='text',
                        marker=dict(size=size, color=color, line=dict(width=2, color=color), symbol='star'),
                        name=label, showlegend=True
                    ))
        
        fig = go.Figure(data=edge_traces + node_traces)
        
        # Layout matches map khi có tọa độ địa lý
        is_geo = all(
            8 <= p[1] <= 12 and 103 <= p[0] <= 108
            for p in (list(self.pos.values())[:3] if self.pos else [])
        )
        layout_kw = dict(
            title=dict(text='Transport Network', font=dict(size=18, color='#1e293b')),
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20, l=20, r=20, t=50),
            xaxis=dict(showgrid=is_geo, zeroline=False, showticklabels=False, gridcolor='rgba(0,0,0,0.05)'),
            yaxis=dict(showgrid=is_geo, zeroline=False, showticklabels=False, gridcolor='rgba(0,0,0,0.05)'),
            plot_bgcolor='#f8fafc',
            paper_bgcolor='white',
            height=520,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family='Inter', size=12)
        )
        if is_geo:
            layout_kw['xaxis']['range'] = [min(p[0] for p in self.pos.values()) - 0.1, max(p[0] for p in self.pos.values()) + 0.1]
            layout_kw['yaxis']['range'] = [min(p[1] for p in self.pos.values()) - 0.1, max(p[1] for p in self.pos.values()) + 0.1]
        fig.update_layout(**layout_kw)
        
        return fig

    def visualize_network_animated(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        optimization_results: Dict[str, Any],
        commodity: Optional[str] = None,
    ) -> Optional[go.Figure]:
        """
        Plotly figure với animation: optimal route animates from origin to destination
        for each route/OD pair (commodity). Dùng frames + play button.
        """
        if not optimization_results:
            return None
        G = self.build_graph(nodes, edges)
        node_positions = nx.get_node_attributes(G, 'pos')
        node_coords_opt = optimization_results.get('node_coords', {})

        valid_positions = {}
        if node_positions:
            for node_id, pos in node_positions.items():
                if pos and pos[0] is not None and pos[1] is not None:
                    lon, lat = float(pos[0]), float(pos[1])
                    lon, lat = self._to_wgs84_if_utm(lon, lat)
                    valid_positions[node_id] = (lon, lat)
        if valid_positions:
            self.pos = valid_positions
        else:
            self.pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

        edge_traces = []
        edge_styles = [
            ('road', 'E', '#78350f', 3), ('road', 'P', '#b45309', 1.5),
            ('water', 'E', '#0369a1', 3.5), ('water', 'P', '#0ea5e9', 1.5),
            ('waterway', 'E', '#0369a1', 3.5), ('waterway', 'P', '#0ea5e9', 1.5),
            ('rail', 'E', '#e11d48', 2.5), ('rail', 'P', '#f472b6', 1.5),
            ('air', 'E', '#f59e0b', 2.5), ('air', 'P', '#fcd34d', 1.5),
        ]
        for mode, proj, color, w in edge_styles:
            mode_edges = [(u, v) for u, v, d in G.edges(data=True)
                          if d.get('mode') == mode
                          and str(d.get('project', 'E')).upper().strip()[:1] == proj]
            if mode_edges:
                edge_x, edge_y = [], []
                for u, v in mode_edges:
                    if u in self.pos and v in self.pos:
                        x0, y0 = self.pos[u]
                        x1, y1 = self.pos[v]
                        edge_x.extend([x0, x1, None])
                        edge_y.extend([y0, y1, None])
                if edge_x:
                    label = f'{mode.capitalize()} ({proj})' if proj == 'P' else f'{mode.capitalize()}'
                    edge_traces.append(go.Scatter(
                        x=edge_x, y=edge_y,
                        line=dict(width=w, color=color, dash='dot' if proj == 'P' else 'solid'),
                        hoverinfo='none', mode='lines', name=label, showlegend=True
                    ))

        top_routes = self._filter_routes_by_commodity(optimization_results, commodity)
        path_coords_list = []
        path_labels = []
        for route in top_routes[:8]:
            path = route.get('path', [])
            coords = []
            for nid in path:
                p = self._resolve_node_pos(nid, node_coords_opt)
                if p:
                    coords.append([p[0], p[1]])
            if len(coords) >= 2:
                path_coords_list.append(coords)
                lbl = str(route.get('commodity', '') or '')
                if not lbl and (route.get('origin') or route.get('destination')):
                    lbl = f"{route.get('origin', '')}→{route.get('destination', '')}"
                path_labels.append(lbl or f"Route {len(path_coords_list)+1}")

        if not path_coords_list:
            return None

        hub_new = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub' and str(d.get('project', '')).upper().strip() == 'NEW']
        hub_upgrade = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub' and str(d.get('project', '')).upper().strip() == 'UPGRADE']
        hub_existing = [n for n, d in G.nodes(data=True) if d.get('type') == 'hub' and str(d.get('project', '')).upper().strip() == 'E']
        normal_nodes = [n for n, d in G.nodes(data=True) if d.get('type') != 'hub']
        node_traces = []
        norm_in_pos = [n for n in normal_nodes if n in self.pos]
        if norm_in_pos:
            node_traces.append(go.Scatter(
                x=[self.pos[n][0] for n in norm_in_pos], y=[self.pos[n][1] for n in norm_in_pos],
                mode='markers+text', text=[G.nodes[n].get('label', str(n)) for n in norm_in_pos],
                textposition="top center", hoverinfo='text',
                marker=dict(size=12, color='#60a5fa', line=dict(width=2, color='#3b82f6')),
                name='Regular Node', showlegend=True
            ))
        for nlist, color, size, label in [
            (hub_new, '#22c55e', 18, 'New Hub'),
            (hub_upgrade, '#a78bfa', 16, 'Upgraded Hub'),
            (hub_existing, '#f97316', 14, 'Existing Hub'),
        ]:
            if nlist:
                nlist = [n for n in nlist if n in self.pos]
                if nlist:
                    node_traces.append(go.Scatter(
                        x=[self.pos[n][0] for n in nlist], y=[self.pos[n][1] for n in nlist],
                        mode='markers+text', text=[G.nodes[n].get('label', str(n)) for n in nlist],
                        textposition="top center", hoverinfo='text',
                        marker=dict(size=size, color=color, line=dict(width=2, color=color), symbol='star'),
                        name=label, showlegend=True
                    ))

        max_len = max(len(p) for p in path_coords_list)
        n_frames = max(1, max_len - 1)

        def make_route_traces_for_frame(frame_idx: int):
            out = []
            for i, coords in enumerate(path_coords_list):
                n_show = min(frame_idx + 2, len(coords))
                if n_show < 2:
                    xs, ys = [coords[0][0]], [coords[0][1]]
                else:
                    xs = [c[0] for c in coords[:n_show]]
                    ys = [c[1] for c in coords[:n_show]]
                out.append(go.Scatter(
                    x=xs, y=ys,
                    line=dict(width=6, color='#27ae60'),
                    mode='lines',
                    name=path_labels[i] if i < len(path_labels) else f'Route {i+1}',
                    showlegend=True,
                    legendgroup='optimal',
                ))
            return out

        base_data = list(edge_traces) + list(node_traces) + make_route_traces_for_frame(0)
        fig = go.Figure(data=base_data)
        frames = []
        for f in range(n_frames):
            frame_data = list(edge_traces) + list(node_traces) + make_route_traces_for_frame(f)
            frames.append(go.Frame(data=frame_data, name=str(f)))

        fig.frames = frames
        is_geo = all(
            8 <= p[1] <= 12 and 103 <= p[0] <= 108
            for p in (list(self.pos.values())[:3] if self.pos else [])
        )
        layout_kw = dict(
            title=dict(text='Animated route per OD pair (commodity)', font=dict(size=18, color='#1e293b')),
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20, l=20, r=20, t=50),
            xaxis=dict(showgrid=is_geo, zeroline=False, showticklabels=False, gridcolor='rgba(0,0,0,0.05)'),
            yaxis=dict(showgrid=is_geo, zeroline=False, showticklabels=False, gridcolor='rgba(0,0,0,0.05)'),
            plot_bgcolor='#f8fafc',
            paper_bgcolor='white',
            height=520,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family='Inter', size=12),
            updatemenus=[dict(
                type='buttons',
                showactive=False,
                buttons=[
                    dict(label='▶ Play', method='animate', args=[None, dict(frame=dict(duration=120, redraw=True), fromcurrent=True, mode='immediate')]),
                    dict(label='⏸ Pause', method='animate', args=[[None], dict(mode='immediate')]),
                ],
                x=0.1, xanchor='left', y=0, yanchor='top',
            )],
            sliders=[dict(
                active=0,
                steps=[dict(args=[[frames[k].name], dict(mode='immediate', frame=dict(duration=0))], label=str(k)) for k in range(len(frames))],
                x=0.1, len=0.8, xanchor='left', y=0, yanchor='top', pad=dict(t=40),
            )],
        )
        if is_geo:
            layout_kw['xaxis']['range'] = [min(p[0] for p in self.pos.values()) - 0.1, max(p[0] for p in self.pos.values()) + 0.1]
            layout_kw['yaxis']['range'] = [min(p[1] for p in self.pos.values()) - 0.1, max(p[1] for p in self.pos.values()) + 0.1]
        fig.update_layout(**layout_kw)
        return fig

    def visualize_network(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        optimization_results: Dict[str, Any] = None,
        highlight_paths: bool = False,
        commodity: Optional[str] = None,
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
            edge_color='#78350f',
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
        
        # Highlight optimal paths if requested (filter by commodity)
        if highlight_paths and optimization_results:
            self._highlight_optimal_paths(G, optimization_results, ax, commodity=commodity)
        
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
            mpatches.Patch(color='#78350f', label='Road Transport'),
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
        ax: plt.Axes,
        commodity: Optional[str] = None
    ):
        """
        Highlight optimal paths from optimization results
        
        Args:
            G: NetworkX graph
            optimization_results: Optimization output
            ax: Matplotlib axes
            commodity: Filter routes by commodity
        """
        top_routes = self._filter_routes_by_commodity(optimization_results, commodity)
        
        for route in top_routes[:5]:  # Top 5 routes (filtered by commodity)
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

    def visualize_network_map(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        optimization_results: Optional[Dict[str, Any]] = None,
        highlight_paths: bool = False,
        commodity: Optional[str] = None,
        center_lat: Optional[float] = None,
        center_lon: Optional[float] = None,
        zoom_start: int = 8,
        use_osm_tiles: bool = True
    ):
        """
        Render logistics network on Folium map.
        use_osm_tiles=True: OpenStreetMap. use_osm_tiles=False: CartoDB Positron (light background, like graph).
        """
        if not _HAS_FOLIUM:
            return None
        if nodes is None or nodes.empty:
            return None
        if edges is None:
            edges = pd.DataFrame()
        nodes = pd.DataFrame(nodes) if not isinstance(nodes, pd.DataFrame) else nodes
        edges = pd.DataFrame(edges) if not isinstance(edges, pd.DataFrame) else edges
        for col in ['lat', 'lon']:
            if col not in nodes.columns:
                return None
        nodes = nodes.copy()
        nodes['lat'] = pd.to_numeric(nodes['lat'], errors='coerce')
        nodes['lon'] = pd.to_numeric(nodes['lon'], errors='coerce')
        valid_nodes = nodes.dropna(subset=['lat', 'lon'])
        if valid_nodes.empty:
            return None
        valid_nodes = valid_nodes[
            (valid_nodes['lat'].between(8, 12)) &
            (valid_nodes['lon'].between(103, 108))
        ]
        if valid_nodes.empty:
            raw = nodes.dropna(subset=['lat', 'lon'])
            if raw.empty:
                return None
            try:
                from coordinate_utils import convert_vn2000_to_wgs84
                lats, lons = [], []
                for _, row in raw.iterrows():
                    x, y = float(row['lon']), float(row['lat'])
                    if 400000 <= x <= 800000 and 1000000 <= y <= 1300000:
                        lat, lon = convert_vn2000_to_wgs84(x, y)
                        lats.append(lat); lons.append(lon)
                    else:
                        lats.append(y); lons.append(x)
                if len(lats) == len(raw):
                    valid_nodes = raw.copy()
                    valid_nodes['lat'] = lats
                    valid_nodes['lon'] = lons
                else:
                    valid_nodes = raw
            except Exception:
                valid_nodes = raw
            # If conversion failed, lat/lon may still be VN2000; Folium needs WGS84
            if not valid_nodes.empty:
                lat_vals = pd.to_numeric(valid_nodes['lat'], errors='coerce')
                lon_vals = pd.to_numeric(valid_nodes['lon'], errors='coerce')
                if (lat_vals.max() > 90 or lat_vals.min() < -90 or
                        lon_vals.max() > 180 or lon_vals.min() < -180):
                    return None

        if center_lat is None:
            center_lat = valid_nodes['lat'].mean()
        if center_lon is None:
            center_lon = valid_nodes['lon'].mean()
        
        # OSM = actual map; tiles=None = no map, white bg
        if use_osm_tiles:
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=zoom_start,
                tiles='OpenStreetMap',
                control_scale=True
            )
        else:
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=zoom_start,
                tiles=None,
                control_scale=True
            )
            # White bg when no map
            m.get_root().html.add_child(folium.Element("""
            <style>
                .leaflet-container { background: #f8fafc !important; }
            </style>
            """))
        
        # Build node lookup
        node_lookup = valid_nodes.set_index('node_id')
        
        # Edges: mode + project (P=potential, E=existing)
        mode_styles = {
            ('road', 'E'): {'color': '#78350f', 'weight': 3, 'dash_array': '0'},
            ('road', 'P'): {'color': '#b45309', 'weight': 2, 'dash_array': '5, 5'},
            ('water', 'E'): {'color': '#0369a1', 'weight': 4, 'dash_array': '0'},
            ('water', 'P'): {'color': '#0ea5e9', 'weight': 2, 'dash_array': '8, 8'},
            ('waterway', 'E'): {'color': '#0369a1', 'weight': 4, 'dash_array': '0'},
            ('waterway', 'P'): {'color': '#0ea5e9', 'weight': 2, 'dash_array': '8, 8'},
        }
        def edge_style(mode, proj):
            p = str(proj).upper()[:1] if proj else 'E'
            return mode_styles.get((mode, p)) or mode_styles.get((mode, 'E')) or {'color': '#64748b', 'weight': 2, 'dash_array': '0'}
        
        optimal_edges = set()
        optimal_path_coords = []
        optimal_paths_for_animation = []  # [{coords: [[lat,lon],...], label: commodity}, ...]
        if highlight_paths and optimization_results:
            top_routes = self._filter_routes_by_commodity(optimization_results, commodity)
            node_coords_opt = optimization_results.get('node_coords') or {}
            for route in top_routes[:5]:
                path = route.get('path', [])
                for i in range(len(path) - 1):
                    optimal_edges.add((path[i], path[i + 1]))
                path_coords = []
                for nid in path:
                    if nid in node_lookup.index:
                        r = node_lookup.loc[nid]
                        path_coords.append([r['lat'], r['lon']])
                    else:
                        c = node_coords_opt.get(nid) or node_coords_opt.get(str(nid))
                        if c and len(c) >= 2:
                            x, y = float(c[0]), float(c[1])
                            if 400000 <= x <= 800000 and 1000000 <= y <= 1300000:
                                try:
                                    from coordinate_utils import convert_vn2000_to_wgs84
                                    lat, lon = convert_vn2000_to_wgs84(x, y)
                                    path_coords.append([lat, lon])
                                except Exception:
                                    path_coords.append([y, x])
                            elif 8 <= y <= 12 and 103 <= x <= 108:
                                path_coords.append([y, x])
                if len(path_coords) >= 2:
                    optimal_path_coords.append(path_coords)
                    optimal_paths_for_animation.append({
                        'coords': path_coords,
                        'label': str(route.get('commodity', '') or 'Optimal')
                    })
        
        for _, edge in edges.iterrows():
            u, v = edge['from_node'], edge['to_node']
            mode = str(edge.get('mode', 'road')).lower()
            proj = edge.get('project', 'E')
            style = edge_style(mode, proj)
            
            if u not in node_lookup.index or v not in node_lookup.index:
                continue
            
            pu = node_lookup.loc[u]
            pv = node_lookup.loc[v]
            coords = [[pu['lat'], pu['lon']], [pv['lat'], pv['lon']]]
            
            if (u, v) in optimal_edges or (v, u) in optimal_edges:
                folium.PolyLine(
                    coords,
                    color='#27ae60',
                    weight=5,
                    opacity=0.9,
                    popup=f'Optimal route: {u} → {v}'
                ).add_to(m)
            else:
                folium.PolyLine(
                    coords,
                    color=style['color'],
                    weight=style['weight'],
                    dash_array=style.get('dash_array', '0'),
                    opacity=0.6,
                    popup=f'{mode} | {u} → {v}'
                ).add_to(m)
        
        for path_coords in optimal_path_coords:
            folium.PolyLine(
                path_coords,
                color='#27ae60',
                weight=5,
                opacity=0.9,
                popup='Optimal route'
            ).add_to(m)

        # Animation ngay trên bản đồ OSM: green route, pin icon Leaflet (marker-icon-2x) each route one color
        if optimal_paths_for_animation and hasattr(folium, 'plugins'):
            try:
                # Same Leaflet pin style, nhiều màu (leaflet-color-markers)
                marker_colors = ["blue", "red", "green", "orange", "violet", "gold", "yellow", "grey"]
                base_url = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img"
                shadow_url = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png"
                features = []
                for idx, p in enumerate(optimal_paths_for_animation):
                    coords = p['coords']
                    if len(coords) < 2:
                        continue
                    color_name = marker_colors[idx % len(marker_colors)]
                    icon_url = f"{base_url}/marker-icon-2x-{color_name}.png"
                    # [lat, lon] -> [lon, lat] cho GeoJSON
                    coords_geojson = [[float(c[1]), float(c[0])] for c in coords]
                    times = [f"2020-01-01T00:00:{i:02d}" for i in range(len(coords))]
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords_geojson},
                        "properties": {
                            "times": times,
                            "style": {"color": "#27ae60", "weight": 6},
                            "popup": p.get('label', 'Optimal route'),
                            "icon": "marker",
                            "iconstyle": {
                                "iconUrl": icon_url,
                                "iconSize": [25, 41],
                                "iconAnchor": [12, 41],
                                "popupAnchor": [1, -34],
                                "shadowUrl": shadow_url,
                                "shadowSize": [41, 41],
                            },
                        },
                    })
                if features:
                    geojson = {"type": "FeatureCollection", "features": features}
                    # duration: drawn route stays visible (does not disappear); period: time step
                    folium.plugins.TimestampedGeoJson(
                        geojson,
                        period="PT1S",
                        duration="PT99S",
                        add_last_point=True,
                        auto_play=False,
                        loop=False,
                        max_speed=2,
                        loop_button=True,
                        time_slider_drag_update=True,
                    ).add_to(m)
            except Exception:
                pass

        # Draw nodes: Normal | Hub Existing (E) | Hub New | Hub Upgrade
        project_col = 'project' if 'project' in valid_nodes.columns else None
        hub_new, hub_upgrade, hub_existing = set(), set(), set()
        if project_col:
            proj_str = valid_nodes[project_col].astype(str).str.upper().str.strip()
            hub_new = set(valid_nodes[proj_str == 'NEW']['node_id'])
            hub_upgrade = set(valid_nodes[proj_str == 'UPGRADE']['node_id'])
            hub_existing = set(valid_nodes[(valid_nodes['type'] == 'hub') & (proj_str == 'E')]['node_id'])
        else:
            hub_existing = set(valid_nodes[valid_nodes['type'] == 'hub']['node_id']) if 'type' in valid_nodes.columns else set()
        
        for _, node in valid_nodes.iterrows():
            nid = node['node_id']
            lat, lon = node['lat'], node['lon']
            name = node.get('name', f'Node {nid}')
            
            if nid in hub_new:
                color, fill_color, radius = '#16a34a', '#22c55e', 10  # Dark green
                node_type = 'New Hub'
            elif nid in hub_upgrade:
                color, fill_color, radius = '#7c3aed', '#a78bfa', 9   # Tím
                node_type = 'Upgraded Hub'
            elif nid in hub_existing:
                color, fill_color, radius = '#ea580c', '#f97316', 7   # Cam
                node_type = 'Existing Hub'
            else:
                color, fill_color, radius = '#3b82f6', '#60a5fa', 5   # Xanh dương
                node_type = 'Regular Node'
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                popup=f'<b>{name}</b><br>ID: {nid}<br>{node_type}',
                color=color,
                fill=True,
                fillColor=fill_color,
                fillOpacity=0.85,
                weight=2
            ).add_to(m)
        
        return m
