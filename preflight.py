"""
preflight.py — one-shot project inspection for deployment.

Run from the repo root:
    python preflight.py

Prints everything needed to plan the Dockerfile and HF Space deploy:
    - what files exist where
    - what entry points are present
    - what data files are populated
    - what environment variables are referenced vs set
    - whether Merna's frontend is in this workspace
    - what endpoints main.py exposes
    - git state

No heavy imports. No model loads. Fast.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

# Force UTF-8 so Arabic content doesn't blow up the terminal
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


ROOT = Path(__file__).resolve().parent


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def line(label: str, value) -> None:
    print(f"  {label:<32} {value}")


def file_info(path: Path) -> str:
    """Return a compact one-line description of a file."""
    if not path.exists():
        return "MISSING"
    if path.is_dir():
        n = sum(1 for _ in path.rglob("*") if _.is_file())
        return f"dir ({n} files)"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# 1. Top-level structure
# ---------------------------------------------------------------------------
def check_structure() -> None:
    section("1. Top-level structure")

    folders = sorted([p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")])
    line("folders", ", ".join(folders) if folders else "(none)")

    py_files = sorted([p.name for p in ROOT.glob("*.py")])
    line("root .py files", ", ".join(py_files) if py_files else "(none)")

    print()
    print("  Deployment-relevant files:")
    for name in ("Dockerfile", "docker-compose.yml", "supervisord.conf", "Procfile",
                 "app.py", "README.md", "requirements.txt", ".env", ".env.example",
                 ".gitignore", ".dockerignore"):
        print(f"    {name:<24} {file_info(ROOT / name)}")


# ---------------------------------------------------------------------------
# 2. Entry points and core modules
# ---------------------------------------------------------------------------
def check_entry_points() -> None:
    section("2. Entry points and core modules")

    checks = [
        "main.py",
        "app.py",
        "database.py",
        "github_client.py",
        "cache.py",
        "config.py",
        "ai/tts.py",
        "ai/stt.py",
        "ai/multi_provider.py",
        "chat/agent.py",
        "chat/memory.py",
        "chat/prompts.py",
        "chat/safety.py",
        "rag/vector_store.py",
        "rag/retriever.py",
        "rag/populate.py",
        "backend/analysis/change_analysis_engine.py",
        "backend/main.py",
    ]
    for path in checks:
        line(path, file_info(ROOT / path))


# ---------------------------------------------------------------------------
# 3. Data files
# ---------------------------------------------------------------------------
def check_data() -> None:
    section("3. Data files")

    checks = [
        "backend/data/dependency_graph.yaml",
        "backend/data/business_map.yaml",
        "backend/data/resource_map.json",
        "history.db",
        "rag_db/chroma.sqlite3",
    ]
    for path in checks:
        line(path, file_info(ROOT / path))

    dg = ROOT / "backend" / "data" / "dependency_graph.yaml"
    if dg.exists():
        text = dg.read_text(encoding="utf-8", errors="replace")
        nodes = len(re.findall(r"^\s{2}\w+:", text, re.MULTILINE))
        line("  nodes in graph (approx)", nodes)

    bm = ROOT / "backend" / "data" / "business_map.yaml"
    if bm.exists():
        text = bm.read_text(encoding="utf-8", errors="replace")
        entries = len(re.findall(r"^\w+:", text, re.MULTILINE))
        line("  entries in business map", entries)


# ---------------------------------------------------------------------------
# 4. RAG DB contents
# ---------------------------------------------------------------------------
def check_rag_db() -> None:
    section("4. RAG database")

    db_path = ROOT / "rag_db" / "chroma.sqlite3"
    if not db_path.exists():
        line("chroma.sqlite3", "MISSING")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        try:
            cur.execute("SELECT COUNT(*) FROM embeddings")
            line("embedding rows", cur.fetchone()[0])
        except Exception as e:
            line("embedding rows", f"error: {e}")

        try:
            cur.execute("SELECT name FROM collections")
            names = [row[0] for row in cur.fetchall()]
            line("collections", ", ".join(names) if names else "(none)")
        except Exception as e:
            line("collections", f"error: {e}")

        conn.close()
    except Exception as e:
        line("chroma.sqlite3 open", f"error: {e}")


# ---------------------------------------------------------------------------
# 5. Environment variables
# ---------------------------------------------------------------------------
def check_env() -> None:
    section("5. Environment variables")

    referenced: set[str] = set()
    skip_dirs = {"venv", ".venv", "node_modules", "__pycache__", ".git", "rag_db"}
    for py in ROOT.rglob("*.py"):
        if any(s in py.parts for s in skip_dirs):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        pattern = r'os\.(?:getenv|environ(?:\.get)?)\s*[\(\[]\s*["\']([A-Z_][A-Z0-9_]*)["\']'
        for m in re.finditer(pattern, text):
            referenced.add(m.group(1))

    line("keys referenced in code", len(referenced))
    for key in sorted(referenced):
        print(f"    - {key}")

    env_file = ROOT / ".env"
    print()
    if env_file.exists():
        set_keys = set()
        for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            set_keys.add(raw.split("=", 1)[0].strip())
        line(".env file", "present")
        line("keys set in .env", len(set_keys))
        for key in sorted(set_keys):
            print(f"    - {key}")

        missing = referenced - set_keys
        if missing:
            print()
            print(f"  KEYS REFERENCED BUT NOT SET: {len(missing)}")
            for key in sorted(missing):
                print(f"    ! {key}")
    else:
        line(".env file", "MISSING")


# ---------------------------------------------------------------------------
# 6. Frontend detection
# ---------------------------------------------------------------------------
def check_frontend() -> None:
    section("6. Frontend detection")

    app_py = ROOT / "app.py"
    pages = ROOT / "pages"
    dashboard = ROOT / "dashboard"

    line("app.py in this workspace", "YES" if app_py.exists() else "NO")
    line("pages/ folder", "YES" if pages.exists() else "NO")
    if pages.exists():
        names = sorted([p.name for p in pages.glob("*.py")])
        print(f"    {', '.join(names) if names else '(empty)'}")
    line("dashboard/ folder", "YES" if dashboard.exists() else "NO")

    merna_root = Path("C:/Users/Malak/merna-review")
    if merna_root.exists():
        print()
        line("Merna's workspace", str(merna_root))
        line("  her app.py", "YES" if (merna_root / "app.py").exists() else "NO")
        line("  her pages/", "YES" if (merna_root / "pages").exists() else "NO")
        if (merna_root / "pages").exists():
            merna_pages = sorted([p.name for p in (merna_root / "pages").glob("*.py")])
            print(f"    {', '.join(merna_pages)}")


# ---------------------------------------------------------------------------
# 7. Requirements check
# ---------------------------------------------------------------------------
def check_requirements() -> None:
    section("7. Requirements.txt")

    req = ROOT / "requirements.txt"
    if not req.exists():
        line("requirements.txt", "MISSING")
        return

    text = req.read_text(encoding="utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    line("non-comment lines", len(lines))

    critical = [
        "fastapi", "uvicorn", "streamlit", "chromadb",
        "sentence-transformers", "transformers", "torch",
        "edge-tts", "faster-whisper", "langchain", "groq",
        "PyGithub", "python-multipart",
    ]
    text_lower = text.lower()
    present = [p for p in critical if p.lower() in text_lower]
    missing = [p for p in critical if p.lower() not in text_lower]

    line("critical present", f"{len(present)}/{len(critical)}")
    if missing:
        line("MISSING critical", ", ".join(missing))


# ---------------------------------------------------------------------------
# 8. main.py endpoints
# ---------------------------------------------------------------------------
def check_main_endpoints() -> None:
    section("8. main.py endpoints")

    main_py = ROOT / "main.py"
    if not main_py.exists():
        line("main.py", "MISSING")
        return

    text = main_py.read_text(encoding="utf-8", errors="replace")
    endpoints = re.findall(r'@app\.(get|post|put|delete|patch)\("([^"]+)"', text)
    line("total endpoints", len(endpoints))
    for method, path in endpoints:
        print(f"    {method.upper():<6} {path}")


# ---------------------------------------------------------------------------
# 9. Git state
# ---------------------------------------------------------------------------
def check_git() -> None:
    section("9. Git state")

    def run_git(*args: str) -> str:
        try:
            r = subprocess.run(["git", *args], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=10)
            return (r.stdout or r.stderr).strip()
        except Exception as e:
            return f"error: {e}"

    line("branch", run_git("branch", "--show-current"))
    print()
    print("  status:")
    status = run_git("status", "--short")
    if status:
        for s in status.splitlines():
            print(f"    {s}")
    else:
        print("    (clean)")
    print()
    print("  last 5 commits:")
    for c in run_git("log", "--oneline", "-5").splitlines():
        print(f"    {c}")


# ---------------------------------------------------------------------------
# 10. README frontmatter check (HF Space needs this)
# ---------------------------------------------------------------------------
def check_readme_frontmatter() -> None:
    section("10. README frontmatter (HF Space requirement)")

    readme = ROOT / "README.md"
    if not readme.exists():
        line("README.md", "MISSING")
        return

    text = readme.read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        # Find the closing ---
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1].strip()
            line("frontmatter", "present")
            for fm_line in fm.splitlines()[:20]:
                print(f"    {fm_line}")
        else:
            line("frontmatter", "malformed (no closing ---)")
    else:
        line("frontmatter", "MISSING (HF Space won't know how to build)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 72)
    print("  SPECTRE IMPACT — PREFLIGHT CHECK")
    print("=" * 72)
    print(f"  Repo root: {ROOT}")
    print(f"  Python:    {sys.version.split()[0]}")

    check_structure()
    check_entry_points()
    check_data()
    check_rag_db()
    check_env()
    check_frontend()
    check_requirements()
    check_main_endpoints()
    check_git()
    check_readme_frontmatter()

    print()
    print("=" * 72)
    print("  END OF REPORT")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())