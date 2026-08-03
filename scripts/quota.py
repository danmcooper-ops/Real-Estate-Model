# scripts/quota.py
"""Monthly RentCast request budget tracking.

RentCast's free Developer plan allows 50 successful requests per calendar
billing period and charges an overage fee for every request beyond that, so an
automated refresh needs to know what it has already spent this month. RentCast
exposes no usage endpoint, so we keep our own tally in ``output/api_usage.json``
and treat it as the source of truth.

Billing is per *request*, not per record: one 500-listing page costs exactly 1.
A full VT refresh is therefore ~8 requests (3,600 listings / 500 per page).

The helpers here are pure (path in, dict out) so they can be unit-tested
without the network — see tests/test_quota.py.
"""

import os
import json
from datetime import datetime, timezone

# Free-plan allowance. Kept separate from DEFAULT_BUDGET so the reserve is
# explicit: we deliberately stop short of the true ceiling, because the last
# few requests are the ones that tip into overage fees.
FREE_PLAN_LIMIT = 50
DEFAULT_BUDGET = 45

# Assumed cost of a refresh before we've ever measured one (first run on a new
# install). Real runs overwrite this with their observed cost.
FALLBACK_RUN_COST = 10


def current_month(now=None):
    """Billing bucket key, e.g. '2026-08' (UTC, matching fetch timestamps)."""
    return (now or datetime.now(timezone.utc)).strftime('%Y-%m')


def load_usage(path, month):
    """Read the usage tally for ``month``.

    A missing/corrupt file, or one written in an earlier month, yields a fresh
    zeroed tally — the month rollover is what resets the budget.
    """
    blank = {'month': month, 'requests': 0, 'runs': 0,
             'last_run_cost': None, 'updated_at': None}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return blank
    if not isinstance(data, dict) or data.get('month') != month:
        return blank
    blank.update({k: data.get(k, blank[k]) for k in blank})
    blank['month'] = month
    return blank


def expected_cost(usage):
    """Best guess at what the next refresh will cost, in requests."""
    last = usage.get('last_run_cost')
    return last if isinstance(last, int) and last > 0 else FALLBACK_RUN_COST


def check_budget(usage, budget=DEFAULT_BUDGET, cost=None):
    """Decide whether another refresh fits in this month's budget.

    Returns ``(ok, message)``. The check is on the *projected* total rather
    than the current one: a run that starts with 3 requests left would burn
    them and still produce a truncated cache, which is worse than not running.
    """
    used = usage.get('requests', 0)
    cost = expected_cost(usage) if cost is None else cost
    remaining = budget - used
    if cost > remaining:
        return False, (f"Monthly RentCast budget reached: {used}/{budget} requests "
                       f"used this month ({usage['month']}), next refresh needs "
                       f"~{cost}. Skipping to avoid overage fees; the budget "
                       f"resets at the start of next month.")
    return True, (f"Budget OK: {used}/{budget} used this month "
                  f"({usage['month']}), next refresh needs ~{cost}.")


def record_usage(path, month, count):
    """Add ``count`` requests to the month's tally and persist it."""
    usage = load_usage(path, month)
    usage['requests'] = usage.get('requests', 0) + count
    usage['runs'] = usage.get('runs', 0) + 1
    if count > 0:
        usage['last_run_cost'] = count
    usage['updated_at'] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(usage, f, indent=2)
    return usage
