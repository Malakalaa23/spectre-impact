"""Measure the actual chat pipeline latency, layer by layer."""
import os
import sys
import time
import asyncio
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import groq
from chat.agent import SYSTEM_PROMPT, DEFAULT_MODEL, chat


def main():
    print("=" * 60)
    print(f"Chat model in use: {DEFAULT_MODEL}")
    print("=" * 60)

    client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

    # [1] Simple prompt, no system message — measures pure Groq network latency
    start = time.time()
    client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=10,
    )
    print(f"[1] Simple prompt               {time.time() - start:6.2f}s")

    # [2] Same but with Lya's full system prompt — measures prompt size impact
    start = time.time()
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Say OK"},
        ],
        max_tokens=10,
    )
    tokens = response.usage.prompt_tokens if response.usage else "?"
    print(f"[2] With Lya system prompt      {time.time() - start:6.2f}s   (input tokens: {tokens})")

    # [3] Full agent pipeline — what /api/chat actually does
    start = time.time()
    result = asyncio.run(chat(
        "Who owns payment service?",
        session_id="timing-test",
        user_id="timing-test",
    ))
    print(f"[3] Full agent pipeline         {time.time() - start:6.2f}s   tools={result.get('tool_calls')}")

    # [4] Second call, warm
    start = time.time()
    result = asyncio.run(chat(
        "And who owns customer_database?",
        session_id="timing-test",
        user_id="timing-test",
    ))
    print(f"[4] Second call (warm)          {time.time() - start:6.2f}s   tools={result.get('tool_calls')}")

    print("=" * 60)
    print()
    print("Interpretation:")
    print("  [1] < 3s, [2] < 5s, [3] > 30s  ->  LangChain agent is the bottleneck")
    print("  [2] > 30s                       ->  system prompt is too large")
    print("  [1] > 30s                       ->  Groq network from this machine")


if __name__ == "__main__":
    main()