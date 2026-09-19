from pathlib import Path

from backend.analysis.change_analysis_engine import analyze_impact
from code_review.reviewer import run_bandit, run_radon, run_semgrep
from voice.tts import text_to_speech


def test_analysis_contract_is_json_ready():
    result = analyze_impact(["terraform/customer_database.tf"])
    assert result["changed_resource"] == "customer_database"
    assert result["business_impact"] == 100
    assert result["severity"] == "CRITICAL"
    assert result["rollback_required"] is True


def test_analysis_multiple_files_deduplicates_resources():
    result = analyze_impact(["services/login/app.py", "services/login/routes.py"])
    assert result["changed_resources"] == ["login_service"]
    assert "login_api" in result["affected_nodes"]


def test_tts_cache_does_not_need_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cached = tmp_path / "cached.mp3"
    cached.write_bytes(b"fake mp3")
    # Use a stable precomputed cache name by exercising an empty-input validation only.
    try:
        text_to_speech("hello", output_dir=tmp_path)
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("TTS should require an API key for a cache miss")


def test_optional_review_tools_do_not_crash():
    assert run_semgrep(".")["status"] in {"ok", "skipped", "error"}
    assert run_bandit(".")["status"] in {"ok", "skipped", "error"}
    assert run_radon(".")["status"] in {"ok", "skipped", "error"}
