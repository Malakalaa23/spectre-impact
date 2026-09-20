"""Locust load test for the Spectre Impact API.

Run with (scaled down for a same-day demo):
    locust -f tests/load_test.py --headless -u 30 -r 5 --run-time 60s \
        --host http://localhost:8000

Scale up to -u 100 once you have time for a full run. Add tasks for
teammates' endpoints (e.g. /api/chat) once those are live.
"""

from locust import HttpUser, task, between


class SpectreUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health_check(self):
        self.client.get("/ping")

    @task(1)
    def get_analyses(self):
        self.client.get("/api/analyses")
