"""ChromaDB-backed knowledge store with a JSON fallback for minimal installs."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
DEFAULT_PATH = Path(os.getenv("SPECTRE_CHROMA_PATH", ".spectre/chroma"))
COLLECTION = os.getenv("SPECTRE_CHROMA_COLLECTION", "spectre_impact")


class VectorStore:
    def __init__(self, path: str | Path = DEFAULT_PATH, collection: str = COLLECTION):
        self.path = Path(path)
        self.collection = collection
        self.path.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.path))
            self._collection = self._client.get_or_create_collection(collection)
        except Exception:
            self._client = None
            self._collection = None
        self._fallback = self.path / f"{collection}.json"

    @property
    def using_chroma(self) -> bool:
        return self._collection is not None

    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        if not text.strip():
            return
        metadata = {k: (v if isinstance(v, (str, int, float, bool)) else json.dumps(v)) for k, v in (metadata or {}).items()}
        with _LOCK:
            if self._collection is not None:
                self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
                return
            data = self._read_fallback()
            data[doc_id] = {"text": text, "metadata": metadata}
            self._fallback.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def count(self) -> int:
        with _LOCK:
            return self._collection.count() if self._collection is not None else len(self._read_fallback())

    def query(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        if self._collection is not None:
            result = self._collection.query(query_texts=[query], n_results=max(1, n_results))
            ids = result.get("ids", [[]])[0]
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0] if result.get("distances") else []
            return [
                {"id": i, "text": d, "metadata": m or {}, "distance": distances[idx] if idx < len(distances) else None}
                for idx, (i, d, m) in enumerate(zip(ids, docs, metas))
            ]
        # Tiny lexical fallback: deterministic and dependency-free.
        terms = {term.lower() for term in query.split() if term.strip()}
        rows = []
        for doc_id, item in self._read_fallback().items():
            text = item["text"].lower()
            score = sum(term in text for term in terms)
            if score:
                rows.append((score, doc_id, item))
        rows.sort(reverse=True)
        return [{"id": doc_id, **item, "score": score} for score, doc_id, item in rows[:n_results]]

    def _read_fallback(self) -> dict[str, Any]:
        if not self._fallback.exists():
            return {}
        try:
            return json.loads(self._fallback.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}


_default_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _default_store
    with _LOCK:
        if _default_store is None:
            _default_store = VectorStore()
        return _default_store


def add_document(doc_id: str, text: str, metadata: dict[str, Any] | None = None, doc_type: str = "general") -> None:
    metadata = dict(metadata or {})
    metadata.setdefault("doc_type", doc_type)
    get_store().add(doc_id, text, metadata)


def query_documents(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    return get_store().query(query, n_results)
