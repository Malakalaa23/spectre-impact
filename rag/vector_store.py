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
        if not text or not text.strip():
            return

        meta = dict(metadata or {})
        if not meta:
            meta = {"doc_type": "general"}

        clean_meta = {}
        for k, v in meta.items():
            if v is None:
                clean_meta[k] = ""
            elif isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            else:
                clean_meta[k] = json.dumps(v)

        if not clean_meta:
            clean_meta = {"doc_type": "general"}

        with _LOCK:
            if self._collection is not None:
                self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[clean_meta])
                return
            data = self._read_fallback()
            data[doc_id] = {"text": text, "metadata": clean_meta}
            self._fallback.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def count(self) -> int:
        with _LOCK:
            return self._collection.count() if self._collection is not None else len(self._read_fallback())

    def query(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        res = self.search_similar(query, n_results=n_results)
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]
        return [
            {"id": i, "text": d, "metadata": m or {}, "distance": distances[idx] if idx < len(distances) else None}
            for idx, (i, d, m) in enumerate(zip(ids, docs, metas))
        ]

    def search_similar(self, query: str, n_results: int = 5, doc_type: str | None = None) -> dict[str, list[list[Any]]]:
        n_results = max(1, n_results)
        with _LOCK:
            if self._collection is not None:
                where = {"doc_type": doc_type} if doc_type else None
                try:
                    res = self._collection.query(query_texts=[query], n_results=n_results, where=where)
                    return {
                        "ids": res.get("ids") or [[]],
                        "documents": res.get("documents") or [[]],
                        "metadatas": res.get("metadatas") or [[]],
                        "distances": res.get("distances") or [[]],
                    }
                except Exception:
                    pass

            terms = {term.lower() for term in query.split() if term.strip()}
            rows = []
            for doc_id, item in self._read_fallback().items():
                meta = item.get("metadata", {})
                if doc_type and meta.get("doc_type") != doc_type and meta.get("type") != doc_type:
                    continue
                text = item.get("text", "").lower()
                score = sum(term in text for term in terms)
                rows.append((score, doc_id, item.get("text", ""), meta))

            rows.sort(key=lambda x: x[0], reverse=True)
            selected = rows[:n_results]

            ids = [r[1] for r in selected]
            docs = [r[2] for r in selected]
            metas = [r[3] for r in selected]
            distances = [1.0 / (r[0] + 1) for r in selected]

            return {"ids": [ids], "documents": [docs], "metadatas": [metas], "distances": [distances]}

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


def search_similar(query: str, n_results: int = 5, doc_type: str | None = None) -> dict[str, list[list[Any]]]:
    return get_store().search_similar(query, n_results=n_results, doc_type=doc_type)

