# tests/test_quota.py
"""Unit tests for the monthly RentCast request budget (no live API)."""

import json
from datetime import datetime, timezone

from scripts import quota


def _usage_path(tmp_path):
    return str(tmp_path / 'output' / 'api_usage.json')


# --- month bucketing ---

def test_current_month_formats_utc():
    assert quota.current_month(datetime(2026, 8, 3, tzinfo=timezone.utc)) == '2026-08'


def test_load_usage_missing_file_is_zeroed(tmp_path):
    u = quota.load_usage(_usage_path(tmp_path), '2026-08')
    assert u['requests'] == 0 and u['runs'] == 0 and u['month'] == '2026-08'


def test_load_usage_resets_on_new_month(tmp_path):
    path = _usage_path(tmp_path)
    quota.record_usage(path, '2026-07', 40)
    assert quota.load_usage(path, '2026-07')['requests'] == 40
    assert quota.load_usage(path, '2026-08')['requests'] == 0  # rollover


def test_load_usage_survives_corrupt_file(tmp_path):
    path = _usage_path(tmp_path)
    (tmp_path / 'output').mkdir()
    with open(path, 'w') as f:
        f.write('{not json')
    assert quota.load_usage(path, '2026-08')['requests'] == 0


# --- budget arithmetic ---

def test_check_budget_allows_when_room_remains():
    usage = {'month': '2026-08', 'requests': 8, 'last_run_cost': 8}
    ok, msg = quota.check_budget(usage, budget=45)
    assert ok and '8/45' in msg


def test_check_budget_blocks_when_next_run_would_not_fit():
    # 40 used, a run costs 8, budget 45 -> would land at 48. Refuse.
    usage = {'month': '2026-08', 'requests': 40, 'last_run_cost': 8}
    ok, msg = quota.check_budget(usage, budget=45)
    assert not ok and 'budget reached' in msg


def test_check_budget_uses_fallback_cost_before_first_run():
    usage = {'month': '2026-08', 'requests': 0, 'last_run_cost': None}
    assert quota.expected_cost(usage) == quota.FALLBACK_RUN_COST
    assert quota.check_budget(usage, budget=45)[0]


def test_budget_leaves_headroom_under_the_free_plan_limit():
    assert quota.DEFAULT_BUDGET < quota.FREE_PLAN_LIMIT


# --- accumulation ---

def test_record_usage_accumulates_across_runs(tmp_path):
    path = _usage_path(tmp_path)
    quota.record_usage(path, '2026-08', 8)
    u = quota.record_usage(path, '2026-08', 9)
    assert u['requests'] == 17 and u['runs'] == 2 and u['last_run_cost'] == 9
    with open(path) as f:
        assert json.load(f)['requests'] == 17  # persisted, not just returned


def test_record_usage_keeps_last_cost_when_run_spent_nothing(tmp_path):
    path = _usage_path(tmp_path)
    quota.record_usage(path, '2026-08', 8)
    u = quota.record_usage(path, '2026-08', 0)
    assert u['last_run_cost'] == 8
