"""Time each Groq model directly. No agent, no tools, no RAG."""
import time
import os
from dotenv import load_dotenv
import groq

load_dotenv()
client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

models = [
    "allam-2-7b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
]

print("Testing Groq latency from this machine...")
print("=" * 60)

for model in models:
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with one word: OK"}],
            max_tokens=10,
            temperature=0,
        )
        elapsed = time.time() - start
        text = response.choices[0].message.content.strip()
        print(f"  {model:<28} {elapsed:6.2f}s   -> {text}")
    except Exception as e:
        print(f"  {model:<28}  ERROR: {e}")

print("=" * 60)