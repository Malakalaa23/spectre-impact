"""
github_client.py — GitHub API helpers for Spectre Impact.

Handles:
  1. Formatting analysis results as memorable, personality-rich PR comments.
  2. Posting PR-level comments.
  3. Posting inline comments on specific lines of a commit.

Design notes:
  - Comments are varied per PR via deterministic randomization (seeded by
    PR number) — the same PR always produces the same comment, but no two
    PRs share the same greeting, quip, or sign-off.
  - Severity drives tone: CRITICAL is urgent, LOW is casual.
  - Emoji used as status markers, never decoration. Every emoji has meaning.
  - GitHub Alerts (`> [!CAUTION]` etc.) provide native colored callouts.
  - Shields.io badges give the top of the comment a professional header.

The vibe: a senior engineer who has seen everything, doesn't panic, and
enjoys their job. Direct, dry, occasionally funny, never unprofessional.
"""

import hashlib
import os
import random
from datetime import datetime, timezone
from typing import Any

from github import Auth, Github, GithubException


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

MAX_COMMENT_CHARS = 60_000
MAX_EVIDENCE_PATHS = 8
MAX_AFFECTED_SERVICES_SHOWN = 25


# ---------------------------------------------------------------------------
# Deterministic randomization
# ---------------------------------------------------------------------------
def _seed_for(*parts) -> random.Random:
    """
    Build a Random instance seeded by the given parts.

    Ensures the same PR always gets the same comment. Different PRs get
    different comments. Deterministic, testable, and pleasant to demo.
    """
    material = "|".join(str(p) for p in parts).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    seed = int(digest[:16], 16)
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Variation pools — grouped by severity tier
# ---------------------------------------------------------------------------
GREETINGS_BY_SEVERITY = {
    "Critical": [
        "🚨 **Yo, this is a big one.**",
        "🚨 **Alright, deep breath. This one's spicy.**",
        "🚨 **Red alert. Someone hold my coffee.**",
        "🚨 **We need to talk about this change.**",
        "🚨 **Grab a chair. This is not a small PR.**",
        "🚨 **Full stop. This one deserves your full attention.**",
        "🚨 **Houston, we have a blast radius.**",
    ],
    "High": [
        "⚠️ **This one's going to leave a mark.**",
        "⚠️ **Not catastrophic, but definitely not chill.**",
        "⚠️ **Heads up — this change has reach.**",
        "⚠️ **This PR is doing a lot. Let's talk.**",
        "⚠️ **Somebody's been busy. Here's what it touches.**",
    ],
    "Medium": [
        "🟡 **Moderate risk. Worth a look before merge.**",
        "🟡 **Not a fire drill, but grab your helmet.**",
        "🟡 **Reasonable change, real blast radius.**",
        "🟡 **Some downstream effects worth knowing about.**",
    ],
    "Low": [
        "🟢 **Small change, small impact. Nice.**",
        "🟢 **Clean PR. Nothing to see here — carry on.**",
        "🟢 **Low risk. Ship it (after the usual checks).**",
        "🟢 **This one's well behaved.**",
    ],
    "Unknown": [
        "🤔 **Severity unclear — worth a manual look.**",
        "🤔 **Unusual change. Can't classify it confidently.**",
    ],
}

SIGNOFFS_BY_SEVERITY = {
    "Critical": [
        "_We checked. So you don't have to._",
        "_Because production is not the place to find out._",
        "_Now you know. Now you can't un-know._",
        "_Sleep better, deploy smarter._",
    ],
    "High": [
        "_Awareness is 90% of the battle._",
        "_Prepared beats surprised. Every time._",
        "_You're welcome. Or, sorry. Depends on the outcome._",
    ],
    "Medium": [
        "_Nothing exploded. Yet._",
        "_Standard vigilance recommended._",
        "_Just the facts, ma'am._",
    ],
    "Low": [
        "_All good. Back to your coffee._",
        "_Business as usual._",
        "_Proceed with confidence._",
    ],
    "Unknown": [
        "_When in doubt, ask a human._",
        "_Uncertainty is honest. Hallucination is not._",
    ],
}

SIMULATION_OPENERS = [
    "🔮 **What likely happens if you ship this:**",
    "🔮 **Best guess at the downstream story:**",
    "🔮 **Here's the simulation, in plain English:**",
    "🔮 **If this change goes wrong, here's how:**",
    "🔮 **The model says, and I quote:**",
]

EVIDENCE_OPENERS = [
    "Here's the trail BFS followed to reach this conclusion:",
    "The engine traced this path from your change to the affected services:",
    "Receipts (because we don't guess):",
    "The hop-by-hop path we computed:",
    "How we know (so you can verify):",
]

NEXT_STEP_OPENERS = [
    "🎯 **What you should actually do:**",
    "🎯 **Action items, in priority order:**",
    "🎯 **If I were you, here's what I'd do:**",
    "🎯 **Your move:**",
]

RISK_TIER_BADGES = {
    "Critical": "critical-red",
    "High": "high-orange",
    "Medium": "medium-yellow",
    "Low": "low-green",
    "Unknown": "unknown-lightgrey",
}


# ---------------------------------------------------------------------------
# Public: format
# ---------------------------------------------------------------------------
def format_analysis_comment(
    bfs_result: dict,
    ai_result: dict,
    code_review: dict | None = None,
    pr_number: int | None = None,
) -> str:
    """
    Build the full PR comment. Varies per PR via deterministic seeding.

    Args:
        bfs_result: Output of analyze_impact().
        ai_result: Output of generate_insights().
        code_review: Output of generate_code_review() or None.
        pr_number: Optional PR number used to seed the randomization so
                   the same PR always gets the same comment.

    Returns:
        Markdown string, ready for GitHub.
    """
    severity = ai_result.get("severity", "Unknown") or "Unknown"
    rng = _seed_for(pr_number, severity, bfs_result.get("changed_resource", ""))

    affected_services = bfs_result.get("affected_services") or []
    business_impact = bfs_result.get("business_impact", 0) or 0
    changed_resource = bfs_result.get("changed_resource", "unknown")
    evidence = bfs_result.get("evidence") or []

    risk_score = _compute_risk_score(severity, business_impact, len(affected_services))

    greeting = rng.choice(GREETINGS_BY_SEVERITY.get(severity, GREETINGS_BY_SEVERITY["Unknown"]))
    signoff = rng.choice(SIGNOFFS_BY_SEVERITY.get(severity, SIGNOFFS_BY_SEVERITY["Unknown"]))
    sim_opener = rng.choice(SIMULATION_OPENERS)
    evi_opener = rng.choice(EVIDENCE_OPENERS)
    next_opener = rng.choice(NEXT_STEP_OPENERS)

    sections = [
        _build_badges(severity, risk_score, business_impact),
        "",
        greeting,
        "",
        _build_headline(changed_resource, len(affected_services), business_impact),
        "",
        _build_alert(severity),
        "",
        "---",
        "",
        _build_blast_radius_table(affected_services, business_impact),
        "",
        _build_evidence_section(evidence, evi_opener),
        "",
        _build_simulation_section(ai_result.get("simulation", ""), sim_opener),
        "",
        _build_code_review_section(code_review),
        "",
        _build_rollback_section(ai_result.get("rollback", [])),
        "",
        _build_validation_section(ai_result.get("validation", [])),
        "",
        _build_next_steps_section(next_opener, severity, affected_services, code_review),
        "",
        _build_signature(signoff),
    ]

    comment = "\n".join(s for s in sections if s is not None).strip()

    if len(comment) > MAX_COMMENT_CHARS:
        comment = comment[: MAX_COMMENT_CHARS - 300] + "\n\n---\n\n*[Comment truncated to fit GitHub's size limit.]*"

    return comment


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def _build_badges(severity: str, risk_score: int, business_impact: int) -> str:
    """Three shields.io badges in a row — the visual header."""
    sev_color = RISK_TIER_BADGES.get(severity, "unknown-lightgrey")
    risk_color = RISK_TIER_BADGES.get(
        "Critical" if risk_score >= 80 else "High" if risk_score >= 60
        else "Medium" if risk_score >= 40 else "Low",
        "unknown-lightgrey",
    )
    imp_color = RISK_TIER_BADGES.get(
        "Critical" if business_impact >= 80 else "High" if business_impact >= 60
        else "Medium" if business_impact >= 40 else "Low",
        "unknown-lightgrey",
    )
    sev_text = severity.upper().replace(" ", "%20")
    return (
        f"![Severity](https://img.shields.io/badge/Severity-{sev_text}-{sev_color}) "
        f"![Risk](https://img.shields.io/badge/Risk-{risk_score}%2F100-{risk_color}) "
        f"![Impact](https://img.shields.io/badge/Impact-{business_impact}%25-{imp_color})"
    )


def _build_headline(changed_resource: str, affected_count: int, business_impact: int) -> str:
    """One-line summary. Reads like a tweet."""
    if affected_count == 0:
        return f"Your change to `{changed_resource}` didn't resolve to any tracked service. Nothing to see here."
    return (
        f"Changing **`{changed_resource}`** affects **{affected_count}** service(s) "
        f"with **{business_impact}%** business impact."
    )


def _build_alert(severity: str) -> str:
    """GitHub-native alert box, matched to severity."""
    if severity == "Critical":
        return (
            "> [!CAUTION]\n"
            "> **DO NOT MERGE without review.** This change touches production-impacting paths."
        )
    if severity == "High":
        return (
            "> [!WARNING]\n"
            "> High-impact change. At least one senior engineer should sign off before merge."
        )
    if severity == "Medium":
        return (
            "> [!IMPORTANT]\n"
            "> Moderate risk. Standard review is fine, but keep an eye on the downstream services."
        )
    if severity == "Low":
        return (
            "> [!NOTE]\n"
            "> Low-risk change. No elevated action required."
        )
    return (
        "> [!NOTE]\n"
        "> Severity could not be classified. A manual glance is recommended."
    )


def _build_blast_radius_table(affected_services: list[str], business_impact: int) -> str:
    """Blast radius as a table with impact meter."""
    meter = _render_impact_meter(business_impact)
    lines: list[str] = [
        "### 📡 Blast Radius",
        "",
        f"**Business impact:** {meter}",
        "",
    ]

    if not affected_services:
        lines.append("_No affected services were detected._")
        return "\n".join(lines)

    # Render services as a table. If we have many, cap and roll the rest.
    inline = affected_services[:MAX_AFFECTED_SERVICES_SHOWN]
    rest = affected_services[MAX_AFFECTED_SERVICES_SHOWN:]

    lines.append("| # | Service | Impact |")
    lines.append("|---|---------|:------:|")
    for i, svc in enumerate(inline, start=1):
        marker = _impact_marker_for_service(i, len(inline))
        lines.append(f"| {i} | `{svc}` | {marker} |")

    if rest:
        lines.append(f"| ... | _and {len(rest)} more_ | |")

    return "\n".join(lines)


def _build_evidence_section(evidence: list, opener: str) -> str:
    """Evidence chain in a collapsible, with a fixed-width code block."""
    paths = [p for p in evidence if isinstance(p, list) and p]
    if not paths:
        return ""

    sorted_paths = sorted(paths, key=len)
    shown = sorted_paths[:MAX_EVIDENCE_PATHS]
    hidden_count = max(0, len(sorted_paths) - MAX_EVIDENCE_PATHS)

    body_lines = [opener, "", "```"]
    for path in shown:
        body_lines.append(" → ".join(path))
    if hidden_count:
        body_lines.append(f"... and {hidden_count} more")
    body_lines.append("```")

    body = "\n".join(body_lines)

    return (
        "### 🕵️ Evidence Chain\n\n"
        "<details><summary>🔍 <b>Show the trail</b></summary>\n\n"
        f"{body}\n\n"
        "</details>"
    )


def _build_simulation_section(simulation: str, opener: str) -> str:
    """AI simulation as a blockquote. Personality comes from the opener."""
    if not simulation or not simulation.strip():
        return ""

    quoted = "\n".join(f"> {line}" for line in simulation.strip().splitlines())
    return f"### {opener}\n\n{quoted}"


def _build_code_review_section(code_review: dict | None) -> str:
    """Code review, collapsible, with counts and emoji markers."""
    if not code_review:
        return ""

    verdict = code_review.get("overall_verdict", "Unknown")
    quality = code_review.get("code_quality", "Unknown")
    verdict_badge = _verdict_badge(verdict)

    bugs = code_review.get("bugs_found") or []
    security = code_review.get("security_issues") or []
    missing = code_review.get("missing_tests") or []
    suggestions = code_review.get("suggestions") or []

    total_findings = len(bugs) + len(security) + len(missing)

    lines: list[str] = [
        "### 🔎 Code Review",
        "",
        f"**Verdict:** {verdict_badge} · **Quality:** {quality}",
        "",
    ]

    if total_findings == 0:
        lines.append("_The review found nothing alarming. Cleaner than most PRs we see._")
        return "\n".join(lines)

    lines.append(f"<details><summary>📋 <b>Show full review ({total_findings} finding(s))</b></summary>")
    lines.append("")
    lines.extend(_render_finding_block("🐛 Bugs", bugs, "None detected"))
    lines.append("")
    lines.extend(_render_finding_block("🔐 Security", security, "None detected"))
    lines.append("")
    lines.extend(_render_finding_block("📝 Missing Tests", missing, "None detected"))
    lines.append("")
    lines.extend(_render_finding_block("💡 Suggestions", suggestions, "No suggestions"))
    lines.append("")
    lines.append("</details>")

    return "\n".join(lines)


def _build_rollback_section(rollback: list) -> str:
    lines = ["### ⏪ Rollback Plan", ""]
    if not rollback:
        lines.append("_No rollback steps provided. YOLO, apparently._")
        return "\n".join(lines)
    lines.append("_If this blows up (and it might), here's how to undo it:_")
    lines.append("")
    for step in rollback:
        lines.append(f"- [ ] {step}")
    lines.append("")
    lines.append("_Pro tip: keep this window open during deploy._")
    return "\n".join(lines)


def _build_validation_section(validation: list) -> str:
    lines = ["### ✅ Validation Checklist", ""]
    if not validation:
        lines.append("_No validation steps provided._")
        return "\n".join(lines)
    lines.append("_Before you call this done, verify:_")
    lines.append("")
    for step in validation:
        lines.append(f"- [ ] {step}")
    return "\n".join(lines)


def _build_next_steps_section(
    opener: str,
    severity: str,
    affected_services: list[str],
    code_review: dict | None,
) -> str:
    steps: list[str] = []

    if severity in ("Critical", "High"):
        steps.append(
            "**Get a second pair of eyes.** At this severity, no single engineer should merge alone."
        )
    elif severity == "Medium":
        steps.append(
            "**Give the team a heads-up.** A quick ping in the channel goes a long way."
        )
    else:
        steps.append("**Proceed with the usual review.** No elevated action needed.")

    if affected_services:
        first = affected_services[0]
        steps.append(
            f"**Smoke-test `{first}` after deploy.** It's the first hop in the evidence chain — "
            f"if it's broken, everything downstream is too."
        )

    if code_review:
        verdict = code_review.get("overall_verdict", "")
        if verdict in ("Request Changes", "Reject"):
            steps.append("**Address the code review findings.** The AI reviewer flagged blocking issues.")
        elif code_review.get("security_issues"):
            steps.append("**Review the security findings.** They may need mitigation before merge.")

    steps = steps[:3]

    lines = [opener, ""]
    for i, step in enumerate(steps, start=1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)


def _build_signature(signoff: str) -> str:
    base_url = (os.getenv("SPECTRE_PUBLIC_URL") or "").strip().rstrip("/")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    chat_link = (
        f"[💬 Ask Lya about this change]({base_url}/chat)"
        if base_url else "💬 Ask Lya in the chat endpoint"
    )
    return (
        "---\n\n"
        f"*🤖 Spectre Impact · {timestamp} · {chat_link}*\n\n"
        f"<sub>{signoff}</sub>"
    )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _render_impact_meter(percent: int) -> str:
    pct = max(0, min(int(percent), 100))
    filled = round(pct / 5)
    bar = "█" * filled + "░" * (20 - filled)
    label = (
        "Critical" if pct >= 80 else
        "High" if pct >= 60 else
        "Moderate" if pct >= 40 else
        "Low" if pct >= 20 else
        "Minimal"
    )
    emoji = (
        "🔴" if pct >= 80 else
        "🟠" if pct >= 60 else
        "🟡" if pct >= 40 else
        "🟢"
    )
    return f"`{bar}` {pct}% · {emoji} {label}"


def _impact_marker_for_service(index: int, total: int) -> str:
    """Assign a visually descending marker to services by position."""
    if total == 0:
        return "⚪"
    ratio = index / total
    if ratio <= 0.25:
        return "🔴"
    if ratio <= 0.6:
        return "🟠"
    if ratio <= 0.85:
        return "🟡"
    return "🟢"


def _verdict_badge(verdict: str) -> str:
    if verdict in ("Approve", "Approved"):
        return "🟢 **PASS**"
    if verdict in ("Needs Review", "Manual Review Required"):
        return "🟡 **REVIEW**"
    if verdict in ("Request Changes", "Reject"):
        return "🔴 **BLOCK**"
    return "⚪ **UNKNOWN**"


def _render_finding_block(header: str, items: list, empty_msg: str) -> list[str]:
    if not items:
        return [f"**{header}:** {empty_msg}"]
    lines = [f"**{header}:**"]
    for item in items:
        lines.append(f"- {item}")
    return lines


def _compute_risk_score(severity: str, business_impact: int, affected_count: int) -> int:
    sev_map = {"Critical": 100, "High": 75, "Medium": 50, "Low": 25}
    sev = sev_map.get(severity, 0)
    count_factor = min(affected_count, 20) / 20 * 100
    impact_factor = min(max(business_impact, 0), 100)
    return int(round(0.4 * sev + 0.4 * impact_factor + 0.2 * count_factor))


# ---------------------------------------------------------------------------
# Public: GitHub actions
# ---------------------------------------------------------------------------
def _get_github() -> Github:
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not set")
    return Github(auth=Auth.Token(GITHUB_TOKEN))


def post_github_comment(
    pr_number: int,
    repo_name: str,
    bfs_result: dict,
    ai_result: dict,
    code_review: dict | None = None,
) -> None:
    """Post the analysis as a PR comment. Never raises."""
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set — skipping comment post.")
        return

    try:
        gh = _get_github()
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        body = format_analysis_comment(bfs_result, ai_result, code_review, pr_number=pr_number)
        pr.create_issue_comment(body)
        print(f"Posted analysis comment to PR #{pr_number} in {repo_name}")
    except GithubException as e:
        print(f"GitHub API error posting comment: {e.status} — {e.data}")
    except Exception as e:
        print(f"Failed to post GitHub comment: {type(e).__name__}: {e}")


def get_pr_for_branch(repo_name: str, branch: str) -> int | None:
    """Find the open PR number for a branch, or None."""
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set — skipping PR lookup.")
        return None

    try:
        gh = _get_github()
        repo = gh.get_repo(repo_name)
        owner = repo_name.split("/")[0]
        for head_ref in (f"{owner}:{branch}", branch):
            for pr in repo.get_pulls(state="open", head=head_ref):
                return pr.number
        return None
    except GithubException as e:
        print(f"GitHub API error looking up PR: {e.status} — {e.data}")
        return None
    except Exception as e:
        print(f"Unexpected error in get_pr_for_branch: {e}")
        return None


def post_inline_comment(
    repo_name: str,
    commit_sha: str,
    file_path: str,
    line_number: int,
    suggestion: str,
    severity: str,
) -> None:
    """Post an inline comment on a specific line of a commit."""
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set — skipping inline comment post.")
        return

    marker = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(severity, "⚪")
    body = f"{marker} **{severity}** — {suggestion}"

    try:
        gh = _get_github()
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)
        commit.create_comment(body, path=file_path, position=line_number)
        print(f"Posted inline comment on {file_path} in commit {commit_sha[:7]}")
    except GithubException as e:
        print(f"GitHub API error posting inline comment: {e.status} — {e.data}")
    except Exception as e:
        print(f"Failed to post inline comment: {type(e).__name__}: {e}")


def fetch_commit_diff(repo_name: str, commit_sha: str) -> str:
    """Fetch the unified diff for a commit. Returns '' on failure."""
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set — cannot fetch diff.")
        return ""

    try:
        gh = _get_github()
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(commit_sha)
        patches: list[str] = []
        for f in commit.files:
            if f.patch:
                patches.append(f"--- {f.filename}\n{f.patch}")
        return "\n".join(patches)
    except GithubException as e:
        print(f"GitHub API error fetching diff: {e.status} — {e.data}")
        return ""
    except Exception as e:
        print(f"Unexpected error fetching diff: {e}")
        return ""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_bfs = {
        "changed_resource": "customer_database",
        "affected_services": ["checkout_api", "payment_service", "login_service", "web_frontend"],
        "business_impact": 100,
        "evidence": [
            ["customer_database", "login_service"],
            ["customer_database", "login_service", "checkout_api"],
            ["customer_database", "payment_service", "checkout_api", "web_frontend"],
        ],
    }
    sample_ai = {
        "severity": "Critical",
        "simulation": "A change to customer_database will cascade through login and payment flows.",
        "rollback": ["Revert the Terraform change", "Restart affected services"],
        "validation": ["Check /health on checkout_api", "Verify login flow end-to-end"],
    }
    sample_review = {
        "code_quality": "Fair",
        "overall_verdict": "Request Changes",
        "bugs_found": ["Hardcoded credentials in diff"],
        "security_issues": ["publicly_accessible = true"],
        "missing_tests": ["No integration test for payment flow"],
        "suggestions": ["Move credentials to environment variables"],
    }

    # Render 3 variants for the same PR — should be identical (deterministic)
    for pr in (5, 5, 5):
        body = format_analysis_comment(sample_bfs, sample_ai, sample_review, pr_number=pr)
        print(f"PR #{pr}: {len(body)} chars, seed preview: {body[200:400].strip()[:80]!r}")
    print()

    # Show full output for PR #5
    full = format_analysis_comment(sample_bfs, sample_ai, sample_review, pr_number=5)
    print(full)