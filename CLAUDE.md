# Real Estate Model

## Overview

Explorer for for-sale real estate listings in New York & Vermont: a filterable
map + table with Excel export. Data from the RentCast API. **Standalone project —
no connection to any other repo.**

## Tech Stack

- **Language:** Python 3.9+
- **Dependencies:** flask, openpyxl, jinja2, certifi, pytest (see requirements.txt)
- **Frontend:** Leaflet + markercluster + SheetJS (loaded from CDN)
- **Data source:** RentCast API (residential for-sale listings; no commercial)

## Architecture

- **Data layer (`data/`):** `RentCastClient` — class-based, urllib-only, API key
  from `RENTCAST_API_KEY` env (falls back via constructor), throttling, in-memory
  cache, graceful degradation, certifi SSL context.
- **Scripts layer (`scripts/`):** ingestion CLI, Flask app, Excel builder, static
  site builder. Use `sys.path.append` for imports; paths come from `scripts/config.py`.
- **Ingestion vs serving are decoupled:** the app reads `output/listings_cache.json`
  and never calls RentCast on page load.

## Conventions

- Data client is a class; helpers (`normalize_listing`, `categorize`,
  `filter_listings`) are pure functions and unit-tested.
- Normalized listing schema is flat (see `scripts/fetch_listings.py:normalize_listing`).
- `filter_listings` (in `scripts/listings_app.py`) is the single source of filter
  logic for the Flask API and Excel export; the static site re-implements the same
  logic in JS — keep them in sync.

## Running

```bash
python scripts/fetch_listings.py --states VT      # populate cache
python scripts/listings_app.py                    # local app at :5000
python scripts/build_static_site.py               # build docs/ for Pages
pytest                                            # tests
```

## Hosting

GitHub Pages serves the static site from **main /docs**. Live:
https://danmcooper-ops.github.io/Real-Estate-Model/
Refresh = re-run fetch + build_static_site, then commit & push `docs/`.

## API quota budget

RentCast's free Developer plan allows **50 successful requests per billing
month**, with an overage fee per request beyond that. Billing is per *request*,
not per record — one 500-listing page costs 1. A full VT refresh is ~8 requests
(3,600 listings / 500 per page), so the free plan affords ~6 refreshes a month.

`scripts/quota.py` tracks spend in `output/api_usage.json` (git-ignored, local
machine state; the month key resets the tally). `fetch_listings.py` checks the
budget *before* fetching and skips the run — exit 0, `SKIPPED:` on stdout, zero
requests — when the next refresh wouldn't fit. Defaults: budget 45 of 50, so
5 requests stay in reserve for ad-hoc work.

```bash
python scripts/fetch_listings.py --states VT --quota-budget 45   # default
python scripts/fetch_listings.py --states VT --ignore-quota      # override (may bill)
```

Adding New York is **not** free-plan viable: NY carries far more listings than
VT, so a single NY refresh would exceed the whole monthly allowance.

## Scheduled refresh (Claude scheduled task)

A Claude scheduled task (`real-estate-refresh`) re-runs fetch + build + push
automatically, **Mondays at 8:00am Eastern** (cron `0 8 * * 1`, local time),
republishing the Pages site. It appears in the app's **Scheduled** section. It
runs while the Claude app is open; if the app is closed at the scheduled time,
it runs on next launch.

Weekly is the sustainable maximum on the free plan: 4–5 runs/month × ~8 requests
= 32–40 of the 50 allowance. RentCast updates each listing at least daily, so
the quota — not data freshness — is what caps the cadence. (The earlier Mon+Fri
schedule was ~8.6 runs/month ≈ 69 requests, i.e. over the free allowance.)

- Task definition: `~/.claude/scheduled-tasks/real-estate-refresh/SKILL.md`
- The task fetches `--states VT`.
- The repo path used by the task is this repo:
  `/Users/danmcooper/Desktop/Workspace Folder/Real-Estate-Model`.

(A local macOS launchd agent was used earlier but removed in favor of this, to
avoid double-publishing — launchd-spawned git/python can't reach a repo under
the TCC-protected `~/Desktop`. Claude scheduled tasks have no such restriction.)

## API Keys

- `RENTCAST_API_KEY` required for fetching (set in `.env`, git-ignored). Not needed
  to view the static site (data is pre-baked into `docs/listings.json`).
