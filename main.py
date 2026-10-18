
import time
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

EMAIL = "25f2006465@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://dash-m20210.example.com"

api = FastAPI()

# Configure CORS for the one permitted dashboard origin.
api.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@api.get("/stats")
async def stats(values: str = Query(...)):
    try:
        numbers = [int(value.strip()) for value in values.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="values must be integers",
        )

    if not numbers:
        raise HTTPException(
            status_code=400,
            detail="values cannot be empty",
        )

    total = sum(numbers)

    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": total,
        "min": min(numbers),
        "max": max(numbers),
        "mean": total / len(numbers),
    }


class RequestMetricsMiddleware:
    """Add request ID and processing time to every HTTP response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                headers.append(
                    (b"x-request-id", request_id.encode("ascii"))
                )

                elapsed = max(
                    0.0,
                    time.perf_counter() - start_time,
                )
                headers.append(
                    (b"x-process-time", f"{elapsed:.6f}".encode("ascii"))
                )

                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_headers)


# Wrap the complete FastAPI app so these headers also appear on
# CORS preflight responses.
app = RequestMetricsMiddleware(api)

