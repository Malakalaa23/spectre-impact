#style.py

import streamlit as st

from data import set_uploaded_pr_data, clear_uploaded_data, has_uploaded_data


# =========================================================
# HTML HELPER
# =========================================================
# Streamlit renders text passed to st.markdown() through a CommonMark
# markdown parser before injecting raw HTML (when unsafe_allow_html=True).
# A raw HTML block like <div>...</div> is only left untouched up until the
# first BLANK LINE inside it. clean_html() strips indentation and blank
# lines so any HTML string always renders correctly in one piece.
def clean_html(content: str) -> str:
    lines = [line.strip() for line in content.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


# =========================================================
# NAVIGATION CONFIG
# =========================================================
# (label, active_page name, target file, widget key, which view modes see it)

NAV_ITEMS = [
    ("🏠  Dashboard",         "Dashboard",         "app.py",                   "side_dashboard", ["developer"]),
    ("🔍  PR Analysis",       "PR Analysis",       "pages/PR_Analysis.py",     "side_pr",         ["developer"]),
    ("💬  AI Chat",            "Chat",              "pages/Chat.py",            "side_chat",       ["developer"]),
    ("🔍  Code Review",        "Code Review",       "pages/Code_Review.py",    "side_review",     ["developer"]),
    ("🔄  Rollback Center",    "Rollback Center",   "pages/Rollback_Center.py","side_rollback",   ["developer"]),
    ("📊  Analytics",         "Analytics",         "pages/Analytics.py",       "side_analytics",  ["developer"]),
    ("📅  Weekly Review",     "Weekly Review",     "pages/Weekly_Review.py",   "side_weekly",      ["developer"]),
    ("💼  Business Overview", "Business Overview", "pages/Business_View.py",  "side_business",    ["business"]),
    ("⚙️  How It Works",      "How It Works",      "pages/How_It_Works.py",    "side_how",         ["developer"]),
    ("ℹ️  About",             "About",             "pages/About.py",           "side_about",       ["developer", "business"]),
]

DEFAULT_LANDING_PAGE = {
    "developer": "app.py",
    "business": "pages/Business_View.py",
}


# =========================================================
# REUSABLE COMPONENTS
# =========================================================

def metric_card(icon, value, label, delta=None, positive=True):
    """A KPI card with an icon, big value, label and an optional trend delta."""
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


def empty_state(icon, title, subtitle=""):
    """A friendly placeholder shown instead of a section when there's
    no data for it yet -- used everywhere instead of letting a section
    disappear or crash."""
    subtitle_html = f'<div class="empty-state-subtitle">{subtitle}</div>' if subtitle else ""
    return clean_html(f"""
    <div class="card empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-title">{title}</div>
        {subtitle_html}
    </div>
    """)


def severity_badge_html(severity):
    """Small colored pill for a severity value. Falls back to a neutral
    gray badge for "UNKNOWN" instead of guessing a color that could be
    misleading."""
    mapping = {
        "HIGH":   ("🔴", "sev-high"),
        "MEDIUM": ("🟠", "sev-medium"),
        "LOW":    ("🟢", "sev-low"),
    }
    emoji, css_class = mapping.get(severity, ("⚪", "sev-unknown"))
    label = severity if severity in mapping else "UNKNOWN"
    return f'<span class="{css_class}">{emoji} {label}</span>'


# =========================================================
# GLOBAL STYLE
# =========================================================

def apply_style():
    """Inject the Spectre design system.

    All styling lives in styles/custom.css so there is exactly one source of
    truth. The colours below are only a minimal safety net used if the file
    cannot be read, so the app never falls back to a white Streamlit theme.
    """
    from pathlib import Path

    css_path = Path(__file__).resolve().parent / "styles" / "custom.css"
    try:
        css = css_path.read_text(encoding="utf-8")
    except Exception:
        css = """
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background-color: #020617 !important;
            color: #e8eef7 !important;
        }
        section[data-testid="stSidebar"] { background: #050c1c !important; }
        div[data-testid="stSidebarNav"] { display: none !important; }
        """

    # Blank lines can make Streamlit's markdown parser split a raw HTML block,
    # so the stylesheet is collapsed before it is injected.
    css = "\n".join(line for line in css.splitlines() if line.strip())
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =========================================================
# SIDEBAR
# =========================================================
# All nav items are rendered fully on every run -- nothing is skipped.
# We only remember which button (if any) was clicked, and call
# st.switch_page() ONCE, after the whole sidebar has already been drawn,
# so nothing appears to flicker or vanish on click.

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

        # -----------------------------------------------------
        # VIEW MODE (Developer / Business) — a simple, always-visible
        # toggle. No login system: anyone can switch freely, which is
        # exactly what's needed for demoing both audiences quickly.
        # -----------------------------------------------------

        mode_choice = st.radio(
            "View as",
            ["👨‍💻 Developer", "💼 Business"],
            index=0 if st.session_state.get("view_mode", "developer") == "developer" else 1,
            key="view_mode_radio",
            label_visibility="collapsed",
        )
        mode = "developer" if "Developer" in mode_choice else "business"
        st.session_state["view_mode"] = mode

        st.markdown("")

        visible_items = [item for item in NAV_ITEMS if mode in item[4]]

        for label, page_name, target, key, _modes in visible_items:

            if page_name == active_page:
                st.markdown(
                    clean_html(f'<div class="nav-active">{label}</div>'),
                    unsafe_allow_html=True
                )
            else:
                if st.button(label, key=key, use_container_width=True):
                    target_page = target

        # If the current page doesn't belong to this view mode (e.g. the
        # mode was just switched), redirect to that mode's home page.
        visible_page_names = [item[1] for item in visible_items]
        if target_page is None and active_page not in visible_page_names:
            target_page = DEFAULT_LANDING_PAGE[mode]

        # -----------------------------------------------------
        # PERSISTENT TEST-DATA UPLOAD — always visible, on every page,
        # in every mode. Never blocks the app if the file is bad.
        # -----------------------------------------------------

        st.markdown("---")

        st.markdown(
            '<div class="sidebar-section">TEST DATA</div>',
            unsafe_allow_html=True
        )

        uploaded_file = st.file_uploader(
            "Upload PR data (JSON)",
            type=["json"],
            key="pr_data_uploader",
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            success, message = set_uploaded_pr_data(uploaded_file)
            if success:
                st.success(message, icon="✅")
            else:
                st.warning(message, icon="⚠️")

        if has_uploaded_data():
            st.caption(f"📄 Using: {st.session_state.get('upload_filename', 'uploaded file')}")
            if st.button("🗑️ Clear & use defaults", key="clear_upload", use_container_width=True):
                clear_uploaded_data()
                st.rerun()
        else:
            st.caption("📦 Using built-in sample data")

        # -----------------------------------------------------
        # DATA SOURCE
        # -----------------------------------------------------

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
        <div style="text-align:center;color:#475569;font-size:10px;margin-top:20px;">
            Spectre Impact v1.0<br>
            Know what will break before you deploy.
        </div>
        """), unsafe_allow_html=True)

    if target_page is not None:
        st.switch_page(target_page)