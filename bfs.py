"""Small deterministic BFS blast-radius engine used as a local fallback/demo.
The production backend can replace these results without changing the UI."""

from collections import deque

SERVICE_GRAPH = {
    "login.py": ["Login Service", "Authentication"],
    "auth_middleware.py": ["Authentication", "API Gateway"],
    "session_manager.py": ["Authentication", "Login Service"],
    "database.tf": ["Main Database", "Login Service", "Payment Gateway"],
    "docker-compose.yml": ["API Gateway", "Main Database"],
    "gateway_config.yaml": ["API Gateway", "Authentication"],
    "payment_client.py": ["Payment Gateway", "Main Database"],
    "retry_policy.py": ["Payment Gateway"],
    "logging_config.py": [],
}


def calculate_blast_radius(changed_files: list[str]) -> list[str]:
    """Traverse a tiny dependency graph from changed files.
    Unknown files return an empty list rather than failing."""
    queue = deque(changed_files or [])
    seen_files = set()
    services = []
    seen_services = set()

    while queue:
        file_name = queue.popleft()
        if file_name in seen_files:
            continue
        seen_files.add(file_name)
        for service in SERVICE_GRAPH.get(file_name, []):
            if service not in seen_services:
                seen_services.add(service)
                services.append(service)
    return services
