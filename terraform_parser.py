"""
terraform_parser.py — Extract a dependency graph from Terraform files.

Reads every .tf file in a target directory, finds `resource` blocks,
extracts explicit `depends_on` references and implicit attribute
references, and builds the same node schema that
backend/data/dependency_graph.yaml uses.

Why this exists:
    Onboarding a real customer means building a dependency graph from
    their infrastructure. If they use Terraform, we can read it
    automatically instead of asking them to write YAML by hand.

Limitations:
    Terraform knows infrastructure dependencies. It does not know
    application call graphs. A resource that reads from a database
    in Terraform is not the same as a service that queries it at
    runtime. We surface what Terraform knows and flag what it cannot.

Usage:
    python terraform_parser.py terraform/ -o parsed_graph.yaml
    python terraform_parser.py terraform/customer_database.tf
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any


try:
    import hcl2
except ImportError as exc:
    print("python-hcl2 is not installed.", file=sys.stderr)
    print("  pip install python-hcl2", file=sys.stderr)
    raise SystemExit(1) from exc


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resource-type mapping
# ---------------------------------------------------------------------------
RESOURCE_TYPE_MAP: dict[str, str] = {
    "aws_db_instance": "database",
    "aws_rds_cluster": "database",
    "aws_dynamodb_table": "database",
    "aws_redshift_cluster": "database",
    "aws_elasticache_cluster": "cache",
    "aws_elasticache_replication_group": "cache",
    "aws_instance": "service",
    "aws_ecs_service": "service",
    "aws_ecs_task_definition": "service",
    "aws_lambda_function": "service",
    "aws_batch_compute_environment": "service",
    "aws_api_gateway_rest_api": "api",
    "aws_apigatewayv2_api": "api",
    "aws_lb": "api",
    "aws_alb": "api",
    "aws_cloudfront_distribution": "frontend",
    "aws_s3_bucket": "storage",
    "aws_vpc": "network",
    "aws_subnet": "network",
    "aws_security_group": "network",
    "aws_route53_zone": "network",
}


def _short_name(resource_address: str) -> str:
    """
    Convert a Terraform resource address to a short node name.

    "aws_db_instance.customer_database" -> "customer_database"
    """
    return resource_address.split(".", 1)[-1]


def _classify(resource_type: str) -> str:
    """Return the node type for a Terraform resource type."""
    return RESOURCE_TYPE_MAP.get(resource_type, "unknown")


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
# Different python-hcl2 versions behave differently:
#
#   Newer versions (4.x+) strip source quotes and return plain keys:
#       {"aws_db_instance": {"customer_database": {...}}}
#
#   Older versions (3.x and some 4.x builds) keep the quotes:
#       {'"aws_db_instance"': {'"customer_database"': {...}}}
#
# And references inside depends_on or interpolations can come back as:
#       "aws_db_instance.customer_database"           (clean)
#       '"aws_db_instance"."customer_database"'       (quoted)
#       "${aws_db_instance.customer_database}"        (interpolated)
#
# Every helper below normalises toward the clean form so the rest of
# the parser only has to deal with one shape.

# Matches a quote, optional whitespace, a dot, optional whitespace,
# another quote. This is the HCL source form of a segmented reference
# like "aws_db_instance"."customer_database".
_QUOTED_DOT_RE = re.compile(r'"\s*\.\s*"')


def _clean_hcl2_key(key: Any) -> str:
    """
    Strip surrounding double quotes from a key produced by hcl2.

    Older python-hcl2 versions return resource type and name keys with
    their source quotes attached. Leaving them on makes the resource
    type fail the RESOURCE_TYPE_MAP lookup and the address fail to
    match a dependency reference.
    """
    if not isinstance(key, str):
        return str(key)
    key = key.strip()
    if key.startswith('"') and key.endswith('"') and len(key) >= 2:
        key = key[1:-1]
    return key


def _normalize_ref(ref: str) -> str:
    """
    Collapse a raw reference string to its bare Terraform address.

    Handles all three shapes hcl2 has produced across versions:

        aws_db_instance.customer_database
        ${aws_db_instance.customer_database}
        "aws_db_instance"."customer_database"

    The last form is the source form you'd write inside an HCL
    expression like depends_on = [aws_db_instance.customer_database]
    when the segments are quoted. Older hcl2 preserves the quotes.
    """
    ref = (ref or "").strip()

    # Strip ${...} interpolation wrapper
    if ref.startswith("${") and ref.endswith("}"):
        ref = ref[2:-1].strip()

    # Collapse "A"."B" into A.B
    ref = _QUOTED_DOT_RE.sub(".", ref)

    # Strip any remaining outer quotes
    ref = ref.strip('"')

    return ref


# ---------------------------------------------------------------------------
# Dependency extraction
# ---------------------------------------------------------------------------
_REF_PATTERN = re.compile(
    r"\b((?:aws|google|azurerm|kubernetes|helm)_[a-z0-9_]+)\.([a-z0-9_]+)\b"
)


def _extract_depends_on(config: dict[str, Any]) -> list[str]:
    """Extract explicit depends_on references from a resource config."""
    raw = config.get("depends_on", [])
    if not isinstance(raw, list):
        return []

    refs: list[str] = []
    for item in raw:
        if isinstance(item, str):
            refs.append(_normalize_ref(item))
        elif isinstance(item, dict):
            ref = item.get("__ref__") or item.get("ref") or ""
            refs.append(_normalize_ref(ref))
    return [r for r in refs if r]


def _extract_implicit_refs(config: dict[str, Any]) -> list[str]:
    """
    Find implicit references to other resources anywhere in the config.

    Terraform allows this:
        subnet_id = aws_subnet.main.id

    Which creates an implicit dependency without an explicit depends_on.
    We walk the whole config tree looking for strings matching the
    pattern "<provider>_<type>.<name>".
    """
    refs: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            # Normalise the string first so quoted segment forms
            # like "aws_subnet"."main" still match the pattern.
            normalized = _normalize_ref(node)
            for match in _REF_PATTERN.finditer(normalized):
                refs.add(f"{match.group(1)}.{match.group(2)}")
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(config)
    return list(refs)


# ---------------------------------------------------------------------------
# Single-file parsing
# ---------------------------------------------------------------------------
def parse_terraform_file(file_path: Path) -> dict[str, dict[str, Any]]:
    """
    Parse one .tf file and return a dict of resources keyed by address.

    Reads with utf-8-sig so a leading UTF-8 BOM (written by many
    Windows editors such as Notepad) is stripped before the HCL
    parser sees it.
    """
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            data = hcl2.load(f)
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return {}

    resources: dict[str, dict[str, Any]] = {}

    for block in data.get("resource", []) or []:
        if not isinstance(block, dict):
            continue
        for resource_type_raw, instances in block.items():
            resource_type = _clean_hcl2_key(resource_type_raw)
            if not isinstance(instances, dict):
                continue
            for resource_name_raw, config in instances.items():
                resource_name = _clean_hcl2_key(resource_name_raw)
                if not isinstance(config, dict):
                    continue

                address = f"{resource_type}.{resource_name}"
                explicit = _extract_depends_on(config)
                implicit = _extract_implicit_refs(config)
                deps = sorted({
                    d for d in (explicit + implicit)
                    if d and d != address
                })

                resources[address] = {
                    "resource_type": resource_type,
                    "name": resource_name,
                    "node_type": _classify(resource_type),
                    "source_file": file_path.name,
                    "depends_on": deps,
                }

    return resources


# ---------------------------------------------------------------------------
# Directory parsing + graph assembly
# ---------------------------------------------------------------------------
def parse_terraform_directory(directory: str | Path) -> dict[str, Any]:
    """
    Parse every .tf file in a directory (recursively) and merge the
    results into a single dependency_graph.yaml-shaped document.
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    all_resources: dict[str, dict[str, Any]] = {}
    files_parsed = 0

    for tf_file in sorted(directory.rglob("*.tf")):
        resources = parse_terraform_file(tf_file)
        if resources:
            files_parsed += 1
        for address, data in resources.items():
            if address in all_resources:
                all_resources[address]["depends_on"] = sorted(set(
                    all_resources[address]["depends_on"] + data["depends_on"]
                ))
            else:
                all_resources[address] = data

    address_to_short = {addr: data["name"] for addr, data in all_resources.items()}

    children_by_short: dict[str, list[str]] = {
        name: [] for name in address_to_short.values()
    }

    for addr, data in all_resources.items():
        short = data["name"]
        for dep_address in data["depends_on"]:
            dep_short = address_to_short.get(dep_address)
            if dep_short and dep_short != short:
                if short not in children_by_short[dep_short]:
                    children_by_short[dep_short].append(short)

    nodes: dict[str, dict[str, Any]] = {}
    for addr, data in all_resources.items():
        short = data["name"]
        nodes[short] = {
            "type": data["node_type"],
            "owner": "unknown",
            "criticality": "medium",
            "customer_facing": False,
            "children": sorted(children_by_short.get(short, [])),
            "terraform_address": addr,
            "source_file": data["source_file"],
        }

    return {
        "nodes": nodes,
        "meta": {
            "files_parsed": files_parsed,
            "resources_found": len(nodes),
        },
    }


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------
def to_documents(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a parsed graph into RAG-ready documents.
    """
    out: list[dict[str, Any]] = []

    for name, node in (graph.get("nodes") or {}).items():
        children = node.get("children") or []
        text_lines = [
            f"Terraform resource: {name}",
            f"Terraform address: {node.get('terraform_address', 'unknown')}",
            f"Resource type: {node.get('type', 'unknown')}",
            f"Source file: {node.get('source_file', 'unknown')}",
        ]
        if children:
            text_lines.append(
                f"Downstream dependents: {', '.join(children)}"
            )
            text_lines.append(
                f"Impact: if {name} changes or fails, the following "
                f"components depend on it downstream: {', '.join(children)}."
            )
        else:
            text_lines.append(
                f"Impact: {name} has no downstream dependents in the "
                f"Terraform configuration."
            )
        text_lines.append(
            "Source: parsed from Terraform infrastructure files."
        )

        out.append({
            "id": f"tf_parse_{name}",
            "text": "\n".join(text_lines),
            "metadata": {
                "service": name,
                "node_type": node.get("type", "unknown"),
                "terraform_address": node.get("terraform_address"),
                "source_file": node.get("source_file"),
                "source": "terraform_parse",
            },
        })

    return out


def write_graph_yaml(graph: dict[str, Any], output_path: str | Path) -> None:
    """Write the parsed graph to a YAML file for inspection."""
    import yaml
    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Generated by terraform_parser.py\n")
        f.write("# Owner, criticality, and customer_facing are defaults.\n")
        f.write("# Terraform cannot infer these values. Edit manually.\n\n")
        yaml.dump(graph, f, default_flow_style=False, sort_keys=False)
    logger.info("Wrote graph to %s", output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Extract a dependency graph from Terraform files."
    )
    parser.add_argument("target", help="Directory or single .tf file")
    parser.add_argument(
        "--output", "-o", default="terraform_graph.yaml",
        help="Output YAML path (default: terraform_graph.yaml)",
    )
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"Target not found: {target}", file=sys.stderr)
        return 1

    if target.is_file():
        resources = parse_terraform_file(target)
        if not resources:
            print("No resources found.", file=sys.stderr)
            return 1
        graph = parse_terraform_directory(target.parent)
    else:
        graph = parse_terraform_directory(target)

    write_graph_yaml(graph, args.output)

    meta = graph.get("meta", {})
    print()
    print(f"Files parsed:    {meta.get('files_parsed', 0)}")
    print(f"Resources found: {meta.get('resources_found', 0)}")
    print(f"Output written:  {args.output}")
    print()
    for name, node in (graph.get("nodes") or {}).items():
        children = node.get("children") or []
        print(f"  {name:<28} ({node.get('type', 'unknown')})")
        if children:
            print(f"    -> {', '.join(children)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())