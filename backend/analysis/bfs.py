from collections import deque


def bfs(graph, start_node):
    """
    Breadth-First Search (BFS)

    Starts from one node and discovers every
    reachable component in the dependency graph.

    Parameters
    ----------
    graph : DependencyGraph

    start_node : str

    Returns
    -------
    list[str]
        Every affected component.
    """

    # Nodes we've already visited
    visited = set()

    # Queue used by BFS
    queue = deque()

    # Final result
    affected = []

    # Start from the changed resource
    queue.append(start_node)

    while queue:

        # Take the next node from the front
        current = queue.popleft()

        # Ignore duplicates
        if current in visited:
            continue

        # Mark as visited
        visited.add(current)

        # Save the node
        affected.append(current)

        # Visit every child
        children = graph.get_children(current)

        for child in children:

            # Only visit unseen nodes
            if child not in visited:
                queue.append(child)

    return affected


def bfs_with_paths(graph, start_node: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return BFS nodes plus the shortest evidence path to every node."""
    queue = deque([start_node])
    paths = {start_node: [start_node]}
    affected = []

    while queue:
        current = queue.popleft()
        affected.append(current)
        for child in graph.get_children(current):
            if child not in paths:
                paths[child] = [*paths[current], child]
                queue.append(child)

    return affected, paths
