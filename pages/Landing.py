import os
from io import BytesIO
import streamlit as st

from style import apply_style, clean_html

st.set_page_config(page_title="Spectre Impact", page_icon="🚀", layout="centered", initial_sidebar_state="collapsed")
apply_style()

landing_url = os.getenv("SPECTRE_LANDING_URL", "").strip()

st.markdown(clean_html("""
<div style="text-align:center;padding:48px 15px 24px;">
    <div style="font-size:58px;">🚀</div>
    <h1 style="font-size:44px;margin-bottom:8px;">SPECTRE IMPACT</h1>
    <p style="font-size:18px;color:#94a3b8;">Know what will break before you deploy.</p>
</div>
"""), unsafe_allow_html=True)

if not landing_url:
    st.error("⚠️ SPECTRE_LANDING_URL is not configured. The QR code cannot be generated.")
    st.caption("Set SPECTRE_LANDING_URL to your public product URL before deployment.")
else:
    try:
        import qrcode
        qr = qrcode.make(landing_url)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="Scan to open Spectre Impact", width=210)
        st.caption(f"QR destination: {landing_url}")
    except Exception as exc:
        st.warning(f"QR generation failed: {exc}")

features = [
    ("💥","Blast Radius","See which services a change can affect."),
    ("💼","Business Impact","Translate technical changes into business risk."),
    ("🤖","AI Code Review","Review changes and surface potential issues."),
    ("🎙️","Voice Intelligence","Listen to deployment analysis."),
    ("🔄","Controlled Rollback","Move from rollback planning to controlled recovery."),
    ("💬","AI Chat","Ask Lya about changes and risk."),
]
cols = st.columns(2)
for i,(icon,title,text) in enumerate(features):
    with cols[i % 2]:
        st.markdown(clean_html(f'''
        <div class="card" style="min-height:145px;">
            <div style="font-size:25px;">{icon}</div>
            <h3>{title}</h3>
            <p style="color:#94a3b8;">{text}</p>
        </div>
        '''), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 Open Developer Dashboard", type="primary", use_container_width=True, help="Open the main Spectre developer dashboard."):
    st.switch_page("app.py")

st.markdown("---")
footer_cols = st.columns(3)
with footer_cols[0]: st.caption("[Privacy Policy](https://spectre.example.com/privacy)")
with footer_cols[1]: st.caption("[Terms of Service](https://spectre.example.com/terms)")
with footer_cols[2]: st.caption("[Contact](mailto:hello@spectre.example.com)")
st.caption("Spectre Impact · Know what will break before you deploy.")
