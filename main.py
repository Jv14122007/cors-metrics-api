
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path

import jwt
import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send


# ----------------------------
# Configuration
# ----------------------------
EMAIL = "25f2006465@ds.study.iitm.ac.in"

ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-os3x4y2c.apps.exam.local"

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

ANALYTICS_API_KEY = "ak_9lakrklc9jdh5e5pj2m28409"

api = FastAPI()

# Allow browser requests from the exam page.
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# Q3: Stats endpoint
# ----------------------------
@api.get("/stats")
def stats(values: str):
    try:
        numbers = [float(x.strip()) for x in values.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid values")

    if not numbers:
        raise HTTPException(status_code=400, detail="No values provided")

    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": sum(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "mean": sum(numbers) / len(numbers),
    }


# ----------------------------
# Q4: OAuth2/OIDC token verification
# ----------------------------
@api.post("/verify")
def verify_token(body: dict):
    token = body.get("token", "")

    try:
        claims = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["exp", "iss", "aud", "sub", "email"]},
        )
        return {
            "valid": True,
            "email": claims["email"],
            "sub": claims["sub"],
            "aud": claims["aud"],
        }
    except Exception:
        return JSONResponse(status_code=401, content={"valid": False})


# ----------------------------
# Q5: Effective configuration
# ----------------------------
DEFAULT_CONFIG = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

CONFIG_FILE = Path("config.development.yaml")
if CONFIG_FILE.exists():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        YAML_CONFIG = yaml.safe_load(f) or {}
else:
    YAML_CONFIG = {}

DOTENV_CONFIG = dotenv_values(".env")


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def coerce_config(key, value):
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return to_bool(value)
    return str(value)


@api.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    config = DEFAULT_CONFIG.copy()

    # Layer 2: YAML
    config.update({k: v for k, v in YAML_CONFIG.items() if k in config})

    # Layer 3: .env
    env_aliases = {
        "NUM_WORKERS": "workers",
        "APP_DEBUG": "debug",
        "APP_LOG_LEVEL": "log_level",
        "APP_PORT": "port",
        "APP_API_KEY": "api_key",
    }
    for env_name, config_key in env_aliases.items():
        value = DOTENV_CONFIG.get(env_name)
        if value is not None:
            config[config_key] = value

    # Layer 4: operating-system environment variables
    for env_name, config_key in env_aliases.items():
        value = os.getenv(env_name)
        if value is not None:
            config[config_key] = value

    # Layer 5: repeated query params set=key=value
    for item in set:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key in config:
            config[key] = value

    result = {key: coerce_config(key, value) for key, value in config.items()}
    result["api_key"] = "****"
    return result


# ----------------------------
# Q7: Analytics endpoint
# ----------------------------
@api.post("/analytics")
def analytics(
    body: dict,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    if x_api_key != ANALYTICS_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    events = body.get("events", [])
    users = set()
    user_totals = defaultdict(float)
    revenue = 0.0

    for event in events:
        user = event["user"]
        amount = float(event["amount"])
        users.add(user)

        if amount > 0:
            revenue += amount
            user_totals[user] += amount

    top_user = max(user_totals, key=user_totals.get) if user_totals else ""

    return {
        "email": EMAIL,
        "total_events": len(events),
        "unique_users": len(users),
        "revenue": revenue,
        "top_user": top_user,
    }


# ----------------------------
# Request ID and processing-time headers on every response
# ----------------------------
class RequestMetricsMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        async def send_with_metrics(message):
            if message["type"] == "http.response.start":
                elapsed = max(0.0, time.perf_counter() - start)
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-request-id", request_id.encode("ascii")),
                    (b"x-process-time", str(elapsed).encode("ascii")),
                ])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_metrics)


app = RequestMetricsMiddleware(api)
