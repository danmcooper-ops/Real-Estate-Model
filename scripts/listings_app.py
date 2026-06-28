# scripts/listings_app.py
"""Flask app: interactive NY+VT real estate listings explorer.

Reads the local cache written by scripts/fetch_listings.py (never calls
RentCast directly), serves a filterable table + Leaflet map, a JSON filter
endpoint, and an Excel export of the current filtered set.

Run:
    python scripts/listings_app.py            # http://127.0.0.1:5000
    python scripts/listings_app.py --port 8000

The ``filter_listings`` helper is a pure function shared by /api/listings and
/api/export.xlsx so the table, map, and Excel always agree.
"""

import sys
import os
import json
import tempfile
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, request, render_template, send_file

from scripts.config import OUTPUT_DIR
from scripts.report_listings_excel import build_listings_excel
from scripts.fetch_listings import UI_CATEGORIES

DEFAULT_CACHE = os.path.join(OUTPUT_DIR, 'listings_cache.json')

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
)

# Populated by load_cache() at startup.
_LISTINGS = []
_META = {}


def load_cache(path=DEFAULT_CACHE):
    """Load the listings cache into module state. Returns the listings list."""
    global _LISTINGS, _META
    if not os.path.exists(path):
        _LISTINGS, _META = [], {}
        return _LISTINGS
    with open(path) as f:
        data = json.load(f)
    _LISTINGS = data.get('listings', [])
    _META = {'fetched_at': data.get('fetched_at'), 'states': data.get('states')}
    return _LISTINGS


def filter_listings(listings, *, price_min=None, price_max=None, zip=None,
                    beds_min=None, baths_min=None, categories=None):
    """Return the subset of ``listings`` matching the given filters.

    ``categories`` is an iterable of UI buckets (e.g. {'residential','condo'});
    None/empty means "no category filter". All numeric bounds are inclusive and
    skip listings missing that field.
    """
    cats = set(categories) if categories else None
    out = []
    for L in listings:
        price = L.get('price')
        if price_min is not None and (price is None or price < price_min):
            continue
        if price_max is not None and (price is None or price > price_max):
            continue
        if zip and str(L.get('zip')) != str(zip):
            continue
        if beds_min is not None and (L.get('bedrooms') is None or L['bedrooms'] < beds_min):
            continue
        if baths_min is not None and (L.get('bathrooms') is None or L['bathrooms'] < baths_min):
            continue
        if cats is not None and L.get('category') not in cats:
            continue
        out.append(L)
    return out


def _filters_from_args(args):
    """Parse filter values from a request args (or any dict-like) object."""
    def _num(name, cast):
        v = args.get(name)
        if v in (None, ''):
            return None
        try:
            return cast(v)
        except (ValueError, TypeError):
            return None

    cats = args.get('categories')
    categories = [c for c in cats.split(',') if c] if cats else None
    return {
        'price_min': _num('price_min', float),
        'price_max': _num('price_max', float),
        'zip': args.get('zip') or None,
        'beds_min': _num('beds_min', float),
        'baths_min': _num('baths_min', float),
        'categories': categories,
    }


@app.route('/')
def index():
    prices = [L['price'] for L in _LISTINGS if L.get('price') is not None]
    zips = sorted({str(L['zip']) for L in _LISTINGS if L.get('zip')})
    bootstrap = {
        'count': len(_LISTINGS),
        'fetched_at': _META.get('fetched_at'),
        'states': _META.get('states') or [],
        'price_min': min(prices) if prices else 0,
        'price_max': max(prices) if prices else 0,
        'zips': zips,
        'categories': UI_CATEGORIES,
    }
    return render_template('listings.html', bootstrap=bootstrap)


@app.route('/api/listings')
def api_listings():
    filters = _filters_from_args(request.args)
    results = filter_listings(_LISTINGS, **filters)
    return jsonify({'count': len(results), 'listings': results})


@app.route('/api/export.xlsx')
def api_export():
    filters = _filters_from_args(request.args)
    results = filter_listings(_LISTINGS, **filters)
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    tmp.close()
    build_listings_excel(results, tmp.name)
    return send_file(
        tmp.name,
        as_attachment=True,
        download_name='listings.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def main():
    parser = argparse.ArgumentParser(description='Serve the listings explorer')
    parser.add_argument('--cache', default=DEFAULT_CACHE, help='Listings cache path')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    load_cache(args.cache)
    if not _LISTINGS:
        print(f"WARNING: no listings loaded from {args.cache}. "
              f"Run scripts/fetch_listings.py first.", file=sys.stderr)
    else:
        print(f"Loaded {len(_LISTINGS)} listings from {args.cache}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
