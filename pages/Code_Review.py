import streamlit as st

from data import get_pr_data, get_pr_details
from api_client import post_json_detailed
from style import apply_style, sidebar, empty_state, severity_badge_html
from components.code_review import render_finding, render_diffs

st.set_page_config(page_title="Code Review | Spectre", page_icon="🔍", layout="wide")
apply_style()
sidebar("Code Review")

prs = get_pr_data()
if not prs:
    st.markdown(
        empty_state("📭", "No PRs available", "Waiting for analyzed changes."),
        unsafe_allow_html=True,
    )
    st.stop()

selected = st.selectbox(
    "Pull Request",
    [p["pr_number"] for p in prs],
    key="review_pr",
    help="Choose a pull request to review.",
)
d = get_pr_details(selected)

st.title("🔍 AI Code Review")
st.caption(f"Reviewing {selected} · {d['repository']}")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Changed Files", len(d["changed_files"]))
with c2:
    st.metric("Affected Services", len(d["affected_services"]))
with c3:
    st.markdown(severity_badge_html(d["severity"]), unsafe_allow_html=True)

if "review_running" not in st.session_state:
    st.session_state.review_running = False

if st.button(
    "✨ Run AI Code Review",
    type="primary",
    use_container_width=True,
    disabled=st.session_state.review_running,
    help="Run the AI review for the selected pull request.",
):
    st.session_state.review_running = True
    try:
        progress = st.progress(0, text="Starting review...")
        progress.progress(10, text="Running static analysis...")
        with st.spinner("This may take up to 120 seconds..."):
            ok, result, status = post_json_detailed(
                "/api/review",
                {
                    "pr_number": selected,
                    "repository": d["repository"],
                    "changed_files": d["changed_files"],
                },
                timeout=120,
            )
        progress.progress(100, text="Review complete.")
        if ok:
            st.session_state["code_review_result"] = result
            st.session_state["code_review_pr"] = selected
        else:
            st.session_state["code_review_result"] = None
            st.warning(
                "Review API is not connected yet. Showing the existing PR analysis below."
            )
    finally:
        st.session_state.review_running = False

r = (
    st.session_state.get("code_review_result")
    if st.session_state.get("code_review_pr") == selected
    else None
) or {}

st.subheader("🤖 AI Summary")
st.info(
    r.get("summary")
    or d.get("ai_analysis")
    or d.get("summary")
    or "No AI review summary available yet."
)

findings = r.get("findings") or r.get("issues") or []
if findings:
    st.subheader(f"Findings · {len(findings)}")
    for i, finding in enumerate(findings, 1):
        render_finding(
            finding if isinstance(finding, dict) else {"message": str(finding)},
            i,
        )
else:
    st.subheader("💡 Recommendations")
    for item in d["validation"] or ["Connect the Code Review API to receive AI findings."]:
        st.write("• " + item)

st.subheader("📁 Changed Files")
for file_name in d["changed_files"] or ["No changed files reported"]:
    st.code(str(file_name), language="text")

st.subheader("📝 Diff Viewer")
render_diffs(
    r.get("diffs")
    or r.get("diff")
    or r.get("patches")
    or r.get("patch")
)
