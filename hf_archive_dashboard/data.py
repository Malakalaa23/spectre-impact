#data.py

import pandas as pd


# =========================================================
# PR TABLE (used by app.py's dashboard table)
# =========================================================

pr_data = pd.DataFrame({
    "PR": ["#445", "#443", "#442", "#441", "#440"],
    "Repository": [
        "Spectre",
        "Spectre",
        "Spectre",
        "Auth-Gateway",
        "Payment-Service"
    ],
    "Severity": [
        "HIGH",
        "HIGH",
        "MEDIUM",
        "LOW",
        "MEDIUM"
    ],
    "Impact": [
        "80%",
        "75%",
        "45%",
        "15%",
        "40%"
    ],
    "Date": [
        "Aug 9, 2026",
        "Aug 9, 2026",
        "Aug 8, 2026",
        "Aug 8, 2026",
        "Aug 7, 2026"
    ]
})


# =========================================================
# PR DETAILS (used by pages/PR_Analysis.py)
# =========================================================
# Keyed by the same PR numbers as pr_data above.

pr_details = {

    "#445": {
        "repository": "Spectre",
        "severity": "HIGH",
        "impact": 80,
        "summary": (
            "Payment service experienced elevated latency due to "
            "expired TLS certificates. Pods required restart."
        ),
        "changed_files": [
            "database.tf",
            "login.py",
            "docker-compose.yml"
        ],
        "services": [
            "Login Service",
            "Payment Gateway",
            "Main Database"
        ],
        "simulation": [
            "Database migration fails",
            "Login service loses connection",
            "Checkout requests timeout",
            "Customers cannot purchase"
        ],
        "rollback": [
            "Revert the database migration",
            "Restart the login service",
            "Verify database connectivity"
        ]
    },

    "#443": {
        "repository": "Spectre",
        "severity": "HIGH",
        "impact": 75,
        "summary": (
            "A change to the authentication middleware caused "
            "intermittent 401 errors for a subset of active sessions."
        ),
        "changed_files": [
            "auth_middleware.py",
            "session_manager.py"
        ],
        "services": [
            "Login Service",
            "Authentication",
            "API Gateway"
        ],
        "simulation": [
            "Auth middleware deploys",
            "Session tokens fail validation",
            "Users get logged out unexpectedly",
            "Support tickets spike"
        ],
        "rollback": [
            "Revert the auth middleware change",
            "Invalidate and reissue affected sessions",
            "Confirm login success rate returns to normal"
        ]
    },

    "#442": {
        "repository": "Spectre",
        "severity": "MEDIUM",
        "impact": 45,
        "summary": (
            "API Gateway rate-limit thresholds were tightened, "
            "which may throttle legitimate traffic during peak hours."
        ),
        "changed_files": [
            "gateway_config.yaml"
        ],
        "services": [
            "API Gateway",
            "Authentication"
        ],
        "simulation": [
            "New rate limits deploy",
            "Peak-hour traffic approaches the new threshold",
            "Some legitimate requests get throttled"
        ],
        "rollback": [
            "Revert rate-limit thresholds to previous values",
            "Monitor gateway error rate for 15 minutes"
        ]
    },

    "#441": {
        "repository": "Auth-Gateway",
        "severity": "LOW",
        "impact": 15,
        "summary": (
            "Minor logging changes to the Auth-Gateway service. "
            "No functional behavior was modified."
        ),
        "changed_files": [
            "logging_config.py"
        ],
        "services": [
            "Authentication"
        ],
        "simulation": [
            "Logging change deploys",
            "Log verbosity increases slightly",
            "No impact on request handling"
        ],
        "rollback": [
            "Revert the logging configuration"
        ]
    },

    "#440": {
        "repository": "Payment-Service",
        "severity": "MEDIUM",
        "impact": 40,
        "summary": (
            "Payment retry logic was updated to add exponential "
            "backoff, slightly increasing checkout latency."
        ),
        "changed_files": [
            "retry_policy.py",
            "payment_client.py"
        ],
        "services": [
            "Payment Gateway",
            "Main Database"
        ],
        "simulation": [
            "New retry policy deploys",
            "Failed payments retry with backoff",
            "Checkout latency increases slightly"
        ],
        "rollback": [
            "Revert to the previous retry policy",
            "Verify checkout latency returns to baseline"
        ]
    }
}


# =========================================================
# ANALYTICS DATA (used by pages/Analytics.py)
# =========================================================

repository_prs = {
    "Spectre": 62,
    "Auth-Gateway": 28,
    "Payment-Service": 20,
    "Notification-Service": 9,
    "API-Gateway": 6
}

risk_distribution = {
    "HIGH": 18,
    "MEDIUM": 20,
    "LOW": 12
}

affected_services = {
    "Payment Gateway": 28,
    "Main Database": 24,
    "Login Service": 18,
    "Authentication": 15,
    "API Gateway": 10
}

risk_over_time = pd.DataFrame({
    "Week": ["W1", "W2", "W3", "W4", "W5", "W6"],
    "High Risk PRs": [5, 7, 6, 9, 12, 18]
})
