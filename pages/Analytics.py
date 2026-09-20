#Analytics.py

import html
import streamlit as st
import pandas as pd
import plotly.express as px

from data import (
    get_pr_data,
    get_metrics,
    get_repository_distribution,
    get_risk_distribution,
    get_affected_services_distribution,
    get_risk_trend,
)
from style import apply_style, sidebar, clean_html, empty_state


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
st.caption("Visual insights and trends across analyzed Pull Requests")

col1, col2 = st.columns([5, 1])
with col2:
    if st.button("← Dashboard", key="analytics_dashboard", help="Return to the developer dashboard."):
        st.switch_page("app.py")

st.markdown("---")


# =========================================================
# KPI (live)
# =========================================================

metrics = get_metrics()

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Total PRs", metrics["total"])
with c2: st.metric("High Risk", metrics["high"])
with c3: st.metric("Medium Risk", metrics["medium"])
with c4: st.metric("Low Risk", metrics["low"])

st.markdown("---")

if metrics["total"] == 0:
    st.markdown(
        empty_state(
            "📉", "No data to chart yet",
            "Charts will appear automatically once PR analyses exist."
        ),
        unsafe_allow_html=True
    )
    st.stop()


# =========================================================
# CHART COLORS
# =========================================================

SEVERITY_COLORS = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e", "UNKNOWN": "#64748b"}

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#cbd5e1",
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", y=-0.15)
)


# =========================================================
# ROW 1 — PRs BY REPOSITORY | RISK DISTRIBUTION
# =========================================================

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    with st.container(border=True):
        st.markdown("**📦 PRs by Repository**")

        repo_dist = get_repository_distribution()
        if not repo_dist:
            st.markdown(empty_state("📦", "No repository data yet"), unsafe_allow_html=True)
        else:
            repo_df = pd.DataFrame({
                "Repository": list(repo_dist.keys()),
                "PRs": list(repo_dist.values())
            })
            st.bar_chart(repo_df.set_index("Repository"), color="#ef4444")

with row1_col2:
    with st.container(border=True):
        st.markdown("**🎯 Risk Distribution**")

        risk_dist = get_risk_distribution()
        if not risk_dist:
            st.markdown(empty_state("🎯", "No severity data yet"), unsafe_allow_html=True)
        else:
            risk_df = pd.DataFrame({
                "Risk": list(risk_dist.keys()),
                "PRs": list(risk_dist.values())
            })
            fig = px.pie(
                risk_df, names="Risk", values="PRs", hole=0.55,
                color="Risk", color_discrete_map=SEVERITY_COLORS
            )
            fig.update_traces(textinfo="percent+label", textfont_color="#f8fafc")
            fig.update_layout(**PLOTLY_LAYOUT, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)


# =========================================================
# ROW 2 — MOST AFFECTED SERVICES | RISK TRENDS
# =========================================================

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    with st.container(border=True):
        st.markdown("**🔗 Most Affected Services**")

        services_dist = get_affected_services_distribution()
        if not services_dist:
            st.markdown(
                empty_state("🔗", "No affected-service data yet"),
                unsafe_allow_html=True
            )
        else:
            services_df = pd.DataFrame({
                "Service": list(services_dist.keys()),
                "Mentions": list(services_dist.values())
            })
            st.bar_chart(services_df.set_index("Service"), color="#f59e0b")

with row2_col2:
    with st.container(border=True):
        st.markdown("**📈 Risk Trends Over Time**")

        trend, is_sample = get_risk_trend()
        trend_df = pd.DataFrame(trend).rename(
            columns={"week": "Week", "high": "High", "medium": "Medium", "low": "Low"}
        )
        st.line_chart(trend_df.set_index("Week"))

        if is_sample:
            st.caption(
                "ℹ️ Sample trend — connect real weekly history to replace this."
            )

st.markdown("---")


# =========================================================
# INSIGHTS
# =========================================================

st.subheader("💡 Analytics Insights")

pr_data = get_pr_data()
high_risk = [pr for pr in pr_data if pr["severity"] == "HIGH"]
services_dist = get_affected_services_distribution()

a, b, c = st.columns(3)

with a:
    if high_risk:
        top = high_risk[0]
        st.markdown(
            clean_html(f"""
            <div class="red-card">
                <h3>🔴 Highest Risk</h3>
                <h2>{html.escape(str(top['pr_number']))}</h2>
                <p>Business impact: <strong>
                {html.escape(str(top['business_impact']))}%</strong></p>
            </div>
            """),
            unsafe_allow_html=True
        )
    else:
        st.markdown(empty_state("🔴", "No high-risk PRs"), unsafe_allow_html=True)

with b:
    if services_dist:
        top_service = max(services_dist, key=services_dist.get)
        st.markdown(
            clean_html(f"""
            <div class="blue-card">
                <h3>🗄️ Most Affected</h3>
                <h2>{html.escape(str(top_service))}</h2>
                <p>{services_dist[top_service]} analyzed impacts</p>
            </div>
            """),
            unsafe_allow_html=True
        )
    else:
        st.markdown(empty_state("🗄️", "No service data yet"), unsafe_allow_html=True)

with c:
    st.markdown(
        clean_html(f"""
        <div class="card">
            <h3>📈 Trend</h3>
            <h2>{metrics['high']} High-Risk PR(s)</h2>
            <p>Out of {metrics['total']} total PRs currently analyzed.</p>
        </div>
        """),
        unsafe_allow_html=True
    )

st.markdown("---")
st.caption("Analytics powered by Spectre Impact analysis engine.")