import pytest
from fakeredis import FakeAsyncRedis
from starlette.requests import Request

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, client_address


def request(client='172.30.42.2', forwarded='203.0.113.7', path='/api/auth/login'):
    return Request({'type': 'http', 'method': 'POST', 'path': path, 'scheme': 'https',
                    'server': ('website.test', 443), 'client': (client, 1234),
                    'headers': [(b'x-imagevault-client', forwarded.encode())]})


def test_forwarded_address_is_only_accepted_from_gateway():
    assert client_address(request(), '172.30.42.0/24') == '203.0.113.7'
    assert client_address(request(client='198.51.100.1'), '172.30.42.0/24') == '198.51.100.1'
    assert client_address(request(forwarded='invalid'), '172.30.42.0/24') == '172.30.42.2'


@pytest.mark.asyncio
async def test_atomic_lua_bucket_limits_auth_and_separates_clients(monkeypatch):
    monkeypatch.setattr(get_settings(), 'rate_limit_enabled', True)
    monkeypatch.setattr(get_settings(), 'trusted_proxy_cidr', '172.30.42.0/24')
    limiter = RateLimiter()
    await limiter.redis.aclose()
    limiter.redis = FakeAsyncRedis()
    try:
        for _ in range(10):
            assert await limiter.check(request()) is None
        limited = await limiter.check(request())
        assert limited.status_code == 429
        assert 1 <= int(limited.headers['retry-after']) <= 12
        assert await limiter.check(request(forwarded='203.0.113.8')) is None
        assert await limiter.check(request(path='/api/images/upload')) is None
        assert await limiter.check(request(path='/health/ready')) is None
        keys = await limiter.redis.keys('imagevault:rate:*')
        assert len(keys) == 3
        for key in keys:
            assert await limiter.redis.ttl(key) > 0
    finally:
        await limiter.redis.aclose()


@pytest.mark.asyncio
async def test_rate_limits_fail_closed_on_redis_outage(monkeypatch):
    monkeypatch.setattr(get_settings(), 'rate_limit_enabled', True)
    limiter = RateLimiter()
    async def unavailable(*_):
        raise ConnectionError('down')
    monkeypatch.setattr(limiter.redis, 'eval', unavailable)
    try:
        assert (await limiter.check(request())).status_code == 503
    finally:
        await limiter.redis.aclose()
