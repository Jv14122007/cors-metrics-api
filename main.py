
import os
from fastapi import FastAPI
from redis import Redis
from fastapi.responses import JSONResponse

app = FastAPI()

redis_client = Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    decode_responses=True,
    socket_connect_timeout=3,
)

@app.post("/hit/{key}")
def hit(key: str):
    count = redis_client.incr(key)
    return {"key": key, "count": count}

@app.get("/count/{key}")
def count(key: str):
    value = redis_client.get(key)
    return {"key": key, "count": int(value) if value else 0}

@app.get("/healthz")
def healthz():
    try:
        redis_client.ping()
        return {"status": "ok", "redis": "up"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "redis": "down"},
        )
