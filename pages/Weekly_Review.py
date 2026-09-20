#Weekly_Review.py

import html
import streamlit as st
import pandas as pd

from data import get_pr_data, get_metrics, get_affected_services_distribution, get_risk_trend
from style import apply_style, sidebar, clean_html, empty_state


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
st.caption("Comprehensive weekly analysis and AI recommendations")

if st.button("← Back to Dashboard", key="weekly_dashboard", help="Return to the developer dashboard."):
    st.switch_page("app.py")

st.markdown("---")


# =========================================================
# WEEKLY SUMMARY (live)
# =========================================================

pr_data = get_pr_data()
metrics = get_metrics()
services_dist = get_affected_services_distribution()

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("PRs Analyzed", metrics["total"])
with c2: st.metric("High Risk", metrics["high"])
with c3: st.metric("Affected Services", len(services_dist))
with c4: st.metric("Recommendations", metrics["high"] + metrics["medium"])

st.markdown("---")


# =========================================================
# RISK TREND | TOP RISKS
# =========================================================

left, right = st.columns(2)

with left:
    st.subheader("📈 Risk Trends Over Time")

    trend, is_sample = get_risk_trend()
    trend_df = pd.DataFrame(trend).rename(
        columns={"week": "Week", "high": "High", "medium": "Medium", "low": "Low"}
    )
    st.line_chart(trend_df.set_index("Week"))
    if is_sample:
        st.caption("ℹ️ Sample trend — connect real weekly history to replace this.")

with right:
    st.subheader("🔥 Top Risks")

    if not services_dist:
        st.markdown(
            empty_state("🔥", "No risk data yet", "Top affected services will appear here."),
            unsafe_allow_html=True
        )
    else:
        ranked = sorted(services_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        rows = ""
        for index, (service, count) in enumerate(ranked, start=1):
            rows += (
                f'<strong>{index}. {html.escape(str(service))}</strong>'
                f'<span style="float:right;">{count} PR(s)</span><br><br>'
            )
        st.markdown(clean_html(f'<div class="card">{rows}</div>'), unsafe_allow_html=True)

st.markdown("---")


# =========================================================
# MOST AFFECTED SERVICES
# =========================================================

st.subheader("🔗 Most Affected Services")

if not services_dist:
    st.markdown(empty_state("🔗", "No affected-service data yet"), unsafe_allow_html=True)
else:
    services_df = pd.DataFrame({
        "Service": list(services_dist.keys()),
        "Affected PRs": list(services_dist.values())
    })
    st.bar_chart(services_df.set_index("Service"))

st.markdown("---")


# =========================================================
# DEVOPS / EXECUTIVE SUMMARY (derived from live data)
# =========================================================

st.subheader("⚙️ DevOps Summary")

if not pr_data:
    st.markdown(empty_state("⚙️", "No activity to summarize yet"), unsafe_allow_html=True)
else:
    top_services = ", ".join(list(services_dist.keys())[:3]) or "no specific services"
    st.info(f"""
    {metrics['total']} PR(s) were analyzed, with {metrics['high']} flagged as high risk.

    The main risk this period comes from changes affecting: {top_services}.

    Additional validation is recommended before high-risk deployments.
    """)

st.subheader("📋 Executive Summary")

if not pr_data:
    st.markdown(empty_state("📋", "No activity to summarize yet"), unsafe_allow_html=True)
else:
    st.success(f"""
    The platform analyzed {metrics['total']} Pull Request(s) this period and
    identified {metrics['high']} high-impact change(s).

    Automated impact simulation and rollback recommendations can help
    reduce deployment risk and improve release safety.
    """)


# =========================================================
# AI RECOMMENDATIONS
# =========================================================

st.markdown("---")
st.subheader("🤖 AI Recommendations")

st.markdown(
    "- **Automate certificate rotation** to prevent TLS expiry incidents.\n"
    "- **Add deployment validation** to catch configuration issues before release.\n"
    "- **Improve rollback procedures** by practicing rollback drills monthly."
)

summary_text = "Spectre Impact — Weekly Review\n\n"
summary_text += f"Total PRs: {metrics['total']}\n"
summary_text += f"High Risk: {metrics['high']}\n"
summary_text += f"Medium Risk: {metrics['medium']}\n"
summary_text += f"Low Risk: {metrics['low']}\n"
summary_text += f"Affected Services: {len(services_dist)}\n"

st.download_button(
    "📄 Download Weekly Summary",
    summary_text,
    file_name="spectre_weekly_review.txt",
    mime="text/plain",
    help="Download the current weekly summary as a text file.",
)

st.caption("Weekly Review powered by BFS Engine + AI Agent.")
