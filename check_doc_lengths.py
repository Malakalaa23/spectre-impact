"""
Measure token length of every document in the RAG corpus.

WHY this exists: candidate embedding models have max sequence limits
(128 for mentee-embed-v3, 32768 for granite-embedding-97m). Documents
longer than the limit get silently truncated during embedding, which
degrades retrieval without any warning. We need the real numbers before
committing to a model.

WHY it must be one file and not a `python -c` one-liner: PowerShell
garbles Arabic in command-line arguments, and every fresh interpreter
pays the model-load cost again. One file = one load = one clean run.
"""

import sys

# Force UTF-8 so Arabic doc ids / text don't crash the print.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

import inspect

from sentence_transformers import SentenceTransformer

import rag.populate as populate


def call_builder(name: str):
    """Call a build_* function, passing no args if it takes none."""
    fn = getattr(populate, name)
    sig = inspect.signature(fn)
    required = [
        p for p in sig.parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    ]
    if required:
        print(f"  [skip] {name} requires args: {sig}")
        return []
    result = fn()
    if result is None:
        print(f"  [skip] {name} returned None")
        return []
    return list(result)


def main() -> int:
    print("=" * 72)
    print("RAG document token-length check")
    print("=" * 72)

    # Collect every doc from every builder.
    builders = [
        "build_service_docs",
        "build_business_docs",
        "build_resource_map_docs",
        "build_incident_docs",
    ]

    docs = []
    for name in builders:
        print(f"Calling {name}...")
        try:
            batch = call_builder(name)
        except Exception as e:
            print(f"  [error] {name}: {e}")
            continue
        print(f"  -> {len(batch)} docs")
        for d in batch:
            if isinstance(d, dict):
                docs.append((d.get("id", "?"), d.get("text", "")))
            else:
                docs.append(("?", str(d)))

    if not docs:
        print("No documents collected. Check the builder function signatures.")
        return 1

    print()
    print(f"Total docs collected: {len(docs)}")
    print("Loading tokenizer...")

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    tokenizer = model.tokenizer

    print("Tokenizing...")
    lengths = []
    for doc_id, text in docs:
        n = len(tokenizer(text)["input_ids"])
        lengths.append((n, doc_id))

    lengths.sort(reverse=True)

    over_128 = sum(1 for n, _ in lengths if n > 128)
    over_256 = sum(1 for n, _ in lengths if n > 256)
    over_512 = sum(1 for n, _ in lengths if n > 512)

    print()
    print("=" * 72)
    print(f"max    : {lengths[0][0]:>6} tokens  ({lengths[0][1]})")
    print(f"median : {lengths[len(lengths) // 2][0]:>6} tokens")
    print(f"min    : {lengths[-1][0]:>6} tokens")
    print()
    print(f">128   : {over_128:>4} docs")
    print(f">256   : {over_256:>4} docs")
    print(f">512   : {over_512:>4} docs")
    print()
    print("Top 10 longest:")
    for n, doc_id in lengths[:10]:
        print(f"  {n:>6}  {doc_id}")
    print("=" * 72)

    print()
    if over_128 == 0:
        print("VERDICT: mentee-embed-v3 (128-token cap) is SAFE.")
    else:
        print(f"VERDICT: {over_128} docs exceed 128 tokens.")
        print("         Use granite-embedding-97m-multilingual-r2 instead.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())