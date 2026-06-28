# scripts/fetch_listings.py
"""Ingestion CLI: pull NY + VT active for-sale listings into a local cache.

Hits RentCast, normalizes each record to a flat schema, dedupes across states
by listing id, and writes a JSON cache that the Flask app reads at startup.
Keeping ingestion separate from serving means the app never calls RentCast on
page load (fast pages, no wasted API quota).

Usage:
    python scripts/fetch_listings.py                       # NY + VT, full
    python scripts/fetch_listings.py --states VT           # one state
    python scripts/fetch_listings.py --states VT --max-records 500   # scoped
    python scripts/fetch_listings.py --zips 10001 05401    # specific ZIPs

The normalize/category helpers are module-level pure functions so they can be
unit-tested without hitting the network (see tests/test_fetch_listings.py).
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone
from urllib.parse import quote_plus

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load .env from project root (simple key=value parser, no dependency needed)
_env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from data.rentcast_client import RentCastClient
from scripts.config import OUTPUT_DIR

DEFAULT_STATES = ['NY', 'VT']
DEFAULT_CACHE = os.path.join(OUTPUT_DIR, 'listings_cache.json')

# RentCast propertyType -> UI filter bucket. RentCast never emits a commercial
# type, so 'commercial' is absent here by design (kept selectable in the UI for
# when a commercial source is added later).
CATEGORY_MAP = {
    'Land':          'land',
    'Condo':         'condo',
    'Apartment':     'apartment',
    'Single Family': 'residential',
    'Townhouse':     'residential',
    'Multi-Family':  'residential',
    'Manufactured':  'residential',
}

# The buckets the UI exposes as checkboxes, in display order.
UI_CATEGORIES = ['residential', 'condo', 'apartment', 'land', 'commercial']


def categorize(property_type):
    """Map a RentCast propertyType to a UI filter bucket ('other' if unknown)."""
    return CATEGORY_MAP.get(property_type, 'other')


def normalize_listing(rec):
    """Convert a raw RentCast listing dict to the flat normalized schema.

    RentCast provides no public listing URL, so ``url`` is a Google search for
    the address — good enough for a "view this property" link.
    """
    address = rec.get('formattedAddress') or rec.get('addressLine1') or ''
    ptype = rec.get('propertyType')
    return {
        'id':            rec.get('id'),
        'address':       address,
        'city':          rec.get('city'),
        'state':         rec.get('state'),
        'zip':           rec.get('zipCode'),
        'lat':           rec.get('latitude'),
        'lng':           rec.get('longitude'),
        'propertyType':  ptype,
        'category':      categorize(ptype),
        'price':         rec.get('price'),
        'bedrooms':      rec.get('bedrooms'),
        'bathrooms':     rec.get('bathrooms'),
        'squareFootage': rec.get('squareFootage'),
        'lotSize':       rec.get('lotSize'),
        'yearBuilt':     rec.get('yearBuilt'),
        'daysOnMarket':  rec.get('daysOnMarket'),
        'listedDate':    rec.get('listedDate'),
        'url':           'https://www.google.com/search?q=' + quote_plus(address + ' for sale') if address else '',
    }


def fetch_all(client, states, zips=None, max_records=None):
    """Fetch + normalize + dedupe listings across states (and optional ZIPs)."""
    seen = set()
    listings = []
    for state in states:
        if zips:
            raw = []
            for z in zips:
                raw.extend(client.fetch_sale_listings(
                    state, zip_code=z, max_records=max_records))
        else:
            raw = client.fetch_sale_listings(state, max_records=max_records)

        for rec in raw:
            norm = normalize_listing(rec)
            rid = norm['id']
            if not rid or rid in seen:
                continue
            seen.add(rid)
            listings.append(norm)
        print(f"  {state}: {len(listings)} listings so far")
    return listings


def main():
    parser = argparse.ArgumentParser(description='Fetch NY+VT for-sale listings into a local cache')
    parser.add_argument('--states', nargs='+', default=DEFAULT_STATES,
                        help='State codes to fetch (default: NY VT)')
    parser.add_argument('--zips', nargs='+', default=None,
                        help='Limit to specific ZIP codes (across the given states)')
    parser.add_argument('--max-records', type=int, default=None,
                        help='Cap records per state/ZIP query (protects API quota)')
    parser.add_argument('--out', default=DEFAULT_CACHE,
                        help=f'Output cache path (default: {DEFAULT_CACHE})')
    args = parser.parse_args()

    client = RentCastClient()
    if not client.available:
        print('ERROR: RENTCAST_API_KEY not set (add it to .env).', file=sys.stderr)
        sys.exit(1)

    print(f"Fetching states={args.states} zips={args.zips} max_records={args.max_records}")
    listings = fetch_all(client, args.states, zips=args.zips,
                         max_records=args.max_records)

    if not listings and client.last_error:
        print(f"\nERROR: RentCast request failed — {client.last_error}", file=sys.stderr)
        if '403' in client.last_error or 'subscription' in client.last_error.lower():
            print("Activate an API plan (the free tier still counts) at "
                  "https://app.rentcast.io/app/api, then re-run.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    envelope = {
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'states': args.states,
        'count': len(listings),
        'listings': listings,
    }
    with open(args.out, 'w') as f:
        json.dump(envelope, f)
    print(f"Wrote {len(listings)} listings to {args.out}")


if __name__ == '__main__':
    main()
