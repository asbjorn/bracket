import asyncio

import pytest

from bracket.database import database
from bracket.utils.client_ip import client_ip_from
from bracket.utils.rate_limit import RateLimiter, delete_old_rate_limit_hits, hash_key


@pytest.mark.asyncio(loop_scope="session")
async def test_limit_shared_through_the_database(startup_and_shutdown_uvicorn_server: None) -> None:
    """Two limiters with the same bucket (like two server processes) share one count."""
    first = RateLimiter("test_shared", limit=3, window_seconds=3600)
    second = RateLimiter("test_shared", limit=3, window_seconds=3600)
    await first.clear()
    try:
        results = [await first.allow("client"), await second.allow("client")]
        results += [await first.allow("client"), await second.allow("client")]
        assert results == [True, True, True, False]
        # Other keys and buckets are counted on their own
        assert await first.allow("other client")
        other_bucket = RateLimiter("test_other", limit=1, window_seconds=3600)
        await other_bucket.clear()
        assert await other_bucket.allow("client")
        await other_bucket.clear()
    finally:
        await first.clear()


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_hits_never_exceed_the_limit(
    startup_and_shutdown_uvicorn_server: None,
) -> None:
    limiter = RateLimiter("test_concurrent", limit=5, window_seconds=3600)
    await limiter.clear()
    try:
        results = await asyncio.gather(*(limiter.allow("client") for _ in range(20)))
        assert sum(results) == 5
    finally:
        await limiter.clear()


@pytest.mark.asyncio(loop_scope="session")
async def test_keys_are_hashed_and_old_rows_deleted(
    startup_and_shutdown_uvicorn_server: None,
) -> None:
    limiter = RateLimiter("test_hashed", limit=5, window_seconds=60)
    await limiter.clear()
    try:
        await limiter.allow("secret-token:10.0.0.1")
        rows = await database.fetch_all(
            "SELECT key_hash FROM rate_limit_hits WHERE bucket = 'test_hashed'"
        )
        assert [row["key_hash"] for row in rows] == [
            hash_key("test_hashed", "secret-token:10.0.0.1")
        ]
        assert "secret" not in rows[0]["key_hash"]

        await database.execute(
            "UPDATE rate_limit_hits SET window_start = now() - interval '3 days' "
            "WHERE bucket = 'test_hashed'"
        )
        await delete_old_rate_limit_hits()
        assert not await database.fetch_all(
            "SELECT 1 FROM rate_limit_hits WHERE bucket = 'test_hashed'"
        )
    finally:
        await limiter.clear()


def test_client_ip_behind_proxies() -> None:
    proxies = "10.0.0.0/8, 127.0.0.1"
    # No trusted proxies configured: the header is ignored
    assert client_ip_from("203.0.113.5", "1.2.3.4", "") == "203.0.113.5"
    # A client talking directly can't spoof its address with the header
    assert client_ip_from("203.0.113.5", "1.2.3.4", proxies) == "203.0.113.5"
    # Behind a trusted proxy: the right-most address that isn't a trusted proxy
    assert client_ip_from("10.0.0.2", "198.51.100.7", proxies) == "198.51.100.7"
    assert client_ip_from("10.0.0.2", "1.2.3.4, 198.51.100.7, 10.0.0.9", proxies) == "198.51.100.7"
    # Junk in the header is not trusted as a proxy, so it's taken as the client
    assert client_ip_from("127.0.0.1", "garbage", proxies) == "garbage"
    assert client_ip_from("127.0.0.1", None, proxies) == "127.0.0.1"
    assert client_ip_from(None, None, proxies) == "unknown"
