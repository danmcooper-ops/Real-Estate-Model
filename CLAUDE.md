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

## Scheduled refresh (Claude scheduled task)

A Claude scheduled task (`real-estate-refresh`) re-runs fetch + build + push
automatically, **Mondays and Fridays at 5:00pm Eastern** (cron `0 17 * * 1,5`,
local time), republishing the Pages site. It appears in the app's **Scheduled**
section. It runs while the Claude app is open; if the app is closed at the
scheduled time, it runs on next launch.

- Task definition: `~/.claude/scheduled-tasks/real-estate-refresh/SKILL.md`
- The task fetches `--states VT`; edit its prompt to use `NY VT` to add New York.
- The repo lives at `~/Real-Estate-Model` (the task uses that path).

(A local macOS launchd agent was used earlier but removed in favor of this, to
avoid double-publishing. launchd-spawned git/python can't access a repo under the
TCC-protected `~/Desktop`, which is why the repo lives in the home directory.)

## API Keys

- `RENTCAST_API_KEY` required for fetching (set in `.env`, git-ignored). Not needed
  to view the static site (data is pre-baked into `docs/listings.json`).
