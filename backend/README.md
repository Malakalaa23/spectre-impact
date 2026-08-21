# Spectre Impact BFS Engine

This module automatically turns changed GitHub PR file paths into a blast-radius analysis. It is self-contained and does not need the webhook backend or AI agent to run.

## Install and verify

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m backend.analysis.visual_graph
```

The last command writes `backend/data/dependency_graph.png`.

## Backend integration contract

Ahmed's backend should call exactly this function after retrieving the PR's changed-file paths:

```python
from backend.analysis.change_analysis_engine import analyze_impact

result = analyze_impact([
    "terraform/customer_database.tf",
    "services/login/routes/session.py",
])
```

It returns JSON-ready data:

```python
{
    "changed_resource": "customer_database",
    "changed_resources": ["customer_database", "login_service"],
    "affected_services": ["...all affected graph nodes..."],
    "business_impact": 100,
    "unknown_resources": [],
    "evidence": [["customer_database", "login_service"], "..."],
}
```

`business_impact` is the highest affected percentage in `data/business_map.yaml`. `evidence` contains shortest dependency paths, so the AI agent and dashboard can explain each impact result.

## Advanced automation

Generate **proposed** maps by scanning another repository (the command never overwrites the curated maps):

```powershell
python -m backend.analysis.auto_discovery C:\path\to\application-repository
```

It creates `backend/data/generated/resource_map.generated.json` and `dependency_graph.generated.yaml`. Review these inferred maps before copying confirmed relationships into the curated data files.

Create a highlighted graph for a PR and JSON for the frontend:

```python
from backend.analysis.visual_graph import create_blast_radius_graph, export_graph_json

changed_files = ["services/payment/routes/charge.py"]
create_blast_radius_graph(changed_files)
export_graph_json(changed_files=changed_files)
```

## Data files

- `data/resource_map.json`: explicit file-to-resource mappings.
- `data/dependency_graph.yaml`: the BFS dependency graph. An edge points from a changed component to a component that depends on it.
- `data/business_map.yaml`: estimated percentage of users affected by each component.
