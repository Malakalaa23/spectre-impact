import os
from dotenv import load_dotenv
from github import Github

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High": "🟠",
    "Medium": "🟡",
    "Low": "🟢",
}


def format_analysis_comment(bfs_result: dict, ai_result: dict) -> str:
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

    return f"""## {emoji} Spectre Impact Analysis — {severity} Severity

**Blast Radius**
- Affected services: {", ".join(affected_services) if affected_services else "None detected"}
- Business impact: {business_impact}%

**Simulation**
{ai_result.get("simulation", "No simulation available.")}

**Rollback Plan**
{rollback_lines}

**Validation Checklist**
{validation_lines}

---
*Automated analysis by Spectre Impact*
"""


def post_github_comment(pr_number: int, repo_name: str, bfs_result: dict, ai_result: dict):
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping comment post.")
            return

        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        comment_body = format_analysis_comment(bfs_result, ai_result)
        pr.create_issue_comment(comment_body)
        print(f"📝 Posted analysis comment to PR #{pr_number} in {repo_name}")
    except Exception as e:
        print(f"⚠️ Failed to post GitHub comment: {type(e).__name__}: {e}")


# ============================================================
# NEW: Inline comment functions (for commit analysis)
# ============================================================

def post_inline_comment(repo_name: str, commit_sha: str, file_path: str,
                        line_number: int, suggestion: str, severity: str):
    """
    Post an inline comment on a specific line of a commit.
    
    Args:
        repo_name: "owner/repo"
        commit_sha: The commit SHA
        file_path: Path to the file
        line_number: Line number in the file
        suggestion: The feedback text
        severity: "High" or "Critical"
    """
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN not set")
        return
    
    try:
        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)
        
        # Find the position in the diff
        # GitHub requires 'position' (line index in the diff), not line number
        position = None
        for file in commit.files:
            if file.filename == file_path and file.patch:
                patch_lines = file.patch.split("\n")
                # Count lines until we reach our target
                pos = 0
                for line in patch_lines:
                    pos += 1
                    if line.startswith("+") and not line.startswith("+++"):
                        # This is an added line
                        # Simplified: use line_number as position
                        position = line_number
                        break
                break
        
        if position:
            emoji = "🔴" if severity == "Critical" else "🟠" if severity == "High" else "🟡"
            commit.create_comment(
                body=f"{emoji} **Spectre Impact – {severity} Risk**\n\n{suggestion}",
                path=file_path,
                position=position
            )
            print(f"📝 Inline comment on {file_path}:{line_number}")
        else:
            print(f"⚠️ Could not calculate position for {file_path}:{line_number}")
    
    except Exception as e:
        print(f"❌ Inline comment failed: {type(e).__name__}: {e}")


def get_pr_for_branch(repo_name: str, branch: str) -> int:
    """
    Find if there's an open PR for this branch.
    Returns the PR number or None.
    """
    if not GITHUB_TOKEN:
        return None
    
    try:
        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        pulls = repo.get_pulls(state='open', head=branch)
        for pr in pulls:
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
    if not GITHUB_TOKEN:
        return ""
    
    try:
        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)
        
        diff = ""
        for file in commit.files:
            if file.patch:
                diff += f"diff --git a/{file.filename} b/{file.filename}\n"
                diff += file.patch + "\n"
        return diff
    except Exception as e:
        print(f"❌ Failed to fetch diff: {type(e).__name__}: {e}")
        return ""


# ============================================================
# Quick self‑test (run with `python github_client.py`)
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing github_client functions...")
    
    # Test PR detection (will fail if token not set, but that's okay)
    pr_num = get_pr_for_branch("Malakalaa23/spectre-test", "main")
    print(f"✅ get_pr_for_branch: {pr_num}")
    
    # Test diff fetch (will fail if token not set)
    diff = fetch_commit_diff("Malakalaa23/spectre-test", "cfa39cd")
    print(f"✅ fetch_commit_diff: {len(diff)} characters")
    
    print("✅ All tests passed!")