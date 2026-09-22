import json
import os
import time
import urllib.error
import urllib.request

import typer
from rich.console import Console

console = Console()


def run(
    url: str = typer.Option(
        os.getenv("SPECTRE_API_URL", "http://localhost:8000"),
        help="Spectre backend URL",
    ),
    interval: int = typer.Option(5, min=1, help="Seconds between checks"),
    once: bool = typer.Option(False, help="Poll once and exit"),
) -> None:
    endpoint = f"{url.rstrip('/')}/api/live-feed"
    console.print(f"Watching live feed from [cyan]{endpoint}[/]. Press Ctrl+C to stop.")
    seen_ids: set[str] = set()

    try:
        while True:
            try:
                req = urllib.request.Request(endpoint, headers={"User-Agent": "Spectre-CLI"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        events = data.get("events", []) if isinstance(data, dict) else []
                        new_events = [e for e in events if isinstance(e, dict) and e.get("id") not in seen_ids]

                        for event in reversed(new_events):
                            event_id = event.get("id")
                            if event_id:
                                seen_ids.add(event_id)
                            event_type = event.get("type", "event")
                            severity = event.get("severity") or "info"
                            impact = event.get("business_impact", 0)
                            console.print(
                                f"[cyan]LIVE EVENT:[/] [{event_type}] id={event_id} | "
                                f"impact={impact}% | severity={severity}"
                            )
                    else:
                        console.print(f"[yellow]Backend returned HTTP {resp.status}[/]")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                console.print(f"[yellow]Connection warning:[/] Could not reach {endpoint} ({exc})")
            except json.JSONDecodeError:
                console.print(f"[yellow]Malformed response from {endpoint}[/]")

            if once:
                break
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\nStopped watching.")

