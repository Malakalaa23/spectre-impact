"""Reusable live filters for the developer dashboard."""


def filter_prs(prs, severity="All", repository="All", developer="All"):
    result = list(prs or [])
    if severity != "All":
        result = [pr for pr in result if pr.get("severity") == severity]
    if repository != "All":
        result = [pr for pr in result if pr.get("repository") == repository]
    if developer != "All":
        result = [pr for pr in result if pr.get("author") == developer]
    return result
