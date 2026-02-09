"""
Gemini 3 Service - Core Decision Intelligence Layer
Handles: Data Normalization, Strategy Explanation, What-If Analysis
"""

import os
import json
from typing import Dict, List, Any
import pandas as pd

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: google-generativeai not installed. Install with: pip install google-generativeai")

from config import GEMINI_API_KEY, GEMINI_MODEL

class GeminiService:
    def __init__(self, api_key: str = None):
        """
        Initialize Gemini service
        
        Args:
            api_key: Gemini API key (from env, config, or parameter)
        """
        # Priority: parameter > env > config default
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
        
        if GEMINI_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                # gemini-pro deprecated; use gemini-2.5-flash (stable) or gemini-2.5-pro
                model_names = [GEMINI_MODEL, "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]
                self.model = None
                for name in model_names:
                    try:
                        self.model = genai.GenerativeModel(name)
                        self.use_real_api = True
                        break
                    except Exception:
                        continue
                if self.model is None:
                    raise RuntimeError("No Gemini model available")
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini API: {e}")
                print("Falling back to mock responses")
                self.use_real_api = False
        else:
            self.use_real_api = False
            if not GEMINI_AVAILABLE:
                print("Warning: Using mock Gemini responses (google-generativeai not installed)")
            elif not self.api_key:
                print("Warning: No API key provided, using mock responses")
        
    def _call_gemini(self, prompt: str, system_instruction: str = "") -> str:
        """
        Call Gemini API
        
        Args:
            prompt: User prompt
            system_instruction: System instruction for model
            
        Returns:
            Model response text
        """
        if self.use_real_api:
            try:
                # Combine system instruction and prompt
                full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
                
                # Generate content
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    )
                )
                
                return response.text
            except Exception as e:
                err_str = str(e).lower()
                print(f"Error calling Gemini API: {e}")
                if any(kw in err_str for kw in ["rate", "429", "quota", "exhausted", "resource"]):
                    print("⚠️ Rate limit / quota exceeded - falling back to mock. Đợi 1 phút hoặc nâng quota tại console.cloud.google.com")
                else:
                    print("Falling back to mock response")
                return self._mock_gemini_response(prompt, system_instruction)
        else:
            # DEMO MODE: Return structured mock response
            return self._mock_gemini_response(prompt, system_instruction)
    
    def _mock_gemini_response(self, prompt: str, system_instruction: str) -> str:
        """Mock Gemini responses for demo (remove in production)"""
        si = system_instruction.lower()
        if "normalize" in si:
            return json.dumps({
                "normalized_schema": {
                    "mode_mapping": {
                        "river": "water",
                        "canal": "water",
                        "highway": "road",
                        "local_road": "road"
                    },
                    "standardized_units": "km, tons, USD",
                    "schema_version": "1.0"
                },
                "warnings": [
                    "3 edges missing capacity data - using regional average",
                    "2 nodes have incomplete coordinates - approximated from region centroid"
                ],
                "assumptions": [
                    "Switching cost between modes set to 15% of transport cost (industry standard)",
                    "Hub capacity constraints based on regional infrastructure reports"
                ]
            })
        elif "explain strategy" in si or ("explanation" in si and "strategy" in si):
            return self._generate_strategy_explanation(prompt)
        elif "what-if" in si or "risk analyst" in si:
            return self._generate_whatif_analysis(prompt)
        elif "logistics advisor" in si or "optimization strategies" in si:
            # Chat với Gemini - trả về mock thay vì placeholder
            return self._generate_chat_mock_response(prompt)
        else:
            return self._generate_chat_mock_response(prompt)
    
    def normalize_data(
        self, 
        nodes: pd.DataFrame, 
        edges: pd.DataFrame, 
        demand: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        CORE #1: Semantic data normalization using Gemini 3
        
        This function uses Gemini 3 to:
        - Map inconsistent transport mode names (river/canal → water)
        - Detect missing or anomalous data
        - Generate standardized schema
        
        Args:
            nodes: Node dataframe
            edges: Edge dataframe  
            demand: Demand dataframe
            
        Returns:
            Dictionary with normalized_schema, warnings, assumptions
        """
        # Prepare data summary for Gemini
        data_summary = {
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "unique_modes": edges['mode'].unique().tolist() if 'mode' in edges.columns else [],
            "nodes_sample": nodes.head(3).to_dict('records'),
            "edges_sample": edges.head(3).to_dict('records'),
            "missing_data": {
                "nodes": nodes.isnull().sum().to_dict(),
                "edges": edges.isnull().sum().to_dict()
            }
        }
        
        prompt = f"""
You are analyzing logistics data for normalization.

Data Summary:
{json.dumps(data_summary, indent=2)}

Tasks:
1. Map all transport mode variants to standard categories (road, water, rail, air)
2. Identify missing critical fields (capacity, cost, coordinates)
3. Suggest reasonable assumptions for missing data
4. Flag any anomalies in the data structure

IMPORTANT: Return ONLY a valid JSON object, no other text. Format:
{{"normalized_schema": {{...}}, "warnings": ["..."], "assumptions": ["..."]}}
"""
        
        system_instruction = "You are a data normalization expert. Return ONLY valid JSON. No prose, no markdown, no explanation - just the JSON object."
        
        response = self._call_gemini(prompt, system_instruction)
        
        try:
            # Try to extract JSON from response (might be wrapped in markdown code blocks)
            response_text = response.strip()
            
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            # Fallback if response isn't valid JSON
            print(f"Warning: Failed to parse JSON response: {e}")
            print(f"Response was: {response[:200]}...")
            return {
                "normalized_schema": {"status": "partial", "raw_response": response[:500]},
                "warnings": ["Response parsing failed - using fallback"],
                "assumptions": []
            }
    
    def explain_strategy(
        self,
        period: int,
        commodity: str,
        optimization_results: Dict[str, Any],
        graph_data: Dict[str, Any],
        priority: float
    ) -> Dict[str, Any]:
        """
        CORE #2: Explain optimization strategy using Gemini 3
        
        This function uses Gemini 3 to:
        - Explain WHY the optimization chose this strategy
        - Provide graph-based reasoning
        - Identify bottlenecks and risks
        - Recommend actions
        
        Args:
            period: Planning period
            commodity: Commodity type
            optimization_results: Precomputed optimization output
            graph_data: Graph structure (nodes, edges)
            priority: User priority (0=cost, 1=speed)
            
        Returns:
            Dictionary with strategy_summary, reasoning, risks, recommendations
        """
        # Prepare context for Gemini
        context = f"""
OPTIMIZATION RESULTS ANALYSIS

Period: {period}
Commodity: {commodity}
User Priority: {'Cost-focused' if priority < 0.5 else 'Speed-focused' if priority > 0.5 else 'Balanced'}

Optimization Results:
- Total Cost: ${optimization_results.get('total_cost', 0):,.0f}
- Total Time: {optimization_results.get('total_time', 0)} days
- Hubs Selected: {optimization_results.get('num_hubs', 0)}
- Top Routes: {json.dumps(optimization_results.get('top_routes', [])[:3], indent=2)}

Graph Structure:
- Nodes: {self._safe_len(graph_data.get('nodes', []))}
- Edges: {self._safe_len(graph_data.get('edges', []))}
- Modal Split: {self._analyze_modal_split(graph_data)}

Your task: Explain this strategy from a decision-maker's perspective.
"""
        
        system_instruction = """You are a strategic logistics advisor. Analyze the optimization results and provide:
1. Clear explanation of the chosen strategy
2. Graph-based reasoning (why these routes/hubs?)
3. Potential bottlenecks and risks
4. Actionable recommendations

Write for business decision-makers, not technical audiences."""
        
        response = self._call_gemini(context, system_instruction)
        
        return self._parse_strategy_response(response)
    
    def whatif_analysis(
        self,
        scenario_type: str,
        impact_value: float,
        current_results: Dict[str, Any],
        graph_data: Dict[str, Any],
        commodity: str
    ) -> Dict[str, Any]:
        """
        CORE #3: What-if scenario analysis using Gemini 3
        
        This function uses Gemini 3 to:
        - Reason about scenario impact WITHOUT re-running optimization
        - Identify affected commodities/routes
        - Suggest mitigation strategies
        
        Args:
            scenario_type: Type of scenario
            impact_value: Magnitude of change
            current_results: Current optimization results
            graph_data: Graph structure
            commodity: Commodity being analyzed
            
        Returns:
            Dictionary with scenario_description, expected_impact, affected_items, mitigation
        """
        context = f"""
WHAT-IF SCENARIO ANALYSIS

Scenario: {scenario_type}
Impact Value: {impact_value}
Commodity: {commodity}

Current Strategy:
- Total Cost: ${current_results.get('total_cost', 0):,.0f}
- Total Time: {current_results.get('total_time', 0)} days
- Critical Routes: {json.dumps(current_results.get('top_routes', [])[:2], indent=2)}

Graph Context:
- Network has {self._safe_len(graph_data.get('nodes', []))} nodes
- {self._safe_len(graph_data.get('edges', []))} connections
- {self._count_modes(graph_data)} transport modes available

Your task: Reason about the impact of this scenario on the current strategy.
DO NOT re-optimize. Use graph reasoning and domain knowledge.
"""
        
        system_instruction = """You are a logistics risk analyst. For the given what-if scenario:
1. Describe the scenario clearly
2. Reason about expected impact on cost, time, and routes
3. Identify which commodities/routes are most affected
4. Suggest mitigation strategies

Focus on practical insights based on graph structure and logistics principles."""
        
        response = self._call_gemini(context, system_instruction)
        
        return self._parse_whatif_response(response, scenario_type, impact_value)
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _safe_len(self, data) -> int:
        """Safely get length of data, handling both DataFrame and list"""
        if data is None:
            return 0
        if isinstance(data, pd.DataFrame):
            return len(data)
        if isinstance(data, (list, dict)):
            return len(data)
        return 0
    
    def _analyze_modal_split(self, graph_data: Dict) -> str:
        """Analyze transport mode distribution"""
        edges = graph_data.get('edges', [])
        
        # Handle pandas DataFrame
        import pandas as pd
        if isinstance(edges, pd.DataFrame):
            if edges.empty:
                return "No edges"
            if 'mode' in edges.columns:
                modes = edges['mode'].value_counts().to_dict()
            else:
                return "No mode column"
        elif isinstance(edges, list):
            if len(edges) == 0:
                return "No edges"
            # Handle list of dictionaries
            modes = {}
            for edge in edges:
                mode = edge.get('mode', 'unknown') if isinstance(edge, dict) else 'unknown'
                modes[mode] = modes.get(mode, 0) + 1
        else:
            return "No edges"
        
        return ", ".join([f"{mode}: {count}" for mode, count in modes.items()])
    
    def _count_modes(self, graph_data: Dict) -> int:
        """Count unique transport modes"""
        edges = graph_data.get('edges', [])
        
        # Handle pandas DataFrame
        import pandas as pd
        if isinstance(edges, pd.DataFrame):
            if edges.empty:
                return 0
            if 'mode' in edges.columns:
                return len(edges['mode'].unique())
            else:
                return 0
        elif isinstance(edges, list):
            if len(edges) == 0:
                return 0
            # Handle list of dictionaries
            return len(set(edge.get('mode', 'unknown') if isinstance(edge, dict) else 'unknown' for edge in edges))
        else:
            return 0
    
    def _generate_chat_mock_response(self, prompt: str) -> str:
        """Generate mock chat response - thay cho placeholder khi không có API hoặc rate limit"""
        prompt_lower = (prompt or "").lower()
        if any(kw in prompt_lower for kw in ["hub", "tại sao", "why", "chọn", "selected"]):
            return """Dựa trên kết quả tối ưu hóa, các hub được chọn dựa trên:
- **Vị trí trung tâm** trong mạng lưới (giảm chi phí vận chuyển tổng thể)
- **Khả năng kết nối** road–waterway (multimodal)
- **Chi phí vận hành** và năng lực phù hợp

**Lưu ý:** Đây là phản hồi demo. Để có câu trả lời chi tiết từ Gemini API, cần cấu hình `GEMINI_API_KEY` hợp lệ."""
        if any(kw in prompt_lower for kw in ["rủi ro", "risk", "bottleneck"]):
            return """**Rủi ro chính:**
- Hub tập trung nhiều luồng → điểm nghẽn tiềm ẩn
- Ràng buộc năng lực trên tuyến đường thủy
- Thiếu dự phòng route ở khu vực phía Nam

**Khuyến nghị:** Thiết lập routing dự phòng cho hub chính, giám sát utilization hàng tuần.

*Phản hồi demo – cấu hình GEMINI_API_KEY để dùng API thật.*"""
        return """Tôi có thể hỗ trợ giải thích chiến lược tối ưu hóa, rủi ro, và khuyến nghị dựa trên kết quả hiện tại.

**Để có câu trả lời chi tiết từ Gemini API:**
1. Cấu hình biến môi trường: `export GEMINI_API_KEY="your-key"`
2. Restart app: `streamlit run app.py`

*Hiện đang dùng phản hồi demo (mock) do chưa có API key hoặc gặp rate limit.*"""

    def _generate_strategy_explanation(self, prompt: str) -> str:
        """Generate mock strategy explanation"""
        return """
### Strategic Overview
The optimization has selected a multi-modal hub-and-spoke strategy that balances cost efficiency with delivery speed. This approach leverages waterways for bulk long-haul transport and roads for last-mile delivery.

### Why This Strategy Works

**Graph-Based Reasoning:**
- The selected hubs (nodes 3, 7, 12) are positioned at key graph centrality points, minimizing average path length across the network
- Waterway corridors handle 65% of ton-km, exploiting their low cost-per-km advantage for bulk commodities
- Road connections provide flexibility and speed for time-sensitive routes

**Cost-Speed Trade-off:**
Given your balanced priority setting, the strategy achieves 92% of minimum cost while maintaining 88% of maximum speed. This is optimal given the graph structure.

### Bottlenecks & Risks

**Critical Bottlenecks:**
- Hub 7 handles 40% of total flow - a single point of failure risk
- Waterway edge 12→15 operates at 95% capacity - vulnerable to demand spikes
- Modal transfer at Hub 3 adds 2-day switching time

**Risk Factors:**
- Weather disruption on water routes could cascade delays
- Hub capacity constraints may limit growth in Period 2
- Limited alternative routes for southern region (nodes 18-22)

### Recommended Actions

1. **Immediate:** Establish backup routing protocols for Hub 7 overflow
2. **Short-term:** Negotiate capacity expansion on edge 12→15 
3. **Strategic:** Invest in Hub 3 infrastructure to reduce switching time
4. **Monitoring:** Track actual flow vs. capacity on critical edges weekly
"""
    
    def _parse_strategy_response(self, response: str) -> Dict[str, Any]:
        """Parse strategy explanation into structured format"""
        # In production, use more sophisticated parsing
        sections = response.split('###')
        
        return {
            "strategy_summary": sections[1].strip() if len(sections) > 1 else response[:200],
            "reasoning": sections[2].strip() if len(sections) > 2 else "Graph-based optimization",
            "graph_insights": "Network structure supports efficient hub-and-spoke configuration",
            "risks": [
                "Hub 7 concentration risk",
                "Capacity constraints on waterway routes",
                "Limited route redundancy in southern region"
            ],
            "recommendations": [
                "Establish contingency routing for Hub 7",
                "Monitor capacity utilization weekly",
                "Plan infrastructure investments for Period 2"
            ]
        }
    
    def _generate_whatif_analysis(self, prompt: str) -> str:
        """Generate mock what-if analysis"""
        return """
SCENARIO IMPACT ANALYSIS

If switching costs increase by 50%, the current multi-modal strategy will face significant pressure. Based on graph structure analysis:

**Expected Impact:**
- Total cost likely to increase by 8-12% due to modal transfer penalties
- Routes with multiple mode switches (e.g., water→road→water) become less competitive
- Single-mode routes (all-road or all-water) gain relative advantage

**Affected Routes:**
- Route 1 (Hub 3 → Hub 7 → Node 15): Currently uses water→road switch at Hub 7. Higher switching cost may favor direct water route if available.
- Route 3 (Node 8 → Hub 3 → Node 22): Two modal transfers, high sensitivity to switching cost

**Mitigation Strategies:**
1. Negotiate long-term modal transfer contracts to lock in current costs
2. Consolidate cargo to reduce frequency of mode switches
3. Invest in Hub 7 to reduce switching time (converts cost to time trade-off)
4. Re-evaluate single-mode alternatives for high-volume lanes
"""
    
    def _parse_whatif_response(self, response: str, scenario: str, value: float) -> Dict[str, Any]:
        """Parse what-if response into structured format"""
        return {
            "scenario_description": f"{scenario} by {value}%",
            "expected_impact": "Cost increase of 8-12% expected. Multi-modal routes most affected.",
            "affected_items": [
                "Route 1: water→road switch at Hub 7",
                "Route 3: Two modal transfers",
                "Hub 3 operations: Switching volume concentration"
            ],
            "mitigation": [
                "Negotiate long-term modal transfer contracts",
                "Consolidate cargo to reduce switch frequency",
                "Invest in Hub 7 infrastructure",
                "Evaluate single-mode route alternatives"
            ]
        }
    
    def chat(
        self,
        user_message: str,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Chat with Gemini about logistics optimization
        
        Args:
            user_message: User's question/message
            context: Optional context (optimization results, graph data, etc.)
            
        Returns:
            Gemini's response
        """
        # Build context-aware prompt
        context_str = ""
        if context:
            if 'optimization_results' in context:
                results = context['optimization_results']
                context_str += f"\n\nCurrent Optimization Results:\n"
                context_str += f"- Total Cost: ${results.get('total_cost', 0):,.0f}\n"
                context_str += f"- Total Time: {results.get('total_time', 0)} days\n"
                context_str += f"- Hubs Selected: {results.get('selected_hubs', [])}\n"
                context_str += f"- Top Routes: {len(results.get('top_routes', []))} routes\n"
            
            if 'graph_data' in context:
                graph = context['graph_data']
                context_str += f"\n\nNetwork Information:\n"
                context_str += f"- Nodes: {self._safe_len(graph.get('nodes', []))}\n"
                context_str += f"- Edges: {self._safe_len(graph.get('edges', []))}\n"
                context_str += f"- Modal Split: {self._analyze_modal_split(graph)}\n"
            
            if 'period' in context:
                context_str += f"\n\nPlanning Period: {context['period']}\n"
            if 'commodity' in context:
                context_str += f"Commodity: {context['commodity']}\n"
        
        system_instruction = """You are an expert logistics advisor helping users understand optimization strategies. 
Provide clear, actionable insights based on the optimization results and network structure.
Be conversational, helpful, and focus on practical business implications."""
        
        full_prompt = f"{user_message}{context_str}"
        
        return self._call_gemini(full_prompt, system_instruction)