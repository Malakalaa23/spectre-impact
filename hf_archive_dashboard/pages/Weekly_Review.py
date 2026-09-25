#Weekly_Review.py

import streamlit as st
import pandas as pd

from data import affected_services, risk_over_time
from style import apply_style, sidebar, clean_html


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Weekly Review | Spectre Impact",
    page_icon="📅",
    layout="wide"
)

apply_style()

sidebar("Weekly Review")


# =========================================================
# HEADER
# =========================================================

st.title("📅 Weekly Review")

st.caption(
    "Comprehensive weekly analysis and AI recommendations"
)

if st.button("← Back to Dashboard", key="weekly_dashboard"):
    st.switch_page("app.py")

st.markdown("---")


# =========================================================
# WEEKLY SUMMARY
# =========================================================

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("PRs Analyzed", "50", "+8%")

with c2:
    st.metric("High Risk", "18", "+12%")

with c3:
    st.metric("Affected Services", "15", "+3")

with c4:
    st.metric("Recommendations", "9", "+4")

st.markdown("---")


# =========================================================
# RISK TREND
# =========================================================

left, right = st.columns(2)

with left:

    st.subheader("📈 Risk Trends Over Time")

    st.line_chart(risk_over_time.set_index("Week"))

with right:

    st.subheader("🔥 Top Risks")

    st.markdown(
        clean_html("""
        <div class="card">
            <strong>1. Payment Service</strong>
            <span style="float:right;">
                5 PRs
            </span>
            <br><br>
            <strong>2. Main Database</strong>
            <span style="float:right;">
                4 PRs
            </span>
            <br><br>
            <strong>3. Authentication</strong>
            <span style="float:right;">
                3 PRs
            </span>
        </div>
        """),
        unsafe_allow_html=True
    )

st.markdown("---")


# =========================================================
# MOST AFFECTED SERVICES
# =========================================================

st.subheader("🔗 Most Affected Services")

services_df = pd.DataFrame({
    "Service": list(affected_services.keys()),
    "Affected PRs": list(affected_services.values())
})

st.bar_chart(services_df.set_index("Service"))

st.markdown("---")


# =========================================================
# DEVOPS SUMMARY
# =========================================================

st.subheader("⚙️ DevOps Summary")

st.info("""
Several deployment changes affected payment,
authentication and database services.

The analysis indicates that the main risk comes from
dependency chains between these services.

Additional validation should be performed before
high-risk deployments.
""")


# =========================================================
# EXECUTIVE SUMMARY
# =========================================================

st.subheader("📋 Executive Summary")

st.success("""
The platform analyzed the week's Pull Requests and
identified several high-impact changes.

Automated impact simulation and rollback recommendations
can help reduce deployment risk and improve release safety.
""")


# =========================================================
# AI RECOMMENDATIONS
# =========================================================

st.markdown("---")

st.subheader("🤖 AI Recommendations")

rec1, rec2, rec3 = st.columns(3)

with rec1:
    if st.button(
        "🔧 Automate certificate rotation",
        key="weekly_rec_1",
        use_container_width=True
    ):
        st.success("Recommendation added.")

with rec2:
    if st.button(
        "🛡️ Add deployment validation",
        key="weekly_rec_2",
        use_container_width=True
    ):
        st.success("Recommendation added.")

with rec3:
    if st.button(
        "↩️ Improve rollback procedures",
        key="weekly_rec_3",
        use_container_width=True
    ):
        st.success("Recommendation added.")

st.markdown("---")


# =========================================================
# EXPORT
# =========================================================

if st.button("📄 Generate Weekly Report", key="generate_report"):
    st.success("Weekly report generated successfully.")

st.caption(
    "Weekly Review powered by BFS Engine + AI Agent."
)
