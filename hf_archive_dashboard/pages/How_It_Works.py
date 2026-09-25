#How_It_Works.py

import streamlit as st

from style import apply_style, sidebar, clean_html


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="How It Works | Spectre Impact",
    page_icon="⚙️",
    layout="wide"
)

apply_style()

sidebar("How It Works")


# =========================================================
# HEADER
# =========================================================

st.title("⚙️ How Spectre Impact Works")

st.caption(
    "Understanding our AI-powered change intelligence pipeline"
)

if st.button("← Back to Dashboard", key="how_dashboard"):
    st.switch_page("app.py")

st.markdown("---")


# =========================================================
# PIPELINE
# =========================================================

st.subheader("🔄 Change Intelligence Pipeline")

steps = [
    ("👨‍💻", "Developer", "Opens PR"),
    ("🐙", "GitHub", "Webhook"),
    ("⚡", "FastAPI", "Server"),
    ("🧩", "BFS Engine", "Blast Radius"),
    ("🤖", "AI Agent", "Analysis"),
    ("🖥️", "Dashboard", "Visualization")
]

cols = st.columns(len(steps))

for col, step in zip(cols, steps):

    icon, title, description = step

    with col:

        st.markdown(
            clean_html(f"""
            <div class="card" style="text-align:center;">
                <div style="font-size:35px; margin-bottom:10px;">
                    {icon}
                </div>
                <strong>
                    {title}
                </strong>
                <br>
                <small style="color:#64748b;">
                    {description}
                </small>
            </div>
            """),
            unsafe_allow_html=True
        )


# =========================================================
# AI AGENT
# =========================================================

st.markdown("---")

st.subheader("🤖 AI Agent Generates")

a, b, c, d = st.columns(4)

with a:

    st.markdown(
        clean_html("""
        <div class="blue-card">
            🛡️
            <h4>
                Impact Simulation
            </h4>
            <small>
                What-if failure scenarios
            </small>
        </div>
        """),
        unsafe_allow_html=True
    )

with b:

    st.markdown(
        clean_html("""
        <div class="card">
            📋
            <h4>
                Rollback Plan
            </h4>
            <small>
                Safe recovery strategy
            </small>
        </div>
        """),
        unsafe_allow_html=True
    )

with c:

    st.markdown(
        clean_html("""
        <div class="card">
            ✅
            <h4>
                Validation Checklist
            </h4>
            <small>
                Commands to verify the fix
            </small>
        </div>
        """),
        unsafe_allow_html=True
    )

with d:

    st.markdown(
        clean_html("""
        <div class="card">
            🧠
            <h4>
                Multi-Level Summary
            </h4>
            <small>
                DevOps + Executive views
            </small>
        </div>
        """),
        unsafe_allow_html=True
    )


# =========================================================
# BFS ENGINE
# =========================================================

st.markdown("---")

left, right = st.columns(2)

with left:

    st.markdown(
        clean_html("""
        <div class="card">
            <h3>🧩 BFS Engine</h3>
            <p>
            The BFS engine performs deterministic dependency
            analysis to calculate the potential blast radius
            of a Pull Request.
            </p>
            <p>
            The result is repeatable and explainable.
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )

with right:

    st.markdown(
        clean_html("""
        <div class="card">
            <h3>🤖 AI Agent</h3>
            <p>
            The AI Agent transforms dependency analysis into
            human-readable insights and recommendations.
            </p>
            <p>
            It generates simulations, rollback plans and
            validation checklists.
            </p>
        </div>
        """),
        unsafe_allow_html=True
    )


# =========================================================
# WHY BOTH?
# =========================================================

st.markdown("---")

st.markdown(
    clean_html("""
    <div class="red-card">
        <h3>💡 Why combine BFS + AI?</h3>
        <p>
        We combine deterministic dependency analysis with
        AI intelligence to provide both reliable calculations
        and understandable recommendations.
        </p>
    </div>
    """),
    unsafe_allow_html=True
)
