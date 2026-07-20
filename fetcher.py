"""Fetch and parse Kimi (Moonshot AI) Coding Plan quotas.

Hits the internal usage endpoint (reverse-engineered, undocumented):
    GET https://api.kimi.com/coding/v1/usages
Auth: Bearer <coding-plan API key> (sk-kimi-xxx, from the Kimi Code console —
NOT a platform.kimi.com / api.moonshot.cn key).

Response shape (relevant part; numbers may come as strings):
    {
      user: {membership: {level: "LEVEL_INTERMEDIATE", ...}},
      subType: "TYPE_PURCHASE",
      usage:   {used, limit, resetTime},                 # weekly quota
      limits:  [{window: {duration: 300, timeUnit: "TIME_UNIT_MINUTE"},
                 detail: {used, limit, resetTime}}, ...], # 5-hour window
      totalQuota: {limit, remaining},                    # monthly total (no reset)
      parallel: {limit}                                  # max concurrent requests
    }

resetTime is an ISO-8601 string (sometimes epoch seconds/ms).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

TITLES = {
    "five_hour": "5 Hours Quota",
    "weekly": "Weekly Quota",
    "monthly": "Monthly Total Quota",
}

# Best-effort unit labels (the API returns bare numbers).
UNIT_TEXT = {
    "five_hour": "Requests",
    "weekly": "Tokens",
    "monthly": "Tokens",
}

USER_AGENT = "KimiCLI/1.6"


def _to_int(v: object) -> int | None:
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None


def _parse_reset(v: object) -> datetime | None:
    """resetTime comes as ISO-8601 string or epoch seconds/ms."""
    if v in (None, "", 0):
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
        ts = float(str(v))
        if ts > 1e12:  # milliseconds
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass
class Quota:
    key: str
    title: str
    unit_text: str
    percentage: int  # 0-100
    next_reset: datetime | None
    has_counts: bool = False
    usage: int | None = None  # limit
    used: int | None = None  # currentValue
    remaining: int | None = None
    usage_details: list[dict] = field(default_factory=list)


@dataclass
class Snapshot:
    fetched_at: datetime
    level: str | None
    quotas: dict[str, Quota]
    raw: dict
    parallel_limit: int | None = None

    def get(self, key: str) -> Quota | None:
        return self.quotas.get(key)


class KimiError(RuntimeError):
    pass


def _token() -> str:
    key = os.getenv("KIMI_API_KEY", "").strip() or os.getenv("KIMI_CODING_API_KEY", "").strip()
    if not key:
        raise KimiError("KIMI_API_KEY not set (check .env)")
    return key


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }


def _hint(status: int) -> str:
    hints = {
        401: "auth failed: use a Kimi Code (Coding Plan) key sk-kimi-xxx, "
        "not a platform.kimi.com / api.moonshot.cn sk-xxx key",
        403: "access denied: the key has no permission for the usage endpoint",
        404: "usage endpoint not found: base must be https://api.kimi.com/coding/v1",
        429: "rate limited: retry later",
    }
    return hints.get(status, f"HTTP {status}")


def _mk_quota(key: str, used: int | None, limit: int | None, reset: object) -> Quota:
    pct = round(used / limit * 100) if (used is not None and limit) else 0
    remaining = (limit - used) if (used is not None and limit is not None) else None
    return Quota(
        key=key,
        title=TITLES[key],
        unit_text=UNIT_TEXT[key],
        percentage=pct,
        next_reset=_parse_reset(reset),
        has_counts=True,
        usage=limit,
        used=used,
        remaining=remaining,
    )


def _parse(payload: dict) -> Snapshot:
    quotas: dict[str, Quota] = {}

    # 5-hour rolling window (duration=300 minutes), fallback: first entry
    limits = payload.get("limits") or []
    win = next(
        (
            item
            for item in limits
            if isinstance(item, dict)
            and (item.get("window") or {}).get("duration") == 300
            and "MINUTE" in str((item.get("window") or {}).get("timeUnit", "")).upper()
        ),
        limits[0] if limits else None,
    )
    if isinstance(win, dict):
        detail = win.get("detail") if isinstance(win.get("detail"), dict) else win
        quotas["five_hour"] = _mk_quota(
            "five_hour",
            _to_int(detail.get("used")),
            _to_int(detail.get("limit")),
            detail.get("resetTime"),
        )

    # Weekly quota
    usage = payload.get("usage")
    if isinstance(usage, dict):
        quotas["weekly"] = _mk_quota(
            "weekly",
            _to_int(usage.get("used")),
            _to_int(usage.get("limit")),
            usage.get("resetTime"),
        )

    # Monthly total quota (API does not expose its reset time)
    tq = payload.get("totalQuota")
    if isinstance(tq, dict):
        limit = _to_int(tq.get("limit"))
        used = _to_int(tq.get("used"))
        if used is None and limit is not None:
            rem = _to_int(tq.get("remaining"))
            used = limit - rem if rem is not None else None
        quotas["monthly"] = _mk_quota("monthly", used, limit, tq.get("resetTime"))

    level = ((payload.get("user") or {}).get("membership") or {}).get("level")
    parallel = _to_int((payload.get("parallel") or {}).get("limit"))

    return Snapshot(
        fetched_at=datetime.now(tz=timezone.utc),
        level=level,
        quotas=quotas,
        raw=payload,
        parallel_limit=parallel,
    )


def fetch_snapshot(client: httpx.Client | None = None, api_key: str | None = None) -> Snapshot:
    """Fetch a fresh quota snapshot. Raises KimiError on auth/logic failure.

    api_key: the coding-plan API key (sk-kimi-xxx). Defaults to KIMI_API_KEY
    (or KIMI_CODING_API_KEY) from env.
    """
    endpoint = os.getenv("KIMI_QUOTA_ENDPOINT", "https://api.kimi.com/coding/v1/usages")
    token = (api_key or "").strip() or _token()
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=20.0)
    try:
        r = client.get(endpoint, headers=_headers(token), timeout=20.0)
        if r.status_code == 404 and endpoint.endswith("/usages"):
            # older deployments exposed /usage (singular)
            fallback = endpoint[: -len("usages")] + "usage"
            r = client.get(fallback, headers=_headers(token), timeout=20.0)
        if r.status_code != 200:
            raise KimiError(_hint(r.status_code))
        payload = r.json()
    except httpx.RequestError as e:
        raise KimiError(f"network error: {e}") from e
    except ValueError as e:
        raise KimiError(f"invalid JSON: {e}") from e
    finally:
        if own_client and client is not None:
            client.close()

    if not isinstance(payload, dict) or not (payload.get("usage") or payload.get("limits")):
        raise KimiError(f"unexpected payload: {str(payload)[:200]}")

    return _parse(payload)


if __name__ == "__main__":
    snap = fetch_snapshot()
    par = f"  parallel={snap.parallel_limit}" if snap.parallel_limit else ""
    print(f"level={snap.level}  fetched={snap.fetched_at.isoformat()}{par}")
    for key in ("five_hour", "weekly", "monthly"):
        q = snap.get(key)
        if not q:
            continue
        extra = ""
        if q.has_counts:
            extra = f"  [{q.used}/{q.usage} {q.unit_text}, {q.remaining} left]"
        reset = q.next_reset.isoformat() if q.next_reset else "?"
        print(f"  {q.title:<22} {q.percentage:>3}%{extra}  resets {reset}")
