"""
preload_demo_responses.py — Ingest stage-script answers into the RAG store.

Run this ONCE before the demo:
    python scripts/preload_demo_responses.py

It adds each demo response as a document to ChromaDB, keyed by the
query text. When Lya receives the same query on stage, the retriever
matches it and returns the pre-authored answer directly.

Safe to re-run: existing docs with the same IDs are skipped.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Make the project root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.demo_responses import DEMO_RESPONSES  # noqa: E402
from rag.vector_store import add_document, get_collection  # noqa: E402


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    collection = get_collection()
    existing = {m.get("id") for m in collection.get()["metadatas"] if m}

    added = 0
    skipped = 0

    for entry in DEMO_RESPONSES:
        doc_id = entry["id"]
        if doc_id in existing:
            logger.info("Skipping %s (already present)", doc_id)
            skipped += 1
            continue

        # The document text is the query itself so the retriever matches
        # on query semantics. The answer lives in metadata.
        add_document(
            doc_id=doc_id,
            text=entry["query"],
            metadata={
                "type": "demo_response",
                "answer": entry["answer"],
                "language": entry["language"],
                "beat": entry["beat"],
            },
        )
        logger.info("Added %s (beat %s)", doc_id, entry["beat"])
        added += 1

    logger.info("Done. Added %d, skipped %d.", added, skipped)


if __name__ == "__main__":
    main()