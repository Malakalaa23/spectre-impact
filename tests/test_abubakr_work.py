"""Test suite for Abu Bakr's Spectre Impact work.

Run:
    python -m pytest test_abubakr_work.py -v
"""

from __future__ import annotations

import concurrent.futures
import importlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent


# ===========================================================================
# IMPORTS
# ===========================================================================


class TestImports:
    def test_import_ai_agent_groq(self):
        import ai_agent_groq
        for name in ("generate_text", "generate_insights", "AIResponse", "SYSTEM_PROMPT"):
            assert hasattr(ai_agent_groq, name), f"missing {name}"

    def test_import_code_review(self):
        from code_review import reviewer
        for name in ("full_review", "run_semgrep", "run_bandit", "run_radon",
                     "ai_code_review", "extract_changed_files", "_run"):
            assert hasattr(reviewer, name), f"missing {name}"

    def test_import_rag_vector_store(self):
        from rag import vector_store
        for name in ("VectorStore", "get_store", "add_document", "query_documents"):
            assert hasattr(vector_store, name), f"missing {name}"

    def test_import_rag_enrich(self):
        from rag import enrich
        for name in ("enrich_repository", "_chunks"):
            assert hasattr(enrich, name), f"missing {name}"

    def test_import_voice_tts(self):
        from voice import tts
        for name in ("text_to_speech", "fallback_audio", "VOICES", "_safe_name"):
            assert hasattr(tts, name), f"missing {name}"

    def test_import_voice_fallbacks(self):
        from voice import fallbacks
        for name in ("install_fallbacks", "FALLBACK_NAMES"):
            assert hasattr(fallbacks, name), f"missing {name}"

    def test_import_session_manager(self):
        from backend import session_manager
        for name in ("SessionManager", "sessions"):
            assert hasattr(session_manager, name), f"missing {name}"

    def test_import_backend_main(self):
        from backend import main
        assert hasattr(main, "app") or hasattr(main, "create_app")

    def test_import_cli_main(self):
        from cli import main as cli_main
        assert hasattr(cli_main, "app") or hasattr(cli_main, "main")

    def test_all_cli_command_modules_import(self):
        commands = [
            "cli.commands.analyze", "cli.commands.auth",
            "cli.commands.chat", "cli.commands.config",
            "cli.commands.init", "cli.commands.rag",
            "cli.commands.report", "cli.commands.review",
            "cli.commands.watch",
        ]
        missing = []
        for c in commands:
            try:
                importlib.import_module(c)
            except Exception as e:
                missing.append((c, str(e)))
        assert not missing, f"Missing/broken CLI modules: {missing}"


# ===========================================================================
# AI AGENT
# ===========================================================================


class TestAIAgentGroq:
    def test_provider_order_basic(self):
        from ai_agent_groq import _provider_order
        os.environ["SPECTRE_AI_PROVIDERS"] = "groq,openai,anthropic"
        assert _provider_order() == ["groq", "openai", "anthropic"]

    def test_provider_order_strips_spaces(self):
        from ai_agent_groq import _provider_order
        os.environ["SPECTRE_AI_PROVIDERS"] = " groq , openai "
        assert _provider_order() == ["groq", "openai"]

    def test_provider_order_empty(self):
        from ai_agent_groq import _provider_order
        os.environ["SPECTRE_AI_PROVIDERS"] = ""
        assert _provider_order() == []

    def test_provider_order_lowercases(self):
        from ai_agent_groq import _provider_order
        os.environ["SPECTRE_AI_PROVIDERS"] = "GROQ,OpenAI"
        assert _provider_order() == ["groq", "openai"]

    def test_generate_text_no_providers_raises_clear(self):
        from ai_agent_groq import generate_text
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            os.environ.pop(k, None)
        os.environ["SPECTRE_AI_PROVIDERS"] = "groq,openai,anthropic"
        with pytest.raises(RuntimeError, match="No AI provider succeeded"):
            generate_text("test prompt")

    def test_generate_insights_degrades_gracefully(self):
        from ai_agent_groq import generate_insights
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            os.environ.pop(k, None)
        result = generate_insights(["service_a"], 80, context={"pr": "#123"})
        for key in ("severity", "simulation", "rollback", "validation"):
            assert key in result, f"missing {key}"

    def test_generate_insights_never_raises(self):
        from ai_agent_groq import generate_insights
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            os.environ.pop(k, None)
        for services in ([], ["a"], ["a"] * 100):
            for impact in (0, 50, 100):
                assert isinstance(generate_insights(services, impact), dict)

    def test_system_prompt_exists(self):
        from ai_agent_groq import SYSTEM_PROMPT
        assert isinstance(SYSTEM_PROMPT, str) and len(SYSTEM_PROMPT) > 20


# ===========================================================================
# DIFF PARSING
# ===========================================================================


class TestExtractChangedFiles:
    def test_basic(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        (tmp_path / "test.py").write_text("x = 1\n")
        files = extract_changed_files("+++ b/test.py\n", tmp_path)
        assert len(files) == 1 and files[0].endswith("test.py")

    def test_skips_dev_null(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        assert extract_changed_files("+++ /dev/null\n", tmp_path) == []

    def test_skips_missing_file(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        assert extract_changed_files("+++ b/ghost.py\n", tmp_path) == []

    def test_deduplicates(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        (tmp_path / "a.py").write_text("x = 1\n")
        assert len(extract_changed_files("+++ b/a.py\n+++ b/a.py\n", tmp_path)) == 1

    def test_handles_no_prefix(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        (tmp_path / "a.py").write_text("x = 1\n")
        assert len(extract_changed_files("+++ a.py\n", tmp_path)) == 1

    def test_handles_whitespace(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        (tmp_path / "a.py").write_text("x = 1\n")
        assert len(extract_changed_files("+++ b/a.py   \n", tmp_path)) == 1

    def test_handles_nested_path(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n")
        assert len(extract_changed_files("+++ b/src/app.py\n", tmp_path)) == 1

    def test_handles_empty_diff(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        assert extract_changed_files("", tmp_path) == []

    def test_handles_malformed_diff(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        extract_changed_files("not a diff\nrandom\n+++ \n", tmp_path)

    def test_path_traversal_protection(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        outside = tmp_path.parent / "outside_secret.py"
        outside.write_text("SECRET_KEY = 'oops'\n")
        try:
            files = extract_changed_files(f"+++ b/../{outside.name}\n", tmp_path)
            for f in files:
                assert str(Path(f).resolve()).startswith(str(tmp_path.resolve())), \
                    f"Path traversal! {f}"
        finally:
            outside.unlink(missing_ok=True)

    def test_symlink_traversal_protection(self, tmp_path):
        from code_review.reviewer import extract_changed_files
        target = tmp_path.parent / "symlink_target.py"
        target.write_text("SECRET = 1\n")
        link = tmp_path / "link.py"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported")
        try:
            files = extract_changed_files("+++ b/link.py\n", tmp_path)
            for f in files:
                assert str(Path(f).resolve()).startswith(str(tmp_path.resolve())), \
                    f"Symlink traversal! {f}"
        finally:
            link.unlink(missing_ok=True)
            target.unlink(missing_ok=True)


# ===========================================================================
# STATIC ANALYSIS TOOLS
# ===========================================================================


class TestRunTools:
    def test_semgrep_missing_returns_skipped(self):
        from code_review.reviewer import run_semgrep
        backup = os.environ.get("PATH", "")
        try:
            os.environ["PATH"] = ""
            assert run_semgrep(".")["status"] in ("skipped", "error")
        finally:
            os.environ["PATH"] = backup

    def test_bandit_missing_returns_skipped(self):
        from code_review.reviewer import run_bandit
        backup = os.environ.get("PATH", "")
        try:
            os.environ["PATH"] = ""
            assert run_bandit(".")["status"] in ("skipped", "error")
        finally:
            os.environ["PATH"] = backup

    def test_radon_missing_returns_skipped(self):
        from code_review.reviewer import run_radon
        backup = os.environ.get("PATH", "")
        try:
            os.environ["PATH"] = ""
            assert run_radon(".")["status"] in ("skipped", "error")
        finally:
            os.environ["PATH"] = backup

    def test_run_timeout_respected(self):
        from code_review.reviewer import _run
        if os.name == "nt":
            cmd = ["cmd", "/c", "ping", "127.0.0.1", "-n", "100"]
        else:
            cmd = ["sleep", "100"]
        t0 = time.time()
        result = _run(cmd, timeout=2)
        assert time.time() - t0 < 8
        assert result["status"] == "error"

    def test_run_invalid_command(self):
        from code_review.reviewer import _run
        assert _run(["this_command_definitely_does_not_exist_xyz"])["status"] == "skipped"

    def test_semgrep_real_run(self, tmp_path):
        from code_review.reviewer import run_semgrep
        (tmp_path / "vuln.py").write_text("import subprocess\nsubprocess.call('ls', shell=True)\n")
        assert "status" in run_semgrep([str(tmp_path / "vuln.py")])

    def test_bandit_real_run(self, tmp_path):
        from code_review.reviewer import run_bandit
        (tmp_path / "vuln.py").write_text("def f():\n    password = 'secret123'\n    return password\n")
        assert run_bandit([str(tmp_path / "vuln.py")])["status"] in ("ok", "skipped", "error")

    def test_radon_real_run(self, tmp_path):
        from code_review.reviewer import run_radon
        (tmp_path / "complex.py").write_text(
            "def f(x):\n" + "\n".join(f"    if x > {i}: x = {i}" for i in range(30)) + "\n    return x\n"
        )
        assert "status" in run_radon([str(tmp_path / "complex.py")])


# ===========================================================================
# AI CODE REVIEW
# ===========================================================================


class TestAICodeReview:
    def test_no_api_key_returns_unavailable(self):
        from code_review.reviewer import ai_code_review
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            os.environ.pop(k, None)
        assert ai_code_review("+ password = 'secret123'\n")["status"] in ("ok", "unavailable")

    def test_empty_diff(self):
        from code_review.reviewer import ai_code_review
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            os.environ.pop(k, None)
        assert "status" in ai_code_review("")

    def test_huge_diff_truncated(self):
        from code_review.reviewer import ai_code_review
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            os.environ.pop(k, None)
        assert "status" in ai_code_review("+" + "x = 1\n" * 100_000)


# ===========================================================================
# FULL REVIEW
# ===========================================================================


class TestFullReview:
    def test_empty_diff(self):
        from code_review.reviewer import full_review
        result = full_review("", ".")
        assert result["changed_files"] == []
        for key in ("semgrep", "bandit", "radon", "ai_review"):
            assert key in result

    def test_real_file(self, tmp_path):
        from code_review.reviewer import full_review
        (tmp_path / "vuln.py").write_text("def process(data):\n    password = 'secret123'\n    return data\n")
        assert len(full_review("+++ b/vuln.py\n", tmp_path)["changed_files"]) == 1

    def test_output_is_json_serializable(self):
        from code_review.reviewer import full_review
        json.dumps(full_review("", "."))

    def test_output_has_consistent_tool_shape(self):
        from code_review.reviewer import full_review
        result = full_review("", ".")
        for tool in ("semgrep", "bandit", "radon"):
            assert "status" in result[tool]


# ===========================================================================
# VECTOR STORE
# ===========================================================================


class TestVectorStore:
    def test_add_increases_count(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_add")
        assert store.count() == 0
        store.add("doc1", "hello world", {"type": "test"})
        assert store.count() == 1

    def test_add_skips_empty_text(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_empty")
        store.add("doc1", "   \n\t", {"k": "v"})
        assert store.count() == 0

    def test_add_idempotent(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_idem")
        store.add("doc1", "first", {"k": "v"})
        store.add("doc1", "second", {"k": "v"})
        assert store.count() == 1

    def test_add_with_empty_metadata(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_empty_meta")
        store.add("doc1", "hello", {})
        assert store.count() == 1

    def test_add_with_none_metadata(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_none_meta")
        store.add("doc1", "hello", None)
        assert store.count() == 1

    def test_add_with_complex_metadata(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_complex_meta")
        store.add("doc1", "content", {"tags": ["a", "b"], "nested": {"k": "v"}, "n": 42, "flag": True})
        assert store.count() == 1

    def test_query_finds_results(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_query")
        store.add("a", "payment service handles checkout", {"type": "service"})
        store.add("b", "login service handles authentication", {"type": "service"})
        store.add("c", "database stores user records", {"type": "service"})
        assert len(store.query("payment", n_results=2)) >= 1

    def test_query_empty_store(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_qempty")
        assert store.query("anything", n_results=5) == []

    def test_query_respects_limit(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_limit")
        for i in range(10):
            store.add(f"doc{i}", f"document {i} about testing", {"i": i})
        assert len(store.query("document", n_results=3)) <= 3

    def test_query_n_results_zero(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_zero")
        store.add("a", "test", {"k": "v"})
        assert isinstance(store.query("test", n_results=0), list)

    def test_query_negative_n_results(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_neg")
        store.add("a", "test", {"k": "v"})
        assert isinstance(store.query("test", n_results=-5), list)

    def test_corrupt_fallback_recovers(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_corrupt")
        if not store.using_chroma:
            store._fallback.write_text("{ not valid json")
            assert store.count() == 0
            assert store.query("x") == []

    def test_singleton_get_store(self):
        from rag.vector_store import get_store
        assert get_store() is get_store()

    def test_persistence_across_instances(self, tmp_path):
        from rag.vector_store import VectorStore
        s1 = VectorStore(path=tmp_path, collection="t_persist")
        s1.add("doc1", "persistent content", {"k": "v"})
        s2 = VectorStore(path=tmp_path, collection="t_persist")
        assert s2.count() == 1

    def test_unicode_content(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_uni")
        store.add("ar1", "خدمة الدفع تعالج الطلبات", {"lang": "ar"})
        assert store.count() == 1

    def test_very_long_text(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_long")
        store.add("long1", "x" * 100_000, {"k": "v"})
        assert store.count() == 1

    def test_concurrent_adds(self, tmp_path):
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path, collection="t_concurrent")

        def writer(tid):
            for i in range(20):
                store.add(f"t{tid}_d{i}", f"content {tid}", {"tid": tid})

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            for f in [ex.submit(writer, i) for i in range(5)]:
                f.result()

        assert store.count() == 100


# ===========================================================================
# RAG ENRICH
# ===========================================================================


class TestEnrich:
    def test_empty_repo(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        store = VectorStore(path=tmp_path / "s", collection="t_e_empty")
        assert enrich_repository(tmp_path, store) == 0

    def test_indexes_python_files(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "a.py").write_text("def f(): pass\n")
        (tmp_path / "b.py").write_text("def g(): pass\n")
        store = VectorStore(path=tmp_path / "s", collection="t_e_py")
        assert enrich_repository(tmp_path, store) >= 2

    def test_skips_binary(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (tmp_path / "z.zip").write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        store = VectorStore(path=tmp_path / "s", collection="t_e_bin")
        assert enrich_repository(tmp_path, store) == 0

    def test_skips_git_and_venv(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config.py").write_text("# fake")
        (tmp_path / "venv").mkdir()
        (tmp_path / "venv" / "lib.py").write_text("# fake")
        store = VectorStore(path=tmp_path / "s", collection="t_e_skip")
        assert enrich_repository(tmp_path, store) == 0

    def test_handles_unicode(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "ar.py").write_text("# تعليق\ndef f(): return 'مرحبا'\n", encoding="utf-8")
        store = VectorStore(path=tmp_path / "s", collection="t_e_utf8")
        assert enrich_repository(tmp_path, store) >= 1

    def test_handles_invalid_utf8(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "broken.py").write_bytes(b"# \xff\xfe\x00\ndef f(): pass\n")
        store = VectorStore(path=tmp_path / "s", collection="t_e_invalid")
        assert enrich_repository(tmp_path, store) >= 1

    def test_idempotent(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "a.py").write_text("x = 1\n")
        store = VectorStore(path=tmp_path / "s", collection="t_e_idem")
        assert enrich_repository(tmp_path, store) == enrich_repository(tmp_path, store)

    def test_chunks_split_long_files(self):
        from rag.enrich import _chunks
        text = "\n".join(f"line {i}" for i in range(500))
        assert len(_chunks(text, size=500)) > 1

    def test_chunks_handles_empty(self):
        from rag.enrich import _chunks
        assert isinstance(_chunks(""), list)

    def test_chunks_handles_single_line(self):
        from rag.enrich import _chunks
        assert _chunks("hello") == ["hello"]

    def test_indexes_yaml_files(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "config.yaml").write_text("service: payment\nrisk: high\n")
        store = VectorStore(path=tmp_path / "s", collection="t_e_yaml")
        assert enrich_repository(tmp_path, store) >= 1

    def test_indexes_json_files(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "data.json").write_text('{"service": "payment"}')
        store = VectorStore(path=tmp_path / "s", collection="t_e_json")
        assert enrich_repository(tmp_path, store) >= 1

    def test_indexes_markdown(self, tmp_path):
        from rag.enrich import enrich_repository
        from rag.vector_store import VectorStore
        (tmp_path / "README.md").write_text("# Service\nPayment processor")
        store = VectorStore(path=tmp_path / "s", collection="t_e_md")
        assert enrich_repository(tmp_path, store) >= 1


# ===========================================================================
# VOICE TTS
# ===========================================================================


class TestVoiceTTS:
    def test_voice_presets(self):
        from voice.tts import VOICES
        for key in ("devops", "executive", "critical", "default"):
            assert key in VOICES

    def test_safe_name_removes_separators(self):
        from voice.tts import _safe_name
        for bad in ("a/b", "a\\b", "a:b", "a b"):
            out = _safe_name(bad)
            assert "/" not in out and "\\" not in out and ":" not in out

    def test_fallback_audio_exists(self):
        from voice.tts import fallback_audio
        assert os.path.exists(fallback_audio("unknown"))

    def test_fallback_audio_unknown_level(self):
        from voice.tts import fallback_audio
        assert os.path.exists(fallback_audio("nonexistent"))

    def test_fallback_audio_all_levels(self):
        from voice.tts import fallback_audio
        for level in ("critical", "high", "medium", "low", "unknown"):
            path = fallback_audio(level)
            assert os.path.exists(path), f"Missing: {level}"
            assert os.path.getsize(path) > 0, f"Empty: {level}"

    def test_empty_text_raises(self):
        from voice.tts import text_to_speech
        with pytest.raises(ValueError):
            text_to_speech("   ")

    def test_no_api_key_with_fallback(self, tmp_path):
        from voice.tts import text_to_speech
        backup = os.environ.pop("OPENAI_API_KEY", None)
        try:
            assert os.path.exists(text_to_speech("test", output_dir=tmp_path, fallback_level="unknown"))
        finally:
            if backup:
                os.environ["OPENAI_API_KEY"] = backup

    def test_no_api_key_without_fallback_raises(self, tmp_path):
        from voice.tts import text_to_speech
        backup = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(RuntimeError):
                text_to_speech("test", output_dir=tmp_path)
        finally:
            if backup:
                os.environ["OPENAI_API_KEY"] = backup

    def test_real_tts_if_key_available(self, tmp_path):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")
        from voice.tts import text_to_speech
        path = text_to_speech("Hello, this is a test.", output_dir=tmp_path)
        assert os.path.exists(path) and os.path.getsize(path) > 1000

    def test_arabic_tts_if_key_available(self, tmp_path):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")
        from voice.tts import text_to_speech
        path = text_to_speech("أهلاً يا باشا", output_dir=tmp_path)
        assert os.path.exists(path) and os.path.getsize(path) > 1000


# ===========================================================================
# VOICE FALLBACKS
# ===========================================================================


class TestFallbacks:
    def test_install_copies_existing_files(self, tmp_path):
        from voice.fallbacks import install_fallbacks, FALLBACK_NAMES
        src = tmp_path / "src"; dst = tmp_path / "dst"; src.mkdir()
        for name in FALLBACK_NAMES:
            (src / name).write_bytes(b"\x00" * 100)
        assert len(install_fallbacks(src, dst)) == len(FALLBACK_NAMES)

    def test_install_skips_empty_files(self, tmp_path):
        from voice.fallbacks import install_fallbacks, FALLBACK_NAMES
        src = tmp_path / "src"; dst = tmp_path / "dst"; src.mkdir()
        for name in FALLBACK_NAMES:
            (src / name).write_bytes(b"")
        assert install_fallbacks(src, dst) == []

    def test_install_skips_missing_files(self, tmp_path):
        from voice.fallbacks import install_fallbacks
        src = tmp_path / "src"; dst = tmp_path / "dst"; src.mkdir()
        assert install_fallbacks(src, dst) == []


# ===========================================================================
# SESSION MANAGER
# ===========================================================================


class TestSessionManager:
    def test_create_returns_uuid_hex(self):
        from backend.session_manager import SessionManager
        sid = SessionManager().create()
        assert len(sid) == 32 and int(sid, 16) >= 0

    def test_get_unknown_empty(self):
        from backend.session_manager import SessionManager
        assert SessionManager().get("nonexistent_" + uuid.uuid4().hex) == []

    def test_append_and_get(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(); sid = sm.create()
        sm.append(sid, "user", "hello")
        assert sm.get(sid) == [{"role": "user", "content": "hello"}]

    def test_order_preserved(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(); sid = sm.create()
        for role, content in [("user", "first"), ("assistant", "second"), ("user", "third")]:
            sm.append(sid, role, content)
        assert [m["content"] for m in sm.get(sid)] == ["first", "second", "third"]

    def test_truncation_window(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(); sid = sm.create()
        for i in range(30):
            sm.append(sid, "user", f"m{i}")
        messages = sm.get(sid)
        assert len(messages) == 20
        assert messages[0]["content"] == "m10"
        assert messages[-1]["content"] == "m29"

    def test_session_isolation(self):
        from backend.session_manager import SessionManager
        sm = SessionManager()
        a = sm.create(); b = sm.create()
        sm.append(a, "user", "for a")
        sm.append(b, "user", "for b")
        assert sm.get(a)[0]["content"] == "for a"
        assert sm.get(b)[0]["content"] == "for b"

    def test_max_sessions_eviction(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(max_sessions=5)
        ids = [sm.create() for _ in range(10)]
        for sid in ids:
            sm.append(sid, "user", "test")
        assert sm.get(ids[0]) == []
        assert sm.get(ids[-1]) != []

    def test_concurrent_append_no_loss(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(); sid = sm.create()

        def writer(tid):
            for i in range(50):
                sm.append(sid, "user", f"t{tid}_m{i}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        for m in sm.get(sid):
            assert "role" in m and "content" in m

    def test_backend_attribute(self):
        from backend.session_manager import SessionManager
        assert SessionManager().backend in ("redis", "memory")

    def test_ttl_expiry(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(ttl_seconds=1); sid = sm.create()
        sm.append(sid, "user", "test")
        assert len(sm.get(sid)) == 1
        time.sleep(1.2)
        assert sm.get(sid) == []

    def test_200_concurrent_session_creates(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(max_sessions=1000)

        def create_and_use(_):
            sid = sm.create()
            sm.append(sid, "user", "hello")
            return sid

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
            sids = [f.result() for f in [ex.submit(create_and_use, i) for i in range(200)]]
        assert len(set(sids)) == 200

    def test_500_concurrent_appends(self):
        from backend.session_manager import SessionManager
        sm = SessionManager(); sid = sm.create()

        def writer(_):
            for i in range(20):
                sm.append(sid, "user", f"msg{i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as ex:
            for f in [ex.submit(writer, i) for i in range(25)]:
                f.result()
        assert len(sm.get(sid)) <= 20


# ===========================================================================
# CLI
# ===========================================================================


class TestCLI:
    def _run(self, args, timeout=60):
        return subprocess.run(
            [sys.executable, "-m", "cli.main"] + args,
            capture_output=True, text=True, timeout=timeout, cwd=REPO_ROOT,
        )

    def test_help(self):
        assert self._run(["--help"], timeout=60).returncode == 0

    def test_version(self):
        assert self._run(["version"], timeout=60).returncode in (0, 2)

    def test_help_for_each_command(self):
        commands = ["init", "analyze", "review", "chat", "watch", "config", "auth", "report", "rag"]
        failures = []
        for cmd in commands:
            try:
                result = self._run([cmd, "--help"], timeout=30)
                if result.returncode != 0:
                    failures.append((cmd, result.returncode))
            except subprocess.TimeoutExpired:
                failures.append((cmd, "TIMEOUT"))
        assert not failures, f"Commands failing --help: {failures}"


# ===========================================================================
# FRONTEND CONTRACT
# ===========================================================================


class TestFrontendContract:
    def test_tts_signature(self):
        import inspect
        from voice.tts import text_to_speech
        assert "text" in inspect.signature(text_to_speech).parameters

    def test_session_api_shape(self):
        from backend.session_manager import SessionManager
        sm = SessionManager()
        for method in ("create", "get", "append"):
            assert callable(getattr(sm, method, None))

    def test_reviewer_output_keys(self):
        from code_review.reviewer import full_review
        result = full_review("", ".")
        for key in ("semgrep", "bandit", "radon", "ai_review", "changed_files"):
            assert key in result

    def test_vector_store_signature(self):
        import inspect
        from rag.vector_store import VectorStore
        sig = inspect.signature(VectorStore.__init__)
        assert "path" in sig.parameters and "collection" in sig.parameters


# ===========================================================================
# SECURITY
# ===========================================================================


class TestSecurity:
    def test_no_hardcoded_api_keys_in_source(self):
        patterns = [r"sk-[a-zA-Z0-9]{40,}", r"gsk_[a-zA-Z0-9]{40,}", r"sk-ant-[a-zA-Z0-9\-_]{40,}"]
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "site-packages" in str(py):
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pat in patterns:
                match = re.search(pat, text)
                assert not match, f"Possible API key in {py}: {match.group()[:20]}..."

    def test_no_aws_keys(self):
        pattern = r"AKIA[0-9A-Z]{16}"
        for py in REPO_ROOT.rglob("*.py"):
            if ".venv" in str(py) or "site-packages" in str(py):
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            assert not re.search(pattern, text), f"AWS key in {py}"

    def test_env_in_gitignore_if_present(self):
        env = REPO_ROOT / ".env"
        if env.exists():
            gitignore = REPO_ROOT / ".gitignore"
            if gitignore.exists():
                assert ".env" in gitignore.read_text(), ".env exists but is not in .gitignore"


# ===========================================================================
# REPO'S OWN TESTS
# ===========================================================================


def test_repo_own_tests():
    tests_dir = REPO_ROOT / "tests"
    if not tests_dir.exists():
        pytest.skip("No tests/ folder in branch")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--tb=no", "--no-header"],
            capture_output=True, text=True, timeout=180, cwd=REPO_ROOT,
        )
        print("\n--- Repo tests stdout ---")
        print(result.stdout[-4000:])
        print("--- Repo tests stderr ---")
        print(result.stderr[-2000:])
    except subprocess.TimeoutExpired:
        pytest.fail("Repo's own tests timed out after 180 seconds")