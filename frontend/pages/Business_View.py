import html
import streamlit as st
import pandas as pd

from data import (
    get_pr_data,
    get_metrics,
    get_risk_trend,
    get_affected_services_distribution,
)
from style import apply_style, sidebar, clean_html, empty_state

st.set_page_config(page_title="Business Overview | Spectre Impact", page_icon="💼", layout="wide")
apply_style()
sidebar("Business Overview")

st.markdown('<div class="main-title">💼 Business Overview</div>', unsafe_allow_html=True)
st.caption("Executive view — understand business risk, release readiness, and where attention is needed without technical noise.")
st.markdown("---")

prs = get_pr_data()
metrics = get_metrics()

if not prs:
    st.markdown(
        empty_state(
            "📭",
            "Nothing to report yet",
            "Business insights will appear after engineering activity is analyzed.",
        ),
        unsafe_allow_html=True,
    )
    st.stop()

# ------------------------------------------------------------------
# Executive KPI layer
# ------------------------------------------------------------------
total = metrics["total"]
high = metrics["high"]
medium = metrics["medium"]
low = metrics["low"]
attention = high + medium
avg_impact = round(
    sum(pr["business_impact"] for pr in prs if pr["business_impact"] is not None)
    / max(1, sum(1 for pr in prs if pr["business_impact"] is not None))
)

# Business-friendly readiness signal. This is deliberately not called a
# technical deployment gate; it is an executive attention indicator.
if high == 0:
    readiness_label = "READY TO REVIEW"
    readiness_icon = "🟢"
    readiness_note = "No high-risk changes are currently flagged."
elif high <= 1:
    readiness_label = "REVIEW REQUIRED"
    readiness_icon = "🟠"
    readiness_note = "One high-risk area needs focused review before release."
else:
    readiness_label = "HEIGHTENED RISK"
    readiness_icon = "🔴"
    readiness_note = f"{high} high-risk changes need attention before release."

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(clean_html(f'''<div class="metric-card"><div class="metric-card-icon">🧾</div><div class="metric-value">{total}</div><div class="metric-label">Changes Reviewed</div></div>'''), unsafe_allow_html=True)
with c2:
    st.markdown(clean_html(f'''<div class="metric-card"><div class="metric-card-icon">🔴</div><div class="metric-value">{high}</div><div class="metric-label">High Risk</div></div>'''), unsafe_allow_html=True)
with c3:
    st.markdown(clean_html(f'''<div class="metric-card"><div class="metric-card-icon">🟠</div><div class="metric-value">{medium}</div><div class="metric-label">Moderate Risk</div></div>'''), unsafe_allow_html=True)
with c4:
    st.markdown(clean_html(f'''<div class="metric-card"><div class="metric-card-icon">🎯</div><div class="metric-value">{avg_impact}%</div><div class="metric-label">Avg. Business Impact</div></div>'''), unsafe_allow_html=True)
with c5:
    st.markdown(clean_html(f'''<div class="metric-card"><div class="metric-card-icon">🟢</div><div class="metric-value">{low}</div><div class="metric-label">Low Risk</div></div>'''), unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Release-readiness banner
# ------------------------------------------------------------------
banner_class = "red-card" if high > 1 else ("risk-card" if high == 1 else "blue-card")
st.markdown(
    clean_html(f'''
    <div class="{banner_class}">
        <div style="font-size:12px;letter-spacing:1px;color:#94a3b8;font-weight:800;">EXECUTIVE RELEASE SIGNAL</div>
        <div style="font-size:22px;font-weight:800;margin-top:6px;">{readiness_icon} {readiness_label}</div>
        <div style="color:#cbd5e1;margin-top:6px;">{html.escape(str(readiness_note))}</div>
    </div>
    '''),
    unsafe_allow_html=True,
)

st.markdown("---")

# ------------------------------------------------------------------
# Business Impact Summary + attention list
# ------------------------------------------------------------------
st.subheader("🧭 Business Impact Summary")

affected_counts = get_affected_services_distribution()
top_areas = sorted(affected_counts.items(), key=lambda x: x[1], reverse=True)[:5]

left, right = st.columns([1.15, 0.85])
with left:
    if high:
        high_areas = sorted({s for pr in prs if pr["severity"] == "HIGH" for s in pr["affected_services"]})
        areas_text = ", ".join(high_areas[:4]) if high_areas else "key business services under review"
        st.markdown(
            clean_html(f'''
            <div class="insight-card">
                <div style="font-size:12px;color:#94a3b8;font-weight:800;letter-spacing:.8px;">WHAT COULD MATTER TO THE BUSINESS</div>
                <h3 style="margin:8px 0 8px;color:#f8fafc;">{high} change(s) may affect customer-facing operations.</h3>
                <p style="color:#cbd5e1;line-height:1.65;margin-bottom:8px;">
                    The main areas currently associated with higher risk are <strong>{html.escape(str(areas_text))}</strong>.
                    Business owners should confirm release timing, customer impact, and mitigation ownership.
                </p>
                <div style="color:#94a3b8;font-size:12px;">Average estimated impact across available analyses: <strong style="color:#f8fafc;">{avg_impact}%</strong></div>
            </div>
            '''),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            clean_html('''
            <div class="insight-card">
                <div style="font-size:12px;color:#94a3b8;font-weight:800;letter-spacing:.8px;">BUSINESS HEALTH</div>
                <h3 style="margin:8px 0;color:#f8fafc;">🟢 No high-risk changes detected.</h3>
                <p style="color:#cbd5e1;line-height:1.65;">Current engineering activity does not contain a high-risk signal. Continue normal release review and monitoring.</p>
            </div>
            '''),
            unsafe_allow_html=True,
        )

with right:
    with st.container(border=True):
        st.markdown(
            '<div style="font-size:12px;color:#94a3b8;font-weight:800;letter-spacing:.8px;">MOST AFFECTED AREAS</div>',
            unsafe_allow_html=True,
        )
        if top_areas:
            for service, count in top_areas:
                st.markdown(f"**{html.escape(str(service))}**  ·  {count} change(s)")
        else:
            st.caption("No affected business areas have been identified yet.")

# ------------------------------------------------------------------
# Priority attention queue
# ------------------------------------------------------------------
st.markdown("---")
st.subheader("🚦 Priority Attention Queue")

priority = sorted(
    prs,
    key=lambda p: (
        {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(p["severity"], 0),
        p["business_impact"] or 0,
    ),
    reverse=True,
)

for pr in priority[:4]:
    severity = pr["severity"]
    icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢"}.get(severity, "⚪")
    impact = f"{pr['business_impact']}% estimated impact" if pr["business_impact"] is not None else "Impact under review"
    summary = pr["summary"] or "Business-friendly impact summary is not available yet."
    st.markdown(
        clean_html(f'''
        <div class="insight-card" style="margin-bottom:10px;min-height:0;">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;">
                <div><strong style="color:#f8fafc;">{icon} {severity}</strong> &nbsp; {html.escape(str(pr['repository']))} · {html.escape(str(pr['pr_number']))}</div>
                <div style="font-size:12px;color:#94a3b8;">{impact}</div>
            </div>
            <div style="color:#cbd5e1;margin-top:8px;line-height:1.55;">{html.escape(str(summary))}</div>
        </div>
        '''),
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------
# Risk trend
# ------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 Business Risk Trend")
trend, is_sample = get_risk_trend()
trend_df = pd.DataFrame(trend).rename(
    columns={"week": "Period", "high": "High Risk", "medium": "Moderate Risk", "low": "Low Risk"}
)
if not trend_df.empty and "Period" in trend_df.columns:
    st.line_chart(trend_df.set_index("Period"))
else:
    st.info("Historical trend data is not available yet.")
if is_sample:
    st.caption("Demo trend shown until historical backend data is connected. Live risk cards above are calculated from the active dataset.")

# ------------------------------------------------------------------
# Executive interpretation
# ------------------------------------------------------------------
st.markdown("---")
st.subheader("💡 Executive Takeaway")
if high >= 2:
    takeaway = "Multiple high-risk changes are active. Prioritize ownership, mitigation, and release timing before customer-facing rollout."
elif high == 1:
    takeaway = "The overall picture is manageable, but one high-risk change deserves focused business review before rollout."
elif medium >= 2:
    takeaway = "No high-risk change is currently flagged, but several moderate changes should remain visible during release planning."
else:
    takeaway = "Current change activity is relatively low risk from the available business-impact signals."

st.markdown(
    clean_html(f'''
    <div class="blue-card">
        <div style="font-size:18px;font-weight:800;color:#f8fafc;">{html.escape(str(takeaway))}</div>
        <div style="margin-top:8px;color:#94a3b8;font-size:12px;">This is an executive decision-support signal, not a replacement for release governance.</div>
    </div>
    '''),
    unsafe_allow_html=True,
)

st.markdown("---")
st.markdown(clean_html('''
<div class="footer">
<strong>Spectre Impact</strong> — Business Overview<br><br>
This view intentionally hides implementation details. Technical live activity, code changes, and developer communication remain available only in the Developer view.
</div>
'''), unsafe_allow_html=True)
