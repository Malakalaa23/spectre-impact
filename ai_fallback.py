"""Safe local AI-style fallback.
A real AI endpoint can be configured later; the dashboard never depends on it
being available to render an analysis."""

from bfs import calculate_blast_radius


def analyze_change(changed_files, severity="UNKNOWN"):
    services = calculate_blast_radius(changed_files)
    if not services:
        return {
            "problem": "No known service dependency was detected from the changed files.",
            "summary": "The change needs manual review because the local dependency map has no matching service.",
            "affected_services": [],
        }
    risk = severity if severity in {"HIGH", "MEDIUM", "LOW"} else "UNKNOWN"
    service_text = ", ".join(services[:3])
    problem = (
        f"This {risk.lower()}-risk change may affect {service_text}. "
        "Validate the affected services before deployment."
    )
    return {
        "problem": problem,
        "summary": (
            f"The dependency analysis found a potential blast radius across {service_text}. "
            "The AI fallback recommends health checks and rollback readiness before release."
        ),
        "affected_services": services,
    }
