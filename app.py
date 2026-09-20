import streamlit as st
import html

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from data import get_pr_data, get_metrics, get_recent_activity
from filters import filter_prs
from realtime import get_live_events, get_team_messages, add_team_message, get_realtime_status
from style import apply_style, sidebar, clean_html, metric_card, empty_state, severity_badge_html
from api_client import get_json_detailed

st.set_page_config(
    page_title="Spectre Impact — Developer Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_style()
sidebar("Dashboard")
backend_ok, _, _ = get_json_detailed("/ping")

# Refresh the developer dashboard automatically. If the optional package is
# unavailable, the page remains fully usable with the manual Refresh button.
if st_autorefresh is not None:
    st_autorefresh(interval=2000, limit=None, key="developer_live_refresh")
else:
    if st.button("↻ Refresh Live Feed", key="manual_refresh", help="Reload the live webhook feed."):
        st.rerun()

status = get_realtime_status()
status_class = "live-badge" if status["status"] == "LIVE" else "cached-badge"

header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.markdown('<div class="main-title">🚀 Spectre Impact</div>', unsafe_allow_html=True)
    st.caption("Developer Control Center — real-time code changes, impact and team communication")
with header_col2:
    st.markdown(clean_html(f'<div class="{status_class}">● {status["label"]}</div>'), unsafe_allow_html=True)
    st.caption(status["detail"])

st.markdown("---")

# ----------------------------- Live code activity --------------------------
st.subheader("🟢 Live Code Activity")

live_feed_endpoint = "/api/live-feed"
live_events = get_live_events(limit=12)
if not live_events:
    st.markdown(empty_state("📭", "No live events yet", "GitHub webhook changes will appear here."), unsafe_allow_html=True)
else:
  for event in live_events:
    severity = event.get("severity", "UNKNOWN")
    files = event.get("changed_files") or ["unknown file"]
    files_text = ", ".join(f"`{file}`" for file in files[:4])

    author = html.escape(str(event.get("author", "Unknown Developer")))
    repository = html.escape(str(event.get("repository", "Unknown Repository")))
    pr_number = html.escape(str(event.get("pr_number", "#?")))
    commit_message = html.escape(str(event.get("commit_message", "Code change")))
    timestamp = html.escape(str(event.get("timestamp", "unknown time")))

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(
                f"**👨‍💻 {author}** changed {files_text} "
                f"in **{repository}** · `{pr_number}`"
            )
            st.caption(f"{commit_message} · {timestamp}")

        with c2:
            st.markdown(severity_badge_html(severity), unsafe_allow_html=True)

        if event.get("problem"):
            st.warning(f"⚠️ **Potential Problem:** {event['problem']}")

        if event.get("ai_analysis"):
            st.info(f"🤖 **AI Analysis:** {event['ai_analysis']}")

        services = event.get("affected_services") or []
        if services:
            st.caption("Affected services: " + ", ".join(services))

        a, b, c = st.columns([1, 1, 4])

        with a:
            if st.button(
                "View PR",
                key=f"event_view_{event.get('event_id')}",
                help="Open the full analysis for this pull request.",
            ):
                st.session_state["selected_pr"] = event.get("pr_number")
                st.switch_page("pages/PR_Analysis.py")

        with b:
            if st.button(
                "Acknowledge",
                key=f"event_ack_{event.get('event_id')}",
                help="Mark this event as seen on this dashboard.",
            ):
                st.session_state[f"ack_{event.get('event_id')}"] = True
                st.success("Acknowledged")

        with c:
            if st.session_state.get(f"ack_{event.get('event_id')}"):
                st.caption("✅ Acknowledged by current dashboard user")
st.markdown("---")

# ----------------------------- Developer filters --------------------------
st.subheader("🎛️ Developer Filters")
prs = get_pr_data()
col1, col2, col3 = st.columns(3)
with col1:
    severity_filter = st.selectbox("Severity", ["All", "HIGH", "MEDIUM", "LOW"], key="dev_severity", help="Filter pull requests by risk level.")
with col2:
    repositories = ["All"] + sorted({pr.get("repository", "Unknown") for pr in prs})
    repo_filter = st.selectbox("Repository", repositories, key="dev_repo", help="Filter pull requests by repository.")
with col3:
    developers = ["All"] + sorted({pr.get("author", "Unknown") for pr in prs})
    developer_filter = st.selectbox("Developer", developers, key="dev_author", help="Filter pull requests by author.")

filtered_prs = filter_prs(prs, severity_filter, repo_filter, developer_filter)
st.caption(f"Showing {len(filtered_prs)} of {len(prs)} analyzed PRs")

st.markdown("---")

# ----------------------------- Developer KPIs -----------------------------
st.subheader("📊 Developer Risk Overview")
metrics = {
    "total": len(filtered_prs),
    "high": sum(1 for pr in filtered_prs if pr.get("severity") == "HIGH"),
    "medium": sum(1 for pr in filtered_prs if pr.get("severity") == "MEDIUM"),
    "low": sum(1 for pr in filtered_prs if pr.get("severity") == "LOW"),
}

m1, m2, m3, m4 = st.columns(4)
for col, icon, value, label in [
    (m1, "📄", metrics["total"], "PRs"),
    (m2, "🔴", metrics["high"], "High Risk"),
    (m3, "🟠", metrics["medium"], "Medium Risk"),
    (m4, "🟢", metrics["low"], "Low Risk"),
]:
    with col:
        st.markdown(metric_card(icon, value, label), unsafe_allow_html=True)

st.markdown("---")

# ----------------------------- Team communication -------------------------
st.subheader("💬 Developer Communication")
messages = get_team_messages(limit=20)
if messages:
    with st.container(border=True):
        for message in messages[-10:]:
            st.markdown(
                f"**{message.get('author', 'Developer')}** · "
                  
               f"{html.escape(message.get('timestamp', ''))}<br>{html.escape(message.get('text', ''))}",
                unsafe_allow_html=True,
            )
else:
    st.caption("No team messages yet.")

msg_col1, msg_col2 = st.columns([1, 4])
with msg_col1:
    current_user = st.selectbox("You", ["Yassin", "Ahmed", "Malak", "Merna", "Habiba", "Abu Bakr"], key="chat_user", help="Choose the name your message is sent under.")
with msg_col2:
    message_text = st.text_input("Message the development team", placeholder="Example: I am checking the login service now…", key="team_message", help="Write a short update for the team feed.")
if st.button("Send Message", key="send_team_message", help="Post this message to the team feed."):
    if add_team_message(current_user, message_text):
        st.success("Message sent to the development team.")
        st.rerun()
    else:
        st.warning("Write a message first.")

st.markdown("---")

# ----------------------------- Recent PR table ----------------------------
st.subheader("📋 Recent PR Analyses")
if not filtered_prs:
    st.markdown(empty_state("📭", "No PR matches these filters", "Change the filters or wait for the next webhook event."), unsafe_allow_html=True)
else:
    h1, h2, h3, h4, h5, h6 = st.columns([1, 2, 1.4, 1, 1.5, 1])
    for col, text in zip((h1, h2, h3, h4, h5, h6), ("PR", "Repository", "Severity", "Impact", "Author", "Action")):
        with col:
            st.caption(text)
    for pr in filtered_prs:
        c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 1.4, 1, 1.5, 1])
        with c1: st.write(f"**{pr['pr_number']}**")
        with c2: st.write(pr["repository"])
        with c3: st.markdown(severity_badge_html(pr["severity"]), unsafe_allow_html=True)
        with c4: st.write(f"{pr['business_impact']}%" if pr["business_impact"] is not None else "—")
        with c5: st.write(pr["author"])
        with c6:
            if st.button("Inspect", key=f"inspect_{pr['pr_number']}", use_container_width=True, help="Open the full analysis for this pull request."):
                st.session_state["selected_pr"] = pr["pr_number"]
                st.switch_page("pages/PR_Analysis.py")
        st.divider()

st.markdown(
    clean_html("""
    <div class="source-box">
        <div class="source-title">🔍 Analysis powered by</div>
        <div class="source-item"><span class="bfs-dot">●</span><strong>BFS Engine</strong> — deterministic blast radius calculation</div>
        <div class="source-item"><span class="ai-dot">●</span><strong>AI Agent</strong> — impact simulation and recommendations</div>
        <div class="source-item"><span class="live-dot">●</span><strong>GitHub Webhook</strong> — real-time developer change events</div>
    </div>
    """),
    unsafe_allow_html=True,
)

st.markdown("---")
st.caption("Spectre Impact · Know what will break before you deploy.")
