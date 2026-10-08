from backend.analysis.change_analysis_engine import ChangeAnalysisEngine, analyze_impact
from backend.models.pull_request import PullRequestEvent


def test_database_change_returns_full_blast_radius():
    result = analyze_impact(["terraform/customer_database.tf"])
    assert result["changed_resource"] == "customer_database"
    assert result["business_impact"] == 100
    assert "payment_service" in result["affected_services"]
    assert ["customer_database", "login_service"] in result["evidence"]


def test_unknown_file_has_zero_impact():
    result = analyze_impact(["docs/readme.md"])
    assert result["changed_resource"] == "unknown"
    assert result["affected_services"] == []
    assert result["business_impact"] == 0


def test_engine_exposes_structured_risk_result():
    engine = ChangeAnalysisEngine(
        "backend/data/resource_map.json", "backend/data/dependency_graph.yaml"
    )
    pull_request = PullRequestEvent(
        action="opened", repository_name="spectre-impact", pr_number=5,
        title="Payment change", body="", author="abubakr", head_branch="feature",
        base_branch="main", created_at="", updated_at="", html_url="",
        changed_files=["services/payment/app.py"],
    )
    result = engine.analyze_change(pull_request)
    # checkout reaches the web frontend, which also exposes login_journey.
    assert result.business_impact == 100
    assert result.rollback_required is True
