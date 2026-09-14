import os
from dotenv import load_dotenv
from github import Github, Auth

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High": "🟠",
    "Medium": "🟡",
    "Low": "🟢",
}

VERDICT_EMOJI = {
    "Approved": "✅",
    "Needs Changes": "⚠️",
    "Rejected": "❌",
    "Manual Review Required": "🔄",
    "No Code Changes": "⚪",
}


def format_analysis_comment(bfs_result: dict, ai_result: dict, code_review: dict = None) -> str:
    """
    Format the analysis comment with blast radius, AI insights, and code review.
    """
    severity = ai_result.get("severity", "Unknown")
    emoji = SEVERITY_EMOJI.get(severity, "⚪")

    affected_services = bfs_result.get("affected_services", [])
    business_impact = bfs_result.get("business_impact", "N/A")

    rollback_lines = "\n".join(
        f"- [ ] {step}" for step in ai_result.get("rollback", [])
    ) or "- No rollback steps provided."

    validation_lines = "\n".join(
        f"- [ ] {step}" for step in ai_result.get("validation", [])
    ) or "- No validation steps provided."

    simulation = ai_result.get("simulation", "No simulation available.")

    code_review_section = ""
    if code_review:
        verdict = code_review.get("overall_verdict", "Unknown")
        verdict_emoji = VERDICT_EMOJI.get(verdict, "⚪")
        
        bugs = code_review.get("bugs_found", [])
        bugs_text = "\n".join(f"- {bug}" for bug in bugs) if bugs else "- None detected"
        
        security = code_review.get("security_issues", [])
        security_text = "\n".join(f"- {issue}" for issue in security) if security else "- None detected"
        
        missing_tests = code_review.get("missing_tests", [])
        tests_text = "\n".join(f"- {test}" for test in missing_tests) if missing_tests else "- None detected"
        
        suggestions = code_review.get("suggestions", [])
        suggestions_text = "\n".join(f"- {suggestion}" for suggestion in suggestions) if suggestions else "- No suggestions"
        
        code_review_section = f"""
### 🔍 Code Review
- **Code Quality**: {code_review.get('code_quality', 'Unknown')}
- **Overall Verdict**: {verdict_emoji} {verdict}

**Bugs Found:**
{bugs_text}

**Security Issues:**
{security_text}

**Missing Tests:**
{tests_text}

**Suggestions:**
{suggestions_text}
"""

    return f"""## {emoji} Spectre Impact Analysis — {severity} Severity

### 💥 Blast Radius
- Affected services: {", ".join(affected_services) if affected_services else "None detected"}
- Business impact: {business_impact}%

### 📊 Simulation
{simulation}

{code_review_section}

### 📋 Rollback Plan
{rollback_lines}

### ✅ Validation Checklist
{validation_lines}

---
*Automated analysis by Spectre Impact*
"""


def _get_github():
    """Helper to get authenticated GitHub client."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not set")
    auth = Auth.Token(GITHUB_TOKEN)
    return Github(auth=auth)


def post_github_comment(pr_number: int, repo_name: str, bfs_result: dict, ai_result: dict, code_review: dict = None):
    """
    Post a comment to the PR with the analysis results.
    """
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping comment post.")
            return

        gh = _get_github()
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        comment_body = format_analysis_comment(bfs_result, ai_result, code_review)
        pr.create_issue_comment(comment_body)
        print(f"📝 Posted analysis comment to PR #{pr_number} in {repo_name}")
    except Exception as e:
        print(f"⚠️ Failed to post GitHub comment: {type(e).__name__}: {e}")


def get_pr_for_branch(repo_name: str, branch: str) -> int:
    """
    Find if there's an open PR for this branch.
    Returns the PR number or None.
    """
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN not set — skipping PR lookup.")
        return None
    
    try:
        gh = _get_github()
        repo = gh.get_repo(repo_name)
        owner = repo_name.split("/")[0]
        
        # Try with full head reference: owner:branch
        head_ref = f"{owner}:{branch}"
        pulls = repo.get_pulls(state='open', head=head_ref)
        for pr in pulls:
            return pr.number
        
        # If that fails, try just the branch name
        pulls = repo.get_pulls(state='open')
        for pr in pulls:
            if pr.head.ref == branch:
                return pr.number
        return None
    except Exception as e:
        print(f"⚠️ PR detection failed: {type(e).__name__}: {e}")
        return None


def fetch_commit_diff(repo_name: str, commit_sha: str) -> str:
    """
    Get the unified diff for a specific commit.
    Returns the full diff as a string.
    """
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping diff fetch.")
            return ""

        gh = _get_github()
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)

        diff_parts = []
        for f in commit.files:
            diff_parts.append(f"diff --git a/{f.filename} b/{f.filename}")
            if f.patch:
                diff_parts.append(f.patch)
        return "\n".join(diff_parts)
    except Exception as e:
        print(f"⚠️ Failed to fetch diff for commit {commit_sha}: {type(e).__name__}: {e}")
        return ""


def post_inline_comment(repo_name: str, commit_sha: str, file_path: str, line_number: int, suggestion: str, severity: str):
    """
    Post an inline comment on a specific line of a commit.
    """
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping inline comment post.")
            return

        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        gh = _get_github()
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)

        body = f"{emoji} **{severity} severity** — {suggestion}"
        commit.create_comment(body, path=file_path, position=line_number)
        print(f"📝 Posted inline comment on {file_path} in commit {commit_sha}")
    except Exception as e:
        print(f"⚠️ Failed to post inline comment: {type(e).__name__}: {e}")


# ============================================================
# Quick test
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing github_client functions...")
    
    # Test PR detection
    pr_num = get_pr_for_branch("Malakalaa23/spectre-impact", "feature/test-pr")
    print(f"✅ get_pr_for_branch: {pr_num}")
    
    # Test diff fetch
    diff = fetch_commit_diff("Malakalaa23/spectre-impact", "dbfa8c6")
    print(f"✅ fetch_commit_diff: {len(diff)} characters")
    
    # Test comment formatting
    test_bfs = {
        "affected_services": ["payment_service", "login_service"],
        "business_impact": 80
    }
    test_ai = {
        "severity": "Critical",
        "simulation": "Database fails -> checkout fails",
        "rollback": ["kubectl undo deployment", "git revert"],
        "validation": ["curl /health", "kubectl get pods"]
    }
    test_code_review = {
        "code_quality": "Needs Improvement",
        "overall_verdict": "Needs Changes",
        "bugs_found": ["Null pointer in payment processing"],
        "security_issues": [],
        "missing_tests": ["test_payment_success"],
        "suggestions": ["Add null check"]
    }
    
    comment = format_analysis_comment(test_bfs, test_ai, test_code_review)
    print(f"✅ format_analysis_comment: {len(comment)} characters")
    
    print("\n✅ All tests passed!")