import yaml


class DependencyGraph:
    """
    Represents our project's dependency graph.

    It loads the YAML file and provides helper methods
    for other parts of the application (like BFS).
    """

    def __init__(self, yaml_path: str):
        # Read the YAML file
        with open(yaml_path, "r") as file:
            data = yaml.safe_load(file)

        # Store every node
        self.nodes = data["nodes"]
        self._validate()

    def _validate(self):
        """Reject dependency maps with references to nonexistent nodes."""
        for node_name, node in self.nodes.items():
            if "type" not in node or "children" not in node:
                raise ValueError(f"Node '{node_name}' must define type and children")
            unknown_children = set(node["children"]) - set(self.nodes)
            if unknown_children:
                missing = ", ".join(sorted(unknown_children))
                raise ValueError(f"Node '{node_name}' references missing node(s): {missing}")

    def get_children(self, node_name: str):
        """
        Returns all direct children of a node.

        Example:
        customer_database
            ↓
        login_service
        payment_service
        """

        # Node doesn't exist
        if node_name not in self.nodes:
            return []

        return self.nodes[node_name]["children"]

    def get_node(self, node_name: str):
        """
        Returns the entire node.

        Useful later for:
        - type
        - owner
        - criticality
        """

        return self.nodes.get(node_name)
