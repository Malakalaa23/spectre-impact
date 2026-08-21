import json

from backend.analysis.auto_discovery import scan_repository, write_discovery_output
from backend.analysis.visual_graph import create_blast_radius_graph, export_graph_json


def test_scanner_generates_resource_and_reverse_dependency_maps(tmp_path):
    (tmp_path / "services" / "payment").mkdir(parents=True)
    (tmp_path / "services" / "login").mkdir(parents=True)
    (tmp_path / "services" / "payment" / "app.py").write_text("from login_service import authenticate")
    (tmp_path / "services" / "login" / "app.py").write_text("def authenticate(): pass")

    resources, graph = scan_repository(tmp_path)
    assert resources["services/payment/app.py"] == "payment_service"
    assert graph["nodes"]["login_service"]["children"] == ["payment_service"]

    resource_path, graph_path = write_discovery_output(tmp_path, tmp_path / "generated")
    assert resource_path.exists() and graph_path.exists()


def test_blast_radius_png_and_frontend_json_are_created(tmp_path):
    png = create_blast_radius_graph(["services/payment/app.py"], tmp_path / "blast.png")
    json_path = export_graph_json(tmp_path / "graph.json", ["services/payment/app.py"])
    payload = json.loads(json_path.read_text())
    assert png.exists()
    assert payload["analysis"]["changed_resource"] == "payment_service"
    assert any(node["changed"] for node in payload["nodes"])
