from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_check  # noqa: E402


UTC = dt.timezone.utc


def test_new_release_is_cached_and_reused_without_a_second_request(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / ".update_check.json"
    now = dt.datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    calls: list[str] = []

    def fetcher(etag: str):
        calls.append(etag)
        return (
            {
                "tag_name": "v2.8.0",
                "name": "Blueprint Wizard v2.8.0",
                "html_url": (
                    "https://github.com/timebeing92/"
                    "brightspace-blueprint-runner/releases/tag/v2.8.0"
                ),
            },
            '"fixture-etag"',
            False,
        )

    first = update_check.check_latest_release(
        current_version="2.7.0",
        cache_path=cache_path,
        now=now,
        fetcher=fetcher,
    )
    second = update_check.check_latest_release(
        current_version="2.7.0",
        cache_path=cache_path,
        now=now + dt.timedelta(hours=1),
        fetcher=lambda etag: (_ for _ in ()).throw(AssertionError(etag)),
    )

    assert first.update_available
    assert first.latest_version == "2.8.0"
    assert first.from_cache is False
    assert second.update_available
    assert second.from_cache is True
    assert calls == [""]
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["schema"] == update_check.SCHEMA
    assert payload["etag"] == '"fixture-etag"'


def test_conditional_not_modified_refreshes_cached_check_time(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / ".update_check.json"
    original = dt.datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    refreshed = dt.datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    update_check.save_cache(
        cache_path,
        {
            "schema": update_check.SCHEMA,
            "checked_at_utc": update_check.utc_text(original),
            "etag": '"fixture-etag"',
            "latest_version": "2.7.0",
            "latest_tag": "v2.7.0",
            "release_name": "Blueprint Wizard v2.7.0",
            "release_url": "https://github.com/example/releases/tag/v2.7.0",
        },
    )

    status = update_check.check_latest_release(
        current_version="2.7.0",
        cache_path=cache_path,
        now=refreshed,
        fetcher=lambda etag: (None, etag, True),
    )

    assert status.state == "current"
    assert status.from_cache is False
    payload = update_check.load_cache(cache_path)
    assert payload["checked_at_utc"] == update_check.utc_text(refreshed)


def test_network_failure_never_raises_or_blocks_the_installed_wizard(
    tmp_path: Path,
) -> None:
    def unavailable(etag: str):
        raise TimeoutError(f"offline {etag}")

    status = update_check.check_latest_release(
        current_version="2.7.0",
        cache_path=tmp_path / ".update_check.json",
        force=True,
        fetcher=unavailable,
    )

    assert status.state == "unavailable"
    assert "offline" in status.error


def test_update_notice_is_limited_to_once_per_day(tmp_path: Path) -> None:
    cache_path = tmp_path / ".update_check.json"
    now = dt.datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    update_check.save_cache(
        cache_path,
        {
            "schema": update_check.SCHEMA,
            "checked_at_utc": update_check.utc_text(now),
            "latest_version": "2.8.0",
            "latest_tag": "v2.8.0",
        },
    )

    assert update_check.notice_is_due(
        cache_path,
        latest_version="2.8.0",
        now=now,
    )
    update_check.mark_notified(
        cache_path,
        latest_version="2.8.0",
        now=now,
    )
    assert not update_check.notice_is_due(
        cache_path,
        latest_version="2.8.0",
        now=now + dt.timedelta(hours=23),
    )
    assert update_check.notice_is_due(
        cache_path,
        latest_version="2.8.0",
        now=now + dt.timedelta(days=1),
    )


def test_version_comparison_rejects_non_release_tags() -> None:
    assert update_check.version_tuple("v2.7.0") == (2, 7, 0)
    assert update_check.version_tuple("2.10.3") == (2, 10, 3)
    assert update_check.version_tuple("main") is None
    assert (
        update_check.safe_release_url("https://malicious.example/update.zip")
        == update_check.RELEASES_URL
    )
