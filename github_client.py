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


def get_pr_for_branch(repo_name: str, branch: str):
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping PR lookup.")
            return None

        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        owner = repo_name.split("/")[0]
        pulls = repo.get_pulls(state="open", head=f"{owner}:{branch}")
        for pr in pulls:
            return pr.number
        return None
    except Exception as e:
        print(f"⚠️ Failed to look up PR for branch {branch}: {type(e).__name__}: {e}")
        return None


def fetch_commit_diff(repo_name: str, commit_sha: str) -> str:
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping diff fetch.")
            return ""

        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)

        # PyGithub doesn't expose the full raw unified diff for a commit directly —
        # reassemble one from each file's patch so parse_unified_diff can consume it.
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
    # NOTE: GitHub's commit-comment API expects a diff "position" (an offset into
    # the patch hunk), not a file line number. Correctly mapping a file line number
    # to a position requires re-walking the same hunk it came from. This is a
    # simplified best-effort mapping (position == line_number) — it works for
    # simple single-hunk diffs but is NOT a fully correct general position mapper.
    try:
        if not GITHUB_TOKEN:
            print("⚠️ GITHUB_TOKEN not set — skipping inline comment post.")
            return

        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)

        body = f"{emoji} **{severity} severity** — {suggestion}"
        commit.create_comment(body, path=file_path, position=line_number)
        print(f"📝 Posted inline comment on {file_path} in commit {commit_sha}")
    except Exception as e:
        print(f"⚠️ Failed to post inline comment: {type(e).__name__}: {e}")
