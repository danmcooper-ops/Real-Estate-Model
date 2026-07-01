# scripts/estimate.py
"""Comparable-sales value estimate for each listing.

This is a simple market heuristic, NOT an appraisal: the estimate is the median
price-per-square-foot of comparable active listings times the home's square
footage. Comps are taken from the most specific group that has enough samples:
same ZIP + category, then ZIP, then state + category, then state, then all.

Listings without a usable square footage (e.g. raw land) get estimate = None.

``add_estimates`` mutates each listing in place, adding:
  - 'estimate':      rounded dollar value, or None
  - 'estimate_ppsf': the median $/sqft used, or None
and returns the list. It is idempotent, so it can be called at fetch time,
build time, and app-load time without harm.
"""

from statistics import median
from collections import defaultdict

MIN_COMPS = 5  # need at least this many comps in a group to trust its median


def _ppsf(listing):
    """Price per square foot for a listing, or None if not computable."""
    p, s = listing.get('price'), listing.get('squareFootage')
    if p and s and p > 0 and s > 0:
        return p / s
    return None


def add_estimates(listings, min_comps=MIN_COMPS):
    """Add a comparable-$/sqft value estimate to each listing (in place)."""
    by_zip_cat = defaultdict(list)
    by_zip = defaultdict(list)
    by_state_cat = defaultdict(list)
    by_state = defaultdict(list)
    all_ppsf = []
    for L in listings:
        v = _ppsf(L)
        if v is None:
            continue
        by_zip_cat[(L.get('zip'), L.get('category'))].append(v)
        by_zip[L.get('zip')].append(v)
        by_state_cat[(L.get('state'), L.get('category'))].append(v)
        by_state[L.get('state')].append(v)
        all_ppsf.append(v)
    global_med = median(all_ppsf) if all_ppsf else None

    for L in listings:
        s = L.get('squareFootage')
        if not s or s <= 0:
            L['estimate'] = None
            L['estimate_ppsf'] = None
            continue
        med = None
        for group in (
            by_zip_cat.get((L.get('zip'), L.get('category'))),
            by_zip.get(L.get('zip')),
            by_state_cat.get((L.get('state'), L.get('category'))),
            by_state.get(L.get('state')),
        ):
            if group and len(group) >= min_comps:
                med = median(group)
                break
        if med is None:
            med = global_med
        L['estimate'] = round(med * s) if med else None
        L['estimate_ppsf'] = round(med) if med else None
    return listings
