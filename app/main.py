import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from pydantic import BaseModel

app = FastAPI(title="SRE Demo API", version="1.0.0")

REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])
FAILURE_MODE = False


class FailureMode(BaseModel):
    enabled: bool


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.perf_counter() - start
        path = request.url.path
        status = getattr(locals().get("response"), "status_code", 500)
        REQUESTS.labels(request.method, path, str(status)).inc()
        LATENCY.labels(request.method, path).observe(elapsed)


@app.get("/healthz")
def healthz():
    return {"status": "healthy"}


@app.get("/readyz")
def readyz():
    if FAILURE_MODE:
        raise HTTPException(status_code=503, detail="failure mode enabled")
    return {"status": "ready"}


@app.get("/demo")
def demo():
    if FAILURE_MODE:
        raise HTTPException(status_code=500, detail="simulated application failure")
    return {"message": "request succeeded"}


@app.post("/admin/failure-mode")
def set_failure_mode(payload: FailureMode):
    global FAILURE_MODE
    FAILURE_MODE = payload.enabled
    return {"failure_mode": FAILURE_MODE}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
