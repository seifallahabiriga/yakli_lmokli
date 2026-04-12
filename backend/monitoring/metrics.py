"""
Prometheus metrics — created at module load, incremented by the
request_logging_and_metrics middleware in main.py.

If METRICS_ENABLED=False in config, these objects still exist but
are never incremented — no conditional imports needed in middleware.
"""

try:
    from prometheus_client import Counter, Histogram

    http_request_counter = Counter(
        "observatory_http_requests_total",
        "Total HTTP requests",
        labelnames=["method", "path", "status"],
    )

    http_request_duration = Histogram(
        "observatory_http_request_duration_seconds",
        "HTTP request duration in seconds",
        labelnames=["method", "path"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )

except ImportError:
    # prometheus_client not installed — provide no-op stubs so
    # main.py doesn't need to guard every .inc() / .observe() call.
    class _NoOp:
        def labels(self, **kwargs):
            return self

        def inc(self, *a, **kw):
            pass

        def observe(self, *a, **kw):
            pass

    http_request_counter = _NoOp()       # type: ignore[assignment]
    http_request_duration = _NoOp()      # type: ignore[assignment]