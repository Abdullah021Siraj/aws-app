"""Gunicorn configuration tuned for a containerised microservice."""

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
backlog = int(os.getenv("GUNICORN_BACKLOG", 2048))

# Threads keep the process count low while the workers wait on Postgres I/O.
workers = int(
    os.getenv("WEB_CONCURRENCY", max(2, multiprocessing.cpu_count() * 2 + 1))
)
threads = int(os.getenv("GUNICORN_THREADS", 4))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

timeout = int(os.getenv("GUNICORN_TIMEOUT", 30))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# Access logging is replaced by the structured request log in app/api/__init__.py.
accesslog = None
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
capture_output = True

# Recycle workers to bound memory growth from long lived connections.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))

preload_app = False
