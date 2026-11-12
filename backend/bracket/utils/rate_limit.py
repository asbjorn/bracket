"""
Rate limits for public endpoints without an account (result links, public sign-up) and for bulk
emails, shared by all server processes through Postgres.

Each limiter counts hits per key in fixed windows (`rate_limit_hits`, one row per bucket, key
and window), with an atomic upsert. The limit is checked against a sliding estimate: the hits
in the current window plus the share of the previous window that still falls within the last
`window_seconds`. Keys are stored as a keyed hash, never as raw tokens or IP addresses.
"""

import hashlib
import hmac

from fastapi import HTTPException
from starlette import status

from bracket.config import config
from bracket.database import database

# Rows older than this are deleted by the maintenance cronjob (the longest window is a day)
KEEP_ROWS_SECONDS = 2 * 24 * 3600


def hash_key(bucket: str, key: str) -> str:
    secret = config.jwt_secret.encode()
    return hmac.new(secret, f"{bucket}:{key}".encode(), hashlib.sha256).hexdigest()


class RateLimiter:
    def __init__(self, bucket: str, limit: int, window_seconds: int) -> None:
        self.bucket = bucket
        self.limit = limit
        self.window_seconds = window_seconds

    async def allow(self, key: str) -> bool:
        """Records a hit for `key`; `False` when the key is over the limit."""
        row = await database.fetch_one(
            """
            WITH now_ AS (
                SELECT extract(epoch FROM now()) AS epoch,
                       CAST(:window AS double precision) AS size
            ),
            hit AS (
                INSERT INTO rate_limit_hits (bucket, key_hash, window_start, count)
                SELECT :bucket, :key_hash, to_timestamp(floor(epoch / size) * size), 1
                FROM now_
                ON CONFLICT (bucket, key_hash, window_start)
                DO UPDATE SET count = rate_limit_hits.count + 1
                RETURNING count, window_start
            )
            SELECT
                hit.count AS current,
                coalesce((
                    SELECT previous.count FROM rate_limit_hits previous, now_
                    WHERE previous.bucket = :bucket AND previous.key_hash = :key_hash
                    AND previous.window_start = hit.window_start - make_interval(secs => now_.size)
                ), 0) AS previous,
                (now_.epoch - extract(epoch FROM hit.window_start)) / now_.size AS elapsed
            FROM hit, now_
            """,
            values={
                "bucket": self.bucket,
                "key_hash": hash_key(self.bucket, key),
                "window": self.window_seconds,
            },
        )
        assert row is not None
        estimate = float(row["current"]) + float(row["previous"]) * (1 - float(row["elapsed"]))
        return estimate <= self.limit

    async def check(self, key: str) -> None:
        if not await self.allow(key):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, please wait a moment and try again",
            )

    async def clear(self) -> None:
        """Forgets all hits of this limiter (for tests)."""
        await database.execute(
            "DELETE FROM rate_limit_hits WHERE bucket = :bucket", values={"bucket": self.bucket}
        )


async def delete_old_rate_limit_hits() -> None:
    await database.execute(
        """
        DELETE FROM rate_limit_hits
        WHERE window_start < now() - make_interval(secs => CAST(:keep AS double precision))
        """,
        values={"keep": KEEP_ROWS_SECONDS},
    )
