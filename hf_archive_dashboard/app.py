#app.py

import streamlit as st

from data import pr_data
from style import apply_style, sidebar, clean_html, metric_card


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Spectre Impact",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_style()

sidebar("Dashboard")


# =========================================================
# HEADER
# =========================================================

header_col1, header_col2 = st.columns([5, 1])

with header_col1:

    st.markdown(
        '<div class="main-title">🚀 Spectre Impact</div>',
        unsafe_allow_html=True
    )

    st.caption(
        "Real-time overview of your infrastructure changes"
    )

with header_col2:

    st.markdown(
        clean_html("""
        <div class="live-badge">
            ● LIVE
        </div>
        """),
        unsafe_allow_html=True
    )

st.markdown("---")


# =========================================================
# EXECUTIVE DASHBOARD — KPI CARDS
# =========================================================

st.subheader("📊 Executive Dashboard")

metric1, metric2, metric3, metric4 = st.columns(4)

with metric1:
    st.markdown(
        metric_card("📄", "125", "Total PRs", "12% this week", positive=True),
        unsafe_allow_html=True
    )

with metric2:
    st.markdown(
        metric_card("⚠️", "18", "High Risk PRs", "3 this week", positive=False),
        unsafe_allow_html=True
    )

with metric3:
    st.markdown(
        metric_card("📦", "6", "Repositories", "No change"),
        unsafe_allow_html=True
    )

with metric4:
    st.markdown(
        metric_card("🕒", "PR #445", "Last Analysis", "2 minutes ago"),
        unsafe_allow_html=True
    )

st.markdown("---")


# =========================================================
# CRITICAL ALERTS — horizontal alert bar
# =========================================================

alert_text_col, alert_btn_col = st.columns([5, 1])

with alert_text_col:
    st.markdown(
        clean_html("""
        <div class="alert-bar">
            ⚠️ 3 High Risk PRs require immediate attention
        </div>
        """),
        unsafe_allow_html=True
    )

with alert_btn_col:
    if st.button("View All Alerts", key="view_all_alerts", use_container_width=True):
        st.session_state["selected_pr"] = "#445"
        st.switch_page("pages/PR_Analysis.py")

st.markdown("")


with st.expander("🔴 PR #445 — Highest priority alert", expanded=False):

    st.markdown(
        clean_html("""
        <div class="risk-card">
            🔴 <strong>HIGH RISK — PR #445</strong>
            <br><br>
            Database migration may affect:
            <br>• Login Service
            <br>• Payment Gateway
            <br>• Main Database
            <br><br>
            <strong>Business Impact: 80%</strong>
        </div>
        """),
        unsafe_allow_html=True
    )

st.markdown("---")


# =========================================================
# RECENT PR ANALYSES
# =========================================================

st.subheader("📋 Recent PR Analyses")

st.caption(
    "Latest Pull Requests analyzed by Spectre Impact"
)

# Table header

h1, h2, h3, h4, h5, h6 = st.columns([1, 2, 1.4, 1, 1.5, 1])

with h1:
    st.caption("PR")

with h2:
    st.caption("Repository")

with h3:
    st.caption("Severity")

with h4:
    st.caption("Impact")

with h5:
    st.caption("Date")

with h6:
    st.caption("Action")


# =========================================================
# PR ROWS
# =========================================================

for _, row in pr_data.iterrows():

    c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 1.4, 1, 1.5, 1])

    with c1:
        st.write(f"**PR {row['PR']}**")

    with c2:
        st.write(row["Repository"])

    with c3:
        if row["Severity"] == "HIGH":
            st.markdown("🔴 **HIGH**")
        elif row["Severity"] == "MEDIUM":
            st.markdown("🟠 **MEDIUM**")
        else:
            st.markdown("🟢 **LOW**")

    with c4:
        st.write(row["Impact"])

    with c5:
        st.write(row["Date"])

    with c6:
        if st.button(
            "Inspect",
            key=f"inspect_{row['PR']}",
            use_container_width=True
        ):
            st.session_state["selected_pr"] = row["PR"]
            st.switch_page("pages/PR_Analysis.py")

    st.divider()


# =========================================================
# ANALYSIS SOURCE
# =========================================================

st.markdown(
    clean_html("""
    <div class="source-box">
        <div class="source-title">
            🔍 Analysis powered by
        </div>
        <div class="source-item">
            <span class="bfs-dot">●</span>
            <strong>BFS Engine</strong>
            &nbsp; Deterministic blast radius calculation
        </div>
        <div class="source-item">
            <span class="ai-dot">●</span>
            <strong>AI Agent</strong>
            &nbsp; Impact intelligence and recommendations
        </div>
    </div>
    """),
    unsafe_allow_html=True
)

st.markdown("---")


# =========================================================
# QUICK INSIGHTS
# =========================================================

st.subheader("💡 Quick Insights")

insight1, insight2, insight3 = st.columns(3)

with insight1:

    st.markdown(
        clean_html("""
        <div class="insight-card">
            <h4>🗄️ Most Affected Service</h4>
            <h3>Main Database</h3>
            <span style="color:#94a3b8;">
                3 services depend on it.
            </span>
        </div>
        """),
        unsafe_allow_html=True
    )

with insight2:

    st.markdown(
        clean_html("""
        <div class="insight-card">
            <h4>🔴 Highest Risk</h4>
            <h3>PR #445</h3>
            <span style="color:#f87171;">
                Business Impact: 80%
            </span>
        </div>
        """),
        unsafe_allow_html=True
    )

with insight3:

    st.markdown(
        clean_html("""
        <div class="insight-card">
            <h4>🟢 System Status</h4>
            <h3>Analysis Engine Online</h3>
            <span style="color:#4ade80;">
                Last analysis: 2 minutes ago
            </span>
        </div>
        """),
        unsafe_allow_html=True
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.markdown(
    clean_html("""
    <div class="footer">
        <strong>Spectre Impact</strong>
        <br>
        AI-Powered GitHub Change Intelligence
        <br><br>
        BFS Engine + AI Agent + GitHub Integration
        <br><br>
        DevOpsDays Hackathon 2026
    </div>
    """),
    unsafe_allow_html=True
)
