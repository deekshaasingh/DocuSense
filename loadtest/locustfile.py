"""
Load test against the live DocuSense API.

Traffic mix mirrors how the review UI actually behaves: listing the review
queue is the most common call, listing everything is next, uploading is the
expensive path (it enqueues a full preprocess -> OCR -> validate -> score ->
route job), and the health probe is cheap.

Set API_KEY when the target has AUTH_ENABLED=true; the upload and correction
routes need it, the read routes do not.

    locust -f locustfile.py --host http://localhost:8000 \
        --headless -u 15 -r 2 -t 90s --csv results
"""
import os
import random

from locust import HttpUser, between, task

API_KEY = os.getenv("API_KEY", "")
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval", "dataset")


def _sample_bytes() -> tuple[str, bytes]:
    name = f"{random.randint(1, 320):04d}.png"
    path = os.path.join(SAMPLE, name)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return name, fh.read()
    return "synthetic.png", b"\x89PNG" + os.urandom(2048)


class ReviewerTraffic(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(3)
    def review_queue(self):
        self.client.get("/documents?status=needs_review", name="GET /documents (queue)")

    @task(2)
    def all_documents(self):
        self.client.get("/documents", name="GET /documents (all)")

    @task(1)
    def upload(self):
        name, data = _sample_bytes()
        headers = {"X-API-Key": API_KEY} if API_KEY else {}
        self.client.post(
            "/documents",
            files={"file": (name, data, "image/png")},
            headers=headers,
            name="POST /documents",
        )

    @task(1)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(1)
    def metrics(self):
        self.client.get("/metrics", name="GET /metrics")
