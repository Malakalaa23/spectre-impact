
#Analytics.py

import streamlit as st
import pandas as pd
import plotly.express as px

from data import (
    repository_prs,
    risk_distribution,
    affected_services,
    risk_over_time
)

from style import apply_style, sidebar, clean_html


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Analytics | Spectre Impact",
    page_icon="📊",
    layout="wide"
)

apply_style()

sidebar("Analytics")


# =========================================================
# HEADER
# =========================================================

st.title("📊 Analytics")

st.caption(
    "Visual insights and trends across analyzed Pull Requests"
)

col1, col2 = st.columns([5, 1])

with col2:
    if st.button("← Dashboard", key="analytics_dashboard"):
        st.switch_page("app.py")

st.markdown("---")


# =========================================================
# KPI
# =========================================================

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Total PRs", "125", "+12")

with c2:
    st.metric("High Risk", "18", "+3")

with c3:
    st.metric("Medium Risk", "20", "+5")

with c4:
    st.metric("Low Risk", "12", "-2")

st.markdown("---")


# =========================================================
# CHART COLORS — same red/amber/green palette used everywhere else
# =========================================================

SEVERITY_COLORS = {
    "HIGH": "#ef4444",
    "MEDIUM": "#f59e0b",
    "LOW": "#22c55e"
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#cbd5e1",
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", y=-0.15)
)


# =========================================================
# ROW 1 — PRs BY REPOSITORY | RISK DISTRIBUTION (DONUT)
# =========================================================

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    with st.container(border=True):

        st.markdown("**📦 PRs by Repository**")

        repo_df = pd.DataFrame({
            "Repository": list(repository_prs.keys()),
            "PRs": list(repository_prs.values())
        })

        st.bar_chart(
            repo_df.set_index("Repository"),
            color="#ef4444"
        )

with row1_col2:
    with st.container(border=True):

        st.markdown("**🎯 Risk Distribution**")

        risk_df = pd.DataFrame({
            "Risk": list(risk_distribution.keys()),
            "PRs": list(risk_distribution.values())
        })

        fig = px.pie(
            risk_df,
            names="Risk",
            values="PRs",
            hole=0.55,
            color="Risk",
            color_discrete_map=SEVERITY_COLORS
        )
        fig.update_traces(textinfo="percent+label", textfont_color="#f8fafc")
        fig.update_layout(**PLOTLY_LAYOUT, showlegend=True)

        st.plotly_chart(fig, use_container_width=True)


# =========================================================
# ROW 2 — MOST AFFECTED SERVICES | RISK TRENDS OVER TIME
# =========================================================

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    with st.container(border=True):

        st.markdown("**🔗 Most Affected Services**")

        services_df = pd.DataFrame({
            "Service": list(affected_services.keys()),
            "Impact": list(affected_services.values())
        })

        st.bar_chart(
            services_df.set_index("Service"),
            color="#f59e0b",
            horizontal=True
        )

with row2_col2:
    with st.container(border=True):

        st.markdown("**📈 Risk Trends Over Time**")

        st.line_chart(
            risk_over_time.set_index("Week"),
            color="#ef4444"
        )


st.markdown("---")


# =========================================================
# INSIGHTS
# =========================================================

st.subheader("💡 Analytics Insights")

a, b, c = st.columns(3)

with a:

    st.markdown(
        clean_html("""
        <div class="red-card">
            <h3>🔴 Highest Risk</h3>
            <h2>PR #445</h2>
            <p>
            Business impact:
            <strong>80%</strong>
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )

with b:

    st.markdown(
        clean_html("""
        <div class="blue-card">
            <h3>🗄️ Most Affected</h3>
            <h2>Payment Service</h2>
            <p>
            28 analyzed impacts
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )

with c:

    st.markdown(
        clean_html("""
        <div class="card">
            <h3>📈 Trend</h3>
            <h2>Risk Increasing</h2>
            <p>
            High-risk PR activity increased
            during the latest analysis period.
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )

st.markdown("---")

st.caption(
    "Analytics powered by Spectre Impact analysis engine."
)
