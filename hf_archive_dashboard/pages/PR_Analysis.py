#PR_Analysis.py

import streamlit as st

from data import pr_details
from style import apply_style, sidebar, clean_html


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="PR Analysis | Spectre Impact",
    page_icon="🔍",
    layout="wide"
)

apply_style()

sidebar("PR Analysis")


# =========================================================
# SELECTED PR
# =========================================================

if "selected_pr" not in st.session_state:
    st.session_state["selected_pr"] = "#445"

selected_pr = st.session_state["selected_pr"]
details = pr_details[selected_pr]


# =========================================================
# BREADCRUMB HEADER
# =========================================================

title_col, action_col1, action_col2 = st.columns([4, 1, 1])

with title_col:
    st.markdown(
        f'<div class="breadcrumb-title">PR Analysis <span>→</span> {selected_pr}</div>',
        unsafe_allow_html=True
    )
    st.caption("Deep analysis of repository changes and deployment impact")

with action_col1:
    if st.button(
        "← Back to List",
        key="back_dashboard",
        use_container_width=True
    ):
        st.switch_page("app.py")

with action_col2:
    if st.button(
        "🚀 Post to GitHub",
        key="post_github",
        use_container_width=True
    ):
        st.success(f"Analysis comment posted to {selected_pr}.")

st.markdown("---")


# =========================================================
# PR HEADER CARD
# =========================================================

st.markdown(
    clean_html(f"""
    <div class="red-card">
        <h2>{selected_pr} Analysis Details</h2>
        <span class="high-badge">🔴 {details["severity"]} RISK</span>
        &nbsp;
        <span class="impact-badge">Business Impact: {details["impact"]}%</span>
        <p style="margin-top:12px;">
            Repository: <strong>{details["repository"]}</strong>
        </p>
    </div>
    """),
    unsafe_allow_html=True
)

st.markdown("")


# =========================================================
# MAIN LAYOUT — LEFT (summary/services/simulation) | RIGHT (files/rollback/validation)
# =========================================================

left_col, right_col = st.columns([1.3, 1])


# ---------------------------------------------------------
# LEFT COLUMN
# ---------------------------------------------------------

with left_col:

    st.subheader("📊 Analysis Summary")

    view = st.radio(
        "View as",
        ["🔧 DevOps Engineer", "👔 Executive"],
        horizontal=True,
        key="pr_summary_view"
    )

    if view == "🔧 DevOps Engineer":

        st.info(f"""
        **Technical Summary**

        {details["summary"]}

        The BFS engine identifies the affected dependency
        chain, while the AI Agent generates the impact
        simulation and recommendations.
        """)

    else:

        st.success(f"""
        **Executive Summary**

        {selected_pr} has a **{details["severity"]}** risk level
        with an estimated business impact of
        **{details["impact"]}%**.

        Review is recommended before deployment.
        """)

    st.subheader("🔗 Affected Microservices")

    service_cols = st.columns(len(details["services"]))

    for col, service in zip(service_cols, details["services"]):

        with col:

            st.markdown(
                clean_html(f"""
                <div class="blue-card">
                    🔗
                    <strong>{service}</strong>
                </div>
                """),
                unsafe_allow_html=True
            )

    st.subheader("🛡️ Impact Simulation")

    flow_html = '<div class="flow-wrap">'

    for index, step in enumerate(details["simulation"]):

        flow_html += f'<div class="flow-box">{step}</div>'

        if index < len(details["simulation"]) - 1:
            flow_html += '<div class="flow-arrow">→</div>'

    flow_html += '</div>'

    st.markdown(clean_html(flow_html), unsafe_allow_html=True)

    st.caption(
        "AI-generated simulation of what could happen if this deployment fails."
    )


# ---------------------------------------------------------
# RIGHT COLUMN
# ---------------------------------------------------------

with right_col:

    st.subheader("📁 Changed Files")

    with st.container(border=True):
        for file in details["changed_files"]:
            st.markdown(f"🔹 `{file}`")

    st.markdown("")

    st.subheader("📋 Rollback Plan")

    with st.container(border=True):
        for index, step in enumerate(details["rollback"]):
            st.write(f"**{index + 1}.** {step}")

    st.markdown("")

    st.subheader("✅ Validation Checklist")

    with st.container(border=True):
        st.checkbox("curl /health", key=f"health_{selected_pr}")
        st.checkbox("kubectl get pods", key=f"pods_{selected_pr}")
        st.checkbox("Check application logs", key=f"logs_{selected_pr}")


# =========================================================
# ANALYSIS SOURCE
# =========================================================

st.markdown("---")

st.markdown(
    clean_html("""
    <div class="card">
        <strong>🔍 Analysis powered by</strong>
        <br><br>
        <span style="color:#22c55e;">
            ● BFS Engine
        </span>
        &nbsp; Deterministic blast radius calculation
        <br><br>
        <span style="color:#a855f7;">
            ● AI Agent
        </span>
        &nbsp; Impact simulation, summaries and recommendations
    </div>
    """),
    unsafe_allow_html=True
)
