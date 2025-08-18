import re
from collections import defaultdict, deque
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, render_template_string
from flask import send_from_directory
import os
import time
from urllib.parse import urlencode

UPLOAD_FOLDER = 'static/images'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

class MeTTaGraphAnalyzer:
    def __init__(self):
        self.graph = nx.Graph()
        self.all_nodes = set()
        self.connection_rules = {
            'default': 'undirected',  # or 'directed'
            'predicates': {
                # Example: 'triggers': 'directed',
                # 'related_to': 'undirected'
            }
        }
    
    def set_connection_rules(self, rules):
        """Configure how different predicates create connections"""
        self.connection_rules.update(rules)
    
    def parse_metta(self, metta_text):
        """Parse MeTTa text into graph structure"""
        # Remove comments and clean input
        metta_text = re.sub(r';.*$', '', metta_text, flags=re.MULTILINE)
        metta_text = metta_text.strip()
        
        # Parse nested S-expressions
        tokens = re.findall(r'\(|\)|[^\s()]+', metta_text)
        stack = []
        current = []
        
        for token in tokens:
            if token == '(':
                stack.append(current)
                current = []
            elif token == ')':
                if stack:
                    last = stack.pop()
                    last.append(current)
                    current = last
            else:
                current.append(token)
        
        # Process parsed expressions
        for expr in current:
            self._process_expression(expr)
    
    def _process_expression(self, expr):
        """Process a single MeTTa expression"""
        if not isinstance(expr, list):
            # Single node
            self.all_nodes.add(expr)
            self.graph.add_node(expr)
            return
        
        if len(expr) == 0:
            return
        
        # Get predicate (first element)
        predicate = expr[0]
        nodes = [n for n in expr[1:] if isinstance(n, str)]
        
        # Add all nodes to graph
        for node in nodes:
            self.all_nodes.add(node)
            self.graph.add_node(node)
        
        # Determine connection type
        connection_type = self.connection_rules['predicates'].get(
            predicate, self.connection_rules['default'])
        
        # Create connections
        if len(nodes) >= 2:
            if connection_type == 'undirected':
                # Connect all nodes to each other
                for i in range(len(nodes)):
                    for j in range(i+1, len(nodes)):
                        self.graph.add_edge(nodes[i], nodes[j], predicate=predicate)
            else:  # directed
                # Connect first node to all others
                source = nodes[0]
                for target in nodes[1:]:
                    self.graph.add_edge(source, target, predicate=predicate)
    
    def analyze_connectivity(self):
        """Analyze the graph and generate report"""
        # Find connected components
        components = list(nx.connected_components(self.graph))
        
        # Find orphan nodes (degree 0)
        orphan_nodes = [n for n in self.graph.nodes() if self.graph.degree(n) == 0]
        
        # Generate report
        report = {
            'total_nodes': len(self.all_nodes),
            'connected_components': len(components),
            'largest_component_size': max(len(c) for c in components) if components else 0,
            'orphan_nodes': orphan_nodes,
            'component_size_distribution': defaultdict(int),
            'components': []
        }
        
        for i, component in enumerate(components, 1):
            size = len(component)
            report['component_size_distribution'][size] += 1
            report['components'].append({
                'id': i,
                'size': size,
                'nodes': sorted(component)
            })
        
        return report
    
    def visualize_graph(self, filename):
        plt.figure(figsize=(16, 14))
        
        try:
            # Create directed graph
            G = nx.DiGraph()
            G.add_edges_from(self.graph.edges(data=True))
            
            # Use spring layout
            pos = nx.spring_layout(G, k=0.5, iterations=200, seed=42)
            
            # Draw edges with simple arrows
            nx.draw_networkx_edges(
                G, pos,
                arrowstyle='-|>',  # Simple arrowhead
                arrowsize=15,      # Perfect arrowhead size
                width=1.5,
                edge_color='#555555',
                node_size=1800,    # Must match node size
                min_source_margin=15,  # Space from source
                min_target_margin=15,  # Space from target
                ax=plt.gca()
            )
            
            # Draw nodes
            nx.draw_networkx_nodes(
                G, pos,
                node_size=1800,
                node_color='lightblue',
                alpha=0.8,
                edgecolors='darkblue',
                linewidths=2,
                ax=plt.gca()
            )
            
            # Draw labels
            nx.draw_networkx_labels(
                G, pos,
                font_size=10,
                bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.3'),
                ax=plt.gca()
            )
            
            plt.title("MeTTa Graph Connectivity", size=18, pad=20)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(filename, dpi=300, bbox_inches='tight')
        finally:
            plt.close()
# Web Application Interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MeTTa Graph Connectivity Analyzer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        textarea { width: 100%; height: 200px; }
        .container { max-width: 900px; margin: 0 auto; }
        .result { margin-top: 20px; padding: 15px; background: #f5f5f5; }
        img { max-width: 100%; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MeTTa Graph Connectivity Analyzer</h1>
        <form method="POST">
            <p>Enter MeTTa data:</p>
            <textarea name="metta_data" required>{{ input_data }}</textarea>
            <br>
            <button type="submit">Analyze</button>
        </form>
        
        {% if report %}
        <div class="result">
            <h2>Analysis Results</h2>
            <p><strong>Total nodes:</strong> {{ report.total_nodes }}</p>
            <p><strong>Connected components:</strong> {{ report.connected_components }}</p>
            <p><strong>Largest component size:</strong> {{ report.largest_component_size }}</p>
            
            <h3>Component Size Distribution</h3>
            <ul>
                {% for size, count in report.component_size_distribution.items() %}
                <li>Size {{ size }}: {{ count }} component(s)</li>
                {% endfor %}
            </ul>
            
            <h3>Orphan Nodes</h3>
            {% if report.orphan_nodes %}
                <p>{{ report.orphan_nodes|join(', ') }}</p>
            {% else %}
                <p>No orphan nodes found</p>
            {% endif %}
            
            <h3>Graph Visualization</h3>
            <img src="/graph.png?t={{ timestamp }}&data={{ input_data|urlencode }}" 
            alt="Graph visualization">
            
            <h3>Detailed Components</h3>
            {% for component in report.components %}
                <h4>Component {{ component.id }} (size={{ component.size }})</h4>
                <p>{{ component.nodes|join(', ') }}</p>
            {% endfor %}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def analyze_metta():
    if request.method == 'POST':
        metta_data = request.form['metta_data']
        analyzer = MeTTaGraphAnalyzer()
        
        # Configure connection rules
        analyzer.set_connection_rules({
            'default': 'undirected',
            'predicates': {
                'triggers': 'directed',
                'causes': 'directed',
                'related_to': 'undirected'
            }
        })
        
        analyzer.parse_metta(metta_data)
        report = analyzer.analyze_connectivity()
        
        # Generate unique filename
        timestamp = str(int(time.time()))
        filename = os.path.join(UPLOAD_FOLDER, f'graph_{timestamp}.png')
        analyzer.visualize_graph(filename)
        
        return render_template_string(HTML_TEMPLATE, 
                                   input_data=metta_data,
                                   report=report,
                                   timestamp=timestamp)
    
    return render_template_string(HTML_TEMPLATE, input_data="")

@app.route('/graph.png')
def serve_graph():
    timestamp = request.args.get('t')
    if not timestamp:
        return "Missing timestamp parameter", 400
        
    filename = f'graph_{timestamp}.png'
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    from datetime import datetime
    app.run(debug=True)
