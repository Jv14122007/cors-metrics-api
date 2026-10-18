
import json
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

EMAIL = "25f2006465@ds.study.iitm.ac.in"
START_TIME = time.monotonic()

app = FastAPI()

# Live Prometheus counter, incremented for every HTTP request.
REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
)

LOG_LIMIT = 2000
logs = deque(maxlen=LOG_LIMIT)
log_lock = Lock()


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    REQUESTS.inc()

    try:
        response = await call_next(request)
        level = "INFO"
    except Exception:
        level = "ERROR"
        response = None
        raise
    finally:
        entry = {
            "level": level,
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "request_id": request_id,
            "method": request.method,
            "duration_s": round(time.perf_counter() - start, 6),
        }

        with log_lock:
            logs.append(entry)

        print(json.dumps(entry), flush=True)

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
def work(n: int = Query(default=1, ge=0, le=1000000)):
    # Perform n units of simple work.
    result = 0
    for i in range(n):
        result += i

    return {"email": EMAIL, "done": n}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_s": float(max(0.0, time.monotonic() - START_TIME)),
    }


@app.get("/logs/tail")
def logs_tail(limit: int = Query(default=100, ge=1, le=2000)):
    with log_lock:
        return list(logs)[-limit:]
