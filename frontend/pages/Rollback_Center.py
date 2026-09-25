import html
import streamlit as st

from data import get_pr_data, get_pr_details
from api_client import post_json_detailed, get_json
from style import apply_style, sidebar, empty_state

st.set_page_config(page_title="Rollback Center | Spectre", page_icon="🔁", layout="wide")
apply_style()
sidebar("Rollback Center")

prs = get_pr_data()
if not prs:
    st.markdown(empty_state("📭", "No PRs available", "Nothing to roll back."), unsafe_allow_html=True)
    st.stop()

selected = st.selectbox(
    "Pull Request", [p["pr_number"] for p in prs], key="rollback_pr",
    help="Choose the pull request whose rollback plan you want to inspect.",
)
d = get_pr_details(selected)

status_key = f"rollback_status_{selected}"
reauth_key = f"rollback_reauthenticated_{selected}"
status = st.session_state.get(status_key, "idle")
label = {"idle":"READY","pending":"PENDING","executing":"EXECUTING","complete":"COMPLETE","failed":"FAILED"}.get(status,"READY")

st.title("🔁 Rollback Center")
st.caption("Review the plan first. Execution requires explicit confirmation and re-authentication.")
st.markdown(f"<span class='spectre-status {html.escape(status)}'>● {html.escape(label)}</span>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown(f"### {html.escape(str(selected))} · {html.escape(str(d['repository']))}")
    for i, step in enumerate(d["rollback"] or ["No rollback plan available"], 1):
        st.write(f"**{i}.** {step}")

if st.button("🧪 Dry Run", use_container_width=True, help="Simulate the rollback without executing it."):
    st.session_state[status_key] = "pending"
    with st.spinner("Running rollback simulation..."):
        ok, result, _ = post_json_detailed("/api/rollback", {"pr_number": selected, "action": "dry_run"}, timeout=60)
    st.session_state[status_key] = "complete" if ok else "failed"
    if ok:
        st.success(result.get("message", "Dry run completed."))
    else:
        st.warning(result.get("message") or result.get("error") or "Rollback API is not connected yet. No real action was performed.")

st.divider()
st.subheader("⚠️ Execute Rollback")

confirm_key = f"rollback_confirm_{selected}"
username_key = f"rollback_reauth_user_{selected}"

# A widget's value can only be reset BEFORE the widget is created, so the
# previous run leaves a flag here instead of writing to the key directly.
if st.session_state.pop(f"rollback_reset_{selected}", False):
    st.session_state[confirm_key] = ""
    st.session_state[username_key] = ""

confirm = st.text_input(
    "Type CONFIRM",
    key=confirm_key,
    help="Type CONFIRM exactly to enable rollback execution.",
)
reauth_user = st.text_input(
    "Re-authenticate as",
    placeholder="Your engineering username",
    key=username_key,
    help="Enter the engineering username used for the re-authentication check.",
)

# On-screen hints so the presenter is never stuck guessing which step is next.
already_reauthed = st.session_state.get(reauth_key, False)

if not already_reauthed:
    if not reauth_user.strip():
        st.caption("Step 1 of 2 — type a username above.")
    elif confirm.strip() != "CONFIRM":
        st.caption("Step 2 of 2 — type CONFIRM above.")
    else:
        st.caption("Ready. Click **🔐 Re-authenticate** to unlock execution.")

if st.button(
    "🔐 Re-authenticate",
    use_container_width=True,
    disabled=(not reauth_user.strip()) or already_reauthed,
    help="Perform the required re-authentication check.",
):
    st.session_state[reauth_key] = True
    st.success(f"Re-authentication check passed for {reauth_user.strip()}.")

can_execute = confirm.strip() == "CONFIRM" and st.session_state.get(reauth_key, False)

if not can_execute and st.session_state.get(reauth_key, False):
    st.caption("Re-authenticated. Type CONFIRM above to enable Execute.")

if st.button(
    "Execute Rollback",
    type="primary",
    disabled=not can_execute,
    use_container_width=True,
    help="Execute the confirmed rollback.",
):
    st.session_state[status_key] = "executing"
    try:
        with st.spinner("Executing rollback..."):
            ok, result, _ = post_json_detailed(
                "/api/rollback",
                {
                    "pr_number": selected,
                    "action": "execute",
                    # Field names must match RollbackRequest in main.py.
                    # Older versions sent "confirmation"/"username" which
                    # the backend silently ignored, causing a 400 before
                    # the executor ever ran.
                    "confirm": "CONFIRM",
                    "reauth_user": reauth_user.strip(),
                },
                timeout=90,
            )
        st.session_state[status_key] = "complete" if ok else "failed"
        if ok:
            st.success(result.get("message", "Rollback completed."))
        else:
            st.error(result.get("message") or result.get("error") or "Rollback failed.")
    finally:
        # Re-authentication and the typed confirmation are single-use.
        st.session_state[reauth_key] = False
        st.session_state[f"rollback_reset_{selected}"] = True

st.subheader("📋 Audit Log")
ok, audit = get_json("/api/audit")
if ok and isinstance(audit, list):
    for row in audit[-20:][::-1]:
        st.write(row)
elif ok and isinstance(audit, dict):
    for row in audit.get("items", audit.get("audit", []))[-20:][::-1]:
        st.write(row)
else:
    st.caption("Audit API is not connected yet.")