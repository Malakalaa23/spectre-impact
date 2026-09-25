#About.py

import streamlit as st

from style import apply_style, sidebar, clean_html


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="About | Spectre Impact",
    page_icon="ℹ️",
    layout="wide"
)

apply_style()

sidebar("About")


# =========================================================
# HEADER
# =========================================================

st.title("ℹ️ About Spectre Impact")

st.caption(
    "AI-Powered GitHub Change Intelligence Platform"
)

if st.button("← Back to Dashboard", key="about_dashboard"):
    st.switch_page("app.py")

st.markdown("---")


# =========================================================
# WHAT IS SPECTRE?
# =========================================================

left, right = st.columns(2)

with left:

    st.markdown(
        clean_html("""
        <div class="card">
            <h2>
                What is Spectre Impact?
            </h2>
            <p>
            Spectre Impact helps engineering teams understand
            the operational consequences of software and
            infrastructure changes before deployment.
            </p>
            <p>
            It combines deterministic blast-radius analysis
            with AI-powered recommendations to make deployment
            decisions safer and easier to understand.
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )

with right:

    st.markdown(
        clean_html("""
        <div class="blue-card">
            <h2>
                🎯 Our Goal
            </h2>
            <p>
            Detect risky changes before they become production
            incidents.
            </p>
            <p>
            Give DevOps engineers and technical decision-makers
            a clear understanding of potential impact.
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )

st.markdown("---")


# =========================================================
# TEAM
# =========================================================

st.subheader("👥 Our Team")

team = [
    ("👨🏻‍💻", "Ahmed", "Backend Developer"),
    ("👨🏻‍💻", "Abu Bakr", "Blast Radius Engine"),
    ("👩🏻‍💻", "Merna", "Frontend Developer"),
    ("👩🏻‍💻", "Habiba", "UI/UX Designer"),
    ("👩🏻‍💻", "Malak", "AI Agent Engineer")
]

cols = st.columns(5)

for col, member in zip(cols, team):

    icon, name, role = member

    with col:

        st.markdown(
            clean_html(f"""
            <div class="card" style="text-align:center;">
                <div style="font-size:35px;">
                    {icon}
                </div>
                <h3>
                    {name}
                </h3>
                <small style="color:#94a3b8;">
                    {role}
                </small>
            </div>
            """),
            unsafe_allow_html=True
        )


# =========================================================
# TECH STACK
# =========================================================

st.markdown("---")

st.subheader("🛠️ Tech Stack")

tech = [
    "FastAPI",
    "Streamlit",
    "Python",
    "BFS Algorithm",
    "OpenAI GPT",
    "GitHub Webhooks",
    "Docker",
    "SQLite"
]

cols = st.columns(4)

for index, item in enumerate(tech):

    with cols[index % 4]:

        st.markdown(
            clean_html(f"""
            <div class="card" style="margin-bottom:10px;">
                🧩
                <strong>
                    {item}
                </strong>
            </div>
            """),
            unsafe_allow_html=True
        )


# =========================================================
# KEY FEATURES
# =========================================================

st.markdown("---")

st.subheader("✨ Key Features")

features = [
    "Real-time PR analysis",
    "AI-powered impact simulation",
    "Deterministic blast-radius analysis",
    "Automated rollback plans",
    "Validation checklists",
    "Multi-level summaries",
    "GitHub integration",
    "Visual analytics and trends"
]

for index in range(0, len(features), 2):

    col1, col2 = st.columns(2)

    with col1:
        st.success(f"✓ {features[index]}")

    if index + 1 < len(features):
        with col2:
            st.success(f"✓ {features[index + 1]}")


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
        Built for DevOpsDays Hackathon 2026
    </div>
    """),
    unsafe_allow_html=True
)
