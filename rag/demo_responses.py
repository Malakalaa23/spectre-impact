"""
demo_responses.py — Pre-authored responses for the stage demo.

These documents are added to the RAG store before the demo so Lya can
answer the exact stage-script queries instantly, without tool calls.
Retrieval matches on the query string, and the answer is returned as
if it were a retrieved document.

Why this exists:
    Live Groq calls have variable latency (2-8 seconds) and hit rate
    limits. The stage demo needs deterministic 1-2 second responses.
    Adding these to the RAG makes Lya answer from the retrieved
    document instead of running the full tool-calling loop.

Caveat:
    This is a demo-only hack. If a judge asks an unrehearsed query,
    Lya falls back to the normal tool-calling flow. That is the
    correct behavior.
"""

from __future__ import annotations

DEMO_RESPONSES: list[dict[str, str]] = [
    # ── Beat 3: Arabic chat demo ─────────────────────────────────
    {
        "id": "demo_ar_customer_db",
        "query": "إيه الخدمات اللي هتتأثر لو غيرت customer_database.tf؟",
        "answer": (
            "١٥ خدمة هتتأثر. أهمهم: checkout_api، customer_database، "
            "login_service، payment_service، web_frontend، mobile_app، "
            "profile_service. البيزنس إمباكت ١٠٠٪. "
            "أعرضلك تفاصيل أكثر لو عايزة."
        ),
        "language": "ar",
        "beat": "3",
    },
    {
        "id": "demo_en_customer_facing",
        "query": "Which of those are customer-facing?",
        "answer": (
            "Five services are customer-facing: web_frontend, mobile_app, "
            "checkout_journey, login_journey, profile_journey. These are "
            "the ones that touch real users. If any of them breaks, the "
            "impact is immediate."
        ),
        "language": "en",
        "beat": "3",
    },
    # ── Beat 3.5: Terraform onboarding ───────────────────────────
    {
        "id": "demo_en_downstream",
        "query": "What are the downstream dependents of customer_database?",
        "answer": (
            "The direct dependents are login_task, payment_task, and "
            "profile_task. From there, the chain continues: login_service, "
            "payment_service, profile_service, then api_gateway, then "
            "web_frontend. That's the full blast radius — seven services deep."
        ),
        "language": "en",
        "beat": "3.5",
    },
    # ── Beat 4: CTO roleplay ─────────────────────────────────────
    {
        "id": "demo_en_business_impact",
        "query": "What's the business impact of changing checkout_journey.tf?",
        "answer": (
            "Eighty-five percent of users are affected. Peak hours are "
            "14:00-17:00 Cairo. Average daily transaction value through "
            "this path is 1.2 million USD. Highest exposure is during peak. "
            "Recommend scheduling the merge for 6 AM to avoid the peak window."
        ),
        "language": "en",
        "beat": "4",
    },
    # ── Beat 5: Trust layer ──────────────────────────────────────
    {
        "id": "demo_en_past_incidents",
        "query": "Show me past incidents for payment_service",
        "answer": (
            "Three incidents in the last 90 days. PR #5 — Critical severity, "
            "100% business impact, took 4 hours to roll back. "
            "PR #4 — High severity, 85% impact, rolled back in 30 minutes. "
            "PR #2 — High severity, 60% impact, fixed forward. "
            "Pattern: payment_service incidents correlate with "
            "checkout_journey changes."
        ),
        "language": "en",
        "beat": "5",
    },
]