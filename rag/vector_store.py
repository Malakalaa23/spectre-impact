"""
vector_store.py — ChromaDB wrapper with LOCAL embeddings.

The vector store holds natural-language documents about:
    - Services and their dependencies (from dependency_graph.yaml)
    - Business impact mappings (from business_map.yaml)
    - File-to-resource mappings (from resource_map.json)
    - Past PR incidents (from history.db)

Embeddings:
    Uses `sentence-transformers` with IBM's
    `granite-embedding-97m-multilingual-r2` — a 97M-parameter model
    that runs on CPU. No API key required. Free forever. Works offline.

    Why this model:
        - Native Arabic + English in one shared vector space. No
          translation step, no cross-lingual routing, no second model.
        - 384-dimensional embeddings (same shape as the previous model,
          so the ChromaDB collection schema does not change).
        - 32,768-token context. Our longest document is ~1,200 tokens,
          so nothing is truncated. The previous model capped at 256
          tokens and was silently cutting documents in half.
        - Scores 60.3 on Multilingual MTEB Retrieval — highest among
          open multilingual embedding models under 100M parameters.
        - Apache 2.0 license.
        - Requires transformers>=4.48.0 (ModernBERT architecture).

    The model is loaded once at first use and cached in module memory.
    First run downloads ~390MB from Hugging Face. After that it reads
    from the local cache.

    IMPORTANT: switching embedding models invalidates every existing
    vector. The old embeddings live in a different semantic space and
    cannot be queried with the new model's vectors. Run
    `reset_collection()` and re-populate after changing EMBEDDING_MODEL.

Public API:
    get_collection()             — lazy singleton ChromaDB collection
    get_embedding(text)          — local embedding for a single text
    get_embeddings_batch(texts)  — batched embeddings (faster)
    add_document(...)            — add one doc with metadata
    add_documents_batch(...)     — add many docs in one call
    search_similar(...)          — top-K nearest neighbors
    collection_stats()           — count, dimensions, backend info
    reset_collection()           — wipe and recreate (for re-population)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_PATH = Path(__file__).resolve().parents[1] / "rag_db"
COLLECTION_NAME = "spectre_knowledge"
EMBEDDING_MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
EMBEDDING_DIM = 384   # output dimension of the granite 97m model
BATCH_SIZE = 64       # number of docs per encoding batch (CPU-friendly)

# The model supports 32,768 tokens. 32,000 characters is a conservative
# ceiling — well under the token limit for English and Arabic, and high
# enough that no document in the current corpus gets cut.
MAX_TEXT_CHARS = 32000


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------
_client: chromadb.PersistentClient | None = None
_collection: Any = None
_model: SentenceTransformer | None = None


def _get_client() -> chromadb.PersistentClient:
    """Get or create the persistent ChromaDB client."""
    global _client
    if _client is None:
        DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(DB_PATH))
        logger.info("ChromaDB client initialized at %s", DB_PATH)
    return _client


def _get_model() -> SentenceTransformer:
    """
    Get or create the SentenceTransformer model.

    First run downloads ~390MB from Hugging Face, then caches it on
    disk and in memory. Subsequent processes read from the cache.
    """
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded (dim=%d)", EMBEDDING_DIM)
    return _model


def get_collection():
    """
    Get or create the ChromaDB collection.

    Returns a singleton collection handle. Auto-creates on first call.
    """
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Collection '%s' ready (count=%d)",
            COLLECTION_NAME,
            _collection.count(),
        )
    return _collection


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def get_embedding(text: str) -> list[float]:
    """
    Generate an embedding for a single text using the local model.

    Args:
        text: The text to embed. Truncated to MAX_TEXT_CHARS if longer.

    Returns:
        A list of floats (length EMBEDDING_DIM = 384).
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    model = _get_model()
    # normalize_embeddings=True gives us cosine-similarity-ready vectors
    vector = model.encode(
        text[:MAX_TEXT_CHARS],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vector.tolist()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for many texts in one batched call.

    Much faster on CPU than calling get_embedding() in a loop.

    Args:
        texts: List of strings.

    Returns:
        A list of embeddings, one per input text, in the same order.
    """
    if not texts:
        return []

    model = _get_model()
    truncated = [t[:MAX_TEXT_CHARS] for t in texts]

    # SentenceTransformer handles batching internally; passing
    # batch_size caps memory use on smaller machines.
    vectors = model.encode(
        truncated,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------
def add_document(
    doc_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    doc_type: str = "general",
) -> None:
    """
    Add a single document to the collection.

    Args:
        doc_id: Unique identifier (e.g. "svc_payment_service").
        text: The document text.
        metadata: Optional metadata dict (service, owner, severity, etc.).
        doc_type: Category for filtering (e.g. "service", "incident").
    """
    collection = get_collection()
    embedding = get_embedding(text)

    meta = dict(metadata or {})
    meta["type"] = doc_type

    collection.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[meta],
    )
    logger.info("Added doc %s (type=%s, %d chars)", doc_id, doc_type, len(text))


def add_documents_batch(
    doc_ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, Any]] | None = None,
    doc_types: list[str] | None = None,
) -> int:
    """
    Add many documents in one batch. Faster than individual adds.

    Args:
        doc_ids: Unique IDs for each document.
        texts: Texts for each document.
        metadatas: Optional metadata for each document.
        doc_types: Optional per-doc type labels. Defaults to "general".

    Returns:
        Number of documents successfully added.
    """
    if not doc_ids or len(doc_ids) != len(texts):
        raise ValueError("doc_ids and texts must be non-empty and equal length")

    collection = get_collection()
    embeddings = get_embeddings_batch(texts)

    metadatas = metadatas or [{} for _ in doc_ids]
    doc_types = doc_types or ["general"] * len(doc_ids)

    final_metas: list[dict[str, Any]] = []
    for meta, doc_type in zip(metadatas, doc_types):
        m = dict(meta or {})
        m["type"] = doc_type
        final_metas.append(m)

    collection.add(
        ids=doc_ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=final_metas,
    )
    logger.info("Added batch of %d docs", len(doc_ids))
    return len(doc_ids)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def search_similar(
    query: str,
    n_results: int = 5,
    doc_type: str | None = None,
) -> dict[str, Any]:
    """
    Find the top-K most similar documents to a query.

    Args:
        query: Natural-language search query.
        n_results: How many results to return.
        doc_type: Optional filter — only return docs of this type
                  (e.g. "service", "incident", "business").

    Returns:
        A dict with keys: ids, documents, metadatas, distances.
        Each is a list of lists (ChromaDB's native shape).
    """
    if not query or not query.strip():
        return {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    collection = get_collection()
    query_embedding = get_embedding(query)

    where = {"type": doc_type} if doc_type else None
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return results


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def collection_stats() -> dict[str, Any]:
    """Return basic stats about the collection."""
    collection = get_collection()
    count = collection.count()
    return {
        "collection_name": COLLECTION_NAME,
        "count": count,
        "db_path": str(DB_PATH),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIM,
    }


def reset_collection() -> None:
    """
    Delete and recreate the collection. Used before re-population.

    WARNING: destroys all stored documents. Required after changing
    EMBEDDING_MODEL, because old vectors are in a different semantic
    space and cannot be queried by the new model.
    """
    global _collection
    client = _get_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
        logger.info("Deleted collection '%s'", COLLECTION_NAME)
    except Exception as exc:  # noqa: BLE001
        logger.info("Collection did not exist or could not be deleted: %s", exc)
    _collection = None
    get_collection()
    logger.info("Collection '%s' recreated", COLLECTION_NAME)


__all__ = [
    "get_collection",
    "get_embedding",
    "get_embeddings_batch",
    "add_document",
    "add_documents_batch",
    "search_similar",
    "collection_stats",
    "reset_collection",
]