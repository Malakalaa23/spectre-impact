"""
seed_nilepay_history.py — populate history.db with realistic NilePay PR history.

Generates 60 PRs across 6 months with realistic severity distribution,
service names from the actual dependency graph, and incident descriptions
that match the NilePay story. Run once before the demo.

    python seed_nilepay_history.py

Then rebuild the RAG:

    python -m rag.populate --reset
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path(__file__).parent / "history.db"

SERVICES = [
    "customer_database", "redis_cache", "login_service", "payment_service",
    "profile_service", "login_api", "checkout_api", "profile_api",
    "web_frontend", "mobile_app", "login_journey", "checkout_journey",
    "profile_journey",
]

FILES = [
    "terraform/customer_database.tf",
    "terraform/redis.tf",
    "services/payment/app.py",
    "services/login/app.py",
    "services/profile/app.py",
    "apis/checkout.py",
    "apis/login.py",
    "apis/profile.py",
    "frontend/checkout.jsx",
    "frontend/login.jsx",
]

SEVERITIES = (
    ["Critical"] * 6 + ["High"] * 12 + ["Medium"] * 24 + ["Low"] * 18
)
random.seed(42)
random.shuffle(SEVERITIES)

INCIDENT_TEMPLATES = [
    "Database connection pool exhaustion during peak traffic.",
    "Cache invalidation caused stale session tokens.",
    "Payment gateway timeout under high concurrency.",
    "Login rate limiter triggered false positives.",
    "Checkout flow failed on iOS Safari after deploy.",
    "Profile image upload failed for files larger than 2 MB.",
    "Redis failover took 14 seconds longer than expected.",
    "Migration script locked the customer table for 45 seconds.",
    "API gateway throttled legitimate traffic during peak.",
    "Mobile app crashed on Android 14 after checkout.",
]

ROLLBACK_STEPS = {
    "Critical": [
        "kubectl rollout undo deployment/payment-service -n prod",
        "kubectl rollout status deployment/payment-service -n prod",
        "curl -f https://api.nilepay.eg/health",
    ],
    "High": [
        "git revert HEAD --no-edit",
        "kubectl rollout restart deployment/login-service -n prod",
    ],
    "Medium": [
        "kubectl rollout undo deployment/profile-service -n prod",
    ],
    "Low": [
        "Revert commit and redeploy during next maintenance window.",
    ],
}

VALIDATION = [
    "curl -f https://api.nilepay.eg/health",
    "kubectl get pods -n prod | grep Running",
    "kubectl logs -l app=payment-service --tail=50",
]

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

cur.execute("DELETE FROM analyses")

now = datetime.now(timezone.utc)
pr_counter = 445

for i in range(60):
    days_ago = random.randint(1, 180)
    created = now - timedelta(days=days_ago, hours=random.randint(0, 23))

    severity = SEVERITIES[i % len(SEVERITIES)]
    file_changed = random.choice(FILES)
    changed_resource = (
        file_changed.split("/")[-1]
        .replace(".tf", "")
        .replace(".py", "")
        .replace(".jsx", "")
    )
    affected = random.sample(SERVICES, k=random.randint(2, 8))

    if severity == "Critical":
        impact = random.randint(85, 100)
    elif severity == "High":
        impact = random.randint(60, 85)
    elif severity == "Medium":
        impact = random.randint(30, 60)
    else:
        impact = random.randint(5, 30)

    sim = random.choice(INCIDENT_TEMPLATES)

    cur.execute(
        """
        INSERT INTO analyses (
            pr_number, repo_name, changed_resource, affected_services,
            business_impact, simulation, severity, rollback, validation,
            tokens_used, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pr_counter,
            "nilepay/core",
            changed_resource,
            json.dumps(affected),
            impact,
            sim,
            severity,
            json.dumps(ROLLBACK_STEPS.get(severity, [])),
            json.dumps(VALIDATION),
            json.dumps({"input_tokens": 0, "output_tokens": 0}),
            created.isoformat(),
        ),
    )
    pr_counter += 1

conn.commit()
conn.close()

print(f"Seeded {pr_counter - 445} NilePay PRs into history.db")
print("PR numbers range from #445 to #504")