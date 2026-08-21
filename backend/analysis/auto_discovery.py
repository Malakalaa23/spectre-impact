"""Generate *proposed* resource and dependency maps from a source repository.

The scanner understands common service-folder layouts and looks for component
names in source files. Generated maps are starting points: review them before
replacing the curated production maps.
"""

import argparse
import json
import re
from pathlib import Path

import yaml


SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".tf"}
SKIPPED_DIRECTORIES = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build"}


def _component_for_path(relative_path: Path) -> tuple[str, str] | None:
    """Return ``(component_name, component_type)`` for a conventional path."""
    parts = relative_path.parts
    if "services" in parts:
        name = parts[parts.index("services") + 1]
        return (name if name.endswith("_service") else f"{name}_service", "service")
    if "apis" in parts or "api" in parts:
        folder = "apis" if "apis" in parts else "api"
        name = relative_path.stem if parts.index(folder) == len(parts) - 2 else parts[parts.index(folder) + 1]
        return (name if name.endswith("_api") else f"{name}_api", "api")
    if "frontend" in parts:
        return (relative_path.stem if relative_path.stem.endswith("_journey") else f"{relative_path.stem}_journey", "frontend")
    if "terraform" in parts:
        return (relative_path.stem, "infrastructure")
    return None


def scan_repository(repository_root: str | Path) -> tuple[dict, dict]:
    """Scan source files and return ``(resource_map, dependency_graph)``."""
    root = Path(repository_root).resolve()
    resource_map: dict[str, str] = {}
    nodes: dict[str, dict] = {}
    component_files: dict[str, list[Path]] = {}

    for file_path in root.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative = file_path.relative_to(root)
        if any(part in SKIPPED_DIRECTORIES for part in relative.parts):
            continue
        component = _component_for_path(relative)
        if not component:
            continue
        name, node_type = component
        resource_map[relative.as_posix()] = name
        nodes.setdefault(name, {
            "type": node_type,
            "owner": "unknown",
            "criticality": "medium",
            "children": [],
        })
        component_files.setdefault(name, []).append(file_path)

    # If component A imports/references B, A depends on B. Impact therefore
    # flows from B to A, so A is added as a child of B.
    for source, files in component_files.items():
        content = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in files)
        for target in nodes:
            if target == source:
                continue
            aliases = {target, target.removesuffix("_service"), target.removesuffix("_api")}
            if any(re.search(rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])", content)
                   for alias in aliases if alias):
                nodes[target]["children"].append(source)

    for node in nodes.values():
        node["children"] = sorted(set(node["children"]))
    return resource_map, {"nodes": dict(sorted(nodes.items()))}


def write_discovery_output(repository_root: str | Path, output_directory: str | Path) -> tuple[Path, Path]:
    """Write generated maps without overwriting the curated production maps."""
    resource_map, dependency_map = scan_repository(repository_root)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    resource_path = output / "resource_map.generated.json"
    dependency_path = output / "dependency_graph.generated.yaml"
    resource_path.write_text(json.dumps(resource_map, indent=2) + "\n", encoding="utf-8")
    dependency_path.write_text(yaml.safe_dump(dependency_map, sort_keys=False), encoding="utf-8")
    return resource_path, dependency_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate proposed Spectre Impact maps from a repository.")
    parser.add_argument("repository_root", help="Repository to scan")
    parser.add_argument("--output-dir", default="backend/data/generated", help="Directory for generated maps")
    args = parser.parse_args()
    resource, dependency = write_discovery_output(args.repository_root, args.output_dir)
    print(f"Generated {resource}\nGenerated {dependency}")
