"""Time a full RAG query end-to-end."""
import time
from rag.retriever import retrieve
from rag.vector_store import collection_stats

print("Testing RAG latency...")
print("=" * 60)

start = time.time()
stats = collection_stats()
print(f"  collection_stats()      {time.time() - start:6.2f}s   count={stats['count']}")

start = time.time()
results = retrieve("payment service owner", n_results=3)
print(f"  retrieve() #1 (cold)    {time.time() - start:6.2f}s   -> {results[0]['id'] if results else 'none'}")

start = time.time()
results = retrieve("payment service owner", n_results=3)
print(f"  retrieve() #2 (warm)    {time.time() - start:6.2f}s   -> {results[0]['id'] if results else 'none'}")

start = time.time()
results = retrieve("خدمة الدفع", n_results=3)
print(f"  retrieve() #3 (Arabic)  {time.time() - start:6.2f}s   -> {results[0]['id'] if results else 'none'}")

print("=" * 60)