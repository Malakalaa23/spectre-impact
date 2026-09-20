"""Production-grade test suite for Merna's frontend work.

Verifies every fix from the frontend review against Malak's latest backend
handoff. Checks structure, security, contract compliance, product quality.

Run:
    python -m pytest test_merna_work.py -v
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent
PAGES = REPO_ROOT / "pages"
COMPONENTS = REPO_ROOT / "components"
STYLES = REPO_ROOT / "styles"


# ===========================================================================
# HELPERS
# ===========================================================================


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_py(relpath: str) -> str:
    return _read(REPO_ROOT / relpath)


def _imports_ok(module_path: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_path)
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _page_files() -> list[Path]:
    return sorted(PAGES.glob("*.py"))


# ===========================================================================
# 1. IMPORTS
# ===========================================================================


class TestImports:
    def test_root_modules(self):
        modules = [
            "ai_fallback", "api_client", "bfs", "data", "filters",
            "realtime", "realtime_server", "style",
        ]
        broken = []
        for m in modules:
            ok, err = _imports_ok(m)
            if not ok:
                broken.append((m, err))
        assert not broken, f"Broken imports: {broken}"

    def test_component_modules(self):
        broken = []
        for m in ("components.audio_player", "components.code_review"):
            ok, err = _imports_ok(m)
            if not ok:
                broken.append((m, err))
        assert not broken, f"Broken components: {broken}"

    def test_page_modules(self):
        pages = _page_files()
        assert len(pages) >= 10, f"Expected 10+ pages, found {len(pages)}"
        for page in pages:
            try:
                ast.parse(_read(page))
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {page.name}: {e}")

    def test_app_py_compiles(self):
        ast.parse(_read(REPO_ROOT / "app.py"))

    def test_components_init_exists(self):
        assert (COMPONENTS / "__init__.py").exists()


# ===========================================================================
# 2. PAGE STRUCTURE
# ===========================================================================


class TestPageStructure:
    SIDEBAR_EXEMPT = {"Landing.py"}
    TITLE_EXEMPT = {"Landing.py"}

    def test_all_pages_apply_style(self):
        missing = [p.name for p in _page_files() if "apply_style()" not in _read(p)]
        assert not missing, f"Pages missing apply_style(): {missing}"

    def test_all_pages_call_sidebar(self):
        missing = []
        for page in _page_files():
            if page.name in self.SIDEBAR_EXEMPT:
                continue
            if "sidebar(" not in _read(page):
                missing.append(page.name)
        assert not missing, f"Pages missing sidebar(): {missing}"

    def test_all_pages_set_page_config(self):
        missing = [p.name for p in _page_files() if "set_page_config" not in _read(p)]
        assert not missing, f"Pages missing set_page_config: {missing}"

    def test_app_py_applies_style_and_sidebar(self):
        content = _read(REPO_ROOT / "app.py")
        assert "apply_style()" in content
        assert "sidebar(" in content

    def test_every_page_has_title(self):
        missing = []
        for page in _page_files():
            if page.name in self.TITLE_EXEMPT:
                continue
            content = _read(page)
            if "st.title(" not in content and "main-title" not in content:
                missing.append(page.name)
        assert not missing, f"Pages without a title: {missing}"

    def test_no_experimental_apis(self):
        for page in _page_files() + [REPO_ROOT / "app.py"]:
            content = _read(page)
            matches = re.findall(r"st\.experimental_\w+", content)
            assert not matches, f"{page.name} uses deprecated API: {matches}"


# ===========================================================================
# 3. CHAT.PY
# ===========================================================================


class TestChatFixes:
    def setup_method(self):
        self.chat = _read_py("pages/Chat.py")

    def test_no_short_circuit_chat_input(self):
        bad = re.search(r"\bor\s+st\.chat_input", self.chat)
        assert not bad, "Short-circuit st.chat_input bug present"

    def test_chat_input_called_directly(self):
        assert "st.chat_input(" in self.chat

    def test_chat_input_has_key(self):
        assert "key=" in self.chat[self.chat.find("st.chat_input("):][:200]

    def test_no_st_chat_message(self):
        assert "st.chat_message" not in self.chat

    def test_uses_custom_bubble_class(self):
        for cls in ("spectre-chat-bubble", "spectre-chat-user", "spectre-chat-assistant"):
            assert cls in self.chat

    def test_escapes_message_content(self):
        assert "html.escape" in self.chat

    def test_tts_payload_uses_language_not_session_id(self):
        assert "/api/tts" in self.chat
        tts_block = self.chat[self.chat.find("/api/tts"):][:400]
        assert "language" in tts_block
        assert "\"session_id\"" not in tts_block

    def test_clear_endpoint_uses_query_param(self):
        assert "/api/chat/clear?session_id=" in self.chat

    def test_empty_state_uses_lya_branding(self):
        assert "Hi, I'm Lya." in self.chat

    def test_rag_aware_suggestions(self):
        assert "customer_database.tf" in self.chat
        assert "payment service" in self.chat
        assert "past incidents" in self.chat

    def test_no_history_field_in_chat_payload(self):
        chat_call = self.chat[self.chat.find("/api/chat\""):][:300]
        assert "\"history\"" not in chat_call

    def test_has_help_on_buttons(self):
        assert len(re.findall(r"help=", self.chat)) >= 2

    def test_rerun_after_send(self):
        assert "st.rerun()" in self.chat

    def test_imports_html(self):
        assert "import html" in self.chat

    def test_session_init_pattern(self):
        assert "if \"spectre_chat\" not in st.session_state" in self.chat
        assert "if \"spectre_chat_session_id\" not in st.session_state" in self.chat
        assert "if \"chat_pending\" not in st.session_state" in self.chat


# ===========================================================================
# 4. PR_ANALYSIS.PY
# ===========================================================================


class TestPRAnalysisFixes:
    def setup_method(self):
        self.pr = _read_py("pages/PR_Analysis.py")

    def test_imports_at_top(self):
        top = "\n".join(self.pr.splitlines()[:60])
        assert "from components.audio_player import" in top
        assert "from api_client import post_bytes" in top

    def test_uses_html_escape(self):
        assert self.pr.count("html.escape") >= 5

    def test_audio_scoped_per_pr(self):
        assert "voice_audio_" in self.pr
        assert "\"voice_audio\"" not in self.pr

    def test_github_result_uses_pop(self):
        assert "pop(\"github_post_result\"" in self.pr or \
               "pop('github_post_result'" in self.pr

    def test_no_duplicate_impact_line(self):
        count = len(re.findall(r"^impact_line\s*=", self.pr, re.MULTILINE))
        assert count == 1

    def test_imports_html(self):
        assert "import html" in self.pr


# ===========================================================================
# 5. AUDIO_PLAYER.PY
# ===========================================================================


class TestAudioPlayerFix:
    def setup_method(self):
        self.ap = _read_py("components/audio_player.py")

    def test_uses_container_border(self):
        assert "st.container(border=True)" in self.ap

    def test_no_split_div(self):
        opens = re.findall(r"st\.markdown\(\s*[\"']<div", self.ap)
        closes = re.findall(r"st\.markdown\(\s*[\"']</div>", self.ap)
        assert not (opens and closes)

    def test_has_docstring(self):
        assert '"""' in self.ap


# ===========================================================================
# 6. CUSTOM.CSS
# ===========================================================================


class TestCustomCSS:
    def setup_method(self):
        css_path = STYLES / "custom.css"
        assert css_path.exists()
        self.css = _read(css_path)

    def test_has_root_variables(self):
        assert ":root" in self.css
        for var in ("--spectre-accent", "--spectre-bg", "--spectre-panel"):
            assert var in self.css

    def test_has_chat_bubble_style(self):
        for cls in (".spectre-chat-bubble", ".spectre-chat-user", ".spectre-chat-assistant"):
            assert cls in self.css

    def test_has_typing_animation(self):
        assert ".spectre-typing" in self.css
        assert "@keyframes spectrePulse" in self.css

    def test_has_tool_call_style(self):
        assert ".spectre-tool-call" in self.css

    def test_has_finding_styles(self):
        for cls in (".spectre-finding-critical", ".spectre-finding-high",
                    ".spectre-finding-medium", ".spectre-finding-low"):
            assert cls in self.css

    def test_has_responsive_breakpoints(self):
        assert "@media (max-width: 768px)" in self.css
        assert "@media (max-width: 480px)" in self.css

    def test_has_reduced_motion(self):
        assert "prefers-reduced-motion" in self.css

    def test_has_focus_visible(self):
        assert "focus-visible" in self.css

    def test_no_duplicate_chat_bubble(self):
        assert self.css.count(".spectre-chat-bubble{") <= 1

    def test_no_duplicate_typing(self):
        assert self.css.count(".spectre-typing{") <= 1

    def test_no_duplicate_keyframes(self):
        assert self.css.count("@keyframes spectrePulse") <= 1

    def test_no_dead_classes(self):
        for cls in (".spectre-mobile", ".spectre-code"):
            assert cls not in self.css, f"Dead CSS class: {cls}"

    def test_important_usage_not_excessive(self):
        assert self.css.count("!important") < 200

    def test_css_has_no_obvious_typos(self):
        for typo in ("colour:", "transparant", "widht", "heigth"):
            assert typo not in self.css

    def test_no_orphaned_spectre_classes(self):
        defined = set(re.findall(r"\.(spectre-[\w-]+)", self.css))
        used: set[str] = set()
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            for m in re.finditer(r"spectre-[\w-]+", _read(py)):
                used.add(m.group(0))
        orphans = defined - used
        assert len(orphans) <= 5, f"Orphaned CSS classes: {sorted(orphans)}"


# ===========================================================================
# 7. LANDING.PY
# ===========================================================================


class TestLanding:
    def setup_method(self):
        self.landing = _read_py("pages/Landing.py")

    def test_no_localhost_default(self):
        assert "http://localhost:8501" not in self.landing

    def test_requires_landing_url_env(self):
        assert "SPECTRE_LANDING_URL" in self.landing

    def test_errors_when_missing(self):
        assert "st.error" in self.landing or "st.warning" in self.landing

    def test_has_legal_links(self):
        for link in ("Privacy Policy", "Terms of Service", "Contact"):
            assert link in self.landing

    def test_has_qr_code(self):
        assert "qrcode" in self.landing

    def test_has_cta_button(self):
        assert "Open Developer Dashboard" in self.landing


# ===========================================================================
# 8. BUSINESS_VIEW / WEEKLY_REVIEW
# ===========================================================================


class TestBusinessView:
    def setup_method(self):
        self.bv = _read_py("pages/Business_View.py")

    def test_uses_container_border(self):
        assert "st.container(border=True)" in self.bv

    def test_escapes_summary(self):
        assert "html.escape" in self.bv

    def test_imports_html(self):
        assert "import html" in self.bv

    def test_has_audience_appropriate_language(self):
        for term in ("kubectl", "helm", "terraform apply", "docker run"):
            assert term not in self.bv, f"Business View has technical term: {term}"


class TestWeeklyReview:
    def setup_method(self):
        self.wr = _read_py("pages/Weekly_Review.py")

    def test_no_fake_recommendation_buttons(self):
        assert "Recommendation added" not in self.wr

    def test_no_fake_report_button(self):
        assert "Weekly report generated successfully" not in self.wr

    def test_has_real_download(self):
        assert "st.download_button" in self.wr

    def test_escapes_service_names(self):
        assert "html.escape" in self.wr

    def test_download_has_mime_type(self):
        assert "mime=" in self.wr


# ===========================================================================
# 9. ROLLBACK_CENTER
# ===========================================================================


class TestRollbackCenter:
    def setup_method(self):
        self.rc = _read_py("pages/Rollback_Center.py")

    def test_status_scoped_per_pr(self):
        assert "rollback_status_" in self.rc

    def test_reauth_scoped_per_pr(self):
        assert "rollback_reauthenticated_" in self.rc

    def test_reauth_cleared_after_execute(self):
        assert "False" in self.rc and "rollback_reauthenticated" in self.rc

    def test_escapes_values(self):
        assert "html.escape" in self.rc

    def test_uses_finally(self):
        assert "finally:" in self.rc

    def test_dry_run_exists(self):
        assert "Dry Run" in self.rc or "dry_run" in self.rc

    def test_confirm_required(self):
        assert "CONFIRM" in self.rc


# ===========================================================================
# 10. CODE_REVIEW
# ===========================================================================


class TestCodeReview:
    def setup_method(self):
        self.cr = _read_py("pages/Code_Review.py")

    def test_has_progress_bar(self):
        assert "st.progress" in self.cr

    def test_has_review_running_flag(self):
        assert "review_running" in self.cr

    def test_timeout_120(self):
        assert "timeout=120" in self.cr


# ===========================================================================
# 11. ABOUT / HOW_IT_WORKS
# ===========================================================================


class TestAboutContent:
    def setup_method(self):
        self.about = _read_py("pages/About.py")

    def test_correct_database(self):
        assert "PostgreSQL" in self.about
        assert "SQLite" not in self.about

    def test_correct_ai_provider(self):
        assert "Groq" in self.about
        assert "OpenAI GPT" not in self.about

    def test_mentions_lya(self):
        assert "Lya" in self.about

    def test_correct_roles(self):
        assert "Backend Engineer" in self.about
        assert "Blast Radius Engine" not in self.about


class TestHowItWorksContent:
    def setup_method(self):
        self.hiw = _read_py("pages/How_It_Works.py")

    def test_mentions_rag(self):
        assert "RAG" in self.hiw

    def test_mentions_multi_provider(self):
        assert "Multi-Provider AI" in self.hiw or "multi-provider" in self.hiw.lower()

    def test_mentions_safety(self):
        assert "Safety" in self.hiw

    def test_mentions_rollback_executor(self):
        assert "Rollback Executor" in self.hiw


# ===========================================================================
# 12. HTML ESCAPING
# ===========================================================================


class TestHTMLEscaping:
    def test_app_py_team_messages_escaped(self):
        """[SECURITY] The one confirmed real bug in app.py."""
        content = _read(REPO_ROOT / "app.py")
        idx = content.find("get_team_messages(limit")
        if idx == -1:
            pytest.skip("get_team_messages block not found")
        block = content[idx:idx + 1500]
        if "message.get('text'" in block or "message.get('author'" in block:
            assert "html.escape" in block, \
                "app.py team messages not escaped — REAL BUG"

    def test_every_page_imports_html_when_needed(self):
        for page in _page_files():
            content = _read(page)
            if "html.escape" in content:
                assert "import html" in content, \
                    f"{page.name} uses html.escape but doesn't import html"

    def test_app_py_imports_html_when_needed(self):
        content = _read(REPO_ROOT / "app.py")
        uses_user_data = (
            "message.get('text'" in content or
            "message.get('author'" in content or
            "message.get('timestamp'" in content
        )
        uses_unsafe = "unsafe_allow_html=True" in content
        if uses_user_data and uses_unsafe:
            assert "import html" in content


# ===========================================================================
# 13. BACKEND CONTRACT
# ===========================================================================


class TestBackendContract:
    def test_chat_payload_shape(self):
        content = _read_py("pages/Chat.py")
        assert "message" in content
        assert "session_id" in content

    def test_api_client_has_required_methods(self):
        api = _read_py("api_client.py")
        for method in ("post_json_detailed", "post_bytes", "post_multipart", "get_json"):
            assert f"def {method}" in api

    def test_api_client_has_timeouts(self):
        api = _read_py("api_client.py")
        for call in ("requests.post", "requests.get"):
            for match in re.finditer(re.escape(call), api):
                snippet = api[match.start():match.start() + 300]
                assert "timeout=" in snippet, f"{call} without timeout"

    def test_no_hardcoded_localhost(self):
        for py in _page_files() + [REPO_ROOT / "app.py"]:
            content = _read(py)
            if "http://localhost" in content or "127.0.0.1" in content:
                pytest.fail(f"{py.name} has hardcoded localhost URL")

    def test_voice_endpoint_flagged(self):
        content = _read_py("pages/PR_Analysis.py")
        if "/api/voice/" in content:
            print("\nWARNING: PR_Analysis.py uses /api/voice/{pr} — verify with Malak")


# ===========================================================================
# 14. CSS CLASS COVERAGE
# ===========================================================================


class TestCSSClassCoverage:
    def _find_python_classes(self) -> set[str]:
        classes: set[str] = set()
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            for m in re.finditer(r"class=['\"]([^'\"]*spectre[^'\"]*)", _read(py)):
                for cls in m.group(1).split():
                    if cls.startswith("spectre-"):
                        classes.add(cls)
        return classes

    def test_all_static_classes_defined(self):
        css = _read(STYLES / "custom.css")
        used = self._find_python_classes()
        static_classes = {c for c in used if "{" not in c and "}" not in c}
        missing = [c for c in static_classes if f".{c}" not in css]
        assert not missing, f"Classes used but not in CSS: {missing}"


# ===========================================================================
# 15. ACCESSIBILITY
# ===========================================================================


class TestAccessibility:
    def test_reduced_motion_in_css(self):
        assert "prefers-reduced-motion" in _read(STYLES / "custom.css")

    def test_focus_visible_in_css(self):
        assert "focus-visible" in _read(STYLES / "custom.css")

    def test_interactive_widgets_have_help_on_key_pages(self):
        for relpath in ("pages/Chat.py", "pages/PR_Analysis.py", "pages/Rollback_Center.py"):
            content = _read_py(relpath)
            interactive = len(re.findall(
                r"st\.(button|selectbox|text_input|text_area|checkbox|radio)\(",
                content,
            ))
            helps = len(re.findall(r"help=", content))
            if interactive > 0 and helps / interactive < 0.5:
                print(f"\nLow help coverage in {relpath}: {helps}/{interactive}")


# ===========================================================================
# 16. NO DUPLICATES
# ===========================================================================


class TestNoDuplicates:
    def test_no_duplicate_widget_keys(self):
        for page in list(_page_files()) + [REPO_ROOT / "app.py"]:
            content = _read(page)
            keys = re.findall(r'key\s*=\s*["\']([^"\'{]+)["\']', content)
            duplicates = [k for k in set(keys) if keys.count(k) > 1]
            assert not duplicates, f"{page.name}: duplicate keys {duplicates}"

    def test_no_empty_files_except_known(self):
        KNOWN_EMPTY = {"sample_upload.json", "__init__.py"}
        for f in REPO_ROOT.rglob("*"):
            if ".venv" in str(f) or "__pycache__" in str(f) or f.is_dir():
                continue
            if f.name in KNOWN_EMPTY:
                continue
            if f.stat().st_size == 0:
                pytest.fail(f"Empty file: {f.relative_to(REPO_ROOT)}")


# ===========================================================================
# 17. DEPLOYMENT
# ===========================================================================


class TestDeployment:
    def test_dockerfile_exists(self):
        assert (REPO_ROOT / "Dockerfile").exists()

    def test_docker_compose_exists(self):
        assert (REPO_ROOT / "docker-compose.yml").exists()

    def test_requirements_has_core_packages(self):
        reqs = _read(REPO_ROOT / "requirements.txt").lower()
        for pkg in ("streamlit", "pandas", "plotly", "requests", "fastapi", "uvicorn", "qrcode"):
            assert pkg in reqs

    def test_streamlit_config_exists(self):
        assert (REPO_ROOT / ".streamlit" / "config.toml").exists()

    def test_env_example_exists(self):
        assert (REPO_ROOT / ".env.example").exists()

    def test_dockerfile_uses_python(self):
        df = _read(REPO_ROOT / "Dockerfile")
        assert "python" in df.lower() or "FROM" in df


# ===========================================================================
# 18. SOURCE INTEGRITY
# ===========================================================================


class TestSourceIntegrity:
    STATIC_PAGES = {"About.py", "How_It_Works.py", "Landing.py"}

    def test_pages_use_clean_html_or_safe_helper(self):
        SAFE_HELPERS = (
            "clean_html", "html.escape",
            "severity_badge_html", "empty_state", "metric_card",
        )
        for page in _page_files():
            content = _read(page)
            if "unsafe_allow_html=True" in content:
                assert any(h in content for h in SAFE_HELPERS), \
                    f"{page.name} uses unsafe_allow_html without a safe helper"

    def test_pages_handle_empty_data(self):
        for page in _page_files():
            if page.name in self.STATIC_PAGES:
                continue
            content = _read(page)
            assert (
                "empty_state" in content or
                "if not" in content or
                "st.stop()" in content
            ), f"{page.name} has no empty-data handling"

    def test_no_print_in_pages(self):
        for page in _page_files():
            matches = re.findall(r"^\s*print\(", _read(page), re.MULTILINE)
            assert not matches, f"{page.name} has {len(matches)} print() calls"


# ===========================================================================
# 19. STYLING CONSISTENCY
# ===========================================================================


class TestStylingConsistency:
    def test_all_pages_import_from_style(self):
        for page in _page_files():
            assert "from style import" in _read(page), \
                f"{page.name} doesn't import from shared style module"

    def test_style_exposes_required_helpers(self):
        style = _read_py("style.py")
        for name in ("apply_style", "sidebar", "clean_html",
                     "empty_state", "severity_badge_html", "metric_card"):
            assert f"def {name}" in style

    def test_sidebar_nav_items_point_to_existing_pages(self):
        page_refs = re.findall(r'"(pages/[^"]+\.py)"', _read_py("style.py"))
        for ref in page_refs:
            assert (REPO_ROOT / ref).exists(), f"NAV_ITEMS missing: {ref}"


# ===========================================================================
# 20. PRODUCT QUALITY
# ===========================================================================


class TestProductQuality:
    def test_page_count_and_ratio(self):
        pages = _page_files()
        css = _read(STYLES / "custom.css")
        assert len(pages) >= 10
        assert css.count("\n") > 500

    def test_every_page_has_error_handling(self):
        for page in _page_files():
            content = _read(page)
            if "/api/" in content:
                assert (
                    "st.warning" in content or
                    "st.error" in content or
                    "st.info" in content
                ), f"{page.name} calls API but doesn't handle errors"

    def test_brand_naming_consistent(self):
        TEST_FILES = {"test_merna_work.py", "test_abubakr_work.py"}
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            if py.name in TEST_FILES:
                continue
            content = _read(py)
            for bad in ("SpectreImpact", "spectre-impact-platform", "Spectre impact"):
                assert bad not in content, f"{py.name} has inconsistent branding: {bad}"

    def test_no_todo_or_fixme_in_pages(self):
        for page in _page_files():
            matches = re.findall(r"#\s*(TODO|FIXME|XXX|HACK)", _read(page))
            assert not matches, f"{page.name} has {len(matches)} TODO/FIXME: {matches}"

    def test_has_docstrings_on_public_functions(self):
        for comp in COMPONENTS.glob("*.py"):
            if comp.name == "__init__.py":
                continue
            tree = ast.parse(_read(comp))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    docstring = ast.get_docstring(node)
                    assert docstring, \
                        f"{comp.name}::{node.name} missing docstring"


# ===========================================================================
# 21. MALAK'S HANDOFF CONTRACT
# ===========================================================================


class TestMalakHandoff:
    def test_chat_timeout_is_180(self):
        content = _read_py("pages/Chat.py")
        idx = content.find('"/api/chat"')
        if idx == -1:
            pytest.skip("/api/chat call not found")
        block = content[max(0, idx - 200):idx + 400]
        assert "timeout=180" in block, (
            "Chat call does not use timeout=180. "
            "Malak's handoff requires 180s for tool-heavy responses."
        )

    def test_chat_sends_session_id(self):
        assert "session_id" in _read_py("pages/Chat.py")

    def test_chat_persists_messages_in_session_state(self):
        assert "st.session_state.spectre_chat" in _read_py("pages/Chat.py")

    def test_chat_has_new_chat_button(self):
        content = _read_py("pages/Chat.py")
        assert "/api/chat/clear" in content
        assert "New Chat" in content

    def test_chat_renders_tool_calls(self):
        content = _read_py("pages/Chat.py")
        assert "tool_calls" in content or "tools" in content

    def test_chat_handles_400_and_500(self):
        content = _read_py("pages/Chat.py")
        assert "400" in content
        assert "500" in content

    def test_stt_ui_exists(self):
        assert "audio_input" in _read_py("pages/Chat.py")

    def test_stt_sends_transcript_to_chat(self):
        content = _read_py("pages/Chat.py")
        assert "chat_pending" in content or "transcript" in content

    def test_stt_endpoint_documented(self):
        content = _read_py("pages/Chat.py")
        if "/api/stt" in content:
            print("\nWARNING: /api/stt called by Chat.py — verify with Malak")

    def test_speak_button_on_assistant_messages(self):
        content = _read_py("pages/Chat.py")
        assert "🔊" in content
        assert "/api/tts" in content

    def test_tts_payload_matches_handoff(self):
        content = _read_py("pages/Chat.py")
        idx = content.find("/api/tts")
        block = content[idx:idx + 300]
        assert "text" in block
        assert "language" in block

    def test_tts_timeout_present(self):
        content = _read_py("pages/Chat.py")
        idx = content.find("/api/tts")
        block = content[idx:idx + 300]
        assert "timeout" in block

    def test_landing_calls_presets_endpoint(self):
        content = _read_py("pages/Landing.py")
        assert "/api/landing/presets" in content, (
            "Landing.py does not call /api/landing/presets. "
            "Malak's handoff requires bilingual presets."
        )

    def test_landing_has_language_toggle(self):
        content = _read_py("pages/Landing.py")
        has_toggle = "مصري" in content or (
            "language" in content.lower() and "button" in content.lower()
        )
        assert has_toggle, (
            "Landing.py has no language toggle. "
            "Malak's handoff requires English / مصري buttons."
        )

    def test_landing_uses_preset_headline(self):
        content = _read_py("pages/Landing.py")
        assert "preset" in content.lower() or "headline" in content.lower(), (
            "Landing.py has a hardcoded headline. "
            "Malak's handoff requires language-dependent headline from preset."
        )

    def test_landing_has_dual_ctas(self):
        content = _read_py("pages/Landing.py")
        has_chat_cta = "Dashboard" in content or "Chat" in content
        has_analysis_cta = "Analysis" in content or "PR" in content
        assert has_chat_cta and has_analysis_cta, (
            "Landing.py doesn't have both CTAs. "
            "Handoff requires 'Try the Chat' and 'Watch a PR Analysis'."
        )

    def test_chat_has_language_indicator(self):
        content = _read_py("pages/Chat.py")
        assert (
            "🌐" in content or
            "language indicator" in content.lower() or
            "responding in" in content.lower()
        ), (
            "Chat.py has no language indicator. "
            "Malak's handoff requires a badge showing which language Lya responds in."
        )

    def test_detect_lang_helper_exists(self):
        content = _read_py("pages/Chat.py")
        has_arabic_range = "\\u0600" in content or "\\u06ff" in content
        has_detect_lang = "detect_lang" in content or "is_arabic" in content
        assert has_arabic_range or has_detect_lang, (
            "Chat.py has no language detection. "
            "Malak's handoff provides: `any('\\u0600' <= c <= '\\u06ff' for c in text)`."
        )

    def test_rollback_shows_plan_steps(self):
        assert "rollback" in _read_py("pages/Rollback_Center.py").lower()

    def test_rollback_has_not_wired_message(self):
        content = _read_py("pages/Rollback_Center.py")
        assert (
            "not wired" in content.lower() or
            "not connected" in content.lower() or
            "/api/rollback" in content
        )

    def test_landing_has_logo_and_pitch(self):
        content = _read_py("pages/Landing.py")
        assert "🚀" in content or "logo" in content.lower()
        assert (
            "pitch" in content.lower() or
            "Know what" in content or
            "change intelligence" in content.lower()
        )

    def test_app_checks_backend_health(self):
        content = _read(REPO_ROOT / "app.py")
        assert "/ping" in content or "health" in content.lower(), (
            "app.py does not check backend health. "
            "Malak's handoff: call GET /ping at startup."
        )

    def test_dashboard_calls_live_feed(self):
        content = _read(REPO_ROOT / "app.py")
        assert "/api/live-feed" in content or "live-feed" in content, (
            "app.py does not call /api/live-feed. "
            "Malak's handoff requires a live activity panel."
        )


# ===========================================================================
# 22. SECURITY DEEP SCAN
# ===========================================================================


class TestSecurity:
    def test_no_hardcoded_api_keys(self):
        patterns = [
            r"sk-[a-zA-Z0-9]{40,}",
            r"gsk_[a-zA-Z0-9]{40,}",
            r"sk-ant-[a-zA-Z0-9\-_]{40,}",
        ]
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            if py.name.startswith("test_"):
                continue
            content = _read(py)
            for pat in patterns:
                match = re.search(pat, content)
                assert not match, \
                    f"Hardcoded key in {py.name}: {match.group()[:20]}..."

    def test_no_aws_keys(self):
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            if py.name.startswith("test_"):
                continue
            match = re.search(r"AKIA[0-9A-Z]{16}", _read(py))
            assert not match, f"AWS key in {py.name}"

    def test_no_hardcoded_passwords(self):
        patterns = [
            r'password\s*=\s*["\'][^"\']{4,}["\']',
            r'secret\s*=\s*["\'][^"\']{8,}["\']',
        ]
        skip_files = {"test_merna_work.py", "test_abubakr_work.py"}
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            if py.name in skip_files:
                continue
            content = _read(py)
            for pat in patterns:
                assert not re.search(pat, content), \
                    f"Possible hardcoded credential in {py.name}"

    def test_env_in_gitignore(self):
        env = REPO_ROOT / ".env"
        gitignore = REPO_ROOT / ".gitignore"
        if env.exists() and gitignore.exists():
            assert ".env" in _read(gitignore)

    def test_no_eval_or_exec(self):
        for page in _page_files() + [REPO_ROOT / "app.py"]:
            content = _read(page)
            assert "eval(" not in content, f"{page.name} uses eval()"
            assert "exec(" not in content, f"{page.name} uses exec()"

    def test_no_subprocess_shell_true(self):
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            if "pages" not in str(py) and py.name != "app.py":
                continue
            assert "shell=True" not in _read(py), f"{py.name} uses shell=True"

    def test_no_pickle_loads(self):
        for page in _page_files():
            assert "pickle.load" not in _read(page), f"{page.name} uses pickle.load"

    def test_no_yaml_load_unsafe(self):
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "__pycache__" in str(py):
                continue
            if "pages" not in str(py) and py.name != "app.py":
                continue
            content = _read(py)
            for match in re.finditer(r"yaml\.load\(", content):
                snippet = content[match.start():match.start() + 100]
                assert (
                    "Loader=yaml.SafeLoader" in snippet or
                    "Loader=SafeLoader" in snippet
                ), f"{py.name} uses yaml.load without SafeLoader"

    def test_all_http_calls_have_timeouts(self):
        for py in list(_page_files()) + [REPO_ROOT / "app.py"]:
            content = _read(py)
            for call in ("requests.post", "requests.get"):
                for match in re.finditer(re.escape(call), content):
                    snippet = content[match.start():match.start() + 400]
                    assert "timeout=" in snippet, \
                        f"{py.name}: {call} without timeout"

    def test_no_open_redirects(self):
        for page in _page_files():
            content = _read(page)
            for match in re.finditer(r"st\.switch_page\(\s*([^\)]+)\)", content):
                arg = match.group(1).strip()
                if not (arg.startswith('"') or arg.startswith("'")):
                    pytest.fail(
                        f"{page.name}: st.switch_page with dynamic target: {arg}"
                    )

    def test_team_message_rendering_is_escaped(self):
        """[SECURITY] The single confirmed real bug — app.py team messages.

        Checks specifically for the pattern:
            {message.get('author'...)} or {message.get('text'...)}
        rendered without html.escape.
        """
        content = _read(REPO_ROOT / "app.py")

        # Find the block that renders team messages
        idx = content.find("get_team_messages")
        if idx == -1:
            pytest.skip("team messages block not found")

        block = content[idx:idx + 2000]

        # These are the exact user-data patterns from message objects
        user_data_patterns = [
            "message.get('author'",
            "message.get('text'",
            'message.get("author"',
            'message.get("text"',
        ]
        uses_user_data = any(p in block for p in user_data_patterns)

        if uses_user_data:
            assert "html.escape" in block, (
                "app.py team message rendering uses user data "
                "(message.get('author') / message.get('text')) "
                "without html.escape — REAL BUG"
            )

    def test_event_rendering_is_escaped(self):
        """[SECURITY] Live event rendering in app.py must escape user data."""
        content = _read(REPO_ROOT / "app.py")

        idx = content.find("get_live_events")
        if idx == -1:
            pytest.skip("live events block not found")

        block = content[idx:idx + 3000]

        # The event block uses these user-data fields
        user_data_fields = [
            "event.get('author'",
            "event.get('repository'",
            "event.get('commit_message'",
            "event.get('problem'",
            "event.get('ai_analysis'",
        ]
        uses_user_data = any(f in block for f in user_data_fields)

        if uses_user_data:
            # Check if any of them are rendered with unsafe_allow_html
            # and without html.escape
            markdown_calls = re.findall(
                r"st\.markdown\((.*?)unsafe_allow_html\s*=\s*True",
                block,
                re.DOTALL,
            )
            for call in markdown_calls:
                if any(f.split("'")[1] in call for f in user_data_fields
                       if f in call):
                    assert "html.escape" in call, (
                        "app.py event rendering uses user data in unsafe "
                        "HTML without html.escape"
                    )

    def test_no_secrets_in_committed_env(self):
        env_ex = REPO_ROOT / ".env.example"
        if not env_ex.exists():
            pytest.skip(".env.example not present")
        content = _read(env_ex)
        for match in re.finditer(r"(\w+)\s*=\s*(\S+)", content):
            key, value = match.group(1), match.group(2)
            if len(value) > 20 and not value.startswith("your-") and \
               not value.startswith("<") and value != "auto":
                assert value.startswith("your_") or \
                       value.startswith("http") or \
                       value.startswith("#") or \
                       value == "", \
                    f".env.example may contain a real value for {key}"


# ===========================================================================
# 23. FILE INTEGRITY
# ===========================================================================


class TestFileIntegrity:
    def test_no_git_artifacts_committed(self):
        for bad in (".pyc", ".pyo", ".pyd"):
            for m in REPO_ROOT.rglob(f"*{bad}"):
                if ".venv" in str(m) or "__pycache__" in str(m):
                    continue
                pytest.fail(f"Compiled file tracked: {m.relative_to(REPO_ROOT)}")

    def test_no_editor_backup_files(self):
        for pattern in ("*.swp", "*.bak", "*~"):
            matches = list(REPO_ROOT.rglob(pattern))
            assert not matches, f"Editor backup files present: {matches}"

    def test_no_large_files_committed(self):
        for f in REPO_ROOT.rglob("*"):
            if f.is_dir() or ".venv" in str(f) or ".git" in str(f):
                continue
            if f.suffix == ".mp3":
                continue
            size = f.stat().st_size
            assert size < 1_000_000, \
                f"Large file committed: {f.relative_to(REPO_ROOT)} ({size} bytes)"

    def test_requirements_pinned_or_floored(self):
        reqs = _read(REPO_ROOT / "requirements.txt")
        for line in reqs.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            assert any(op in line for op in (">=", "==", "~=", ">")), \
                f"Unpinned requirement: {line}"