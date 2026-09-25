
#style.py

import streamlit as st


# =========================================================
# HTML HELPER
# =========================================================
# Streamlit renders text passed to st.markdown() through a CommonMark
# markdown parser before injecting raw HTML (when unsafe_allow_html=True).
# A raw HTML block like <div>...</div> is only left untouched up until the
# first BLANK LINE inside it. After a blank line, any indented line that
# follows gets parsed as a markdown "indented code block" and shown as
# literal, escaped text on the page instead of being rendered as HTML.
#
# clean_html() strips per-line indentation and removes blank lines from
# any HTML string before it's handed to st.markdown, so the whole block
# stays one uninterrupted HTML block and renders correctly. Every page
# imports this from here instead of redefining it.
def clean_html(content: str) -> str:
    lines = [line.strip() for line in content.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


# =========================================================
# NAVIGATION CONFIG
# =========================================================
# One flat list, matching the mockup (no MAIN / SYSTEM section labels).
# (button label, active_page name used to detect the current page,
#  target file passed to st.switch_page, unique widget key)

NAV_ITEMS = [
    ("🏠  Dashboard",     "Dashboard",     "app.py",                 "side_dashboard"),
    ("🔍  PR Analysis",   "PR Analysis",   "pages/PR_Analysis.py",   "side_pr"),
    ("📊  Analytics",     "Analytics",     "pages/Analytics.py",     "side_analytics"),
    ("📅  Weekly Review", "Weekly Review", "pages/Weekly_Review.py", "side_weekly"),
    ("⚙️  How It Works",  "How It Works",  "pages/How_It_Works.py",  "side_how"),
    ("ℹ️  About",         "About",         "pages/About.py",         "side_about"),
]


# =========================================================
# REUSABLE COMPONENTS
# =========================================================

def metric_card(icon, value, label, delta=None, positive=True):
    """A KPI card with an icon, big value, label and an optional trend
    delta (colored green/up or red/down), matching the dashboard mockup.
    Returns ready-to-render HTML -- pass to st.markdown(..., unsafe_allow_html=True).
    """
    delta_html = ""
    if delta:
        css_class = "up" if positive else "down"
        arrow = "↑" if positive else "↓"
        delta_html = f'<div class="metric-delta {css_class}">{arrow} {delta}</div>'

    return clean_html(f"""
    <div class="metric-card">
        <div class="metric-card-icon">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """)


# =========================================================
# GLOBAL STYLE
# =========================================================

def apply_style():

    st.markdown(clean_html("""
    <style>

    /* =====================================================
       APP
       ===================================================== */

    .stApp {
        background:
            radial-gradient(
                circle at 15% 5%,
                rgba(127, 29, 29, 0.18),
                transparent 28%
            ),
            radial-gradient(
                circle at 85% 10%,
                rgba(30, 58, 138, 0.16),
                transparent 30%
            ),
            linear-gradient(
                135deg,
                #020617,
                #030712,
                #020617
            );
        color: #f8fafc;
    }

    /* =====================================================
       DEFAULT STREAMLIT NAVIGATION
       ===================================================== */

    div[data-testid="stSidebarNav"] {
        display: none;
    }

    /* =====================================================
       SIDEBAR
       ===================================================== */

    section[data-testid="stSidebar"] {
        background:
            linear-gradient(
                180deg,
                #020617,
                #071426,
                #030712
            );
        border-right: 1px solid rgba(148,163,184,0.12);
    }

    section[data-testid="stSidebar"] > div {
        padding: 1rem 0.8rem;
    }

    /* =====================================================
       LOGO
       ===================================================== */

    .sidebar-logo {
        padding: 18px;
        margin-bottom: 18px;
        border-radius: 16px;
        background:
            linear-gradient(
                135deg,
                rgba(127,29,29,0.45),
                rgba(15,23,42,0.95)
            );
        border: 1px solid rgba(239,68,68,0.3);
        box-shadow: 0 10px 30px rgba(0,0,0,0.35);
    }

    .sidebar-logo-title {
        font-size: 17px;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: 0.7px;
    }

    .sidebar-logo-title span {
        color: #ef4444;
    }

    .sidebar-logo-subtitle {
        font-size: 10px;
        color: #64748b;
        margin-top: 6px;
    }

    /* =====================================================
       SECTION LABEL (used above the Data Source box)
       ===================================================== */

    .sidebar-section {
        color: #64748b;
        font-size: 10px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 20px 8px 8px;
    }

    /* =====================================================
       SIDEBAR NAV BUTTONS
       ===================================================== */

    section[data-testid="stSidebar"] .stButton {
        margin: 3px 0;
    }

    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        background: transparent;
        color: #cbd5e1;
        border: 1px solid transparent;
        border-radius: 10px;
        text-align: left;
        padding: 10px 13px;
        font-size: 13px;
        transition: all 0.2s ease;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background:
            linear-gradient(
                90deg,
                rgba(127,29,29,0.35),
                rgba(15,23,42,0.8)
            );
        color: white;
        border-color: rgba(239,68,68,0.3);
    }

    /* Current / active page indicator (static, not a button) */
    .nav-active {
        width: 100%;
        box-sizing: border-box;
        padding: 10px 13px;
        margin: 3px 0;
        border-radius: 10px;
        font-size: 13px;
        font-weight: 600;
        color: #ffffff;
        background:
            linear-gradient(
                90deg,
                rgba(127,29,29,0.55),
                rgba(127,29,29,0.20)
            );
        border: 1px solid rgba(239,68,68,0.55);
        box-shadow: 0 0 20px rgba(239,68,68,0.10);
    }

    /* =====================================================
       GLOBAL BUTTONS (main content area)
       ===================================================== */

    .stButton > button {
        background:
            linear-gradient(
                135deg,
                #7f1d1d,
                #dc2626
            );
        color: white;
        border: 1px solid rgba(248,113,113,0.35);
        border-radius: 9px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background:
            linear-gradient(
                135deg,
                #991b1b,
                #ef4444
            );
        border-color: rgba(248,113,113,0.7);
        box-shadow: 0 0 20px rgba(239,68,68,0.25);
        transform: translateY(-1px);
    }

    /* Secondary / outline buttons (e.g. "Back to List") */
    button[kind="secondary"] {
        background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(148,163,184,0.25) !important;
        color: #cbd5e1 !important;
    }

    button[kind="secondary"]:hover {
        border-color: rgba(239,68,68,0.4) !important;
        color: white !important;
    }

    /* =====================================================
       CONTAINER "CARDS" (st.container(border=True))
       ===================================================== */

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background:
            linear-gradient(
                145deg,
                rgba(15,23,42,0.96),
                rgba(2,6,23,0.98)
            );
        border: 1px solid rgba(148,163,184,0.13) !important;
        border-radius: 14px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.22);
    }

    /* =====================================================
       KPI METRIC CARDS
       ===================================================== */

    .metric-card {
        min-height: 110px;
        padding: 16px 18px;
        border-radius: 14px;
        background:
            linear-gradient(
                145deg,
                rgba(15,23,42,0.96),
                rgba(2,6,23,0.98)
            );
        border: 1px solid rgba(148,163,184,0.13);
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
        position: relative;
    }

    .metric-card-icon {
        position: absolute;
        top: 14px;
        right: 16px;
        font-size: 16px;
        opacity: 0.7;
    }

    .metric-value {
        font-size: 28px;
        font-weight: 800;
        color: #f8fafc;
        margin-top: 4px;
    }

    .metric-label {
        color: #94a3b8;
        font-size: 12px;
        margin-top: 4px;
    }

    .metric-delta {
        margin-top: 8px;
        font-size: 11px;
        font-weight: 700;
    }

    .metric-delta.up {
        color: #4ade80;
    }

    .metric-delta.down {
        color: #f87171;
    }

    /* =====================================================
       ALERT BAR (full width banner + action button)
       ===================================================== */

    .alert-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px 18px;
        border-radius: 12px;
        background:
            linear-gradient(
                90deg,
                rgba(127,29,29,0.5),
                rgba(30,10,15,0.3)
            );
        border: 1px solid rgba(239,68,68,0.35);
        color: #fca5a5;
        font-size: 13px;
        font-weight: 700;
    }

    /* =====================================================
       CARDS
       ===================================================== */

    .card {
        background:
            linear-gradient(
                145deg,
                rgba(15,23,42,0.96),
                rgba(2,6,23,0.98)
            );
        border: 1px solid rgba(148,163,184,0.13);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }

    .red-card {
        background:
            linear-gradient(
                135deg,
                rgba(127,29,29,0.4),
                rgba(30,10,15,0.8)
            );
        border: 1px solid rgba(239,68,68,0.4);
        border-radius: 14px;
        padding: 18px;
    }

    .blue-card {
        background:
            linear-gradient(
                135deg,
                rgba(15,35,70,0.8),
                rgba(2,6,23,0.95)
            );
        border: 1px solid rgba(59,130,246,0.25);
        border-radius: 14px;
        padding: 18px;
    }

    .risk-card {
        padding: 17px;
        border-radius: 13px;
        background:
            linear-gradient(
                135deg,
                rgba(127,29,29,0.38),
                rgba(30,10,15,0.75)
            );
        border: 1px solid rgba(239,68,68,0.38);
    }

    .insight-card {
        padding: 17px;
        border-radius: 13px;
        background:
            linear-gradient(
                135deg,
                rgba(15,23,42,0.95),
                rgba(2,6,23,0.95)
            );
        border: 1px solid rgba(148,163,184,0.13);
        min-height: 130px;
    }

    /* =====================================================
       TITLES / BADGES
       ===================================================== */

    .main-title {
        font-size: 42px;
        font-weight: 800;
        letter-spacing: -1px;
        background:
            linear-gradient(
                90deg,
                #ffffff,
                #cbd5e1,
                #ef4444
            );
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .breadcrumb-title {
        font-size: 26px;
        font-weight: 800;
        color: #f8fafc;
    }

    .breadcrumb-title span {
        color: #64748b;
        font-weight: 500;
    }

    .live-badge {
        background: rgba(34,197,94,0.10);
        color: #4ade80;
        border: 1px solid rgba(34,197,94,0.35);
        padding: 9px 20px;
        border-radius: 25px;
        font-size: 11px;
        font-weight: 700;
        text-align: center;
        margin-top: 15px;
        box-shadow: 0 0 20px rgba(34,197,94,0.08);
    }

    .live {
        background: rgba(34,197,94,0.10);
        color: #4ade80;
        border: 1px solid rgba(34,197,94,0.35);
        border-radius: 20px;
        padding: 8px 18px;
        text-align: center;
        font-weight: 700;
    }

    .high-badge {
        color: #f87171;
        background: rgba(220,38,38,0.14);
        border: 1px solid rgba(248,113,113,0.30);
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 800;
    }

    .impact-badge {
        color: #fbbf24;
        background: rgba(245,158,11,0.12);
        border: 1px solid rgba(251,191,36,0.22);
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
    }

    /* =====================================================
       SOURCE BOX
       ===================================================== */

    .source-box {
        margin-top: 15px;
        padding: 16px;
        border-radius: 14px;
        background:
            linear-gradient(
                135deg,
                rgba(15,23,42,0.96),
                rgba(2,6,23,0.96)
            );
        border: 1px solid rgba(148,163,184,0.13);
        box-shadow: 0 10px 25px rgba(0,0,0,0.28);
    }

    .source-title {
        font-size: 12px;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 12px;
    }

    .source-item {
        padding: 8px 0;
        font-size: 12px;
        color: #cbd5e1;
    }

    .source-description {
        display: block;
        margin-left: 18px;
        margin-top: 3px;
        color: #64748b;
        font-size: 9px;
    }

    .bfs-dot {
        color: #22c55e;
        margin-right: 5px;
    }

    .ai-dot {
        color: #a855f7;
        margin-right: 5px;
    }

    /* =====================================================
       FLOW / SIMULATION BOXES
       ===================================================== */

    .flow-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 10px;
    }

    .flow-box {
        padding: 11px 13px;
        border-radius: 9px;
        background: rgba(30,41,59,0.9);
        border: 1px solid rgba(239,68,68,0.2);
        color: #cbd5e1;
        font-size: 11px;
        text-align: center;
        max-width: 130px;
    }

    .flow-arrow {
        color: #ef4444;
        font-size: 16px;
        font-weight: 800;
    }

    /* =====================================================
       FOOTER
       ===================================================== */

    .footer {
        text-align: center;
        color: #475569;
        font-size: 10px;
        padding: 25px;
    }

    </style>
    """), unsafe_allow_html=True)


# =========================================================
# SIDEBAR
# =========================================================
# All nav items are rendered fully on every run -- nothing is skipped.
# We only remember which button (if any) was clicked, and call
# st.switch_page() ONCE, after the whole sidebar has already been drawn.
# Doing the switch_page() call early (inside the button's own "if" block)
# stops the script immediately, so anything meant to render further down
# in the same run never appears -- which is what made the rest of the
# sidebar seem to "disappear" on click.

def sidebar(active_page):

    target_page = None

    with st.sidebar:

        st.markdown(clean_html("""
        <div class="sidebar-logo">
            <div class="sidebar-logo-title">
                🚀 <span>SPECTRE</span> IMPACT
            </div>
            <div class="sidebar-logo-subtitle">
                GitHub Change Intelligence Platform
            </div>
        </div>
        """), unsafe_allow_html=True)

        for label, page_name, target, key in NAV_ITEMS:

            if page_name == active_page:
                st.markdown(
                    clean_html(f'<div class="nav-active">{label}</div>'),
                    unsafe_allow_html=True
                )
            else:
                if st.button(label, key=key, use_container_width=True):
                    target_page = target

        st.markdown("---")

        st.markdown(
            '<div class="sidebar-section">DATA SOURCE</div>',
            unsafe_allow_html=True
        )

        st.markdown(clean_html("""
        <div class="source-box">
            <div class="source-item">
                <span class="bfs-dot">●</span>
                <strong>BFS Engine</strong>
                <span class="source-description">
                    Deterministic blast radius calculation
                </span>
            </div>
            <div class="source-item">
                <span class="ai-dot">●</span>
                <strong>AI Agent</strong>
                <span class="source-description">
                    Impact intelligence and recommendations
                </span>
            </div>
        </div>
        """), unsafe_allow_html=True)

        st.markdown(clean_html("""
        <div style="
            text-align:center;
            color:#475569;
            font-size:10px;
            margin-top:20px;
        ">
            Spectre Impact v1.0<br>
            DevOpsDays Hackathon 2026
        </div>
        """), unsafe_allow_html=True)

    # Navigate only after the entire sidebar has been drawn, so nothing
    # in it appears to flicker or vanish on click.
    if target_page is not None:
        st.switch_page(target_page)
