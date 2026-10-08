"""
test_live_feed.py — Poll the /api/live-feed endpoint.

Run:
    python test_live_feed.py

Optional:
    python test_live_feed.py --watch   # polls every 10 sec until Ctrl+C
"""

import sys
import time
import requests


BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/live-feed"


def fetch_and_print() -> int:
    try:
        response = requests.get(ENDPOINT, timeout=5)
    except requests.RequestException as exc:
        print(f"Error contacting server: {exc}")
        return -1

    if response.status_code != 200:
        print(f"Unexpected status: {response.status_code}")
        return -1

    data = response.json()
    count = data.get("count", 0)
    events = data.get("events", [])

    print(f"COUNT: {count}")
    print("-" * 60)
    for event in events:
        ts = event.get("timestamp", "")
        ts_short = ts[11:19] if len(ts) >= 19 else ts
        msg = event.get("message", "")
        kind = event.get("kind", "")
        print(f"[{ts_short}] ({kind}) {msg}")
    print("-" * 60)
    return count


def main() -> None:
    watch_mode = "--watch" in sys.argv

    if not watch_mode:
        fetch_and_print()
        return

    print("Watching live feed (Ctrl+C to stop)...")
    print()
    last_count = -1
    try:
        while True:
            current = fetch_and_print()
            if current != last_count:
                print()
                last_count = current
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()