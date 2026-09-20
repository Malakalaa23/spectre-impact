"""RQ worker that processes PR analysis jobs off the Redis queue.

Run with: python -m job_queue.worker

Named job_queue (not "queue") to avoid shadowing Python's standard
library queue module, which rq itself depends on internally.

The webhook handler enqueues jobs here instead of running the pipeline
inline, so a burst of PRs doesn't block the HTTP response — this is
what lets the system absorb 100+ concurrent requests without crashing.
"""

import os

from redis import Redis
from rq import Queue, Worker

from database import save_analysis
from ai_agent_groq import generate_insights
from backend.analysis.change_analysis_engine import analyze_impact

redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
queue = Queue("analysis", connection=redis_conn)


def process_pr(pr_number: int, repo_name: str, changed_files: list) -> dict:
    bfs_result = analyze_impact(changed_files)
    ai_result = generate_insights(
        bfs_result["affected_services"],
        bfs_result["business_impact"],
    )
    save_analysis(pr_number, repo_name, bfs_result, ai_result)
    return {"status": "done", "pr_number": pr_number}


if __name__ == "__main__":
    Worker([queue], connection=redis_conn).work()
