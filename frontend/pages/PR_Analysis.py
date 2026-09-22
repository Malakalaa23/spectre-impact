import html
import streamlit as st

from data import get_pr_data, get_pr_details
from realtime import get_live_events, add_team_message, post_github_comment
from style import apply_style, sidebar, clean_html, empty_state, severity_badge_html
from api_client import post_bytes
from components.audio_player import render_audio_player

st.set_page_config(page_title="PR Analysis | Spectre Impact", page_icon="🔍", layout="wide")
apply_style()
sidebar("PR Analysis")

all_prs = get_pr_data()
if not all_prs:
    st.title("🔍 PR Analysis")
    st.markdown(empty_state("📭", "No PRs available", "Waiting for the next analyzed change."), unsafe_allow_html=True)
    st.stop()

selected_pr = st.session_state.get("selected_pr", all_prs[0]["pr_number"])
details = get_pr_details(selected_pr)
if not details.get("found"):
    selected_pr = all_prs[0]["pr_number"]
    details = get_pr_details(selected_pr)
    st.session_state["selected_pr"] = selected_pr

impact_line = f"{details['business_impact']}%" if details['business_impact'] is not None else "Not available"
safe_selected_pr = html.escape(str(selected_pr))
safe_severity = html.escape(str(details["severity"]))
safe_repository = html.escape(str(details["repository"]))
safe_author = html.escape(str(details["author"]))
safe_impact_line = html.escape(str(impact_line))

# Header
c1, c2, c3, c4 = st.columns([4, 1, 1, 1.2])
with c1:
    st.markdown(f'<div class="breadcrumb-title">PR Analysis <span>→</span> {selected_pr}</div>', unsafe_allow_html=True)
    st.caption("Technical deep dive for developers")
with c2:
    if st.button("← Dashboard", use_container_width=True, help="Return to the developer dashboard."):
        st.switch_page("app.py")
with c3:
    if st.button("📝 Post to GitHub", use_container_width=True, help="Post this analysis as a comment on the pull request."):
        body = (
            f"## Spectre Impact Analysis — {selected_pr}\n\n"
            f"**Risk:** {details['severity']}\n\n"
            f"**Business Impact:** {impact_line}\n\n"
            f"**Problem:** {details.get('problem') or details.get('summary') or 'See dashboard for details.'}\n\n"
            f"**Affected Services:** {', '.join(details['affected_services']) or 'None detected'}"
        )
        ok, message = post_github_comment(selected_pr, details['repository'], body)
        st.session_state["github_post_result"] = (ok, message)
with c4:
    st.markdown(clean_html('<div class="live-badge">● LIVE</div>'), unsafe_allow_html=True)

result = st.session_state.pop("github_post_result", None)
if result:
    ok, message = result
    (st.success if ok else st.warning)(message)

st.markdown("---")

st.markdown(clean_html(f"""
<div class="red-card">
<h2>{safe_selected_pr} Analysis Details</h2>
{severity_badge_html(details['severity'])}
&nbsp; <span class="impact-badge">Business Impact: {safe_impact_line}</span>
<p>Repository: <strong>{safe_repository}</strong> · Author: <strong>{safe_author}</strong></p>
</div>
"""), unsafe_allow_html=True)

st.markdown("")

left, right = st.columns([1.25, 1])
with left:
    st.subheader("📊 Analysis Summary")
    view = st.radio("View as", ["🔧 DevOps Engineer", "👔 Executive"], horizontal=True, key="pr_summary_view", help="Switch between the technical and executive summary.")
    if view == "🔧 DevOps Engineer":
        st.info(f"**Technical Summary**\n\n{details['summary'] or 'No technical summary is available yet.'}\n\nBFS maps the deterministic blast radius; AI generates the simulation and recommendations.")
    else:
        st.success(f"**Executive Summary**\n\n{selected_pr} is **{details['severity']}** risk with estimated business impact of **{impact_line}**. Engineering review is recommended before deployment.")

    st.subheader("🔗 Affected Microservices")
    services = details["affected_services"]
    if not services:
        st.markdown(empty_state("🔗", "No affected services detected yet"), unsafe_allow_html=True)
    else:
        service_cols = st.columns(min(len(services), 3))
        for idx, service in enumerate(services):
            with service_cols[idx % len(service_cols)]:
                st.markdown(clean_html(f'<div class="blue-card">🔗 <strong>{html.escape(str(service))}</strong></div>'), unsafe_allow_html=True)

    with st.expander("🛡️ Impact Simulation", expanded=True):
        if not details["simulation"]:
            st.caption("No simulation available yet.")
        else:
            flow_html = '<div class="flow-wrap">'
            for idx, step in enumerate(details["simulation"]):
                flow_html += f'<div class="flow-box">{html.escape(str(step))}</div>'
                if idx < len(details["simulation"]) - 1:
                    flow_html += '<div class="flow-arrow">→</div>'
            flow_html += '</div>'
            st.markdown(clean_html(flow_html), unsafe_allow_html=True)
            st.caption("AI-generated simulation of what could happen if this deployment fails.")

with right:
    st.subheader("📁 Changed Files")
    with st.container(border=True):
        for file in details["changed_files"] or ["No changed files reported"]:
            st.markdown(f"🔹 `{html.escape(str(file))}`")

    with st.expander("🔄 Rollback Plan", expanded=True):
        for idx, step in enumerate(details["rollback"] or ["No rollback plan returned yet"]):
            st.write(f"**{idx + 1}.** {step}")

    with st.expander("✅ Validation Checklist", expanded=True):
        for idx, step in enumerate(details["validation"] or ["Manual validation required"]):
            st.checkbox(step, key=f"validation_{selected_pr}_{idx}")

st.markdown("---")

# Live events related to this PR
st.subheader("🟢 Live Events for This PR")
related = [e for e in get_live_events(30) if e.get("pr_number") == selected_pr]
if related:
    for event in related[:5]:
        st.markdown(clean_html(f"""
        <div class="activity-item">
            <span class="activity-dot">●</span>
            <div><strong>{html.escape(str(event.get("author", "Developer")))}</strong> ·
            {html.escape(str(event.get("action", "updated")))} ·
            {html.escape(str(event.get("timestamp", "")))}<br>
            {html.escape(str(event.get("commit_message", "")))}</div>
        </div>
        """), unsafe_allow_html=True)
else:
    st.caption("No live webhook event has been recorded for this PR yet.")

st.subheader("💬 Discuss This PR")
message = st.text_input("Message the team", key="pr_message", help="Write a short note about this pull request.")
user = st.selectbox("Your name", ["Yassin", "Ahmed", "Malak", "Merna", "Habiba", "Abu Bakr"], key="pr_user", help="Choose the name your message is sent under.")
if st.button("Send PR Message", key="send_pr_message", help="Post this note to the team feed."):
    if add_team_message(user, message, selected_pr):
        st.success("Message sent.")
        st.rerun()
    else:
        st.warning("Write a message first.")

st.markdown("---")
st.markdown(clean_html("""
<div class="source-box">
<div class="source-title">🔍 Analysis powered by</div>
<div class="source-item"><span class="bfs-dot">●</span><strong>BFS Engine</strong> — deterministic blast radius calculation</div>
<div class="source-item"><span class="ai-dot">●</span><strong>AI Agent</strong> — impact simulation and recommendations</div>
<div class="source-item"><span class="live-dot">●</span><strong>GitHub Webhook</strong> — real-time code-change events</div>
</div>
"""), unsafe_allow_html=True)

# ----------------------------- Voice analysis -----------------------------
st.markdown("---")
st.subheader("🎙️ Listen to Analysis")
voice_options={"Default":"default","Alloy":"alloy","Nova":"nova","Shimmer":"shimmer"}
voice_choice=st.selectbox("Voice",list(voice_options.keys()),key=f"voice_choice_{selected_pr}",help="Choose the voice used for the PR analysis.")
if st.button("🔊 Generate Voice Analysis",key="generate_voice",use_container_width=True,help="Generate an audio version of this PR analysis."):
    with st.spinner("Generating audio..."):
        ok,audio,meta=post_bytes(f"/api/voice/{str(selected_pr).lstrip('#')}",{"text":details.get("ai_analysis") or details.get("summary") or "No analysis available.","voice":voice_options[voice_choice]})
        if ok:
            st.session_state[f"voice_audio_{selected_pr}"] = (audio, meta if meta.startswith("audio/") else "audio/mpeg")
        else: st.warning("Voice API is not connected yet. The Voice UI is ready for backend integration.")
voice_key = f"voice_audio_{selected_pr}"
if st.session_state.get(voice_key):
    audio, mime = st.session_state[voice_key]
    render_audio_player(audio, mime, f"pr_{str(selected_pr).lstrip('#')}_analysis.mp3")
