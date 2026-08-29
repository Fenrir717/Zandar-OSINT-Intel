"""Uji logika _is_due (penentu jatuh tempo cron) — murni, tanpa DB."""

from datetime import UTC, datetime

from workers.tasks import _is_due

NOW = datetime(2026, 8, 30, 12, 5, tzinfo=UTC)  # fire terakhir '0 */6 * * *' <= now = 12:00


def test_due_when_never_run() -> None:
    assert _is_due("0 */6 * * *", None, NOW) is True


def test_due_when_last_run_before_last_fire() -> None:
    assert _is_due("0 */6 * * *", datetime(2026, 8, 30, 11, 0, tzinfo=UTC), NOW) is True


def test_not_due_when_last_run_after_last_fire() -> None:
    assert _is_due("0 */6 * * *", datetime(2026, 8, 30, 12, 2, tzinfo=UTC), NOW) is False


def test_invalid_cron_never_due() -> None:
    assert _is_due("bukan cron", None, NOW) is False


def test_naive_last_run_treated_as_utc() -> None:
    # last_run tanpa tzinfo tidak boleh melempar; diperlakukan sebagai UTC
    assert _is_due("0 */6 * * *", datetime(2026, 8, 30, 11, 0), NOW) is True


def test_every_minute_due_after_a_minute() -> None:
    now = datetime(2026, 8, 30, 12, 5, 30, tzinfo=UTC)
    assert _is_due("* * * * *", datetime(2026, 8, 30, 12, 3, tzinfo=UTC), now) is True
    assert _is_due("* * * * *", datetime(2026, 8, 30, 12, 5, 10, tzinfo=UTC), now) is False
