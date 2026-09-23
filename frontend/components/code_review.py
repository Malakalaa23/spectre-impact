import html
import os
import streamlit as st


def _severity_class(severity):
    return {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
    }.get(str(severity or "INFO").upper(), "info")


def _language_for_file(filename):
    ext = os.path.splitext(str(filename).lower())[1]
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "tsx", ".jsx": "jsx", ".json": "json", ".yaml": "yaml",
        ".yml": "yaml", ".md": "markdown", ".html": "html", ".css": "css",
        ".sql": "sql", ".sh": "bash", ".ps1": "powershell", ".tf": "hcl",
        ".java": "java", ".go": "go", ".rs": "rust", ".cpp": "cpp", ".c": "c",
    }.get(ext, "text")


def render_finding(finding, index):
    """Render one code-review finding."""
    severity = str(finding.get("severity", "INFO")).upper()
    title = finding.get("title") or finding.get("message") or f"Finding {index}"
    location = finding.get("file") or finding.get("path") or ""
    line = finding.get("line") or finding.get("line_number")
    if location and line:
        location = f"{location}:{line}"
    details = (
        finding.get("details")
        or finding.get("description")
        or finding.get("recommendation")
        or ""
    )

    safe_severity = html.escape(str(severity))
    safe_title = html.escape(str(title))
    safe_location = html.escape(str(location))

    st.markdown(
        f'<div class="spectre-finding spectre-finding-{_severity_class(severity)}">'
        f'<div class="spectre-finding-title">{safe_severity} · {safe_title}</div>'
        f'<div class="spectre-finding-meta">{safe_location}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if details:
        st.write(details)


def render_diffs(diffs):
    """Render the changed lines from a code diff."""
    if not diffs:
        st.markdown(
            "<div class='card'><b>Diff waiting for backend data</b><br>"
            "<span style='color:#64748b'>The review API must return a patch/diff "
            "or file content to populate this viewer.</span></div>",
            unsafe_allow_html=True,
        )
        return

    if isinstance(diffs, str):
        st.code(diffs, language="diff")
        return

    if isinstance(diffs, dict):
        diffs = [diffs]

    for item in diffs:
        if isinstance(item, str):
            st.code(item, language="diff")
            continue

        filename = (
            item.get("file")
            or item.get("filename")
            or item.get("path")
            or "Changed file"
        )
        patch = item.get("patch") or item.get("diff") or item.get("content") or ""
        is_diff = bool(item.get("patch") or item.get("diff"))
        with st.expander(str(filename), expanded=True):
            st.code(
                patch or "No patch returned.",
                language="diff" if is_diff else _language_for_file(filename),
            )

