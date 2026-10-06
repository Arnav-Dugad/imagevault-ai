"""Shared token buckets, so moving the gateway does not remove rate limits."""
import hashlib
import ipaddress
import math

from fastapi import Request
from redis.asyncio import Redis
from starlette.responses import JSONResponse

from app.core.config import get_settings

BUCKET_SCRIPT = """
local now = redis.call('TIME')
local timestamp = tonumber(now[1]) + tonumber(now[2]) / 1000000
local previous = redis.call('HMGET', KEYS[1], 'tokens', 'time')
local tokens = tonumber(previous[1]) or tonumber(ARGV[2])
local last = tonumber(previous[2]) or timestamp
tokens = math.min(tonumber(ARGV[2]), tokens + math.max(0, timestamp - last) * tonumber(ARGV[1]))
local allowed = 0
if tokens >= 1 then tokens = tokens - 1; allowed = 1 end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'time', timestamp)
redis.call('EXPIRE', KEYS[1], math.ceil(tonumber(ARGV[2]) / tonumber(ARGV[1]) * 2))
return {allowed, math.ceil(math.max(0, 1 - tokens) / tonumber(ARGV[1]))}
"""


def client_address(request: Request, trusted_proxy_cidr: str) -> str:
    address = request.client.host if request.client else "unknown"
    if trusted_proxy_cidr:
        try:
            if ipaddress.ip_address(address) in ipaddress.ip_network(trusted_proxy_cidr):
                forwarded = request.headers.get("X-ImageVault-Client", "")
                return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return address


class RateLimiter:
    def __init__(self):
        self.redis = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)

    async def check(self, request: Request):
        settings = get_settings()
        if not settings.rate_limit_enabled or not request.url.path.startswith("/api/"):
            return None
        path = request.url.path.rstrip("/")
        if path in ("/api/auth/login", "/api/auth/register") and request.method == "POST":
            category, rate, capacity = "auth", 5 / 60, 10
        elif path == "/api/images/upload" and request.method == "POST":
            category, rate, capacity = "upload", 3, 10
        else:
            category, rate, capacity = "api", 20, 40
        address = client_address(request, settings.trusted_proxy_cidr)
        key = f"imagevault:rate:{category}:{hashlib.sha256(address.encode()).hexdigest()}"
        try:
            allowed, wait = await self.redis.eval(BUCKET_SCRIPT, 1, key, rate, capacity)
        except Exception:
            return JSONResponse({"detail": "Request protection unavailable. Try again shortly."}, status_code=503)
        if not allowed:
            return JSONResponse({"detail": "Too many requests. Try again shortly."}, status_code=429,
                                headers={"Retry-After": str(max(1, math.ceil(wait)))})
        return None


rate_limiter = RateLimiter()
