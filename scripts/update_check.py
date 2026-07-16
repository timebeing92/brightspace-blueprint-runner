#!/usr/bin/env python3
"""Cached, non-blocking release checks for the Blueprint Wizard.

The checker uses only Python's standard library. Automatic checks are cached
for one day, require no GitHub token, and never mutate the installed Wizard.
Network and cache failures are returned as ordinary status values so they
cannot prevent a blueprint run.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SCHEMA = "coursecraft.wizard_update_check/1"
API_URL = (
    "https://api.github.com/repos/timebeing92/"
    "brightspace-blueprint-runner/releases/latest"
)
RELEASES_URL = (
    "https://github.com/timebeing92/"
    "brightspace-blueprint-runner/releases"
)
CHECK_INTERVAL = dt.timedelta(days=1)
NOTICE_INTERVAL = dt.timedelta(days=1)
REQUEST_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class UpdateStatus:
    """Result of a release check."""

    state: str
    current_version: str
    latest_version: str = ""
    latest_tag: str = ""
    release_name: str = ""
    release_url: str = RELEASES_URL
    from_cache: bool = False
    error: str = ""

    @property
    def update_available(self) -> bool:
        return self.state == "update_available"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_text(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_utc(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def load_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        return {}
    return payload


def save_cache(path: Path, payload: dict[str, Any]) -> None:
    """Best-effort atomic cache write; a read-only install is still usable."""
    temporary = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def cache_is_fresh(
    cache: dict[str, Any],
    *,
    now: dt.datetime,
    interval: dt.timedelta = CHECK_INTERVAL,
) -> bool:
    checked = parse_utc(cache.get("checked_at_utc"))
    if checked is None:
        return False
    age = now - checked
    return dt.timedelta(0) <= age < interval


def status_from_cache(
    cache: dict[str, Any],
    *,
    current_version: str,
    from_cache: bool,
) -> UpdateStatus:
    latest_tag = str(cache.get("latest_tag") or "")
    latest_version = str(cache.get("latest_version") or "")
    current = version_tuple(current_version)
    latest = version_tuple(latest_version or latest_tag)
    if current is None or latest is None:
        return UpdateStatus(
            state="unavailable",
            current_version=current_version,
            from_cache=from_cache,
            error="GitHub returned an unrecognized release version.",
        )
    if latest > current:
        state = "update_available"
    elif latest < current:
        state = "ahead"
    else:
        state = "current"
    return UpdateStatus(
        state=state,
        current_version=current_version,
        latest_version=".".join(str(part) for part in latest),
        latest_tag=latest_tag or f"v{'.'.join(str(part) for part in latest)}",
        release_name=str(cache.get("release_name") or ""),
        release_url=str(cache.get("release_url") or RELEASES_URL),
        from_cache=from_cache,
    )


def safe_release_url(value: object) -> str:
    text = str(value or "")
    parts = urllib.parse.urlsplit(text)
    expected_prefix = "/timebeing92/brightspace-blueprint-runner/releases/"
    if (
        parts.scheme == "https"
        and parts.netloc.lower() == "github.com"
        and parts.path.startswith(expected_prefix)
    ):
        return text
    return RELEASES_URL


def fetch_latest_release(
    etag: str = "",
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any] | None, str, bool]:
    """Return ``(payload, etag, not_modified)`` from GitHub."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Blueprint-Wizard-Update-Check",
    }
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(API_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("GitHub returned an unexpected response.")
            return payload, str(response.headers.get("ETag") or ""), False
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, etag, True
        raise


Fetcher = Callable[[str], tuple[dict[str, Any] | None, str, bool]]


def check_latest_release(
    *,
    current_version: str,
    cache_path: Path,
    force: bool = False,
    now: dt.datetime | None = None,
    fetcher: Fetcher = fetch_latest_release,
) -> UpdateStatus:
    """Check the latest published Wizard release without blocking on failure."""
    checked_at = now or utc_now()
    cache = load_cache(cache_path)
    if not force and cache_is_fresh(cache, now=checked_at):
        return status_from_cache(
            cache,
            current_version=current_version,
            from_cache=True,
        )

    try:
        payload, etag, not_modified = fetcher(str(cache.get("etag") or ""))
        if not_modified:
            if not cache:
                raise ValueError("GitHub returned no release information.")
            cache["checked_at_utc"] = utc_text(checked_at)
        else:
            assert payload is not None
            latest_tag = str(payload.get("tag_name") or "")
            latest = version_tuple(latest_tag)
            if latest is None:
                raise ValueError("GitHub returned an unrecognized release version.")
            latest_version = ".".join(str(part) for part in latest)
            prior_notice_version = str(cache.get("last_notified_version") or "")
            prior_notice_at = str(cache.get("last_notified_at_utc") or "")
            cache = {
                "schema": SCHEMA,
                "checked_at_utc": utc_text(checked_at),
                "etag": etag,
                "latest_version": latest_version,
                "latest_tag": latest_tag,
                "release_name": str(payload.get("name") or ""),
                "release_url": safe_release_url(payload.get("html_url")),
            }
            if prior_notice_version == latest_version:
                cache["last_notified_version"] = prior_notice_version
                cache["last_notified_at_utc"] = prior_notice_at
        save_cache(cache_path, cache)
        return status_from_cache(
            cache,
            current_version=current_version,
            from_cache=False,
        )
    except (
        OSError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ) as exc:
        return UpdateStatus(
            state="unavailable",
            current_version=current_version,
            error=str(exc) or exc.__class__.__name__,
        )


def notice_is_due(
    cache_path: Path,
    *,
    latest_version: str,
    now: dt.datetime | None = None,
    interval: dt.timedelta = NOTICE_INTERVAL,
) -> bool:
    cache = load_cache(cache_path)
    if cache.get("last_notified_version") != latest_version:
        return True
    notified = parse_utc(cache.get("last_notified_at_utc"))
    if notified is None:
        return True
    age = (now or utc_now()) - notified
    return age < dt.timedelta(0) or age >= interval


def mark_notified(
    cache_path: Path,
    *,
    latest_version: str,
    now: dt.datetime | None = None,
) -> None:
    cache = load_cache(cache_path)
    if not cache:
        return
    cache["last_notified_version"] = latest_version
    cache["last_notified_at_utc"] = utc_text(now or utc_now())
    save_cache(cache_path, cache)
