import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def unroll_cell(cell, graph=None, parent_id=None, visited=None):
    if graph is None:
        graph = nx.DiGraph()
    if visited is None:
        visited = set()

    cell_hash = cell.hash
    cell_id = cell_hash

    if cell_id in visited:
        return graph  # Avoid duplicates
    visited.add(cell_id)

    slice = cell.begin_parse()
    bits_left = len(slice.bits)

    cell_data = {}
    if bits_left >= 32:
        opcode = slice.load_uint(32)
        cell_data['opcode'] = hex(opcode)
    else:
        cell_data['opcode'] = 'N/A'

    graph.add_node(cell_id, **cell_data)

    if parent_id is not None:
        graph.add_edge(parent_id, cell_id)

    for ref in slice.refs:
        unroll_cell(ref, graph, cell_id, visited)

    return graph

def decompose_message(msg):
    return {
        'src': msg.info.src.to_str(1, 1, 1) if msg.info.src else None,
        'dest': msg.info.dest.to_str(1, 1, 1) if msg.info.dest else None,
        'coins': msg.info.value.grams / 1e9 if hasattr(msg.info, 'value') else None,
        'body': unroll_cell(msg.body) if msg.body else None  # Unroll the body cell
    }

def visual_msg(tx):
    graph = nx.DiGraph()

    # Process the input message
    in_msg = tx.in_msg
    if in_msg:
        in_msg_data = decompose_message(in_msg)
        src = in_msg_data['src']
        dest = in_msg_data['dest']
        coins = in_msg_data['coins']
        body_graph = in_msg_data['body']

        # Add nodes for src and dest
        if src:
            graph.add_node(src, label=src, node_type='address')
        else:
            src = 'External'  # For messages from external sources
            graph.add_node(src, label=src, node_type='address')

        if dest:
            graph.add_node(dest, label=dest, node_type='address')

        # Add edge from src to dest with coins and edge_type
        edge_label = f"{coins}" if coins else "Value: Unknown"
        graph.add_edge(src, dest, label=edge_label, edge_type='in_msg')

        # If there's a body, add it to the graph
        if body_graph:
            # Merge the body graph into the main graph
            # First, we need to relabel the nodes to avoid conflicts
            mapping = {}
            for node in body_graph.nodes():
                mapping[node] = f"{src}->{dest}_{node}"
            body_graph = nx.relabel_nodes(body_graph, mapping)

            # Add the nodes and edges to the main graph
            graph.add_nodes_from(body_graph.nodes(data=True))
            graph.add_edges_from(body_graph.edges(data=True))

            # Connect the message edge to the body
            first_cell = list(body_graph.nodes())[0]
            graph.add_edge(dest, first_cell)

    # Process the output messages
    for out_msg in tx.out_msgs:
        out_msg_data = decompose_message(out_msg)
        src = out_msg_data['src']
        dest = out_msg_data['dest']
        coins = out_msg_data['coins']
        body_graph = out_msg_data['body']

        # Add nodes for src and dest
        if src:
            graph.add_node(src, label=src, node_type='address')
        if dest:
            graph.add_node(dest, label=dest, node_type='address')
        else:
            dest = 'External'  # For messages to external destinations
            graph.add_node(dest, label=dest, node_type='address')

        # Add edge from src to dest with coins and edge_type
        edge_label = f"{coins}" if coins else "Value: Unknown"
        graph.add_edge(src, dest, label=edge_label, edge_type='out_msg')

        # If there's a body, add it to the graph
        if body_graph:
            # Merge the body graph into the main graph
            # First, we need to relabel the nodes to avoid conflicts
            mapping = {}
            for node in body_graph.nodes():
                mapping[node] = f"{src}->{dest}_{node}"
            body_graph = nx.relabel_nodes(body_graph, mapping)

            # Add the nodes and edges to the main graph
            graph.add_nodes_from(body_graph.nodes(data=True))
            graph.add_edges_from(body_graph.edges(data=True))

            # Connect the message edge to the body
            first_cell = list(body_graph.nodes())[0]
            graph.add_edge(dest, first_cell)

    # Visualization
    pos = nx.spring_layout(graph, k=10, iterations=50)

    # Prepare labels and colors for nodes
    labels = {}
    node_colors = []
    for node, data in graph.nodes(data=True):
        node_type = data.get('node_type', 'address')
        label = data.get('label', '')
        labels[node] = label

        # Set node colors
        if node_type == 'address':
            node_colors.append('lightblue')
        else:
            node_colors.append('lightgreen')

    # Determine edge colors based on edge_type
    edge_colors = []
    for u, v, data in graph.edges(data=True):
        edge_type = data.get('edge_type', 'other')
        if edge_type == 'in_msg':
            edge_colors.append('blue')    # Color for input messages
        elif edge_type == 'out_msg':
            edge_colors.append('green')   # Color for output messages
        else:
            edge_colors.append('gray')    # Default color for other edges

    # Draw the nodes
    nx.draw_networkx_nodes(graph, pos, node_size=100, node_color=node_colors)

    # Draw the edges with specified colors
    nx.draw_networkx_edges(graph, pos, arrowstyle='->', arrowsize=5, edge_color=edge_colors)

    # Draw the edge labels
    edge_labels = nx.get_edge_attributes(graph, 'label')
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=8)

    # Draw the labels
    nx.draw_networkx_labels(graph, pos, labels, font_size=5)

    # Create custom legend handles
    in_msg_patch = mpatches.Patch(color='blue', label='Input Message')
    out_msg_patch = mpatches.Patch(color='green', label='Output Message')

    plt.legend(handles=[in_msg_patch, out_msg_patch])

    # Display the graph
    plt.title("Transaction Messages Visualization")
    plt.axis('off')
    plt.show()


visual_msg(tx)
