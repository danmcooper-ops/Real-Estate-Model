# Real Estate Model

Interactive explorer for for-sale real estate listings in **New York & Vermont** —
a filterable map + sortable table with Excel export. Data comes from the
[RentCast API](https://www.rentcast.io).

**Live site:** https://danmcooper-ops.github.io/Real-Estate-Model/

## How it works

Two halves, deliberately decoupled:

- **Ingestion** (`scripts/fetch_listings.py`) calls RentCast, normalizes listings,
  and writes a local cache at `output/listings_cache.json`.
- **Serving** — two options:
  - **Local app** (`scripts/listings_app.py`): a Flask server with live filtering
    and an Excel-export endpoint.
  - **Static site** (`docs/`): a self-contained page (no server) that does all
    filtering and Excel export in the browser — this is what GitHub Pages hosts.

Filters: price, ZIP code, minimum beds/baths, and property type (residential,
condo, apartment, land). *Commercial* appears in the UI but isn't provided by
RentCast (residential-focused); a commercial source can be added later.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo 'RENTCAST_API_KEY=your_key_here' > .env      # from https://app.rentcast.io/app/api
```

## Usage

```bash
# 1. Fetch listings into the local cache (start scoped to protect API quota)
python scripts/fetch_listings.py --states VT --max-records 500
python scripts/fetch_listings.py --states NY VT          # full statewide

# 2a. Run the interactive local app
python scripts/listings_app.py                            # http://127.0.0.1:5000

# 2b. ...or build the static site and publish it
python scripts/build_static_site.py                       # writes docs/listings.json
git add docs && git commit -m "Update listings" && git push
```

## Project layout

```
data/rentcast_client.py          RentCast API client (paginate, throttle, cache)
scripts/fetch_listings.py        Ingestion CLI -> output/listings_cache.json
scripts/listings_app.py          Flask app (live filtering + /api/export.xlsx)
scripts/report_listings_excel.py openpyxl Excel builder (used by the Flask export)
scripts/build_static_site.py     Cache -> docs/listings.json for GitHub Pages
templates/listings.html          Flask app UI
docs/                            Static GitHub Pages site (index.html + listings.json)
tests/                           Unit tests (mapping, bucketing, filters)
```

## Tests

```bash
pytest
```

## Notes

- The RentCast free tier is 50 calls/month; Growth (~$99/mo) allows 500. Each call
  returns up to 500 records. Scope fetches by `--states` / `--zips` / `--max-records`
  to stay within quota.
- `output/` and `.env` are git-ignored. The published `docs/listings.json` contains
  listing data — check RentCast's terms before redistributing it publicly.
