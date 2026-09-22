"""Tests for the rollback executor's safety logic.

Run with: pytest tests/test_rollback.py -v
Requires DATABASE_URL pointing at a running Postgres with init_db() applied,
since execute_rollback() writes to the audit log table.
"""

from rollback_executor import validate_command, execute_rollback


def test_blocks_dangerous_commands():
    result = validate_command("rm -rf /")
    assert result.safe is False


def test_blocks_injection_attempts():
    result = validate_command("kubectl rollout undo deployment/payment-service; rm -rf /")
    assert result.safe is False


def test_allows_whitelisted_commands():
    result = validate_command("kubectl rollout undo deployment/payment-service")
    assert result.safe is True


def test_dry_run_executes_without_side_effects():
    result = execute_rollback(
        ["kubectl rollout undo deployment/payment-service"],
        dry_run=True,
    )
    assert result["results"][0]["status"] == "dry_run_ok"


def test_blocked_command_is_logged_not_executed():
    result = execute_rollback(["rm -rf /"], dry_run=False)
    assert result["results"][0]["status"] == "blocked"
