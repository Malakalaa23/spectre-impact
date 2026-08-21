import yaml
import json
import os

def load_dependency_graph():
    graph_path = "backend/data/dependency_graph.yaml"
    resource_path = "backend/data/resource_map.json"
    business_path = "backend/data/business_map.yaml"
    
    graph = {}
    resource_map = {}
    business_map = {}
    
    if os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as f:
            graph = yaml.safe_load(f) or {}
        print("GRAPH:")
        print(yaml.dump(graph))
    else:
        print("Graph not found")
    
    if os.path.exists(resource_path):
        with open(resource_path, "r", encoding="utf-8") as f:
            resource_map = json.load(f) or {}
        print("RESOURCE MAP:")
        print(json.dumps(resource_map, indent=2))
    else:
        print("Resource map not found")
    
    if os.path.exists(business_path):
        with open(business_path, "r", encoding="utf-8") as f:
            business_map = yaml.safe_load(f) or {}
        print("BUSINESS MAP:")
        print(yaml.dump(business_map))
    else:
        print("Business map not found")

if __name__ == "__main__":
    load_dependency_graph()